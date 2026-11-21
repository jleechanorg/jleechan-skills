#!/usr/bin/env python3
"""Inspect enrolled PR owners and optionally nudge their existing sessions."""

import argparse
import fcntl
import json
import re
import socket
import sqlite3
import subprocess
import time
from collections import defaultdict
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from pr_nudger_discovery import discover_owners
import pr_nudger_routes
from pr_nudger_intake import Intake, RateLimited, launch_capacity, remember_binding
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


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _rate_reset(headers, body, now):
    lower = {name.lower(): value for name, value in headers.items()}
    retry = lower.get("retry-after", "")
    reset = lower.get("x-ratelimit-reset", "")
    if retry.isdecimal():
        return now + max(1, int(retry))
    if lower.get("x-ratelimit-remaining") == "0" and reset.isdecimal():
        return max(now + 1, int(reset))
    if "secondary rate limit" in body.lower():
        return now + 60
    return 0


def _github_payload(output, budget, bucket="core"):
    lines, separator, body = output.replace("\r\n", "\n").partition("\n\n")
    if not separator or not lines.startswith("HTTP/"):
        return json.loads(output)
    headers = dict(line.split(": ", 1) for line in lines.splitlines()[1:] if ": " in line)
    code = int(lines.splitlines()[0].split()[1])
    limited = code in (403, 429)
    until = _rate_reset(headers, body if limited else "", budget.now)
    if not until and code == 429:
        until = budget.now + 60
    if until:
        remaining = next((value for name, value in headers.items()
                          if name.lower() == "x-ratelimit-remaining"), None)
        if limited and (
            "secondary rate limit" in body.lower() or (bucket == "core" and remaining != "0")
        ):
            bucket = "secondary"
        budget.rate_limit(until, bucket)
    if code in (403, 429) and until:
        raise RateLimited(until)
    if not 200 <= code < 300:
        raise ValueError("GitHub request failed")
    return json.loads(body)


def github(cwd, endpoint, *, head=None, inspection=False, params=None, budget=None):
    try:
        return _github_rest(cwd, endpoint, head=head, inspection=inspection,
                            params=params, budget=budget)
    except RateLimited:
        exact = re.fullmatch(rf"repos/({REPO})/pulls/([1-9][0-9]*)", endpoint)
        if (not exact or head is not None or params is not None
                or budget.budget_until("secondary") > budget.now
                or budget.budget_until("core") <= budget.now):
            raise
        return _graphql_pull(cwd, exact[1], int(exact[2]), budget)


