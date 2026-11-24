#!/usr/bin/env python3
"""Operator commands for one nudger round: enroll, retire, retry-now."""

import argparse
import json
import os
import shlex
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
from render_pr_owner_nudger import DEFAULT_NAME, lane_targets  # noqa: E402

HOME = Path.home()
CONFIG = HOME / ".config/pr-owner-nudger/config.json"
PROFILES = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "pr-owner-nudger/profiles"
POLICY = Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "AGENTS.md"
AGY_POLICY = HOME / ".gemini/GEMINI.md"
WRAPPER = """#!/bin/bash
set -eu
end={end}
remaining=$((end - $(date +%s)))
((remaining>0)) || exit 124
exec {timeout} --kill-after=2 "${{remaining}}s" {cli} "$@"
"""
# Env vars the calling coding agent advertises its own model through, most specific first.
# A nudger enrolled without `--model`/`--cli` inherits the caller's model, and derives the CLI
# from that model's family, so the PR owner runs as the same agent that dispatched it.
CALLER_MODEL_ENV = (
    "PR_NUDGER_MODEL",
    "PI_MODEL",
    "CLAUDEWA_MODEL",
    "CLAUDE_MODEL",
    "CODEX_MODEL",
    "AGY_MODEL",
    "GEMINI_MODEL",
)

# Used only when the caller advertises neither a CLI nor a model. agy is the documented
# default, and the fallback names an agy-served model.
AGY_FALLBACK_MODEL = "gemini-3.8-flash-high"

SCOPE = """

## Pilot scope (this profile only)
This dedicated owner session owns only {repo} PR #{number} (branch `{branch}`). The run ends {end_utc} ({end_local}). Work on this host only. Do not merge. Drive the PR to /pr final approval (Stage 5).
When Stage 5 is complete so the nudger stops waking you, set `stage:5-final-approval` as the only `stage:*` label, keep one `## PR Stage` or `## Execution Record` section in the PR body with no active `blocker:` (omit or `blocker: none`), and emit unindented lines (with the exact 40-char head SHA, unquoted):
status: FINAL_READY
candidate: <40-char-sha>
owner: <owner>
next_action: none
Fresh repro required: per evidence-standards § Evidence Sequencing, reproduce the failure on the exact pre-change revision on the real boundary, run the same scenario at the current head, and publish both to the existing evidence store.
Apply the repository PR overlay that /pr loads (the repository's `.claude/pr-overlay.md`, else the operator overlay).
"""


def caller_model(environ=None):
    """Return the caller's own advertised model (first variable set), or "".

    The caller's identity is taken at face value here: the CLI is then derived from this
    model's family, so both halves of the route come from the same declaration instead of
    being picked from different variables on a host that advertises several models.
    """
    environ = os.environ if environ is None else environ
    for name in CALLER_MODEL_ENV:
        value = environ.get(name, "").strip()
        if value:
            return value
    return ""


# Models only the codex CLI can run. Anything not matched here or by the agy family below is
# treated as codex-compatible (the permissive default), so this list encodes the exclusions we
# actually know about rather than an invented allowlist of every codex model.
CLAUDE_MODEL_PREFIXES = ("claude", "opus", "sonnet", "haiku")


def model_family(model):
    """Classify `model` as "agy", "claude" or "codex".

    `agy` serves gemini-*. Claude identifiers are their own family because neither enrolled CLI
    can run them here: agy is gemini-only and codex exec --model rejects a Claude name. Treating
    "not gemini" as "codex" is what let `--cli codex` inherit `claude-opus-5-5` and enrol an
    owner whose CLI would fail at bootstrap.
    """
    name = model.strip().lower()
    if name.startswith("gemini"):
        return "agy"
    if name.startswith(CLAUDE_MODEL_PREFIXES):
        return "claude"
    return "codex"


def cli_for_model(model):
    """Which enrolled CLI serves `model`? "" when no enrolled CLI can run it."""
    family = model_family(model)
    return "" if family == "claude" else family


def family_matches(model, cli):
    """Does `model` belong to the family `cli` serves?"""
    return cli_for_model(model) == cli


