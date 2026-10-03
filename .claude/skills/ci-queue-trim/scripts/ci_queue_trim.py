#!/usr/bin/env python3
"""
ci_queue_trim.py — CI Queue Inactivity Triage & Trimming Tool

Audits and trims queued GitHub Actions workflow runs associated with dormant or merged PRs.
Solves the deceptive PR.updatedAt pitfall by verifying head commit committedDate.

Usage:
    python3 ci_queue_trim.py [--repo OWNER/REPO] [--max-age-hours HOURS] [--cancel] [--check-host]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_REPO = "jleechanorg/worldarchitect.ai"
DEFAULT_MAX_AGE_HOURS = 2.0
PROTECTED_BRANCHES = {"main", "master", "production", "staging", "release"}
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
    """Fetch queued workflow runs from GitHub."""
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--status", "queued",
        "--limit", str(limit),
        "--json", "databaseId,name,headBranch,headSha,createdAt,url",
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
                branch_to_pr[branch] = {
                    "number": p.get("number"),
                    "headRefName": branch,
                    "state": state,
                    "updatedAt": p.get("updated_at"),
                    "sha": p.get("head", {}).get("sha"),
                }
    except Exception as exc:
        print(f"Warning: Failed to parse PR list JSON: {exc}", file=sys.stderr)

    return branch_to_pr


_COMMIT_DATE_CACHE: Dict[str, str] = {}


def fetch_single_pr(repo: str, branch: str) -> Optional[Dict[str, Any]]:
    """Fetch PR details for a specific branch using REST API to avoid GraphQL limits."""
    owner = repo.split("/")[0] if "/" in repo else repo
    cmd = [
        "gh", "api", f"repos/{repo}/pulls?state=all&head={owner}:{branch}"
    ]
    rc, stdout, _ = run_cmd(cmd, timeout=15)
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

                return {
                    "number": pr.get("number"),
                    "headRefName": branch,
                    "state": pr.get("state", "").upper(),
                    "updatedAt": pr.get("updated_at"),
                    "commits": [{"committedDate": commit_date}] if commit_date else [],
                }
        except Exception:
            return None
    return None


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
        # Check socket
        sock_exists = os.path.exists(COLIMA_SOCKET)
        report["colima_sock_exists"] = sock_exists

        # Check limactl usernet processes
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
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Audit queued runs and categorize them into KEEP vs CANCEL."""
    runs = get_queued_runs(repo, limit=limit)
    if not runs:
        return [], {"total_queued": 0, "to_cancel": 0, "to_keep": 0}

    branch_to_pr = get_repo_prs(repo, limit=limit)
    now = datetime.datetime.now(datetime.timezone.utc)
    max_age_seconds = max_age_hours * 3600

    audited_runs = []
    cancel_count = 0
    keep_count = 0

    for r in runs:
        run_id = r.get("databaseId")
        name = r.get("name", "Unknown")
        branch = r.get("headBranch") or ""
        run_created_dt = parse_iso_datetime(r.get("createdAt", ""))
        run_age_sec = (now - run_created_dt).total_seconds() if run_created_dt else 0

        # Protected branch check
        if branch in PROTECTED_BRANCHES:
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "pr_number": None,
                "pr_state": "N/A (protected)",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "verdict": "KEEP",
                "reason": f"Protected branch '{branch}'",
            })
            keep_count += 1
            continue

        # Look up PR
        pr = branch_to_pr.get(branch)
        if not pr and branch:
            pr = fetch_single_pr(repo, branch)
            if pr:
                branch_to_pr[branch] = pr
        elif pr and "commits" not in pr and pr.get("state") == "OPEN":
            sha = pr.get("sha")
            commit_date = None
            if sha:
                if sha in _COMMIT_DATE_CACHE:
                    commit_date = _COMMIT_DATE_CACHE[sha]
                else:
                    c_rc, c_out, _ = run_cmd(["gh", "api", f"repos/{repo}/commits/{sha}"], timeout=15)
                    if c_rc == 0 and c_out.strip():
                        try:
                            c_data = json.loads(c_out)
                            commit_date = c_data.get("commit", {}).get("committer", {}).get("date")
                            if commit_date:
                                _COMMIT_DATE_CACHE[sha] = commit_date
                        except Exception:
                            pass
            pr["commits"] = [{"committedDate": commit_date}] if commit_date else []
            branch_to_pr[branch] = pr

        if not pr:
            # Unattached branch (no PR)
            verdict = "KEEP"
            reason = "No PR associated (manual/direct branch)"
            audited_runs.append({
                "run_id": run_id,
                "name": name,
                "branch": branch,
                "pr_number": None,
                "pr_state": "NONE",
                "head_commit_age": "N/A",
                "pr_updated_age": "N/A",
                "deceptive_delta": False,
                "verdict": verdict,
                "reason": reason,
            })
            keep_count += 1
            continue

        pr_num = pr.get("number")
        pr_state = pr.get("state", "UNKNOWN")
        pr_updated_dt = parse_iso_datetime(pr.get("updatedAt", ""))
        pr_updated_age_sec = (now - pr_updated_dt).total_seconds() if pr_updated_dt else 0

        # Extract head commit date
        commits = pr.get("commits") or []
        head_commit_dt = None
        if commits:
            last_commit = commits[-1]
            head_commit_dt = parse_iso_datetime(last_commit.get("committedDate", ""))

        head_commit_age_sec = (now - head_commit_dt).total_seconds() if head_commit_dt else run_age_sec

        # Evaluate verdict
        is_deceptive = False
        if pr_state in ("MERGED", "CLOSED"):
            verdict = "CANCEL"
            reason = f"PR #{pr_num} is {pr_state} (orphaned run)"
            cancel_count += 1
        elif head_commit_age_sec > max_age_seconds:
            verdict = "CANCEL"
            # Check deceptive delta: updatedAt is recent (< 2h) but code commit is stale (> 2h)
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
            reason = f"Active PR: head commit is fresh ({format_duration(head_commit_age_sec)} old)"
            keep_count += 1

        audited_runs.append({
            "run_id": run_id,
            "name": name,
            "branch": branch,
            "pr_number": pr_num,
            "pr_state": pr_state,
            "head_commit_age": format_duration(head_commit_age_sec) if head_commit_dt else "unknown",
            "pr_updated_age": format_duration(pr_updated_age_sec) if pr_updated_dt else "unknown",
            "deceptive_delta": is_deceptive,
            "verdict": verdict,
            "reason": reason,
        })

    stats = {
        "total_queued": len(runs),
        "to_cancel": cancel_count,
        "to_keep": keep_count,
    }
    return audited_runs, stats


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
        description="Audit and trim queued GitHub Actions runs for dormant or merged PRs."
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
    parser.add_argument("--check-host", action="store_true", help="Run Colima and host disk checks")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output audit results as JSON")

    args = parser.parse_args()

    # Host diagnostics if requested
    if args.check_host:
        print("=== Host & Colima Preflight ===")
        host_info = check_host_health()
        for note in host_info.get("notes", []):
            print(f"  • {note}")
        print()

    print(f"Auditing queued CI runs for {args.repo} (max commit age: {args.max_age_hours}h)...")
    audited_runs, stats = audit_queue(args.repo, max_age_hours=args.max_age_hours, limit=args.limit)

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
        print(
            f"{r['run_id']:<13} | {pr_str:<6} | {r['pr_state']:<8} | {r['head_commit_age']:<11} | {r['pr_updated_age']:<12} | {marker:<9} | {r['reason']}"
        )

    print("=" * 115)
    print(
        f"Summary: {stats['total_queued']} total queued runs | "
        f"{stats['to_cancel']} cancel candidates | {stats['to_keep']} active/protected runs to keep"
    )

    deceptive_count = sum(1 for r in audited_runs if r.get("deceptive_delta"))
    if deceptive_count > 0:
        print(
            f"\n* Note: {deceptive_count} run(s) had deceptive PR.updatedAt values (touched recently by bots/comments, but code commit is >{args.max_age_hours}h old)."
        )

    # Cancellation execution
    if args.cancel:
        runs_to_cancel = [r for r in audited_runs if r["verdict"] == "CANCEL"]
        if not runs_to_cancel:
            print("\nNo runs eligible for cancellation.")
            return 0
        cancelled = execute_cancellations(args.repo, runs_to_cancel)
        print(f"\nCompleted: Successfully cancelled {cancelled}/{len(runs_to_cancel)} runs.")
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
