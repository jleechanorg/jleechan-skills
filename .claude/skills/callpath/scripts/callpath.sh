#!/usr/bin/env python3
"""callpath — trace execution across hops, services, and profiles (read-only)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"


def _expand_env_value(raw: str, env: dict) -> str:
    raw = os.path.expanduser(raw.strip().strip('"'))
    if raw.startswith("${") and ":-" in raw:
        inner = raw[2:].rstrip("}")
        var, _, default = inner.partition(":-")
        return env.get(var, os.path.expanduser(default))
    return raw


def _profile_env(prof_dir: Path) -> dict:
    env = os.environ.copy()
    meta = prof_dir / "profile.yaml"
    if not meta.is_file():
        return env
    in_env = False
    for line in meta.read_text().splitlines():
        s = line.strip()
        if s == "env:":
            in_env = True
            continue
        if in_env:
            if line and not line.startswith(" "):
                in_env = False
            elif ":" in line:
                k, _, v = line.strip().partition(":")
                env.setdefault(k.strip(), _expand_env_value(v, env))
    return env


@dataclass
class HopResult:
    hop_id: str
    component: str
    status: str
    detail: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_profiles() -> None:
    print("# callpath profiles\n")
    if not PROFILES.is_dir():
        print("(no profiles)")
        return
    for d in sorted(PROFILES.iterdir()):
        if not d.is_dir():
            continue
        meta = d / "profile.yaml"
        desc = d.name
        if meta.is_file():
            for line in meta.read_text().splitlines():
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip().strip('"')
                    break
        runner = d / "run.sh"
        kind = "shell" if runner.is_file() else "missing-runner"
        print(f"  {d.name:20} {kind:12} {desc}")


def run_profile(name: str, extra: List[str]) -> int:
    prof_dir = PROFILES / name
    runner = prof_dir / "run.sh"
    if not runner.is_file():
        print(f"error: unknown profile {name!r} (no {runner})", file=sys.stderr)
        list_profiles()
        return 2
    env = _profile_env(prof_dir)
    rc = subprocess.call(["bash", str(runner), *extra], env=env)
    return rc


def run_hop(spec: str) -> HopResult:
    """spec: id:component:shell-command  OR  id:shell-command (component=id)"""
    parts = spec.split(":", 2)
    if len(parts) == 2:
        hop_id, cmd = parts[0].strip(), parts[1].strip()
        component = hop_id
    elif len(parts) == 3:
        hop_id, component, cmd = (p.strip() for p in parts)
    else:
        return HopResult("?", "?", "FAIL", f"bad hop spec: {spec!r}")

    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = (p.stdout or p.stderr or "").strip().splitlines()
        tail = out[-1] if out else f"exit {p.returncode}"
        if p.returncode == 0:
            return HopResult(hop_id, component, "PASS", tail[:200])
        return HopResult(hop_id, component, "FAIL", tail[:200] or f"exit {p.returncode}")
    except subprocess.TimeoutExpired:
        return HopResult(hop_id, component, "FAIL", "timeout 30s")
    except Exception as e:
        return HopResult(hop_id, component, "FAIL", str(e)[:200])


def trace_adhoc(hops: List[str], title: Optional[str]) -> int:
    results = [run_hop(h) for h in hops]
    worst = "GREEN"
    for r in results:
        if r.status == "FAIL":
            worst = "RED"
        elif r.status in ("AMBER", "SKIP") and worst != "RED":
            worst = "AMBER"
    print(f"# /callpath trace — {utc_now()} — verdict={worst}")
    if title:
        print(f"trace: {title}")
    print("\n## Hops")
    for r in results:
        print(f"  {r.hop_id:22} {r.status:5} [{r.component}] {r.detail}")
    blocker = next((r for r in results if r.status == "FAIL"), None)
    if blocker:
        print(f"\nblocker: {blocker.hop_id} ({blocker.component}) — {blocker.detail}")
    return 1 if worst == "RED" else 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Trace requests/work across hops and services (read-only)",
        prog="callpath",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List registered profiles")

    run_p = sub.add_parser("run", help="Run a saved profile probe")
    run_p.add_argument("profile", help="Profile name (e.g. dark-factory)")
    run_p.add_argument("args", nargs=argparse.REMAINDER, help="Profile-specific flags")

    tr = sub.add_parser("trace", help="Ad-hoc hop trace")
    tr.add_argument("--hop", action="append", required=True, metavar="SPEC",
                      help="id:component:command or id:command")
    tr.add_argument("--title", default="", help="Trace title")

    args = p.parse_args()
    if args.cmd == "list":
        list_profiles()
        return 0
    if args.cmd == "run":
        extra = [a for a in args.args if a != "--"]
        return run_profile(args.profile, extra)
    if args.cmd == "trace":
        return trace_adhoc(args.hop, args.title or None)
    return 2


if __name__ == "__main__":
    sys.exit(main())
