#!/usr/bin/env python3
"""PRW metrics: collect GitHub PR data, aggregate, render one Markdown dashboard, publish it.

Pipeline (pure-function core, Python 3 stdlib only):
    collect(repos, cutoff, runner) -> (records, health)
    aggregate(records, health, annotations, cutoff) -> metrics
    render(metrics) -> markdown
    publish(markdown, remote, branch, fallback_path) -> exit code

DATA CONTRACT (frozen by Task 0; fixtures in tests/fixtures/prw/ are the executable form)

All timestamps are ISO-8601 UTC strings "YYYY-MM-DDTHH:MM:SSZ". All durations are integer
seconds; None means UNKNOWN and is never rendered or computed as 0.

PR record (one per (repo, number); collect returns them sorted by (repo, number)):
  {repo, number, url, title, author, author_type, created_at, merged_at, closed_at, is_draft,
   labels: [str], status: str|None, timeline_complete: bool,
   events: [{type, at, actor, actor_type, label?, reviewer?, review_state?, new_title?}],
   attempts: [{key, kind: "requested"|"readiness", reviewer: str|None, opened_at,
               closed_at: str|None, closed_reason: "review"|"superseded"|None,
               closed_by: str|None}]}
  - author_type / actor_type are GitHub __typename: "User" or "Bot".
  - labels are the labels applied at collection time (names only).
  - events are stored once, sorted by `at` (stable for equal times, GitHub timeline order).
    type is one of: ready_for_review, review_requested, review, commit, comment, labeled,
    unlabeled, renamed. `label` is set for labeled/unlabeled, `reviewer` for review_requested,
    `review_state` for review, `new_title` for renamed.
  - status: operational status parsed from the CURRENT title's leading "[status]" token
    (one of working, waiting, blocked, queued, ready, unknown, lower-cased), else None.
  - attempts are sorted by (opened_at, key). closed_by is the reviewing actor's login, set only
    when closed_reason is "review". Requested attempt key "<reviewer>@<request_at>"; readiness
    attempt key "*@<ready_at>". Rules are in the design's Event contract.
  - timeline_complete is False when the GraphQL timeline could not be fully read.

health: {repo: {ok: bool, pages: int, truncated_prs: [int], error: str|None}}
  pages counts every GraphQL page fetched for the repo (both queries).

metrics:
  cutoff, repos (sorted keys of health), annotations_status ("OK"|"ABSENT"|"INVALID"),
  health (copied), windows {w1: {start, end}, w2: {start, end}}
  (w1 = [cutoff-14d, cutoff-7d), w2 = [cutoff-7d, cutoff); half-open, start inclusive).
  merge_stats: {repo: {w1, w2, horizon}}, each {all, comparable, backlog}, each a Dist.
    Dist = {n: int, p50, p75, p90, p99}; n == 0 gives None for all percentiles.
    A PR belongs to a window by merged_at. horizon = [cutoff-14d, cutoff).
    comparable = merged_at - created_at <= 7d; backlog = more than 7d; all = both.
    "W2 merged count" on the dashboard is merge_stats[repo].w2.all.n.
  elapsed: {repo: Dist}   created-to-merged over the horizon's merged PRs (== horizon.all).
  stage_dwell: {repo: {stage_label: Dist}}
    stage_label is the raw label name; canonical labels are stage:0-spec, stage:1-code,
    stage:2-evidence, stage:3-review, stage:4-ci, stage:5-approval. A stage with no samples is
    omitted (renderer shows UNKNOWN). One sample = one PR's total dwell in that stage, from
    LabeledEvent to matching UnlabeledEvent, clipped to [cutoff-14d, cutoff), open-ended at
    min(closed_at, cutoff) when still applied. Derived from label events only, never titles.
  handoff: {repo: {requested: Dist, readiness: Dist, open_attempts: int, superseded_attempts: int}}
    Only attempts opened in [cutoff-14d, cutoff) with closed_reason "review" and closed_at
    before cutoff are measured (closed_at - opened_at). An attempt whose closing review is at
    or after cutoff is open at cutoff. Open attempts are counted in open_attempts; superseded
    ones in superseded_attempts; neither is measured.
  user_activity: {repo: {User: {comments, reviews, commits}, Bot: {...}}}
    Counts of comment/review/commit events in [cutoff-14d, cutoff) by actor_type.
  episode_labels: {"<repo>#<n>": {label, evidence}}; empty unless annotations_status is "OK".
  open_attention: [{repo, number, url, title, owner, age_sec, earliest_unmet, status}]
    Every PR open at cutoff (collected regardless of age), sorted by age_sec descending then
    (repo, number). owner = PR author; age_sec = cutoff - created_at; earliest_unmet = the
    stage label currently applied (lowest stage number if several), None if none; status is the
    record's status.

Time rule: every metric ignores events with at >= cutoff.
A record with timeline_complete False contributes to merge_stats/elapsed/open_attention but its
attempts, stage dwell and activity are excluded from those metrics (UNKNOWN, never 0).

Section mapping: 1 repo comparison <- windows+merge_stats; 2 stage dwell <- stage_dwell;
3 time semantics <- elapsed (rest UNKNOWN); 4 handoff <- handoff; 5 user activity and episodes <-
user_activity+episode_labels; 6 open PR attention <- open_attention; 7 notes <- health,
annotations_status, definitions.

Stub signatures: collect(repos, cutoff, runner) -> (records, health);
aggregate(records, health, annotations, cutoff) -> metrics (annotations is load_annotations'
{labels, status}); render(metrics) -> str; publish(markdown, remote, branch, fallback_path) -> int
(0 ok or no change, 2 no remote, 3 push failure); main(argv=None) -> int.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


# --- util ---

_LABELS = ("good", "bad", "mixed")


def parse_iso_utc(text):
    """Parse an ISO-8601 timestamp with a Z or +00:00 offset into an aware UTC datetime."""
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timestamp has no UTC offset: %r" % (text,))
    return value.astimezone(timezone.utc)


def format_iso_utc(moment):
    """Format an aware datetime as YYYY-MM-DDTHH:MM:SSZ."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_duration(seconds):
    """Render integer seconds as e.g. '2d 15h'; None is 'UNKNOWN', 0 is '0s'."""
    if seconds is None:
        return "UNKNOWN"
    if seconds < 0:
        raise ValueError("negative duration: %r" % (seconds,))
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [
        "%d%s" % (n, unit)
        for n, unit in ((days, "d"), (hours, "h"), (minutes, "m"), (secs, "s"))
        if n
    ]
    return " ".join(parts) or "0s"


