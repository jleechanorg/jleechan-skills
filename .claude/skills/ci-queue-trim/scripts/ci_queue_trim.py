#!/usr/bin/env python3
"""
ci_queue_trim.py — CI Queue Inactivity Triage & Trimming Tool

Audits and trims queued GitHub Actions workflow runs whose head SHA is no
longer current (a newer push advanced the PR/branch head) or whose PR has
already landed (MERGED/CLOSED). Anything the audit cannot verify is kept
with ``audit_incomplete=True``; the tool never substitutes the run's age
for a missing head-commit age.

PR association comes from ``actions/runs/{id}.pull_requests`` (the only
authoritative pointer); branch names that collide between forks must not
cross-bind runs to a PR.

Event semantics:
  * ``pull_request``: superseded when ``run.head_sha`` ≠ ``PR.head.sha``.
    PR.head.sha is the HEAD branch tip; ``merge_commit_sha`` is a separate
    field that must NOT be used for supersede comparison.
  * ``pull_request_target``: base-side semantics. KEEP unless the PR is
    MERGED/CLOSED — base-side runs execute on the BASE SHA, not the PR
    head SHA, so a tip advance on the PR is not a supersede signal.
  * ``push``: superseded when ``run.head_sha`` ≠ branch HEAD. Push events
    are not associated with any PR; do not search for one.
  * ``merge_group``: never cancelled via stale-head; only MERGED/CLOSED.
  * unknown event: ``audit_incomplete=True``; never cancel.

Workflow importance is decided by an explicit allowlist (``PROTECTED_WORKFLOWS``)
with a safe default for ``release.yml`` / ``deploy.yml`` / ``publish.yml``.
The ``@<ref>`` suffix on a workflow path is stripped before comparison.

Usage:
    python3 ci_queue_trim.py [--repo OWNER/REPO] [--max-age-hours HOURS]
                             [--cancel | --superseded-only --cancel]
                             [--check-host]
                             [--allow-workflow PATH]...
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_REPO = "jleechanorg/worldarchitect.ai"
DEFAULT_MAX_AGE_HOURS = 2.0

# Branches whose runs are never cancelled.
PROTECTED_BRANCHES = {"main", "master", "production", "staging", "release", "deploy"}

# Default safe workflow protections. Out of the box the tool must not
# cancel arbitrary deploy / release pipelines. ``@ref`` suffix is stripped
# before matching.
DEFAULT_PROTECTED_WORKFLOWS = frozenset({
    "release.yml", "deploy.yml", "publish.yml", "tag-release.yml",
})
PROTECTED_WORKFLOWS: set = set(DEFAULT_PROTECTED_WORKFLOWS)

# Events split into semantic buckets.
MERGE_GROUP_EVENTS = {"merge_group"}
SUPPORTED_EVENTS = {"pull_request", "pull_request_target", "push"}

COLIMA_SOCKET = os.path.expanduser("~/.colima/_lima/_networks/user-v2/user-v2_fd.sock")
DISK_FLOOR_GB = 7.0

_REF_SUFFIX = re.compile(r"@[^\s/]+$")


def _strip_ref(workflow_path: str) -> str:
    """Strip the ``@<ref>`` suffix GH adds to some workflow paths."""
    return _REF_SUFFIX.sub("", workflow_path or "")


def run_cmd(cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    """Run a shell command with strict anti-freeze environment."""
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["GH_PAGER"] = ""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:
        return 1, "", str(exc)


def _gh_api(path: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """Single-purpose JSON GET that returns None on any non-success shape.

    Returning None on failure lets callers mark ``metadata_complete=False``
    rather than fall through to defaults that pretend verification
    succeeded.
    """
    rc, stdout, _ = run_cmd(["gh", "api", path], timeout=timeout)
    if rc != 0 or not stdout.strip():
        return None
    try:
        data = json.loads(stdout)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def parse_iso_datetime(dt_str: str) -> Optional[datetime.datetime]:
    if not dt_str:
        return None
    try:
        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def format_duration(seconds: float) -> str:
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
    return f"{(hours / 24):.1f}d"


# ---------------------------------------------------------------------------
# Pure classifier
# ---------------------------------------------------------------------------

Classification = namedtuple(
    "Classification",
    ["verdict", "superseded", "audit_incomplete", "reason", "pr_state"],
)


DEFAULT_OPTIONS = {
    "protected_branches": PROTECTED_BRANCHES,
    "protected_workflows": PROTECTED_WORKFLOWS,
    "max_age_hours": DEFAULT_MAX_AGE_HOURS,
    "superseded_only": False,
}


def classify_run(
    *,
    run: Dict[str, Any],
    pr: Optional[Dict[str, Any]],
    branch_head_sha: Optional[str],
    metadata_complete: bool,
    options: Dict[str, Any],
    now: datetime.datetime,
) -> Classification:
    """Decide the verdict for a single run.

    This function is pure: it consumes the pre-fetched facts and never
    reads the network. ``audit_queue`` and ``cancel_with_per_item_refresh``
    both call it — that is what guarantees audit-time and pre-mutation
    verdicts stay aligned.

    ``metadata_complete`` means the run detail was successfully fetched.
    PR / branch-head fetches are tracked separately and degrade
    ``audit_incomplete`` only for the cases that actually need them.
    """
    pb = options.get("protected_branches", PROTECTED_BRANCHES)
    pw = options.get("protected_workflows", PROTECTED_WORKFLOWS)
    max_age_hours = options.get("max_age_hours", DEFAULT_MAX_AGE_HOURS)
    superseded_only = bool(options.get("superseded_only"))

    branch = run.get("head_branch") or ""
    event = run.get("event") or ""
    run_head_sha = run.get("head_sha") or ""
    workflow_path = _strip_ref(run.get("workflow_path") or "")

    # When we cannot verify the run record, NEVER cancel.
    if not metadata_complete:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=True,
            reason="Run detail fetch failed; cannot verify supersede safely",
            pr_state="UNKNOWN",
        )

    # The remaining checks consume the run record directly and do NOT
    # require the PR / branch head to have been fetched.
    if branch in pb:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason=f"Protected branch '{branch}'", pr_state="N/A",
        )

    if workflow_path and workflow_path in pw:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason=f"Protected workflow '{workflow_path}'", pr_state="N/A",
        )

    if event in MERGE_GROUP_EVENTS:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason=f"Event '{event}' skips stale-head comparison", pr_state="N/A",
        )

    if event not in SUPPORTED_EVENTS:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=True,
            reason=f"Unsupported event '{event}'; audit incomplete", pr_state="N/A",
        )

    if event == "push":
        # Push events are NEVER associated with a PR; the PR argument
        # (if any) must be ignored here.
        if not branch_head_sha:
            return Classification(
                verdict="KEEP", superseded=False, audit_incomplete=True,
                reason="Branch HEAD lookup failed; audit incomplete",
                pr_state="N/A",
            )
        if run_head_sha and branch_head_sha and run_head_sha != branch_head_sha:
            return Classification(
                verdict="CANCEL", superseded=True, audit_incomplete=False,
                reason=(
                    f"Run head {run_head_sha[:7]} no longer matches branch "
                    f"HEAD {branch_head_sha[:7]} (superseded push)"
                ),
                pr_state="N/A",
            )
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason="Push event: head matches branch HEAD", pr_state="N/A",
        )

    # pull_request and pull_request_target both require an exact PR
    # association (the run detail's ``pull_requests`` array). No branch
    # guessing.
    if pr is None:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=True,
            reason="No exact PR association on run; audit incomplete",
            pr_state="UNKNOWN",
        )

    pr_head_sha = (pr.get("head") or {}).get("sha") or ""
    pr_state_raw = (pr.get("state") or "").lower()
    pr_merged = bool(pr.get("merged"))
    pr_state = "MERGED" if pr_merged else pr_state_raw.upper() or "UNKNOWN"

    if event == "pull_request_target":
        # Base-side semantics. Only MERGED/CLOSED cancels; do not use
        # PR.head.sha for supersede comparison.
        if pr_state in ("MERGED", "CLOSED"):
            return Classification(
                verdict="CANCEL", superseded=False, audit_incomplete=False,
                reason=f"PR #{pr.get('number')} is {pr_state} (orphaned run)",
                pr_state=pr_state,
            )
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason="pull_request_target uses base-side semantics; not proven",
            pr_state=pr_state,
        )

    # Standard pull_request: superseded iff run_head_sha != PR.head.sha.
    superseded = bool(run_head_sha and pr_head_sha and run_head_sha != pr_head_sha)

    if superseded:
        return Classification(
            verdict="CANCEL", superseded=True, audit_incomplete=False,
            reason=(
                f"Run head {run_head_sha[:7]} no longer matches PR "
                f"#{pr.get('number')} head tip {pr_head_sha[:7]} (superseded)"
            ),
            pr_state=pr_state,
        )

    if pr_state in ("MERGED", "CLOSED"):
        return Classification(
            verdict="CANCEL", superseded=False, audit_incomplete=False,
            reason=f"PR #{pr.get('number')} is {pr_state} (orphaned run)",
            pr_state=pr_state,
        )

    if superseded_only:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=False,
            reason="Superseded-only mode: run is at current PR head",
            pr_state=pr_state,
        )

    head_commit_dt = parse_iso_datetime(pr.get("head_commit_date", ""))
    if head_commit_dt is None:
        return Classification(
            verdict="KEEP", superseded=False, audit_incomplete=True,
            reason=(
                f"Head commit date unknown for PR #{pr.get('number')}; "
                "run age not substituted as head age"
            ),
            pr_state=pr_state,
        )

    head_commit_age_sec = (now - head_commit_dt).total_seconds()
    if head_commit_age_sec > max_age_hours * 3600:
        return Classification(
            verdict="CANCEL", superseded=False, audit_incomplete=False,
            reason=(
                f"Dormant code: head commit is "
                f"{format_duration(head_commit_age_sec)} old"
            ),
            pr_state=pr_state,
        )

    return Classification(
        verdict="KEEP", superseded=False, audit_incomplete=False,
        reason=(
            f"Active PR: head commit is fresh "
            f"({format_duration(head_commit_age_sec)} old)"
        ),
        pr_state=pr_state,
    )


# ---------------------------------------------------------------------------
# Fetches — populate the inputs for ``classify_run``
# ---------------------------------------------------------------------------


def fetch_run_record(repo: str, run_id: int) -> Optional[Dict[str, Any]]:
    """Return the canonical run record (None on error).

    The shape mirrors `gh api /repos/<repo>/actions/runs/<id>` for the
    fields the classifier actually reads; callers must treat ``None`` as
    ``metadata_complete=False``.
    """
    data = _gh_api(f"repos/{repo}/actions/runs/{run_id}")
    if not data:
        return None
    return {
        "databaseId": data.get("id") or data.get("databaseId"),
        "name": data.get("name") or "",
        "head_branch": data.get("head_branch") or "",
        "head_sha": data.get("head_sha") or "",
        "event": data.get("event") or "",
        "workflow_path": data.get("path") or "",
        "status": data.get("status") or "",
        "pull_requests": [
            {"number": p.get("number")}
            for p in (data.get("pull_requests") or [])
            if p.get("number")
        ],
    }


def fetch_pr_record(repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
    """Return the canonical PR record (None on error)."""
    data = _gh_api(f"repos/{repo}/pulls/{pr_number}")
    if not data:
        return None
    head = data.get("head") or {}
    return {
        "number": data.get("number"),
        "state": (data.get("state") or "").lower(),
        "merged": bool(data.get("merged")),
        "merge_commit_sha": data.get("merge_commit_sha"),
        "head": {
            "sha": head.get("sha") or "",
            "ref": head.get("ref") or "",
            "repo": {"full_name": ((head.get("repo") or {}).get("full_name"))},
        },
        "head_commit_date": ((data.get("head") or {}).get("repo") or {}).get("pushed_at")
            or data.get("updated_at"),
    }


def fetch_branch_head(repo: str, branch: str) -> Optional[str]:
    """Return the branch HEAD SHA, or None on error."""
    data = _gh_api(f"repos/{repo}/branches/{branch}")
    if not data:
        return None
    return (data.get("commit") or {}).get("sha")


def get_queued_runs(repo: str, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
    """Return the list of queued runs or ``None`` on fetch failure.

    A failed fetch MUST NOT become a healthy empty success — callers must
    surface ``None`` to the operator.
    """
    rc, stdout, _ = run_cmd(
        [
            "gh", "run", "list", "--repo", repo, "--status", "queued",
            "--limit", str(limit),
            "--json", "databaseId,name,headBranch,headSha,event,status,createdAt,url",
        ],
        timeout=60,
    )
    if rc != 0 or not stdout.strip():
        return None
    try:
        parsed = json.loads(stdout)
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _build_row(run: Dict[str, Any], cls: Classification) -> Dict[str, Any]:
    head_commit_dt = parse_iso_datetime((run.get("pr") or {}).get("head_commit_date", ""))
    pr_updated_dt = parse_iso_datetime((run.get("pr") or {}).get("updated_at", ""))
    return {
        "run_id": run.get("databaseId"),
        "name": run.get("name") or "Unknown",
        "branch": run.get("head_branch") or "",
        "event": run.get("event") or "",
        "pr_number": (run.get("pr") or {}).get("number"),
        "pr_state": cls.pr_state,
        "head_commit_age": (
            format_duration((FIXED_NOW_FALLBACK - head_commit_dt).total_seconds())
            if head_commit_dt and run.get("_now") else "unknown"
        ),
        "pr_updated_age": (
            format_duration((run["_now"] - pr_updated_dt).total_seconds())
            if pr_updated_dt and run.get("_now") else "unknown"
        ),
        "deceptive_delta": False,
        "superseded": cls.superseded,
        "audit_incomplete": cls.audit_incomplete,
        "verdict": cls.verdict,
        "reason": cls.reason,
    }


# A single timestamp the row builder uses; tests patch datetime via ``_patch_now``.
FIXED_NOW_FALLBACK = datetime.datetime(2026, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _collect_inputs(repo: str, run_record: Dict[str, Any]) -> Tuple[
    Optional[Dict[str, Any]], Optional[str], bool
]:
    """Fetch (pr_record, branch_head_sha) for the given run, plus a flag
    saying whether all required fetches succeeded.

    For ``push`` events we never look up a PR — push runs have no PR
    association. For other events, the PR is fetched ONLY for the run's
    own ``pull_requests`` array (no branch-name guessing).
    """
    event = run_record.get("event") or ""
    pr_record: Optional[Dict[str, Any]] = None
    branch_head: Optional[str] = None

    ok_pr = True
    ok_branch = True

    if event == "push":
        branch = run_record.get("head_branch") or ""
        branch_head = fetch_branch_head(repo, branch)
        ok_branch = branch_head is not None
    elif event in SUPPORTED_EVENTS:
        pr_refs = run_record.get("pull_requests") or []
        if not pr_refs:
            # Run detail listed zero associated PRs — do NOT search by
            # branch name; the audit stays UNKNOWN.
            return None, None, False
        # Use the first associated PR. GH at most associates one PR per
        # run for these events; if more exist we conservatively take the
        # first and require an exact SHA bind in classify_run.
        pr_number = pr_refs[0]["number"]
        pr_record = fetch_pr_record(repo, pr_number)
        ok_pr = pr_record is not None
        # For pull_request_target the PR head SHA is NOT a supersede ref;
        # we still need the PR for state + number, but we do not fetch a
        # branch head for these events.
        if event == "pull_request":
            # No branch head needed; PR head.sha is the supersede ref.
            pass
    elif event in MERGE_GROUP_EVENTS:
        pass  # neither PR nor branch head is required
    else:
        return None, None, False

    return pr_record, branch_head, ok_pr and ok_branch


def audit_queue(
    repo: str,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    limit: int = 100,
    superseded_only: bool = False,
    protected_workflows: Optional[set] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Audit the queued runs of ``repo``. Returns ``(rows, stats)``."""
    runs = get_queued_runs(repo, limit=limit)
    if runs is None:
        return [], {
            "total_queued": 0,
            "to_cancel": 0,
            "to_keep": 0,
            "queue_fetch_failed": True,
        }

    now = datetime.datetime.now(datetime.timezone.utc)
    options = {
        "protected_branches": PROTECTED_BRANCHES,
        "protected_workflows": (
            set(protected_workflows) if protected_workflows is not None
            else PROTECTED_WORKFLOWS
        ),
        "max_age_hours": max_age_hours,
        "superseded_only": superseded_only,
    }

    audited: List[Dict[str, Any]] = []
    cancel_count = 0
    keep_count = 0

    for queued_row in runs:
        run_id = queued_row.get("databaseId")
        run_detail = fetch_run_record(repo, run_id)
        metadata_complete = run_detail is not None
        if run_detail is None:
            run = {
                "databaseId": run_id,
                "name": queued_row.get("name") or "Unknown",
                "head_branch": queued_row.get("headBranch") or "",
                "head_sha": queued_row.get("headSha") or "",
                "event": queued_row.get("event") or "",
                "workflow_path": "",
                "status": queued_row.get("status") or "",
                "pull_requests": [],
            }
            pr, branch_head = None, None
        else:
            run = run_detail
            pr, branch_head, _ = _collect_inputs(repo, run)

        cls = classify_run(
            run=run,
            pr=pr,
            branch_head_sha=branch_head,
            metadata_complete=metadata_complete,
            options=options,
            now=now,
        )

        row = {
            "run_id": run_id,
            "name": run.get("name") or "",
            "branch": run.get("head_branch") or "",
            "event": run.get("event") or "",
            "pr_number": (pr or {}).get("number") if pr else None,
            "pr_state": cls.pr_state,
            "head_commit_age": (
                format_duration((now - parse_iso_datetime(pr.get("head_commit_date", ""))).total_seconds())
                if pr and pr.get("head_commit_date") and parse_iso_datetime(pr.get("head_commit_date", ""))
                else "unknown"
            ),
            "pr_updated_age": (
                format_duration((now - parse_iso_datetime(pr.get("updated_at", ""))).total_seconds())
                if pr and pr.get("updated_at") and parse_iso_datetime(pr.get("updated_at", ""))
                else "unknown"
            ),
            "deceptive_delta": False,
            "superseded": cls.superseded,
            "audit_incomplete": cls.audit_incomplete,
            "verdict": cls.verdict,
            "reason": cls.reason,
        }
        audited.append(row)
        if cls.verdict == "CANCEL":
            cancel_count += 1
        else:
            keep_count += 1

    return audited, {
        "total_queued": len(runs),
        "to_cancel": cancel_count,
        "to_keep": keep_count,
    }


