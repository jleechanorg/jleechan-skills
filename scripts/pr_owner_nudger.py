#!/usr/bin/env python3
"""Inspect enrolled PR owners and optionally nudge their existing sessions."""

import argparse
import fcntl
import json
import re
import sqlite3
import subprocess
import time
from collections import defaultdict
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path

from pr_nudger_discovery import discover_owners
from pr_nudger_routes import route

REPO = r"[a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+"
ORIGIN = re.compile(rf"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)({REPO})")
CHECK_ERRORS = (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError)


def command(cwd, *args):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.PIPE, timeout=20)


def checkout(cwd):
    root = command(cwd, "git", "rev-parse", "--show-toplevel").rstrip("\n")
    origin = command(cwd, "git", "config", "--get", "remote.origin.url").strip()
    match = ORIGIN.fullmatch(origin.removesuffix(".git"))
    if Path(root).resolve() != cwd or not match:
        raise ValueError("Enrollment requires a GitHub worktree root")
    branch = command(cwd, "git", "symbolic-ref", "--quiet", "HEAD").strip().removeprefix("refs/heads/")
    sha = command(cwd, "git", "rev-parse", "HEAD").strip()
    return match[1].lower(), branch, sha


def github(cwd, *args):
    return json.loads(command(cwd, "gh", "api", *args, "--hostname", "github.com"))


def identity(pr):
    return (pr["base"]["repo"]["full_name"].lower(), pr["number"],
            pr["head"]["repo"]["full_name"].lower(), pr["head"]["ref"], pr["head"]["sha"])


def pr_status(pr):
    if pr["state"] != "open":
        return "closed"
    records = re.findall(
        r"(?ms)^## (?:PR Stage|Execution Record)[ \t]*\n(.*?)(?=^## |\Z)",
        pr.get("body") or "",
    )
    if len(records) != 1:
        return "actionable"
    fields = defaultdict(list)
    for key, value in re.findall(r"(?m)^([a-z_]+):[ \t]*(\S[^\n]*)$", records[0]):
        fields[key].append(value.strip())
    missing = {"n/a", "none", "-", "unknown"}
    if (fields["candidate"] != [pr["head"]["sha"]] or len(fields["owner"]) != 1
            or fields["owner"][0].lower() in missing
            or any(action.lower() not in missing for action in fields["next_action"])):
        return "actionable"
    if fields["status"] == ["FINAL_READY"]:
        return "final_ready"
    if fields["status"] == ["WAITING_HUMAN"] and all(
        len(fields[key]) == 1 and fields[key][0].lower() not in missing
        for key in ("blocker", "wake_condition")
    ):
        return "awaiting_final_approval"
    return "actionable"


def repo_slug(value):
    if not re.fullmatch(REPO, value) or value.split("/")[1] in {".", ".."}:
        raise ValueError("Invalid repository name")
    return value.lower()


def inferred_bases(cwd, origin):
    remote = github(cwd, f"repos/{origin}")
    if repo_slug(remote["full_name"]) != origin:
        raise ValueError("GitHub repository does not match the checkout origin")
    if remote["fork"]:
        return {origin, repo_slug(remote["parent"]["full_name"])}
    return {origin}


def discover(cwd, repos, local):
    origin, branch, sha = local
    matches = []
    for repo in sorted(repos):
        rows = github(cwd, "-X", "GET", f"repos/{repo}/pulls", "-f",
                      f"head={origin.split('/')[0]}:{branch}", "-f", "state=open",
                      "-F", "per_page=2")
        if len(rows) > 1:
            return "ambiguous_pr", None
        if rows:
            actual_repo, number, head_repo, head_branch, _ = identity(rows[0])
            if (type(number) is not int or number < 1
                    or (actual_repo, head_repo, head_branch) != (repo, origin, branch)):
                return "pr_mismatch", None
            matches.extend(rows)
    if len(matches) != 1:
        return ("ambiguous_pr" if matches else "no_open_pr"), None
    pr, = matches
    return ("stale_head" if pr["head"]["sha"] != sha else pr_status(pr)), pr


def dispatch(cwd, owner, local, pr, receipts, cooldown, from_cache):
    expected = identity(pr)
    repo, number, _, branch, sha = expected
    owner = dict(owner, cwd=str(cwd))
    key = (repo, number)
    if receipts is not None:
        previous = receipts.execute(
            "SELECT status, time FROM delivery WHERE repo=? AND number=?", key
        ).fetchone()
        if previous and previous[0] in {"pending_delivery", "attempted_delivery"}:
            return "reconciliation_required"
        if previous and previous[0] == "delivered" and time.time() - previous[1] < cooldown:
            return "cooldown"

    reserved = False
    transport = None
    binding = (str(cwd), *key, branch)
    can_resume = owner.get("headless_resume", from_cache) is True
    if owner.get("cmux_discovered") and not from_cache:
        can_resume = False

    def confirm_owner(workspace, surface):
        owner.update(workspace=workspace, surface=surface)
        if receipts is not None and owner.get("cmux_discovered") and revalidate():
            receipts.execute("INSERT OR REPLACE INTO binding VALUES (?, ?, ?, ?, ?)",
                             (*binding, json.dumps(owner)))

    def record(status):
        fields = ("cwd", "cli", "session", "workspace", "surface", "profile_dir",
                  "account", "destination")
        audit = json.dumps({**{key: owner[key] for key in fields if key in owner},
                            "branch": branch, "transport": transport})
        receipts.execute("INSERT OR REPLACE INTO delivery VALUES (?, ?, ?, ?, ?, ?)",
                         (*key, status, time.time(), sha, audit))

    def revalidate():
        try:
            current = github(cwd, f"repos/{repo}/pulls/{number}")
            return (checkout(cwd) == local and identity(current) == expected
                    and pr_status(current) == "actionable")
        except CHECK_ERRORS:
            return False

    def recheck(mode=None):
        nonlocal reserved, transport
        transport = mode
        if not revalidate():
            return False
        if receipts is not None and not reserved:
            record("pending_delivery")
            reserved = True
        return True

    prompt = (f"PR owner reminder for https://github.com/{repo}/pull/{number} at {sha}. "
              "Recheck the live PR and continue its next authorized /pr obligation in this "
              "session. Preserve existing user constraints and stop for final operator approval.")
    try:
        status = route(dict(owner, pr=number, sha=sha, branch=branch,
                            recheck=recheck, revalidate=revalidate, confirm_owner=confirm_owner,
                            headless_resume=can_resume), prompt, receipts is not None)
    except Exception:
        # An interrupted transport may already have acted. Keep its durable intent.
        return "reconciliation_required" if reserved else "blocked_route"
    if reserved:
        if status not in {"delivered", "attempted_delivery", "no_delivery"}:
            return "reconciliation_required"
        record(status)
    return status