def _github_rest(cwd, endpoint, *, head, inspection, params, budget):
    if budget is not None:
        until = max(budget.budget_until(), budget.budget_until("secondary"))
        if until > budget.now:
            raise RateLimited(until)
    args = (endpoint,)
    if head is not None:
        args = ("-X", "GET", endpoint, "-f", f"head={head}", "-f", "state=open", "-F", "per_page=2")
    if params is not None:
        args = (f"{endpoint}?{urlencode(params)}",)
    include = ("--include",) if budget is not None else ()
    try:
        output = command(cwd, "gh", "api", *include, *args, "--hostname", "github.com")
        return _github_payload(output, budget) if budget else json.loads(output)
    except subprocess.CalledProcessError as error:
        if budget and isinstance(error.output, str) and error.output.startswith("HTTP/"):
            return _github_payload(error.output, budget)
        # gh reserves exit 4 for its local authentication preflight.
        if not inspection or error.returncode != 4:
            raise
    suffix = r"(?:/pulls/[1-9][0-9]*|/activity)?" if head is None else "/pulls"
    match = re.fullmatch(rf"repos/({REPO}){suffix}", endpoint)
    if not match:
        raise ValueError("Unsupported public GitHub endpoint")
    repo_slug(match[1])
    query = params or (dict(head=head, state="open", per_page=2) if head is not None else {})
    request = Request(f"https://api.github.com/{endpoint}" + ("?" + urlencode(query) if query else ""), headers={
        "Accept": "application/vnd.github+json", "User-Agent": "pr-owner-nudger",
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        until = _rate_reset(error.headers, "", budget.now) if budget else 0
        if until:
            primary = error.headers.get("X-RateLimit-Remaining") == "0"
            budget.rate_limit(until, "core" if primary else "secondary")
            raise RateLimited(until) from error
        raise


PULL_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number state title body baseRefName headRefName headRefOid
      baseRepository { nameWithOwner }
      headRepository { nameWithOwner }
      labels(first: 100) { nodes { name } pageInfo { hasNextPage } }
    }
  }
}
"""


def _graphql(cwd, query, repo, number, budget):
    bucket = "graphql"
    until = max(budget.budget_until(bucket), budget.budget_until("secondary"))
    if until > budget.now:
        raise RateLimited(until)
    owner, name = repo.split("/")
    try:
        output = command(cwd, "gh", "api", "graphql", "--include", "--hostname", "github.com",
                         "-f", f"query={query}", "-f", f"owner={owner}",
                         "-f", f"repo={name}", "-F", f"number={number}")
    except subprocess.CalledProcessError as error:
        if not isinstance(error.output, str) or not error.output.startswith("HTTP/"):
            raise
        output = error.output
    response = _github_payload(output, budget, bucket)
    if response.get("errors"):
        if any(error.get("type") == "RATE_LIMITED" for error in response["errors"]):
            until = max(budget.budget_until(bucket), budget.now + 60)
            budget.rate_limit(until, bucket)
            raise RateLimited(until)
        raise ValueError("GitHub GraphQL response has errors")
    return response["data"]["repository"]["pullRequest"]


def _graphql_pull(cwd, repo, number, budget):
    pr = _graphql(cwd, PULL_QUERY, repo, number, budget)
    labels = pr["labels"]
    base_repo = pr["baseRepository"]["nameWithOwner"]
    if (pr["number"] != number or repo_slug(base_repo) != repo_slug(repo)
            or not re.fullmatch(r"[0-9a-f]{40}", pr["headRefOid"])
            or pr["state"] not in {"OPEN", "CLOSED", "MERGED"}
            or labels["pageInfo"]["hasNextPage"]):
        raise ValueError("Incomplete or mismatched GitHub pull request")
    return {
        "number": number, "state": "open" if pr["state"] == "OPEN" else "closed",
        "title": pr["title"], "body": pr["body"], "labels": labels["nodes"],
        "base": {"ref": pr["baseRefName"], "repo": {"full_name": base_repo}},
        "head": {"ref": pr["headRefName"], "sha": pr["headRefOid"],
                 "repo": {"full_name": repo_slug(pr["headRepository"]["nameWithOwner"])}},
    }


def identity(pr):
    return (pr["base"]["repo"]["full_name"].lower(), pr["number"],
            pr["head"]["repo"]["full_name"].lower(), pr["head"]["ref"], pr["head"]["sha"])


def pr_status(pr):
    if pr["state"] != "open":
        return "closed"
    records = re.findall(
        r"(?ms)^## (PR Stage|Execution Record)[ \t]*\n(.*?)(?=^## |\Z)",
        pr.get("body") or "",
    )
    if len(records) != 1:
        return "actionable"
    section, record = records[0]
    fields = defaultdict(list)
    for key, value in re.findall(r"(?m)^([a-z_]+):[ \t]*(\S[^\n]*)$", record):
        fields[key].append(value.strip())
    missing = {"n/a", "none", "-", "unknown"}
    if any(action.lower() not in missing for action in fields["next_action"]):
        return "actionable"
    head = pr["head"]["sha"]
    if (section == "PR Stage" and pr["title"].lower().startswith("[ready]")
            and any(label["name"] == "stage:5-final-approval" for label in pr["labels"])
            and fields["candidate"] in ([], [head]) and fields["status"] in ([], ["FINAL_READY"])
            and all(blocker.lower() in missing for blocker in fields["blocker"])):
        published = re.findall(
            r"(?m)^Stage 5 (?:— |\(final approval\): )(?:FINAL_READY|\*\*FINAL_READY\*\*) "
            r"at `([0-9a-f]{40})`(?:[.,]|$)", record
        )
        if published == [head]:
            return "final_ready"
    if (fields["candidate"] != [head] or len(fields["owner"]) != 1
            or fields["owner"][0].lower() in missing):
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


def inferred_bases(cwd, origin, inspection, read=None):
    remote = (read or github)(cwd, f"repos/{origin}", inspection=inspection)
    if repo_slug(remote["full_name"]) != origin:
        raise ValueError("GitHub repository does not match the checkout origin")
    if remote["fork"]:
        return {origin, repo_slug(remote["parent"]["full_name"])}
    return {origin}


def discover(cwd, repos, local, inspection, read=None):
    origin, branch, sha = local
    matches = []
    for repo in sorted(repos):
        rows = (read or github)(cwd, f"repos/{repo}/pulls", head=f"{origin.split('/')[0]}:{branch}",
                      inspection=inspection)
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


def remember_configured(db, expected, cwd, owner):
    if db is None or owner.get("cmux_discovered") or owner.get("cli") not in {"codex", "claude"}:
        return True
    repo, number, _, branch, _ = expected
    row = db.execute(
        "SELECT owner FROM binding WHERE cwd=? AND repo=? AND number=? AND branch=?",
        (str(cwd), repo, number, branch),
    ).fetchone()
    if row:
        prior = json.loads(row[0])
        if prior.get("binding_source") in {"cmux", "bootstrap"} or prior.get("cmux_discovered"):
            return all(
                field not in owner or field not in prior or owner[field] == prior[field]
                for field in ("cli", "session", "profile_dir")
            )
    try:
        if str(UUID(owner["session"])) != owner["session"]:
            return True
        path, env = pr_nudger_routes._session(dict(owner, branch=branch), cwd)
    except CHECK_ERRORS:
        return True
    if path is not None:
        profile_key = "CODEX_HOME" if owner["cli"] == "codex" else "CLAUDE_CONFIG_DIR"
        verified = dict(owner, cwd=str(cwd), host=socket.gethostname(),
                        profile_dir=str(Path(env[profile_key]).resolve()))
        remember_binding(db, expected, verified, "configured")
    return True


def dispatch(cwd, owner, local, pr, receipts, config, from_cache, read=None, *, resume_sandbox=None):
    read = read or github
    expected = identity(pr)
    repo, number, _, branch, sha = expected
    owner = dict(owner, cwd=str(cwd))
    # Execution permissions come from the current exact enrollment, never a saved owner.
    owner.pop("resume_sandbox", None)
    key = (repo, number)
    cooldown = config.get("cooldown_seconds", 1800)
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
    can_resume = (config.get("headless_resume", True) is True
                  and owner.get("headless_resume", True) is True
                  and (from_cache or not owner.get("cmux_discovered")
                       or owner.get("headless_only") is True))

    def confirm_owner(workspace, surface, profile_dir=None):
        owner.update(workspace=workspace, surface=surface)
        if receipts is not None and owner.get("cmux_discovered") and revalidate():
            verified = dict(owner, host=socket.gethostname())
            if profile_dir:
                verified["profile_dir"] = profile_dir
            remember_binding(receipts, expected, verified, "cmux")

    def record(status):
        fields = ("cwd", "cli", "session", "workspace", "surface", "profile_dir",
                  "account", "destination", "parent_message_id")
        audit = json.dumps({**{key: owner[key] for key in fields if key in owner},
                            "branch": branch, "transport": transport})
        receipts.execute("INSERT OR REPLACE INTO delivery VALUES (?, ?, ?, ?, ?, ?)",
                         (*key, status, time.time(), sha, audit))

    def revalidate():
        try:
            current = read(cwd, f"repos/{repo}/pulls/{number}", inspection=receipts is None)
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
                            resume_sandbox=resume_sandbox, recheck=recheck,
                            revalidate=revalidate, confirm_owner=confirm_owner,
                            headless_resume=can_resume, admit_launch=launch_capacity),
                       prompt, receipts is not None)
    except Exception:
        # An interrupted transport may already have acted. Keep its durable intent.
        return "reconciliation_required" if reserved else "blocked_route"
    if reserved:
        if status not in {"delivered", "attempted_delivery", "no_delivery"}:
            return "reconciliation_required"
        record(status)
    return status


def worktrees(config, enrolled, errors):
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
            errors.append({"cwd": str(root), "status": "blocked_worktree_list"})


def legacy_tick(config, receipts, enrolled, discovered, skip=(), read=None):
    candidates = defaultdict(list)
    inferred = {}
    inspection = receipts is None
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
                    inferred[origin] = inferred_bases(cwd, origin, inspection, read)
                repos = inferred[origin]
            status, pr = discover(cwd, repos, local, inspection, read)
        except CHECK_ERRORS as error:
            yield dict(result, status="blocked_discovery", error=type(error).__name__)
            continue
        if pr is not None:
            repo, number, _, _, sha = identity(pr)
            if (repo, number) in skip:
                continue
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
            elif owners[0].get("host", socket.gethostname()) != socket.gethostname():
                status = "owner_host_unverified"
            elif not from_cache and not remember_configured(receipts, identity(pr), cwd, owners[0]):
                status = "ambiguous_owner"
            else:
                status = dispatch(cwd, owners[0], local, pr, receipts, config, from_cache, read)
            yield dict(result, status=status)


def configured_targets(config):
    targets = {}
    for item in config.get("targets", []):
        repo, number = repo_slug(item["repo"]), item["number"]
        pickup = item.get("pickup_after_seconds")
        if (type(number) is not int or number < 1
                or type(item.get("observe_only", False)) is not bool
                or (pickup is not None and (type(pickup) is not int or pickup != 3600))):
            raise ValueError("Invalid exact target or pickup policy")
        key = repo, number
        if key in targets and targets[key] != item:
            raise ValueError("Conflicting target enrollment")
        targets[key] = item
    return targets


def owners_for_target(enrolled, discovered, head_identity):
    _, _, head_repo, branch, sha = head_identity
    matches = []
    for cwd, configured in sorted(enrolled.items()):
        try:
            local = checkout(cwd)
        except CHECK_ERRORS:
            continue
        if local != (head_repo, branch, sha):
            continue
        live = discovered.get(str(cwd), [])
        explicit = [item for item in configured if item.get("repo", head_identity[0]).lower() == head_identity[0]]
        if len(explicit) == len(live) == 1 and all(
            explicit[0].get(field) == live[0][field] for field in ("cli", "session")
        ):
            owners = [{**explicit[0], **live[0]}]
        else:
            owners = explicit + live
        matches.append((cwd, local, owners))
    return matches


def latest_push(identity, cwd, read, inspection):
    _, _, head_repo, branch, sha = identity
    ref = f"refs/heads/{branch}"
    events = read(cwd, f"repos/{head_repo}/activity", inspection=inspection,
                  params={"ref": ref, "direction": "desc", "per_page": 30})
    candidates = [
        (datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).timestamp(), event)
        for event in events
        if event.get("ref") == ref
        and event.get("activity_type") in {"push", "force_push", "pr_merge", "merge_queue_merge", "branch_creation"}
        and event.get("before") != event.get("after")
    ]
    if not candidates:
        return None
    timestamp = max(candidate[0] for candidate in candidates)
    latest = [event for observed, event in candidates if observed == timestamp]
    return timestamp if all(event.get("after") == sha for event in latest) else None


def bootstrap_enrollment(target, expected, *, require_launch=True):
    enrollment = target.get("enrollment")
    if not isinstance(enrollment, dict):
        return None, "missing_owner"
    _, _, head_repo, branch, _ = expected
    if enrollment.get("host") != socket.gethostname():
        return None, "owner_host_unverified"
    authorized = enrollment.get("launch_authorized") is True
    if not enrollment.get("managed_exclusive") is True or (require_launch and not authorized):
        return None, "missing_launch_authority"
    if enrollment.get("cli") != "codex":
        return None, "bootstrap_cli_unsupported"
    cwd = Path(enrollment["cwd"])
    if not cwd.is_absolute() or cwd.resolve() != cwd or (
        enrollment.get("head_repo"), enrollment.get("branch")
    ) != (head_repo, branch):
        return None, "enrollment_mismatch"
    fields = ("cwd", "head_repo", "branch", "cli", "cli_bin", "profile_dir", "model", "headless_only")
    return {field: enrollment[field] for field in fields if field in enrollment} | {
        "managed_exclusive": True, "launch_authorized": authorized, "host": enrollment["host"]
    }, None


def dispatch_target(key, target, pr, matches, store, config, read):
    expected = identity(pr)
    _, _, head_repo, branch, sha = expected
    note = store.schedule
    row = store.row(key)
    db = store.db
    if row["bootstrap"]:
        attempt = json.loads(row["bootstrap"])
        if tuple(attempt["identity"][:-1]) != expected[:-1]:
            return note(key, "reconciliation_required", "reconcile_bootstrap")
        enrolled, reason = bootstrap_enrollment(target, expected)
        if reason or enrolled != attempt["enrollment"]:
            return note(key, "reconciliation_required", "reconcile_bootstrap")
        status, session = pr_nudger_routes.inspect_codex_bootstrap(
            enrolled, tuple(attempt["identity"]), attempt,
            bind=lambda session: store.bind(key, expected, dict(enrolled, session=session)),
        )
        if status == "bootstrapped":
            if not session or store.row(key)["bootstrap"]:
                return note(key, "reconciliation_required", "reconcile_bootstrap")
            return note(key, status, "dispatch_owner", progress=True)
        return note(key, status, "reconcile_bootstrap")

    if pr_status(pr) != "actionable":
        return note(key, pr_status(pr), "refresh_pr", progress=True)
    previous = db.execute(
        "SELECT status, time FROM delivery WHERE repo=? AND number=?", key
    ).fetchone() if db is not None else None
    if previous and previous[0] in {"pending_delivery", "attempted_delivery"}:
        return note(key, "reconciliation_required", "reconcile_delivery")
    if target.get("observe_only") is True:
        return note(key, "observing", "refresh_pr", progress=True)
    enrollment = target.get("enrollment")
    if isinstance(enrollment, dict) and enrollment.get("host") != socket.gethostname():
        return note(key, "owner_host_unverified", "verify_owner")
    candidates = [(cwd, local, owner) for cwd, local, owners in matches for owner in owners]
    from_cache = not candidates
    if from_cache and db is not None:
        for cwd, local, _ in matches:
            cached = db.execute(
                "SELECT owner FROM binding WHERE cwd=? AND repo=? AND number=? AND branch=?",
                (str(cwd), *key, branch)
            ).fetchone()
            if cached:
                if config.get("headless_resume", True) is not True:
                    return note(key, "blocked_headless_disabled", "verify_owner")
                candidates.append((cwd, local, json.loads(cached[0])))
    if len(candidates) > 1:
        return note(key, "ambiguous_owner", "verify_owner")
    resume_sandbox = None
    if candidates:
        cwd, local, owner = candidates[0]
        if isinstance(enrollment, dict) and enrollment.get("managed_exclusive") is True:
            managed, reason = bootstrap_enrollment(target, expected, require_launch=False)
            if reason or str(cwd) != managed["cwd"] or any(
                field in owner and owner[field] != managed.get(field)
                for field in ("cli", "cli_bin", "profile_dir", "model")
            ):
                return note(key, reason or "enrollment_mismatch", "verify_owner")
            owner = dict(owner, **managed)
            resume_sandbox = enrollment.get("resume_sandbox")
        if owner.get("host", socket.gethostname()) != socket.gethostname():
            return note(key, "owner_host_unverified", "verify_owner")
        candidates[0] = cwd, local, owner
        if not from_cache and not remember_configured(db, expected, cwd, owner):
            return note(key, "ambiguous_owner", "verify_owner")
    authorized_enrollment = None
    if row["next_due"] > store.now:
        if not candidates and row["reason"] in {"missing_owner", "missing_launch_authority"}:
            managed, _ = bootstrap_enrollment(target, expected)
            if managed and any(str(cwd) == managed["cwd"] for cwd, _, _ in matches):
                authorized_enrollment = managed
        # A newly observed cmux owner can use the existing route without a launch.
        launch_deferrals = {"missing_owner", "missing_launch_authority", "bootstrap_cli_unsupported",
                            "blocked_launch_capacity", "stale_checkout"}
        if not from_cache and candidates[0][2].get("cmux_discovered") and row["reason"] in launch_deferrals:
            note(key, "owner_found", "dispatch_owner", progress=True)
        elif authorized_enrollment:
            note(key, "launch_authorized", "bootstrap_owner", progress=True)
        else:
            return dict(status=row["reason"], next_action=row["next_action"],
                        attempts=row["attempts"], next_due=row["next_due"])
    pickup = target.get("pickup_after_seconds")
    if pickup:
        pushed = latest_push(expected, Path.cwd(), read, db is None)
        store.set(key, remote_push_at=pushed)
        if pushed is None:
            return note(key, "remote_push_unverified", "verify_remote_push")
        if pushed + pickup > store.now:
            return note(key, "pickup_not_due", "verify_remote_push", earliest=pushed + pickup)
    if candidates:
        cwd, local, owner = candidates[0]
        status = dispatch(
            cwd, owner, local, pr, db, config, from_cache, read,
            resume_sandbox=resume_sandbox,
        )
        cooldown = config.get("cooldown_seconds", 1800)
        if status == "delivered":
            return note(key, status, "refresh_pr", progress=True, earliest=store.now + cooldown)
        earliest = previous[1] + cooldown if status == "cooldown" and previous else 0
        action = "reconcile_delivery" if status in {"reconciliation_required", "attempted_delivery"} else "dispatch_owner"
        return note(key, status, action, earliest=earliest)
    enrollment, reason = ((authorized_enrollment, None) if authorized_enrollment
                          else bootstrap_enrollment(target, expected))
    if reason:
        return note(key, reason, "verify_owner")
    cwd = Path(enrollment["cwd"])

    def recheck():
        try:
            latest = read(cwd, f"repos/{key[0]}/pulls/{key[1]}", inspection=db is None)
            return checkout(cwd) == (head_repo, branch, sha) and identity(latest) == expected and pr_status(latest) == "actionable"
        except CHECK_ERRORS:
            return False

    if not authorized_enrollment and checkout(cwd) != (head_repo, branch, sha):
        return note(key, "stale_checkout", "verify_checkout")
    if db is not None and not launch_capacity():
        return note(key, "blocked_launch_capacity", "bootstrap_owner")
    status = pr_nudger_routes.start_codex_bootstrap(
        enrollment, expected, apply=db is not None, recheck=recheck,
        begin_attempt=lambda: store.begin(key, expected, enrollment)
    )
    return note(key, status, "reconcile_bootstrap" if store.row(key)["bootstrap"] else "bootstrap_owner")


CI_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      headRefOid
      commits(last:1) { nodes { commit {
        oid
        statusCheckRollup { contexts(first:100) {
          pageInfo { hasNextPage }
          nodes {
            ... on CheckRun { status conclusion }
            ... on StatusContext { state }
          }
        } }
      } } }
    }
  }
}
"""


