#!/usr/bin/env python3
"""
ci_queue_trim.py — CI Queue Inactivity Triage & Trimming Tool

Audits and trims queued GitHub Actions workflow runs associated with dormant,
superseded, or merged PRs. Resolves three pitfalls at audit time:

  1. Deceptive PR.updatedAt (bots touch it constantly) → verify the head
     commit's committer date instead, knowing ``committedDate`` is the
     author's commit timestamp (it precedes the push, not equal to it).
  2. Superseded runs (a newer push advanced the PR/branch head) → compare
     ``run.headSha`` against the PR/branch current head SHA.
  3. Lookup failure (PR/commit unknown) → mark ``audit_incomplete`` and
     keep the run; never substitute the run's age as a head-age fact.

Event semantics:
  * ``pull_request`` / ``pull_request_target``: compare ``run.headSha`` to
    ``PR.head.sha`` (the merge ref inside the base repo).
  * ``push``: compare ``run.headSha`` to the branch HEAD SHA.
  * ``merge_group`` and any unknown event: never apply the generic
    stale-head comparison.

Workflow importance is decided by an explicit configured allowlist
(``PROTECTED_WORKFLOWS``), never by fuzzy substring heuristics.

Usage:
    python3 ci_queue_trim.py [--repo OWNER/REPO] [--max-age-hours HOURS]
                             [--cancel | --superseded-only --cancel]
                             [--check-host]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_REPO = "jleechanorg/worldarchitect.ai"
DEFAULT_MAX_AGE_HOURS = 2.0

# Branches whose runs are never cancelled by this tool. ``deploy`` was added
# because cancel-on-stale behaviour can break an in-progress deploy chain.
PROTECTED_BRANCHES = {"main", "master", "production", "staging", "release", "deploy"}

# Explicit allowlist of workflow filenames / names that are always kept.
# Populate via the operator config; an empty set is the safe default and
# means no fuzzy heuristics are used to infer protection.
PROTECTED_WORKFLOWS: set = set()

# Events where the generic stale-head comparison is sound. Other events
# fall into one of two buckets:
#   * MERGE_GROUP_EVENTS: never stale-head cancel; only MERGED/CLOSED does.
#   * everything else: audit_incomplete=True; never cancel.
MERGE_GROUP_EVENTS = {"merge_group"}
SUPPORTED_EVENTS = {"pull_request", "pull_request_target", "push"}

COLIMA_SOCKET = os.path.expanduser("~/.colima/_lima/_networks/user-v2/user-v2_fd.sock")
DISK_FLOOR_GB = 7.0


def run_cmd(cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    """Run a shell command with strict anti-freeze environment."""
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["GH_PAGER"] = ""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:
        return 1, "", str(exc)


def parse_iso_datetime(dt_str: str) -> Optional[datetime.datetime]:
    """Parse ISO 8601 string to timezone-aware UTC datetime."""
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def format_duration(seconds: float) -> str:
    """Format duration in seconds into human-readable string."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h"
    days = hours / 24
    return f"{days:.1f}d"