def tick(config, receipts):
    enrolled = defaultdict(list)
    for owner in config.get("owners", []):
        enrolled[Path(owner["cwd"]).expanduser().resolve()].append(owner)
    for root in config.get("worktree_roots", []):
        root = Path(root).expanduser().resolve()
        try:
            records = command(root, "git", "worktree", "list", "--porcelain", "-z")
            for item in records.split("\0"):
                if item.startswith("worktree "):
                    enrolled.setdefault(Path(item.removeprefix("worktree ")).resolve(), [])
        except CHECK_ERRORS:
            yield {"cwd": str(root), "status": "blocked_worktree_list"}
    discovered = discover_owners(enrolled) if enrolled else {}
    candidates = defaultdict(list)
    inferred = {}
    for cwd, explicit in sorted(enrolled.items()):
        live = discovered.get(str(cwd), [])
        if len(explicit) == len(live) == 1 and all(
            explicit[0].get(field) == live[0][field] for field in ("cli", "session")
        ):
            owners = [{**explicit[0], **live[0]}]
        else:
            owners = explicit + live
        result = {"cwd": str(cwd)}
        try:
            local = checkout(cwd)
            repos = {repo_slug(item["repo"]) for item in owners if "repo" in item}
            if len(repos) > 1:
                yield dict(result, status="ambiguous_owner")
                continue
            if not repos:
                origin = local[0]
                if origin not in inferred:
                    inferred[origin] = inferred_bases(cwd, origin)
                repos = inferred[origin]
            status, pr = discover(cwd, repos, local)
        except CHECK_ERRORS as error:
            yield dict(result, status="blocked_discovery", error=type(error).__name__)
            continue
        if pr is not None:
            repo, number, _, _, sha = identity(pr)
            result.update(repo=repo, pr=number, sha=sha)
        if status == "actionable":
            candidates[repo, number].append((cwd, result, local, pr, owners))
        else:
            yield dict(result, status=status)
    for key, rows in candidates.items():
        owner_count = sum(len(owners) for *_, owners in rows)
        from_cache = not owner_count
        if from_cache and receipts is not None and config.get("headless_resume", True) is True:
            for cwd, _, local, _, owners in rows:
                row = receipts.execute(
                    "SELECT owner FROM binding WHERE cwd=? AND repo=? AND number=? AND branch=?",
                    (str(cwd), *key, local[1]),
                ).fetchone()
                if row:
                    owners.append(json.loads(row[0]))
                    owner_count += 1
        for cwd, result, local, pr, owners in rows:
            if owner_count > 1:
                status = "ambiguous_owner"
            elif not owners:
                status = "missing_owner"
            else:
                status = dispatch(cwd, owners[0], local, pr, receipts,
                                  config.get("cooldown_seconds", 1800), from_cache)
            yield dict(result, status=status)


def emit(status):
    print(json.dumps({"time": datetime.now(timezone.utc).isoformat(), **status}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Dispatch when configuration is enabled")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text())
        if args.apply and config.get("enabled") is not True:
            emit({"status": "disabled"})
            return 0
        cooldown = config.get("cooldown_seconds", 1800)
        if type(cooldown) is not int or cooldown < 1:
            raise ValueError("Cooldown must be a positive integer")
        with ExitStack() as stack:
            receipts = None
            if args.apply:
                state = Path(config.get("state_dir", "~/.local/state/pr-owner-nudger")).expanduser()
                state.mkdir(mode=0o700, parents=True, exist_ok=True)
                lock = stack.enter_context((state / "tick.lock").open("a"))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    emit({"status": "overlapping_tick"})
                    return 0
                receipts = stack.enter_context(closing(
                    sqlite3.connect(state / "receipts.sqlite3", isolation_level=None)
                ))
                receipts.executescript("""
                    CREATE TABLE IF NOT EXISTS delivery (
                        repo TEXT, number INTEGER, status TEXT, time REAL, sha TEXT, owner TEXT,
                        PRIMARY KEY (repo, number));
                    CREATE TABLE IF NOT EXISTS binding (
                        cwd TEXT, repo TEXT, number INTEGER, branch TEXT, owner TEXT,
                        PRIMARY KEY (cwd, repo, number, branch));
                """)
            for result in tick(config, receipts):
                emit(result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error):
        emit({"status": "blocked_configuration_or_state"})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
