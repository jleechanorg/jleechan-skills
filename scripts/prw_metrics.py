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

def publish(markdown, remote, branch, fallback_path):
    raise NotImplementedError


def main(argv=None):
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
