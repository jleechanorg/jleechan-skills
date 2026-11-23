#!/usr/bin/env python3
"""Operator commands for one nudger round: enroll, retire, retry-now."""

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pr_owner_nudger import checkout  # noqa: E402

HOME = Path.home()
CONFIG = HOME / ".config/pr-owner-nudger/config.json"
PROFILES = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "pr-owner-nudger/profiles"
POLICY = Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "AGENTS.md"
WRAPPER = """#!/bin/bash
set -eu
end={end}
remaining=$((end - $(date +%s)))
((remaining>0)) || exit 124
exec {timeout} --kill-after=2 "${{remaining}}s" {codex} "$@"
"""
SCOPE = """

## Pilot scope (this profile only)
This dedicated owner session owns only {repo} PR #{number} (branch `{branch}`). The run ends {end_utc} ({end_local}). Work on this host only. Do not merge. Drive the PR to /pr final approval (Stage 5).
Fresh repro required: per evidence-standards § Evidence Sequencing, reproduce the failure on the exact pre-change revision on the real boundary, run the same scenario at the current head, and publish both to the existing evidence store.
Apply the repository PR overlay that /pr loads (the repository's `.claude/pr-overlay.md`, else the operator overlay).
"""


def load(path):
    return json.loads(path.read_text()) if path.exists() else {"enabled": False, "targets": []}


def save(path, config):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    path.chmod(0o600)


def target(config, repo, number):
    for item in config.setdefault("targets", []):
        if (item["repo"], item["number"]) == (repo, number):
            return item
    item = {"repo": repo, "number": number, "observe_only": True}
    config["targets"].append(item)
    return item


def enroll(args):
    cwd = Path(args.cwd).resolve(strict=True)
    head_repo, branch, _ = checkout(cwd)
    end = int(time.time() + args.hours * 3600)
    profile = (args.profiles_dir / f"{args.repo.replace('/', '__')}-{args.pr}").resolve()
    profile.mkdir(parents=True, exist_ok=True)
    auth = profile / "auth.json"
    if not (auth.is_symlink() or auth.exists()):
        auth.symlink_to(Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "auth.json")
    stamp = datetime.fromtimestamp(end, timezone.utc)
    scope = SCOPE.format(repo=args.repo, number=args.pr, branch=branch,
                         end_utc=stamp.strftime("%Y-%m-%dT%H:%MZ"),
                         end_local=stamp.astimezone().strftime("%-I:%M %p %Z"))
    extra = Path(args.scope_file).read_text() if args.scope_file else ""
    (profile / "AGENTS.md").write_text(args.policy.read_text().rstrip() + scope + extra)
    timeout = shutil.which("timeout") or shutil.which("gtimeout")
    codex = args.codex or shutil.which("codex")
    if not timeout or not codex:
        sys.exit("enroll needs `timeout` (coreutils) and the codex CLI on PATH")
    # A new path per enrollment makes the nudger retire the old session (enrollment_changed).
    wrapper = profile / f"codex-deadline-{end}"
    wrapper.write_text(WRAPPER.format(end=end, timeout=timeout, codex=codex))
    wrapper.chmod(0o755)
    config = load(args.config)
    item = target(config, args.repo, args.pr)
    item["observe_only"] = False
    item["enrollment"] = {
        "host": socket.gethostname(), "cwd": str(cwd), "head_repo": head_repo, "branch": branch,
        "cli": "codex", "cli_bin": str(wrapper), "profile_dir": str(profile), "model": args.model,
        "managed_exclusive": True, "launch_authorized": True, "resume_sandbox": "danger-full-access",
    }
    save(args.config, config)
    print(f"enrolled {args.repo}#{args.pr} on {branch} until {stamp.astimezone():%-I:%M %p %Z}")
    if not config.get("enabled"):
        print("note: the config has enabled=false, so ticks will not dispatch until you enable it")


def retire(args):
    config = load(args.config)
    if not any((t["repo"], t["number"]) == (args.repo, args.pr) for t in config.get("targets", [])):
        sys.exit(f"{args.repo}#{args.pr} is not a target in {args.config}")
    target(config, args.repo, args.pr)["observe_only"] = True
    save(args.config, config)
    print(f"{args.repo}#{args.pr} is observe-only")


def retry_now(args):
    state_dir = load(args.config).get("state_dir")
    state = Path(state_dir).expanduser() / "receipts.sqlite3" if state_dir else None
    if not state or not state.is_file():
        sys.exit("retry-now needs the config's state_dir with a receipts.sqlite3 from an earlier tick")
    with sqlite3.connect(state) as db:
        db.execute("UPDATE target SET next_due=? WHERE repo=? AND number=?",
                   (time.time(), args.repo, args.pr))
    if args.kick:
        uid = os.getuid()
        command = (["launchctl", "kickstart", f"gui/{uid}/org.prw.pr-owner-nudger"]
                   if sys.platform == "darwin" else ["systemctl", "--user", "start", "pr-owner-nudger.service"])
        subprocess.run(command, check=True, timeout=30)
    print(f"{args.repo}#{args.pr} is due now")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("enroll", "retire", "retry-now"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--repo", required=True)
        cmd.add_argument("--pr", type=int, required=True)
        if name == "enroll":
            cmd.add_argument("--cwd", required=True, help="dedicated worktree on the PR's head branch")
            cmd.add_argument("--model", required=True)
            cmd.add_argument("--hours", type=float, default=2.0)
            cmd.add_argument("--scope-file", help="per-PR scope and proof lines appended to the profile")
            cmd.add_argument("--policy", type=Path, default=POLICY)
            cmd.add_argument("--profiles-dir", type=Path, default=PROFILES)
            cmd.add_argument("--codex")
        if name == "retry-now":
            cmd.add_argument("--kick", action="store_true", help="also start a tick now")
    args = parser.parse_args(argv)
    {"enroll": enroll, "retire": retire, "retry-now": retry_now}[args.command](args)


if __name__ == "__main__":
    main()
