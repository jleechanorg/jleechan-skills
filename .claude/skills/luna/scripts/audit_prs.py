#!/usr/bin/env python3
"""
/luna automated PR audit and tri-engine triage tool.
Scans open non-draft PRs unmodified for >= N hours, classifies CI/merge status,
and dispatches pil (DeepSeek V4 Flash), pig (GLM 5.3), or codexl (Codex Luna).
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ADVISORY_CHECKS = {"CodeRabbit", "Cursor Bugbot", "Green Gate"}
FAILED_CHECK_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "STARTUP_FAILURE",
    "STALE",
    "TIMED_OUT",
}


SCRATCH_RESOLVER = (
    Path(__file__).resolve().parents[2]
    / "scratch-space"
    / "scripts"
    / "scratch-dir.sh"
)


def _scratch_root() -> str:
    try:
        result = subprocess.run(
            [str(SCRATCH_RESOLVER)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as error:
        raise RuntimeError(f"canonical Scratch resolver unavailable: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("canonical Scratch resolver timed out") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"canonical Scratch resolver failed: {detail}")
    candidate = result.stdout.strip()
    if not candidate:
        raise RuntimeError("canonical Scratch resolver returned no path")
    path = Path(candidate)
    if not path.is_absolute():
        raise RuntimeError("canonical Scratch resolver returned a relative path")
    return str(path)


def get_luna_review_dir() -> str:
    review_dir = f"{_scratch_root()}/worldarchitect.ai/luna-reviews"
    os.makedirs(review_dir, exist_ok=True)
    return review_dir


def run_cmd(cmd, check=True, timeout=60):
    env = os.environ.copy()
    env.update({
        "GH_PROMPT_DISABLED": "1",
        "GH_NO_UPDATE_NOTIFIER": "1",
        "GH_PAGER": "",
    })
    try:
        res = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
            timeout=timeout,
            env=env,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_stale_prs(repo="jleechanorg/worldarchitect.ai", hours=8, limit=100):
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=hours)

    raw = run_cmd([
        "gh", "pr", "list", "--repo", repo,
        "--state", "open", "--limit", str(limit),
        "--json", "number,title,isDraft,updatedAt,headRefName,url,author,headRefOid"
    ])
    if not raw:
        return []

    try:
        prs = json.loads(raw)
    except Exception:
        return []

    candidates = []
    for pr in prs:
        if pr.get("isDraft", False):
            continue
        updated_str = pr.get("updatedAt", "")
        if not updated_str:
            continue
        updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        if updated < cutoff:
            age_hours = (now - updated).total_seconds() / 3600.0
            candidates.append({
                "number": pr["number"],
                "age_hours": age_hours,
                "title": pr["title"],
                "url": pr["url"],
                "branch": pr["headRefName"],
                "headRefOid": pr.get("headRefOid", ""),
                "author": pr.get("author", {}).get("login", "")
            })
    return candidates


def inspect_pr_status(pr_item, repo="jleechanorg/worldarchitect.ai"):
    num = pr_item["number"]
    data = {}
    for attempt in range(2):
        raw = run_cmd([
            "gh", "pr", "view", str(num), "--repo", repo,
            "--json", "mergeable,mergeStateStatus,statusCheckRollup,files"
        ], check=False)
        if raw:
            try:
                data = json.loads(raw)
                if data.get("mergeable") != "UNKNOWN":
                    break
            except Exception:
                pass
        if attempt == 0:
            time.sleep(1.0)

    checks = data.get("statusCheckRollup", []) or []
    failed_checks = []
    pending_checks = []
    required_check_count = 0
    for c in checks:
        name = c.get("name") or c.get("context") or "check"
        if name in ADVISORY_CHECKS:
            continue
        required_check_count += 1
        typename = c.get("__typename")
        state = (c.get("state") or "").upper()
        status = (c.get("status") or "").upper()
        conclusion = (c.get("conclusion") or "").upper()

        if typename == "StatusContext":
            if state in {"ERROR", "FAILURE"}:
                failed_checks.append(name)
            elif state == "SUCCESS":
                continue
            else:
                pending_checks.append(name)
        elif typename == "CheckRun":
            if status == "COMPLETED" and conclusion in ["SUCCESS", "NEUTRAL", "SKIPPED"]:
                continue
            if status == "COMPLETED" and conclusion in FAILED_CHECK_CONCLUSIONS:
                failed_checks.append(name)
            else:
                pending_checks.append(name)
        else:
            # GitHub can add union variants, and malformed fixtures can omit the
            # discriminator. Unknown evidence is incomplete, never green.
            pending_checks.append(name)

    if not required_check_count:
        pending_checks.append("no required checks reported")

    mergeable = data.get("mergeable", "UNKNOWN")
    merge_state = data.get("mergeStateStatus", "UNKNOWN")
    files = [f["path"] for f in data.get("files", [])]

    if mergeable == "CONFLICTING" or merge_state == "DIRTY":
        category = "CONFLICTING"
    elif failed_checks:
        category = "CI_FAILED"
    elif pending_checks:
        category = "PENDING_OR_BLOCKED"
    elif mergeable == "MERGEABLE" and merge_state == "CLEAN":
        category = "CLEAN_GREEN"
    else:
        category = "PENDING_OR_BLOCKED"

    pr_item.update({
        "mergeable": mergeable,
        "mergeStateStatus": merge_state,
        "failed_checks": failed_checks,
        "pending_checks": pending_checks,
        "files_count": len(files),
        "category": category,
    })
    return pr_item


def dispatch_review(pr_num, repo="jleechanorg/worldarchitect.ai"):
    report_dir = get_luna_review_dir()
    diff = run_cmd(["gh", "pr", "diff", str(pr_num), "--repo", repo], check=False, timeout=90)
    if not diff:
        print(f"Error: could not fetch diff for PR #{pr_num}")
        return

    report_file = os.path.join(report_dir, f"PR_{pr_num}_review.md")

    print(f"Running /luna fast diff triage via pil on PR #{pr_num}...")
    prompt = (
        "You are an expert pair-programming reviewer. Review this PR diff.\n"
        "Check: 1. Obvious bugs, unhandled exceptions, and regressions 2. Invariants: no hasattr/getattr on GameState, non-zero clamp rules, ZFC ban on regex parsing 3. Missing test coverage.\n"
        "Provide a concise, actionable verdict with specific code pointers."
    )

    proc = subprocess.Popen(
        ["pil", "-nc", "-p", prompt],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input=diff)
    review_content = stdout.strip()

    with open(report_file, "w") as f:
        f.write(f"# /luna Triage Review: PR #{pr_num}\n\n")
        f.write(f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n")
        f.write(review_content + "\n")

    print(f"\n{review_content}\n")
    print(f"Review report saved to: {report_file}")


def review_single_pr(item, repo="jleechanorg/worldarchitect.ai", report_dir=None):
    report_dir = report_dir or get_luna_review_dir()
    pr_num = item["number"]
    diff = run_cmd(["gh", "pr", "diff", str(pr_num), "--repo", repo], check=False, timeout=60)
    if not diff:
        item["review_summary"] = "• Core Purpose: Diff unavailable or branch deleted\n• Risks: None\n• Next Action: Check PR status on GitHub"
        return item

    prompt = (
        f"You are reviewing PR #{pr_num}: {item['title']}.\n"
        "Analyze the diff and state:\n"
        "1. Core Purpose (1 sentence)\n"
        "2. Key Invariants / Risks (GameState, clamp rules, test coverage)\n"
        "3. Exact Next Action Needed (rebase, fix test, update evidence, or merge)\n"
        "Keep the entire output under 6 lines."
    )
    try:
        proc = subprocess.Popen(
            ["pil", "-nc", "-p", prompt],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate(input=diff, timeout=90)
        review_text = stdout.strip()
    except Exception as e:
        review_text = f"• Review timed out or errored: {e}"

    report_file = os.path.join(report_dir, f"PR_{pr_num}_review.md")
    with open(report_file, "w") as f:
        f.write(f"# Review for PR #{pr_num}: {item['title']}\n\n")
        f.write(f"- Status: {item['category']}\n")
        f.write(f"- Branch: {item['branch']}\n")
        f.write(f"- Age: {item['age_hours']:.1f} hours\n")
        f.write(f"- URL: {item['url']}\n\n")
        f.write(review_text + "\n")

    item["review_report_file"] = report_file
    item["review_summary"] = review_text
    return item


def main():
    parser = argparse.ArgumentParser(description="/luna stale PR audit & triage tool")
    parser.add_argument("--repo", default="jleechanorg/worldarchitect.ai", help="Target GitHub repo")
    parser.add_argument("--hours", type=float, default=8.0, help="Hours unmodified threshold (default: 8)")
    parser.add_argument("--limit", type=int, default=100, help="Max open PRs to query")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--review", type=int, help="Run instant triage review on a specific PR")
    parser.add_argument("--dispatch", type=int, help="Alias for --review")
    parser.add_argument("--parallel", action="store_true", help="Run parallel triage reviews across all stale PRs")
    args = parser.parse_args()

    target_review = args.review or args.dispatch
    if target_review:
        dispatch_review(target_review, repo=args.repo)
        return

    candidates = get_stale_prs(repo=args.repo, hours=args.hours, limit=args.limit)
    if not candidates:
        print(f"No non-draft PRs found unmodified for >={args.hours}h in {args.repo}.")
        return

    print(f"Discovered {len(candidates)} non-draft PRs unmodified for >={args.hours}h. Evaluating status...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        audited = list(pool.map(lambda c: inspect_pr_status(c, repo=args.repo), candidates))

    audited.sort(key=lambda x: x["number"], reverse=True)

    if args.parallel:
        report_dir = get_luna_review_dir()
        print(f"\nLaunching parallel tri-engine reviews across {len(audited)} PRs...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            audited = list(pool.map(lambda p: review_single_pr(
                p, repo=args.repo, report_dir=report_dir
            ), audited))

        master_report = os.path.join(report_dir, "MASTER_TRIAGE_REPORT.md")
        with open(master_report, "w") as f:
            f.write(f"# /luna Master Stale PR Triage Report\n\n")
            f.write(f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
            f.write(f"Audited: {len(audited)} PRs unmodified for >={args.hours} hours\n\n")

            for cat, label in [("CI_FAILED", "🚨 CI FAILED"), ("CONFLICTING", "⚠️  CONFLICTING / DIRTY"), ("CLEAN_GREEN", "✅ CLEAN & ALL GREEN")]:
                group = [p for p in audited if p["category"] == cat]
                f.write(f"## {label} ({len(group)})\n\n")
                for p in group:
                    f.write(f"### PR #{p['number']}: {p['title']}\n")
                    f.write(f"- **URL**: {p['url']}\n")
                    f.write(f"- **Branch**: `{p['branch']}` | **Age**: {p['age_hours']:.1f}h\n")
                    if p.get("failed_checks"):
                        f.write(f"- **Failed Checks**: `{', '.join(p['failed_checks'])}`\n")
                    f.write(f"- **Review Summary**:\n{p.get('review_summary', '')}\n")
                    f.write(f"- **Detailed Report**: `{p.get('review_report_file', '')}`\n\n")

        print(f"\nMaster triage report generated: {master_report}")

    if args.json:
        print(json.dumps(audited, indent=2))
        return

    conflicting = [p for p in audited if p["category"] == "CONFLICTING"]
    ci_failed = [p for p in audited if p["category"] == "CI_FAILED"]
    clean_green = [p for p in audited if p["category"] == "CLEAN_GREEN"]
    other = [p for p in audited if p["category"] not in ["CONFLICTING", "CI_FAILED", "CLEAN_GREEN"]]

    print(f"\n=======================================================")
    print(f"  /luna Stale PR Audit (>={args.hours}h unmodified) — {len(audited)} PRs found")
    print(f"=======================================================\n")

    if ci_failed:
        print(f"🚨 1. CI FAILED ({len(ci_failed)}) — Needs Coder Diagnosis (Dispatch: codexl)")
        for p in ci_failed:
            print(f"  • PR #{p['number']} ({p['age_hours']:.1f}h stale): {p['title'][:70]}")
            print(f"    Branch: {p['branch']} | Failed: {', '.join(p['failed_checks'][:3])}")
            if p.get("review_summary"):
                print(f"    Action Plan:\n{p['review_summary']}")
            else:
                print(f"    Action: codexl 'Review failing CI checks on PR #{p['number']} and propose fix'")
        print()

    if conflicting:
        print(f"⚠️  2. CONFLICTING / DIRTY ({len(conflicting)}) — Needs Rebase (Dispatch: /fixpr)")
        for p in conflicting:
            print(f"  • PR #{p['number']} ({p['age_hours']:.1f}h stale): {p['title'][:70]}")
            print(f"    Branch: {p['branch']} | Action: git rebase origin/main && /fixpr")
            if p.get("review_summary"):
                print(f"    Review:\n{p['review_summary']}")
        print()

    if clean_green:
        print(f"✅ 3. CLEAN & ALL GREEN ({len(clean_green)}) — Awaiting Final Verification / Merge Signoff")
        for p in clean_green:
            print(f"  • PR #{p['number']} ({p['age_hours']:.1f}h stale): {p['title'][:70]}")
            if p.get("review_summary"):
                print(f"    Review:\n{p['review_summary']}")
        print()

    if other:
        print(f"ℹ️  4. PENDING / OTHER ({len(other)})")
        for p in other:
            print(f"  • PR #{p['number']} ({p['age_hours']:.1f}h stale): {p['title'][:70]} (Status: {p['mergeStateStatus']})")
        print()


if __name__ == "__main__":
    main()