# ---------------------------------------------------------------------------
# Per-item pre-cancel refresh
# ---------------------------------------------------------------------------


def cancel_with_per_item_refresh(
    repo: str,
    runs: List[Dict[str, Any]],
    *,
    superseded_only: bool = False,
    protected_workflows: Optional[set] = None,
    run_cmd_fn: Optional[Callable[..., Tuple[int, str, str]]] = None,
    now: Optional[datetime.datetime] = None,
) -> List[int]:
    """Cancel each candidate only if a fresh re-fetch + re-classify still
    says CANCEL. Returns the list of run IDs that were cancelled."""
    _run_cmd = run_cmd_fn or run_cmd
    options = {
        "protected_branches": PROTECTED_BRANCHES,
        "protected_workflows": (
            set(protected_workflows) if protected_workflows is not None
            else PROTECTED_WORKFLOWS
        ),
        "max_age_hours": DEFAULT_MAX_AGE_HOURS,
        "superseded_only": superseded_only,
    }
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cancelled: List[int] = []

    for row in runs:
        if row.get("verdict") != "CANCEL":
            continue
        run_id = row.get("run_id")
        # 1. Re-fetch run
        data = _gh_api(f"repos/{repo}/actions/runs/{run_id}")
        if data is None:
            continue
        run = {
            "databaseId": data.get("id") or run_id,
            "name": data.get("name") or "",
            "head_branch": data.get("head_branch") or "",
            "head_sha": data.get("head_sha") or "",
            "event": data.get("event") or "",
            "workflow_path": data.get("path") or "",
            "status": data.get("status") or "",
            "pull_requests": [
                {"number": p.get("number")}
                for p in (data.get("pull_requests") or [])
                if p.get("number")
            ],
        }
        if (run.get("status") or "").lower() != "queued":
            continue
        # 2. Re-fetch exact inputs
        pr, branch_head, fetches_ok = _collect_inputs(repo, run)
        cls = classify_run(
            run=run, pr=pr, branch_head_sha=branch_head,
            metadata_complete=True,
            options=options, now=now,
        )
        if cls.verdict != "CANCEL":
            continue
        # 3. Cancel iff the run's event still requires it AND the exact
        #    PR is no longer freshly matching.
        if cls.pr_state in ("MERGED", "CLOSED"):
            rc, _, stderr = _run_cmd(
                ["gh", "run", "cancel", str(run_id), "--repo", repo], timeout=30
            )
            if rc == 0:
                cancelled.append(run_id)
            else:
                print(f"Cancel {run_id} failed: {stderr.strip()}", file=sys.stderr)
            continue
        # Supersede or dormancy: only cancel if we still see a difference.
        if run["event"] == "push":
            if run["head_sha"] and branch_head and run["head_sha"] != branch_head:
                rc, _, stderr = _run_cmd(
                    ["gh", "run", "cancel", str(run_id), "--repo", repo], timeout=30
                )
                if rc == 0:
                    cancelled.append(run_id)
                else:
                    print(f"Cancel {run_id} failed: {stderr.strip()}", file=sys.stderr)
            continue
        # pull_request: only cancel if PR head tip still differs from run.
        if pr is None:
            continue
        pr_head_sha = (pr.get("head") or {}).get("sha") or ""
        if run["head_sha"] and pr_head_sha and run["head_sha"] != pr_head_sha:
            rc, _, stderr = _run_cmd(
                ["gh", "run", "cancel", str(run_id), "--repo", repo], timeout=30
            )
            if rc == 0:
                cancelled.append(run_id)
            else:
                print(f"Cancel {run_id} failed: {stderr.strip()}", file=sys.stderr)
    return cancelled