def get_queued_runs(repo: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch queued workflow runs from GitHub (includes event + status)."""
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--status", "queued",
        "--limit", str(limit),
        "--json", "databaseId,name,headBranch,headSha,event,status,createdAt,url",
    ]
    rc, stdout, stderr = run_cmd(cmd)
    if rc != 0:
        print(f"Error fetching queued runs: {stderr.strip()}", file=sys.stderr)
        return []
    try:
        return json.loads(stdout)
    except Exception as exc:
        print(f"Failed to parse runs JSON: {exc}", file=sys.stderr)
        return []


def get_repo_prs(repo: str, limit: int = 100) -> Dict[str, Dict[str, Any]]:
    """Fetch recent PRs in bulk using REST API (immune to GraphQL rate limits)."""
    cmd = [
        "gh", "api", f"repos/{repo}/pulls?state=all&per_page={min(limit, 100)}"
    ]
    rc, stdout, stderr = run_cmd(cmd)
    branch_to_pr: Dict[str, Dict[str, Any]] = {}
    if rc != 0:
        print(f"Warning: Failed to bulk fetch PRs via REST: {stderr.strip()}", file=sys.stderr)
        return branch_to_pr

    try:
        prs = json.loads(stdout)
        for p in prs:
            branch = p.get("head", {}).get("ref")
            if branch and branch not in branch_to_pr:
                state = "MERGED" if p.get("merged_at") else p.get("state", "").upper()
                head_obj = p.get("head", {}) or {}
                head_sha = head_obj.get("sha")
                # Some PRs are from forks; we keep head.sha (the merge ref
                # inside the base repo) distinct from the fork's own SHA.
                branch_to_pr[branch] = {
                    "number": p.get("number"),
                    "headRefName": branch,
                    "state": state,
                    "updatedAt": p.get("updated_at"),
                    "sha": head_sha,
                    "head_sha": head_sha,
                    "head_repo": (head_obj.get("repo") or {}).get("full_name"),
                    "is_fork": (head_obj.get("repo") or {}).get("full_name", repo).lower()
                    != repo.lower(),
                }
    except Exception as exc:
        print(f"Warning: Failed to parse PR list JSON: {exc}", file=sys.stderr)

    return branch_to_pr


_COMMIT_DATE_CACHE: Dict[str, str] = {}
_PR_BY_HEAD_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}


def fetch_single_pr(repo: str, branch: str) -> Optional[Dict[str, Any]]:
    """Fetch PR details for a specific branch using REST API to avoid GraphQL limits."""
    if branch in _PR_BY_HEAD_CACHE:
        return _PR_BY_HEAD_CACHE[branch]
    owner = repo.split("/")[0] if "/" in repo else repo
    cmd = [
        "gh", "api", f"repos/{repo}/pulls?state=all&head={owner}:{branch}"
    ]
    rc, stdout, _ = run_cmd(cmd, timeout=15)
    result: Optional[Dict[str, Any]] = None
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if data and isinstance(data, list):
                pr = data[0]
                sha = pr.get("head", {}).get("sha")
                commit_date = None
                if sha:
                    if sha in _COMMIT_DATE_CACHE:
                        commit_date = _COMMIT_DATE_CACHE[sha]
                    else:
                        c_rc, c_out, _ = run_cmd(["gh", "api", f"repos/{repo}/commits/{sha}"], timeout=15)
                        if c_rc == 0 and c_out.strip():
                            c_data = json.loads(c_out)
                            commit_date = c_data.get("commit", {}).get("committer", {}).get("date")
                            if commit_date:
                                _COMMIT_DATE_CACHE[sha] = commit_date

                head_obj = pr.get("head", {}) or {}
                result = {
                    "number": pr.get("number"),
                    "headRefName": branch,
                    "state": pr.get("state", "").upper(),
                    "updatedAt": pr.get("updated_at"),
                    "sha": sha,
                    "head_sha": sha,
                    "head_repo": (head_obj.get("repo") or {}).get("full_name"),
                    "is_fork": (head_obj.get("repo") or {}).get("full_name", repo).lower()
                    != repo.lower(),
                    "commits": [{"committedDate": commit_date}] if commit_date else [],
                }
        except Exception:
            result = None
    _PR_BY_HEAD_CACHE[branch] = result
    return result


def fetch_run_details(repo: str, run_id: int) -> Optional[Dict[str, Any]]:
    """Re-fetch a single run's metadata for pre-cancel validation."""
    rc, stdout, _ = run_cmd(["gh", "api", f"repos/{repo}/actions/runs/{run_id}"], timeout=15)
    if rc != 0 or not stdout.strip():
        return None
    try:
        data = json.loads(stdout)
    except Exception:
        return None
    if not isinstance(data, dict):
        # Defensive: an upstream malformed response must not crash the
        # audit. Returning None means we fall back to the queued-list
        # fields and mark ``audit_incomplete`` for the caller.
        return None
    return {
        "status": data.get("status"),
        "event": data.get("event"),
        "head_sha": data.get("head_sha"),
        "head_branch": data.get("head_branch"),
        "name": (data.get("name") or ""),
        "workflow_filename": os.path.basename(data.get("path") or ""),
    }


def fetch_pr(repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
    """Re-fetch a single PR by number for fingerprint validation."""
    rc, stdout, _ = run_cmd(["gh", "api", f"repos/{repo}/pulls/{pr_number}"], timeout=15)
    if rc != 0 or not stdout.strip():
        return None
    try:
        data = json.loads(stdout)
    except Exception:
        return None
    head_obj = data.get("head", {}) or {}
    head_sha = head_obj.get("sha")
    return {
        "number": data.get("number"),
        "state": ("MERGED" if data.get("merged_at") else (data.get("state", "") or "").upper()),
        "head_sha": head_sha,
        "head_ref": head_obj.get("ref"),
    }


def fetch_branch_head(repo: str, branch: str) -> Optional[str]:
    """Return the current HEAD SHA for ``branch`` (push-event comparison)."""
    rc, stdout, _ = run_cmd(["gh", "api", f"repos/{repo}/branches/{branch}"], timeout=15)
    if rc != 0 or not stdout.strip():
        return None
    try:
        return json.loads(stdout).get("commit", {}).get("sha")
    except Exception:
        return None


def is_protected_workflow(name: str, filename: str = "") -> bool:
    """Decide workflow importance via an explicit configured allowlist.

    Fuzzy substring heuristics are intentionally avoided so a workflow named
    e.g. ``my-deploy-helper`` is not implicitly protected.
    """
    if not PROTECTED_WORKFLOWS:
        return False
    candidates = {name, filename, os.path.basename(filename or "")}
    return any(c for c in candidates if c in PROTECTED_WORKFLOWS)


def _enrich_pr_with_commit_date(repo: str, pr: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ``commits`` to a bulk-fetched PR if its head SHA commit date is missing."""
    if pr.get("commits"):
        return pr
    sha = pr.get("head_sha") or pr.get("sha")
    if not sha:
        return pr
    if sha in _COMMIT_DATE_CACHE:
        commit_date = _COMMIT_DATE_CACHE[sha]
    else:
        c_rc, c_out, _ = run_cmd(["gh", "api", f"repos/{repo}/commits/{sha}"], timeout=15)
        commit_date = None
        if c_rc == 0 and c_out.strip():
            try:
                commit_date = json.loads(c_out).get("commit", {}).get("committer", {}).get("date")
                if commit_date:
                    _COMMIT_DATE_CACHE[sha] = commit_date
            except Exception:
                commit_date = None
    if commit_date:
        pr["commits"] = [{"committedDate": commit_date}]
    return pr


def check_host_health() -> Dict[str, Any]:
    """Check local macOS host disk space and Colima socket state."""
    report: Dict[str, Any] = {"colima_ok": True, "disk_ok": True, "notes": []}

    # 1. Host disk check
    data_path = "/System/Volumes/Data" if os.path.exists("/System/Volumes/Data") else "/"
    try:
        _, _, free_bytes = shutil.disk_usage(data_path)
        free_gb = free_bytes / (1024 ** 3)
        report["free_disk_gb"] = round(free_gb, 2)
        if free_gb < DISK_FLOOR_GB:
            report["disk_ok"] = False
            report["notes"].append(
                f"Disk space critical: {free_gb:.2f} GB free on {data_path} (floor: {DISK_FLOOR_GB} GB)"
            )
        else:
            report["notes"].append(f"Disk space OK: {free_gb:.2f} GB free on {data_path}")
    except Exception as exc:
        report["notes"].append(f"Disk check failed: {exc}")

    # 2. Colima socket & process check (macOS)
    if sys.platform == "darwin" and os.path.exists(os.path.expanduser("~/.colima")):
        sock_exists = os.path.exists(COLIMA_SOCKET)
        report["colima_sock_exists"] = sock_exists

        rc, ps_out, _ = run_cmd(["ps", "-Ao", "pid,command"], timeout=10)
        usernet_pids = []
        if rc == 0:
            for line in ps_out.splitlines():
                if "limactl usernet" in line and "colima" in line:
                    parts = line.strip().split()
                    if parts:
                        usernet_pids.append(parts[0])

        report["colima_usernet_pids"] = usernet_pids
        if len(usernet_pids) > 1:
            report["colima_ok"] = False
            report["notes"].append(
                f"Multiple orphaned limactl usernet processes detected: {usernet_pids} (may wedge socket)"
            )
        elif len(usernet_pids) == 0 and sock_exists:
            report["colima_ok"] = False
            report["notes"].append(f"Dead socket file found with no usernet process: {COLIMA_SOCKET}")
        elif len(usernet_pids) == 1 and sock_exists:
            report["notes"].append("Colima usernet socket & process: Healthy (1 process, socket active)")
        else:
            report["notes"].append("Colima usernet not currently running")

    return report


def audit_queue(
    repo: str,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    limit: int = 100,
    superseded_only: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Audit queued runs and categorize them into KEEP vs CANCEL.

    Event semantics:
      * ``pull_request`` / ``pull_request_target``: superseded if ``run.headSha``
        differs from ``PR.head.sha`` (the merge ref inside the base repo).
      * ``push``: superseded if ``run.headSha`` differs from the branch HEAD SHA.
      * ``merge_group`` / unknown events: never cancelled via stale-head.

    Lookup failures mark the run ``audit_incomplete`` and KEEP it; the run's
    age is never substituted for the head-commit age.
    """
    runs = get_queued_runs(repo, limit=limit)
    if not runs:
        return [], {"total_queued": 0, "to_cancel": 0, "to_keep": 0}

    branch_to_pr = get_repo_prs(repo, limit=limit)
    now = datetime.datetime.now(datetime.timezone.utc)
    max_age_seconds = max_age_hours * 3600

    audited_runs: List[Dict[str, Any]] = []
    cancel_count = 0
    keep_count = 0
    # Track which runs had a failed per-run metadata fetch so the final
    # row always carries ``audit_incomplete=True`` in that case.
    metadata_incomplete_ids: set = set()

    for r in runs:
        run_id = r.get("databaseId")
        name = r.get("name", "Unknown")
        branch = r.get("headBranch") or ""
        event = r.get("event") or ""
        run_head_sha = r.get("headSha") or ""
        run_created_dt = parse_iso_datetime(r.get("createdAt", ""))
        run_age_sec = (now - run_created_dt).total_seconds() if run_created_dt else 0

        # Re-fetch per-run metadata to get the actual event / status /
        # workflow filename, which the list view may not include fully.
        # If the fetch fails, every later verdict must carry
        # ``audit_incomplete=True`` so we never substitute assumed facts.
        run_details = fetch_run_details(repo, run_id)
        metadata_incomplete = run_details is None
        if metadata_incomplete:
            metadata_incomplete_ids.add(run_id)
        if run_details:
            event = run_details.get("event") or event
            run_head_sha = run_details.get("head_sha") or run_head_sha
            workflow_filename = run_details.get("workflow_filename") or ""
        else:
            workflow_filename = ""

        # Protected branch check
        if branch in PROTECTED_BRANCHES:
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "N/A (protected)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": False,
                "verdict": "KEEP",
                "reason": f"Protected branch '{branch}'",
            })
            keep_count += 1
            continue

        # Workflow importance is decided by an explicit allowlist only.
        if is_protected_workflow(name, workflow_filename):
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "N/A (protected workflow)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": False,
                "verdict": "KEEP",
                "reason": f"Protected workflow '{name or workflow_filename}'",
            })
            keep_count += 1
            continue

        # ``merge_group`` events must never be cancelled via stale-head.
        # Only a MERGED/CLOSED PR (which merge-group runs do not have) or
        # an empty queue can justify cancellation here.
        if event in MERGE_GROUP_EVENTS:
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "N/A (merge_group)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": True,
                "verdict": "KEEP",
                "reason": f"Event '{event}' skipped from stale-head comparison",
            })
            keep_count += 1
            continue

        # Unknown / unsupported events: mark audit_incomplete and KEEP.
        if event not in SUPPORTED_EVENTS:
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "N/A (unsupported event)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": True,
                "verdict": "KEEP",
                "reason": f"Unsupported event '{event}'; audit incomplete",
            })
            keep_count += 1
            continue

        # Look up PR — if missing, audit is incomplete (do not substitute).
        pr = branch_to_pr.get(branch)
        if not pr and branch:
            pr = fetch_single_pr(repo, branch)
            if pr:
                branch_to_pr[branch] = pr
        elif pr:
            pr = _enrich_pr_with_commit_date(repo, pr)
            branch_to_pr[branch] = pr

        # For push events, no PR is expected; compare against the branch HEAD.
        if event == "push":
            current_head_sha = fetch_branch_head(repo, branch)
            superseded = bool(current_head_sha and run_head_sha and current_head_sha != run_head_sha)
            if not current_head_sha:
                audited_runs.append({
                    "run_id": run_id,
                    "name": name,
                    "branch": branch,
                    "event": event,
                    "pr_number": None,
                    "pr_state": "N/A (push event)",
                    "head_commit_age": "N/A",
                    "pr_updated_age": "N/A",
                    "deceptive_delta": False,
                    "superseded": False,
                    "audit_incomplete": True,
                    "verdict": "KEEP",
                    "reason": "Branch HEAD lookup failed; audit incomplete",
                })
                keep_count += 1
                continue
            if superseded:
                audited_runs.append({
                    "run_id": run_id,
                    "name": name,
                    "branch": branch,
                    "event": event,
                    "pr_number": None,
                    "pr_state": "N/A (push event)",
                    "head_commit_age": "N/A",
                    "pr_updated_age": "N/A",
                    "deceptive_delta": False,
                    "superseded": True,
                    "audit_incomplete": False,
                    "verdict": "CANCEL",
                    "reason": (
                        f"Run headSha {run_head_sha[:7]} no longer matches branch "
                        f"HEAD {current_head_sha[:7]} (superseded push)"
                    ),
                })
                cancel_count += 1
                continue
            # push event with matching head: keep (no PR to compare dormancy).
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "N/A (push event)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": False,
                "verdict": "KEEP",
                "reason": "Push event: head matches branch HEAD",
            })
            keep_count += 1
            continue

        # pull_request / pull_request_target event: PR lookup required.
        if not pr:
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": None,
                "pr_state": "NONE",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": True,
                "verdict": "KEEP",
                "reason": "PR lookup failed; audit incomplete",
            })
            keep_count += 1
            continue

        pr_num = pr.get("number")
        pr_state = pr.get("state", "UNKNOWN")
        pr_updated_dt = parse_iso_datetime(pr.get("updatedAt", ""))
        pr_updated_age_sec = (now - pr_updated_dt).total_seconds() if pr_updated_dt else 0

        commits = pr.get("commits") or []
        head_commit_dt: Optional[datetime.datetime] = None
        if commits:
            head_commit_dt = parse_iso_datetime(commits[-1].get("committedDate", ""))

        # Supersede comparison: run.headSha vs PR.head.sha (the merge ref).
        pr_head_sha = pr.get("head_sha") or pr.get("sha")
        superseded = bool(
            pr_head_sha and run_head_sha and pr_head_sha != run_head_sha
        )

        head_commit_age_sec = (
            (now - head_commit_dt).total_seconds() if head_commit_dt else None
        )

        # Verdict logic — superseded-only mode skips dormancy entirely.
        if superseded:
            verdict = "CANCEL"
            reason = (
                f"Run headSha {run_head_sha[:7]} no longer matches PR "
                f"#{pr_num} current head {pr_head_sha[:7]} (superseded push)"
            )
            cancel_count += 1
            is_deceptive = False
        elif pr_state in ("MERGED", "CLOSED"):
            verdict = "CANCEL"
            reason = f"PR #{pr_num} is {pr_state} (orphaned run)"
            cancel_count += 1
            is_deceptive = False
        elif superseded_only:
            verdict = "KEEP"
            reason = "Superseded-only mode: run is at current PR head; dormancy not applied"
            keep_count += 1
            is_deceptive = False
        elif head_commit_age_sec is None:
            # Commit date lookup failed → never substitute run age.
            verdict = "KEEP"
            reason = (
                f"Head commit date unknown for PR #{pr_num}; "
                "audit incomplete (run age not substituted as head age)"
            )
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "event": event,
                "pr_number": pr_num,
                "pr_state": pr_state,
                "head_commit_age": "unknown",
                "pr_updated_age": format_duration(pr_updated_age_sec) if pr_updated_dt else "unknown",
                "deceptive_delta": False,
                "superseded": False,
                "audit_incomplete": True,
                "verdict": verdict,
                "reason": reason,
            })
            continue
        elif head_commit_age_sec > max_age_seconds:
            verdict = "CANCEL"
            is_deceptive = False
            if pr_updated_age_sec < max_age_seconds:
                is_deceptive = True
                reason = (
                    f"Dormant code: head commit is {format_duration(head_commit_age_sec)} old "
                    f"(exceeds {max_age_hours}h threshold), though PR updatedAt was touched {format_duration(pr_updated_age_sec)} ago"
                )
            else:
                reason = f"Dormant code: head commit is {format_duration(head_commit_age_sec)} old"
            cancel_count += 1
        else:
            verdict = "KEEP"
            reason = (
                f"Active PR: head commit is fresh ({format_duration(head_commit_age_sec)} old)"
            )
            keep_count += 1
            is_deceptive = False

        audited_runs.append({
            "run_id": run_id,
            "name": name,
            "branch": branch,
            "event": event,
            "pr_number": pr_num,
            "pr_state": pr_state,
            "head_commit_age": (
                format_duration(head_commit_age_sec)
                if head_commit_dt and head_commit_age_sec is not None
                else "unknown"
            ),
            "pr_updated_age": format_duration(pr_updated_age_sec) if pr_updated_dt else "unknown",
            "deceptive_delta": is_deceptive,
            "superseded": superseded,
            "audit_incomplete": False,
            "verdict": verdict,
            "reason": reason,
        })

    stats = {
        "total_queued": len(runs),
        "to_cancel": cancel_count,
        "to_keep": keep_count,
    }
    # Final guard: every row whose per-run metadata fetch failed must
    # carry ``audit_incomplete=True`` so the caller cannot mistake a
    # best-effort fallback for a verified verdict.
    for row in audited_runs:
        if row.get("run_id") in metadata_incomplete_ids:
            row["audit_incomplete"] = True
    return audited_runs, stats