def resolve_route(args, environ=None):
    """Resolve the (cli, model) pair an enrollment will use.

    Precedence: an explicit flag wins; anything unstated is inherited from the caller.
      - `--cli` and `--model` both given: used when the model fits that CLI, else refused.
      - `--cli` only: model comes from the caller when it suits that CLI, else the CLI's own
        fallback (agy: AGY_FALLBACK_MODEL; codex: refuse, since it has no safe default).
      - `--model` only: CLI is derived from that model's family.
      - neither: the caller's model decides both; with no caller model, agy + fallback.
    """
    environ = os.environ if environ is None else environ
    explicit_cli = getattr(args, "cli", None)
    explicit_model = getattr(args, "model", None)

    if explicit_model:
        # A model the selected CLI cannot run would enrol an owner that fails at bootstrap, so
        # refuse rather than guess. A refused pair returns an empty model, which enroll()
        # turns into a named error.
        if explicit_cli and not family_matches(explicit_model, explicit_cli):
            return explicit_cli, ""
        derived = cli_for_model(explicit_model)
        if derived:
            return derived, explicit_model
        # A model no enrolled CLI can run, given without --cli, has no valid route.
        return (explicit_cli or "agy"), explicit_model

    inherited = caller_model(environ)
    if explicit_cli:
        if inherited and family_matches(inherited, explicit_cli):
            return explicit_cli, inherited
        return explicit_cli, (AGY_FALLBACK_MODEL if explicit_cli == "agy" else "")

    if inherited:
        derived = cli_for_model(inherited)
        if derived:
            return derived, inherited
        # e.g. CLAUDE_MODEL on a host with no agent-specific var: no enrolled CLI runs it, so
        # fall back rather than hand agy or codex a model it will reject at bootstrap.
        return "agy", AGY_FALLBACK_MODEL
    return "agy", AGY_FALLBACK_MODEL


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
    cli, model = resolve_route(args)
    if not model:
        sys.exit(f"enroll needs --model, or a caller that advertises a {cli}-family model "
                 f"via {'/'.join(CALLER_MODEL_ENV)} (codex has no safe default)")
    end = int(time.time() + args.hours * 3600)
    profile = (args.profiles_dir / f"{args.repo.replace('/', '__')}-{args.pr}").resolve()
    profile.mkdir(parents=True, exist_ok=True)
    if cli == "codex":
        auth = profile / "auth.json"
        if not (auth.is_symlink() or auth.exists()):
            auth.symlink_to(Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "auth.json")
    if args.policy is not None:
        policy_text = args.policy.read_text().rstrip()
    elif cli == "agy":
        policy_text = AGY_POLICY.read_text().rstrip() if AGY_POLICY.is_file() else ""
    else:
        policy_text = POLICY.read_text().rstrip()
    stamp = datetime.fromtimestamp(end, timezone.utc)
    scope = SCOPE.format(repo=args.repo, number=args.pr, branch=branch,
                         end_utc=stamp.strftime("%Y-%m-%dT%H:%MZ"),
                         end_local=stamp.astimezone().strftime("%-I:%M %p %Z"))
    extra = Path(args.scope_file).read_text() if args.scope_file else ""
    (profile / "scope.md").write_text(scope.lstrip() + extra)
    agents_body = (policy_text + scope + extra) if policy_text else (scope.lstrip() + extra)
    (profile / "AGENTS.md").write_text(agents_body)
    timeout = shutil.which("timeout") or shutil.which("gtimeout")
    cli_bin = args.cli_bin or (args.codex if cli == "codex" else None) or shutil.which(cli)
    if not timeout or not cli_bin:
        sys.exit(f"enroll needs `timeout` (coreutils) and the {cli} CLI on PATH")
    # A new path per enrollment makes the nudger retire the old session (enrollment_changed).
    wrapper = profile / f"{cli}-deadline-{end}"
    wrapper.write_text(WRAPPER.format(end=end, timeout=timeout, cli=shlex.quote(cli_bin)))
    wrapper.chmod(0o755)
    config = load(args.config)
    item = target(config, args.repo, args.pr)
    item["observe_only"] = False
    enrollment = {
        "host": socket.gethostname(), "cwd": str(cwd), "head_repo": head_repo, "branch": branch,
        "cli": cli, "cli_bin": str(wrapper), "profile_dir": str(profile), "model": model,
        "managed_exclusive": True, "launch_authorized": True,
    }
    if cli == "codex":
        enrollment["resume_sandbox"] = "danger-full-access"
    if args.headless_only:
        enrollment["headless_only"] = True
    item["enrollment"] = enrollment
    save(args.config, config)
    print(f"enrolled {args.repo}#{args.pr} ({cli}) on {branch} until {stamp.astimezone():%-I:%M %p %Z}")
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
    if state and state.is_file():
        with sqlite3.connect(state) as db:
            db.execute("UPDATE target SET next_due=? WHERE repo=? AND number=?",
                       (time.time(), args.repo, args.pr))
    elif not args.kick:
        sys.exit("retry-now needs the config's state_dir with a receipts.sqlite3 from an earlier tick")
    if args.kick:
        label, service = lane_targets(args.name)
        uid = os.getuid()
        command = (["launchctl", "kickstart", f"gui/{uid}/{label}"]
                   if sys.platform == "darwin" else ["systemctl", "--user", "start", service])
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
            cmd.add_argument("--cli", choices=("codex", "agy"),
                             help="enrolled CLI; defaults to the calling agent's model family "
                                  "(gemini-* -> agy, else codex)")
            cmd.add_argument("--model",
                             help="model for the enrolled CLI; defaults to the calling agent's "
                                  f"model from {'/'.join(CALLER_MODEL_ENV)}")
            cmd.add_argument("--hours", type=float, default=2.0)
            cmd.add_argument("--scope-file", help="per-PR scope and proof lines appended to the profile")
            cmd.add_argument("--policy", type=Path)
            cmd.add_argument("--profiles-dir", type=Path, default=PROFILES)
            cmd.add_argument("--cli-bin", help="path to the enrolled CLI executable")
            cmd.add_argument("--codex")
            cmd.add_argument("--headless-only", action="store_true",
                             help="enroll for a headless host without cmux")
        if name == "retry-now":
            cmd.add_argument("--kick", action="store_true", help="also start a tick now")
            cmd.add_argument("--name", default=DEFAULT_NAME,
                             help="unit/label name of the nudger lane to kick")
    args = parser.parse_args(argv)
    if args.command == "retry-now":
        try:
            lane_targets(args.name)
        except ValueError as exc:
            parser.error(str(exc))
    {"enroll": enroll, "retire": retire, "retry-now": retry_now}[args.command](args)


if __name__ == "__main__":
    main()