def observe_ci(repo, number, head, budget):
    try:
        pr = _graphql(Path.cwd(), CI_QUERY, repo, number, budget)
        commit = pr["commits"]["nodes"][-1]["commit"]
        if pr["headRefOid"] != head or commit["oid"] != head:
            return "stale_head"
        rollup = commit["statusCheckRollup"]
        if rollup is None:
            return "no_checks_observed"
        contexts = rollup["contexts"]
        if contexts["pageInfo"]["hasNextPage"]:
            return "incomplete"
        states = {check.get("conclusion") or check.get("state") or check.get("status")
                  for check in contexts["nodes"]}
    except RateLimited:
        return "rate_limited"
    except (*CHECK_ERRORS, AttributeError, IndexError):
        return "unavailable"
    if states & {"ACTION_REQUIRED", "CANCELLED", "ERROR", "FAILURE", "STALE", "STARTUP_FAILURE", "TIMED_OUT"}:
        return "failing"
    if states & {"EXPECTED", "IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED", "WAITING"}:
        return "pending"
    if states - {"SUCCESS", "NEUTRAL", "SKIPPED"}:
        return "unavailable"
    return "reported_success" if "SUCCESS" in states else "no_checks_observed"


def tick(config, receipts, state=None):
    targets = configured_targets(config)
    store = Intake(receipts, state, time.time())
    if targets:
        store.prepare(sorted(targets))

    def read(cwd, endpoint, **kwargs):
        return github(cwd, endpoint, budget=store if targets else None, **kwargs)

    observed = {}
    for key in sorted(targets):
        repo, number = key
        result = {"repo": repo, "pr": number}
        try:
            pr = read(Path.cwd(), f"repos/{repo}/pulls/{number}", inspection=receipts is None)
            if identity(pr)[:2] != key:
                raise ValueError("GitHub PR identity mismatch")
            stage, *others = [item["name"] for item in pr["labels"]
                              if item["name"].startswith("stage:")] or [None]
            head = identity(pr)[-1]
            store.observation(key, head, pr_status(pr), None if others else stage)
            ci_status = observe_ci(repo, number, head, store)
            store.ci_observation(key, head, ci_status)
            observed[key] = pr, ci_status
        except RateLimited as error:
            yield dict(result, **store.schedule(key, "blocked_github_rate", "refresh_pr",
                                                earliest=error.until))
        except CHECK_ERRORS:
            yield dict(result, **store.schedule(key, "blocked_pr_refresh", "refresh_pr"))

    legacy_enrolled = defaultdict(list)
    errors = []
    worktrees(config, legacy_enrolled, errors)
    enrolled = dict(legacy_enrolled)
    # A trusted worktree can host an existing owner even when bootstrap is disabled.
    for item in targets.values():
        enrollment = item.get("enrollment")
        if isinstance(enrollment, dict) and Path(enrollment.get("cwd", "")).is_absolute():
            if enrollment.get("host") == socket.gethostname():
                enrolled.setdefault(Path(enrollment["cwd"]).resolve(), [])
    if receipts is not None:
        for key, (pr, _) in observed.items():
            _, _, head_repo, branch, _ = identity(pr)
            for cwd, raw in receipts.execute(
                "SELECT cwd, owner FROM binding WHERE repo=? AND number=? AND branch=?",
                (*key, branch),
            ):
                remembered = json.loads(raw)
                path = Path(cwd)
                if (remembered.get("host") == socket.gethostname()
                        and remembered.get("head_repo") == head_repo
                        and path.is_absolute() and path.resolve() == path):
                    enrolled.setdefault(path, [])
    discovered = discover_owners(enrolled) if enrolled else {}
    yield from errors
    for key in sorted(observed, key=lambda key: (store.row(key)["next_due"], key)):
        pr, ci_status = observed[key]
        expected = identity(pr)
        try:
            outcome = dispatch_target(key, targets[key], pr,
                                      owners_for_target(enrolled, discovered, expected), store, config, read)
        except RateLimited as error:
            outcome = store.schedule(key, "blocked_github_rate", "refresh_pr", earliest=error.until)
        except CHECK_ERRORS:
            action = "reconcile_bootstrap" if store.row(key)["bootstrap"] else "verify_owner"
            outcome = store.schedule(key, "blocked_target_verification", action)
        yield dict(repo=key[0], pr=key[1], sha=expected[-1], ci_status=ci_status, **outcome)
    yield from legacy_tick(config, receipts, legacy_enrolled, discovered, targets, read if targets else None)


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
            receipts = state = None
            if args.apply:
                state = Path(config.get("state_dir", "~/.local/state/pr-owner-nudger")).expanduser().resolve()
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
            for result in tick(config, receipts, state):
                emit(result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error):
        emit({"status": "blocked_configuration_or_state"})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