def nearest_rank_percentile(values, p):
    """Nearest-rank percentile (integer p, 1..100): sorted, rank = ceil(p*n/100), 1-indexed."""
    if not values:
        return None
    ordered = sorted(values)
    rank = -(-p * len(ordered) // 100)
    return ordered[min(max(rank, 1), len(ordered)) - 1]


def load_annotations(path):
    """Load optional episode labels; returns {"labels": {...}, "status": "OK"|"ABSENT"|"INVALID"}.

    A missing path or file is ABSENT. Unreadable, malformed or wrongly shaped content is INVALID
    (all-or-nothing, labels empty). Expected shape: {"<repo>#<number>": {"label":
    "good|bad|mixed", "evidence": "<url>"}}.
    """
    absent = {"labels": {}, "status": "ABSENT"}
    invalid = {"labels": {}, "status": "INVALID"}
    if not path or not os.path.exists(path):
        return absent
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return invalid
    if not isinstance(data, dict):
        return invalid
    for key, entry in data.items():
        if not isinstance(key, str) or not key.rpartition("#")[2].isdigit():
            return invalid
        if not isinstance(entry, dict) or entry.get("label") not in _LABELS:
            return invalid
        if not isinstance(entry.get("evidence"), str):
            return invalid
    return {"labels": data, "status": "OK"}



# --- collect ---

def collect(repos, cutoff, runner):
    raise NotImplementedError



# --- aggregate ---

def aggregate(records, health, annotations, cutoff):
    raise NotImplementedError



# --- render ---

def render(metrics):
    raise NotImplementedError



# --- publish ---

_README_PATH = "dashboards/prw/README.md"
_IDENTITY = ["-c", "user.name=prw-metrics", "-c", "user.email=prw-metrics@localhost"]


def _state_dir():
    return os.environ.get("PRW_METRICS_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "share", "prw-metrics-slim"
    )


def _git(cwd, *args):
    return subprocess.run(["git", *_IDENTITY, *args], cwd=cwd, capture_output=True, text=True)


def _push_once(clone, branch):
    return _git(clone, "push", "origin", "HEAD:refs/heads/%s" % branch)


def _publish_to_clone(markdown, remote, branch, clone):
    """Return 0 on success or no change; raise RuntimeError(message) on any git failure."""
    done = _git(clone, "clone", "--depth", "1", "--branch", branch, remote, ".")
    if done.returncode:
        raise RuntimeError("clone failed: " + done.stderr.strip())
    target = Path(clone, _README_PATH)
    if target.exists() and target.read_text(encoding="utf-8") == markdown:
        print("no change")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    for step in (("add", "--", _README_PATH), ("commit", "-m", "chore(prw-metrics): update PRW dashboard", "--", _README_PATH)):
        done = _git(clone, *step)
        if done.returncode:
            raise RuntimeError("git %s failed: %s" % (step[0], (done.stderr or done.stdout).strip()))
    done = _push_once(clone, branch)
    if done.returncode and ("non-fast-forward" in done.stderr or "fetch first" in done.stderr):
        pulled = _git(clone, "pull", "--rebase", "origin", branch)
        if pulled.returncode:
            raise RuntimeError("rebase failed: " + pulled.stderr.strip())
        done = _push_once(clone, branch)
    if done.returncode:
        raise RuntimeError("push failed: " + done.stderr.strip())
    print("published %s to %s" % (_README_PATH, branch))
    return 0


def publish(markdown, remote, branch, fallback_path):
    """Shallow-clone remote@branch, update the dashboard file, push. 0 ok/no change, 2 no remote, 3 failure."""
    if not remote:
        print("publish requested but no roadmap remote configured", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="prw-publish-") as clone:
        try:
            return _publish_to_clone(markdown, remote, branch, clone)
        except (RuntimeError, OSError) as exc:
            print("publish failed: %s" % exc, file=sys.stderr)
    try:
        Path(fallback_path).parent.mkdir(parents=True, exist_ok=True)
        Path(fallback_path).write_text(markdown, encoding="utf-8")
        print("dashboard saved to %s" % fallback_path, file=sys.stderr)
    except OSError as exc:
        print("fallback write failed: %s" % exc, file=sys.stderr)
    return 3


def _parser():
    p = argparse.ArgumentParser(description="Collect PRW metrics and publish one Markdown dashboard.")
    p.add_argument("--repos", default=os.environ.get("PRW_METRICS_REPOS", ""), help="comma-separated owner/name list")
    p.add_argument("--input-dir", help="replay cached GraphQL pages from this directory instead of calling gh")
    p.add_argument("--cutoff", help="ISO-8601 UTC cutoff (default: now)")
    p.add_argument("--output", help="also write the Markdown to this file")
    p.add_argument("--publish", action="store_true", default=os.environ.get("PRW_METRICS_PUBLISH") == "1")
    p.add_argument("--roadmap-remote", default=os.environ.get("PRW_METRICS_ROADMAP_REMOTE", ""))
    p.add_argument("--roadmap-branch", default="main")
    p.add_argument("--annotations", default=os.path.join(_state_dir(), "annotations.json"))
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("no repos given (--repos or PRW_METRICS_REPOS)", file=sys.stderr)
        return 2
    if args.publish and not args.roadmap_remote:
        print("publish requested but no roadmap remote configured (--roadmap-remote)", file=sys.stderr)
        return 2
    cutoff = format_iso_utc(parse_iso_utc(args.cutoff) if args.cutoff else datetime.now(timezone.utc))
    runner = replay_runner(args.input_dir) if args.input_dir else gh_runner
    records, health = collect(repos, cutoff, runner)
    metrics = aggregate(records, health, load_annotations(args.annotations), cutoff)
    markdown = render(metrics)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    if args.publish:
        fallback = args.output or os.path.join(_state_dir(), "last-dashboard.md")
        return publish(markdown, args.roadmap_remote, args.roadmap_branch, fallback)
    if not args.output:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