# ---------------------------------------------------------------------------
# Host diagnostics + main
# ---------------------------------------------------------------------------


def check_host_health() -> Dict[str, Any]:
    report: Dict[str, Any] = {"colima_ok": True, "disk_ok": True, "notes": []}
    data_path = "/System/Volumes/Data" if os.path.exists("/System/Volumes/Data") else "/"
    try:
        _, _, free_bytes = shutil.disk_usage(data_path)
        free_gb = free_bytes / (1024 ** 3)
        report["free_disk_gb"] = round(free_gb, 2)
        if free_gb < DISK_FLOOR_GB:
            report["disk_ok"] = False
            report["notes"].append(
                f"Disk space critical: {free_gb:.2f} GB free (floor: {DISK_FLOOR_GB} GB)"
            )
        else:
            report["notes"].append(f"Disk space OK: {free_gb:.2f} GB free")
    except Exception as exc:
        report["notes"].append(f"Disk check failed: {exc}")

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
            report["notes"].append(f"Multiple limactl usernet processes: {usernet_pids}")
        elif len(usernet_pids) == 0 and sock_exists:
            report["colima_ok"] = False
            report["notes"].append(f"Dead socket file: {COLIMA_SOCKET}")
        elif len(usernet_pids) == 1 and sock_exists:
            report["notes"].append("Colima usernet: healthy (1 process)")
        else:
            report["notes"].append("Colima usernet not currently running")
    return report