def refresh_before_cancel(
    repo: str,
    runs: List[Dict[str, Any]],
    run_cmd: Optional[Callable[..., Tuple[int, str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Re-validate the candidate fingerprint before any mutation.

    Each CANCEL candidate is re-fetched (run status, event, workflow name;
    current PR head SHA). If any field moved on since the audit, the
    candidate is dropped from the final cancellation list.

    Returns the survivors — runs that the audit still believes should be
    cancelled at the moment of mutation.
    """
    _run_cmd = run_cmd if run_cmd is not None else globals()["run_cmd"]
    survivors: List[Dict[str, Any]] = []
    for r in runs:
        if r.get("verdict") != "CANCEL":
            continue
        run_id = r.get("run_id")
        # 1. Re-fetch run metadata (status must still be queued, event must
        #    still match, workflow still not on the protected allowlist).
        rc, stdout, _ = _run_cmd(
            ["gh", "api", f"repos/{repo}/actions/runs/{run_id}"], timeout=15
        )
        if rc != 0 or not stdout.strip():
            continue
        try:
            run_data = json.loads(stdout)
        except Exception:
            continue
        if (run_data.get("status") or "").lower() != "queued":
            continue
        refreshed_event = run_data.get("event") or ""
        if refreshed_event in MERGE_GROUP_EVENTS:
            continue
        if refreshed_event and refreshed_event not in SUPPORTED_EVENTS:
            continue
        workflow_path = run_data.get("path") or ""
        workflow_filename = os.path.basename(workflow_path)
        run_name = run_data.get("name") or ""
        if is_protected_workflow(run_name, workflow_filename):
            continue

        # 2. Re-fetch PR fingerprint (PR head SHA must still differ from
        #    the run's recorded head SHA; otherwise the supersede resolved).
        pr_number = r.get("pr_number")
        if pr_number is None:
            # No PR (push event). Verify branch HEAD still differs.
            branch = r.get("branch") or ""
            rc, bh_stdout, _ = _run_cmd(
                ["gh", "api", f"repos/{repo}/branches/{branch}"], timeout=15
            )
            if rc != 0 or not bh_stdout.strip():
                continue
            try:
                current_head_sha = json.loads(bh_stdout).get("commit", {}).get("sha")
            except Exception:
                continue
            run_head_sha = run_data.get("head_sha") or ""
            if not current_head_sha or current_head_sha == run_head_sha:
                continue
        else:
            rc, pr_stdout, _ = _run_cmd(
                ["gh", "api", f"repos/{repo}/pulls/{pr_number}"], timeout=15
            )
            if rc != 0 or not pr_stdout.strip():
                continue
            try:
                pr_data = json.loads(pr_stdout)
            except Exception:
                continue
            current_pr_head = (pr_data.get("head") or {}).get("sha") or ""
            run_head_sha = run_data.get("head_sha") or ""
            # If the PR head advanced to match the run head, the supersede
            # has resolved and we must not cancel.
            if not current_pr_head or current_pr_head == run_head_sha:
                continue
            current_state = (
                "MERGED" if pr_data.get("merged_at")
                else (pr_data.get("state", "") or "").upper()
            )
            # For MERGED/CLOSED PRs we don't need the head comparison — the
            # PR is an orphan regardless. But the run must still be queued.
            if current_state not in ("MERGED", "CLOSED") and current_pr_head != run_head_sha:
                # PR is still open and not superseded anymore → keep.
                continue

        survivors.append(r)
    return survivors


def execute_cancellations(repo: str, runs_to_cancel: List[Dict[str, Any]]) -> int:
    """Execute cancellation of the targeted workflow runs."""
    cancelled = 0
    total = len(runs_to_cancel)
    print(f"\nExecuting cancellation of {total} workflow runs on {repo}...")
    for idx, r in enumerate(runs_to_cancel, 1):
        run_id = r["run_id"]
        pr_info = f"PR #{r['pr_number']}" if r.get("pr_number") else f"branch {r['branch']}"
        print(f"[{idx}/{total}] Cancelling Run {run_id} ({pr_info} - {r['name']})...", end="", flush=True)
        rc, _, stderr = run_cmd(["gh", "run", "cancel", str(run_id), "--repo", repo])
        if rc == 0:
            cancelled += 1
            print(" ✓ Cancelled")
        else:
            print(f" ✗ Error / already completed: {stderr.strip()}")
    return cancelled


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and trim queued GitHub Actions runs for dormant, superseded, or merged PRs."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"Target GitHub repo (default: {DEFAULT_REPO})")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=f"Max allowed head commit age in hours before considering PR dormant (default: {DEFAULT_MAX_AGE_HOURS})",
    )
    parser.add_argument("--limit", type=int, default=100, help="Max queued runs to evaluate (default: 100)")
    parser.add_argument(
        "--cancel",
        action="store_true",
        help="Actually execute cancellations (default is dry-run mode)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run audit in dry-run mode (default)")
    parser.add_argument(
        "--superseded-only",
        action="store_true",
        help="Cancel only runs whose head SHA is proven obsolete (superseded by a newer push). "
             "Dormancy is ignored even if the head commit is ancient.",
    )
    parser.add_argument("--check-host", action="store_true", help="Run Colima and host disk checks")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output audit results as JSON")

    args = parser.parse_args()

    if args.check_host:
        print("=== Host & Colima Preflight ===")
        host_info = check_host_health()
        for note in host_info.get("notes", []):
            print(f"  • {note}")
        print()

    print(
        f"Auditing queued CI runs for {args.repo} "
        f"(max commit age: {args.max_age_hours}h, mode: "
        f"{'superseded-only' if args.superseded_only else 'standard'})..."
    )
    audited_runs, stats = audit_queue(
        args.repo,
        max_age_hours=args.max_age_hours,
        limit=args.limit,
        superseded_only=args.superseded_only,
    )

    if not audited_runs:
        print("Queue is empty! No queued runs found.")
        return 0

    if args.json_output:
        print(json.dumps({"stats": stats, "runs": audited_runs}, indent=2))
        return 0

    # Print human-readable report
    print("\n" + "=" * 115)
    print(
        f"{'RUN ID':<13} | {'PR #':<6} | {'STATE':<8} | {'COMMIT AGE':<11} | {'UPDATED AGE':<12} | {'ACTION':<7} | {'REASON / WORKFLOW'}"
    )
    print("-" * 115)

    for r in audited_runs:
        pr_str = str(r["pr_number"]) if r["pr_number"] else "-"
        action = r["verdict"]
        marker = "🚨 CANCEL" if action == "CANCEL" else "✓ KEEP"
        if r.get("deceptive_delta"):
            marker = "⚠️ CANCEL*"
        elif r.get("superseded") and action == "CANCEL":
            marker = "🚨 SUPERSEDED"
        elif r.get("audit_incomplete"):
            marker = "⚠ KEEP*"
        print(
            f"{r['run_id']:<13} | {pr_str:<6} | {r['pr_state']:<8} | {r['head_commit_age']:<11} | {r['pr_updated_age']:<12} | {marker:<9} | {r['reason']}"
        )

    print("=" * 115)
    print(
        f"Summary: {stats['total_queued']} total queued runs | "
        f"{stats['to_cancel']} cancel candidates | {stats['to_keep']} active/protected runs to keep"
    )

    superseded_count = sum(1 for r in audited_runs if r.get("superseded"))
    incomplete_count = sum(1 for r in audited_runs if r.get("audit_incomplete"))
    deceptive_count = sum(1 for r in audited_runs if r.get("deceptive_delta"))
    if superseded_count > 0:
        print(
            f"\n* Note: {superseded_count} run(s) were cancelled as superseded "
            "(run headSha no longer matches the PR/branch current head)."
        )
    if incomplete_count > 0:
        print(
            f"\n* Note: {incomplete_count} run(s) were kept with audit_incomplete=True "
            "(PR/commit/run lookup failed; not cancelled to be safe)."
        )
    if deceptive_count > 0:
        print(
            f"\n* Note: {deceptive_count} run(s) had deceptive PR.updatedAt values "
            "(touched recently by bots/comments, but code commit is >"
            f"{args.max_age_hours}h old)."
        )

    # Cancellation execution
    if args.cancel:
        runs_to_cancel = [r for r in audited_runs if r["verdict"] == "CANCEL"]
        if not runs_to_cancel:
            print("\nNo runs eligible for cancellation.")
            return 0
        # Re-validate every candidate's fingerprint immediately before
        # any mutation; state may have moved on since the audit.
        survivors = refresh_before_cancel(args.repo, runs_to_cancel)
        dropped = len(runs_to_cancel) - len(survivors)
        if dropped:
            print(
                f"\nPre-cancel refresh dropped {dropped} run(s) whose state "
                "moved on (no longer queued, head advanced, workflow now protected, etc)."
            )
        if not survivors:
            print("\nNo runs survived pre-cancel refresh; nothing to cancel.")
            return 0
        cancelled = execute_cancellations(args.repo, survivors)
        print(f"\nCompleted: Successfully cancelled {cancelled}/{len(survivors)} runs.")
    else:
        if stats["to_cancel"] > 0:
            print(
                f"\nDry-run mode: {stats['to_cancel']} runs eligible for cancellation. Re-run with --cancel to execute."
            )
        else:
            print("\nAll queued runs belong to active PRs or protected branches. No trimming needed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())