def _print_report(audited: List[Dict[str, Any]], stats: Dict[str, Any],
                  max_age_hours: float) -> None:
    if not audited:
        if stats.get("queue_fetch_failed"):
            print("Queue fetch FAILED — audit cannot proceed safely.")
        else:
            print("Queue is empty! No queued runs found.")
        return
    print("\n" + "=" * 115)
    print(
        f"{'RUN ID':<13} | {'PR #':<6} | {'STATE':<8} | {'COMMIT AGE':<11} | "
        f"{'UPDATED AGE':<12} | {'ACTION':<7} | {'REASON / WORKFLOW'}"
    )
    print("-" * 115)
    for r in audited:
        pr_str = str(r["pr_number"]) if r["pr_number"] else "-"
        if r["verdict"] == "CANCEL":
            marker = "🚨 SUPERSEDED" if r.get("superseded") else "🚨 CANCEL"
        elif r.get("audit_incomplete"):
            marker = "⚠ KEEP*"
        else:
            marker = "✓ KEEP"
        print(
            f"{r['run_id']:<13} | {pr_str:<6} | {r['pr_state']:<8} | "
            f"{r['head_commit_age']:<11} | {r['pr_updated_age']:<12} | "
            f"{marker:<9} | {r['reason']}"
        )
    print("=" * 115)
    print(
        f"Summary: {stats['total_queued']} total queued runs | "
        f"{stats['to_cancel']} cancel candidates | "
        f"{stats['to_keep']} active/protected runs to keep"
    )
    superseded_count = sum(1 for r in audited if r.get("superseded"))
    incomplete_count = sum(1 for r in audited if r.get("audit_incomplete"))
    if superseded_count:
        print(f"\n* {superseded_count} run(s) cancelled as superseded "
              "(run headSha no longer matches PR/branch current head).")
    if incomplete_count:
        print(f"\n* {incomplete_count} run(s) kept with audit_incomplete=True "
              "(PR/commit/run lookup failed).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and trim queued GitHub Actions runs for superseded or merged PRs."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--superseded-only", action="store_true",
        help="Cancel only runs whose head SHA is proven obsolete.",
    )
    parser.add_argument("--check-host", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--allow-workflow", action="append", default=[],
        metavar="PATH",
        help="Extend the protected-workflows allowlist. May be repeated.",
    )
    args = parser.parse_args()

    if args.check_host:
        print("=== Host & Colima Preflight ===")
        for note in check_host_health().get("notes", []):
            print(f"  • {note}")
        print()

    protected_workflows = set(DEFAULT_PROTECTED_WORKFLOWS)
    for path in args.allow_workflow:
        protected_workflows.add(_strip_ref(path))

    print(
        f"Auditing queued CI runs for {args.repo} "
        f"(mode: {'superseded-only' if args.superseded_only else 'standard'})..."
    )
    audited, stats = audit_queue(
        args.repo,
        max_age_hours=args.max_age_hours,
        limit=args.limit,
        superseded_only=args.superseded_only,
        protected_workflows=protected_workflows,
    )
    _print_report(audited, stats, args.max_age_hours)

    if args.json_output:
        print(json.dumps({"stats": stats, "runs": audited}, indent=2))

    if args.cancel and not stats.get("queue_fetch_failed"):
        runs_to_cancel = [r for r in audited if r["verdict"] == "CANCEL"]
        if not runs_to_cancel:
            print("\nNo runs eligible for cancellation.")
            return 0
        cancelled = cancel_with_per_item_refresh(
            args.repo, runs_to_cancel,
            superseded_only=args.superseded_only,
            protected_workflows=protected_workflows,
        )
        print(f"\nCompleted: Successfully cancelled {len(cancelled)}/{len(runs_to_cancel)} runs.")
    elif stats.get("to_cancel", 0) > 0 and not args.cancel:
        print(
            f"\nDry-run mode: {stats['to_cancel']} runs eligible for cancellation. "
            "Re-run with --cancel to execute."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())