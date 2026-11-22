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

import re

_STATUSES = ("working", "waiting", "blocked", "queued", "ready", "unknown")
_TITLE_STATUS = re.compile(r"^\s*\[([^\]]*)\]")

_QUERY = """
query($search: String!, $cursor: String) {
  search(query: $search, type: ISSUE, first: 25, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on PullRequest {
        number url title createdAt mergedAt closedAt isDraft
        author { login __typename }
        labels(first: 50) { nodes { name } }
        timelineItems(first: 100, itemTypes: [READY_FOR_REVIEW_EVENT, REVIEW_REQUESTED_EVENT,
            PULL_REQUEST_REVIEW, PULL_REQUEST_COMMIT, ISSUE_COMMENT, LABELED_EVENT,
            UNLABELED_EVENT, RENAMED_TITLE_EVENT]) {
          pageInfo { hasNextPage endCursor }
          nodes {
            __typename
            ... on ReadyForReviewEvent { createdAt actor { login __typename } }
            ... on ReviewRequestedEvent {
              createdAt actor { login __typename }
              requestedReviewer { __typename ... on User { login } ... on Team { name } }
            }
            ... on PullRequestReview { submittedAt state author { login __typename } }
            ... on PullRequestCommit {
              commit { committedDate author { user { login __typename } } }
            }
            ... on IssueComment { createdAt author { login __typename } }
            ... on LabeledEvent { createdAt actor { login __typename } label { name } }
            ... on UnlabeledEvent { createdAt actor { login __typename } label { name } }
            ... on RenamedTitleEvent { createdAt actor { login __typename } currentTitle }
          }
        }
      }
    }
  }
}
"""

# timeline __typename -> (event type, timestamp field, actor field)
_EVENT_KINDS = {
    "ReadyForReviewEvent": ("ready_for_review", "createdAt", "actor"),
    "ReviewRequestedEvent": ("review_requested", "createdAt", "actor"),
    "PullRequestReview": ("review", "submittedAt", "author"),
    "IssueComment": ("comment", "createdAt", "author"),
    "LabeledEvent": ("labeled", "createdAt", "actor"),
    "UnlabeledEvent": ("unlabeled", "createdAt", "actor"),
    "RenamedTitleEvent": ("renamed", "createdAt", "actor"),
}


def parse_operational_title(title):
    """Status from a leading "[status]" title token (lower-cased), or None if absent/unknown."""
    found = _TITLE_STATUS.match(title or "")
    token = found.group(1).strip().lower() if found else None
    return token if token in _STATUSES else None


def gh_runner(args):
    """Run `gh api graphql <args>` (auth comes from gh itself) and return the parsed JSON."""
    done = subprocess.run(
        ["gh", "api", "graphql"] + list(args), capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout).strip()[:500] or "gh api failed")
    return json.loads(done.stdout)


def replay_runner(input_dir):
    """Runner that replays a directory of saved GraphQL pages, in sorted filename order.

    Files without a `data.search` payload are ignored. Each call returns the next page, so a
    capture must be ordered as requested: per repo, the updated query's pages, then the open
    query's pages. Calling past the last page raises.
    """
    pages = []
    for path in sorted(Path(input_dir).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and isinstance(doc.get("data"), dict) and "search" in doc["data"]:
            pages.append(doc)
    served = iter(pages)

    def run(args):
        try:
            return next(served)
        except StopIteration:
            raise RuntimeError("replay directory has no more pages: %s" % input_dir) from None

    return run


def _actor(node):
    return (node or {}).get("login"), (node or {}).get("__typename")


def _event(item):
    """Normalize one timeline node into an event dict, or None for an unusable node."""
    kind = item.get("__typename")
    if kind == "PullRequestCommit":
        commit = item.get("commit") or {}
        at, who = commit.get("committedDate"), (commit.get("author") or {}).get("user")
        etype = "commit"
    elif kind in _EVENT_KINDS:
        etype, at_field, who_field = _EVENT_KINDS[kind]
        at, who = item.get(at_field), item.get(who_field)
    else:
        return None
    if not at:
        return None
    actor, actor_type = _actor(who)
    event = {"type": etype, "at": at, "actor": actor, "actor_type": actor_type}
    if kind in ("LabeledEvent", "UnlabeledEvent"):
        event["label"] = (item.get("label") or {}).get("name")
    elif kind == "ReviewRequestedEvent":
        target = item.get("requestedReviewer") or {}
        event["reviewer"] = target.get("login") or target.get("name")
    elif kind == "PullRequestReview":
        event["review_state"] = item.get("state")
    elif kind == "RenamedTitleEvent":
        event["new_title"] = item.get("currentTitle")
    return event


def _derive_attempts(events, author):
    """Per-attempt review handoffs (design: Event contract); events must be time-ordered."""
    attempts, open_requested, open_readiness = [], {}, None

    def close(attempt, at, reason, by):
        attempt["closed_at"], attempt["closed_reason"], attempt["closed_by"] = at, reason, by

    for event in events:
        kind, at, actor = event["type"], event["at"], event["actor"]
        if kind == "review_requested" and event.get("reviewer"):
            reviewer = event["reviewer"]
            if reviewer in open_requested:
                close(open_requested.pop(reviewer), at, "superseded", None)
            attempt = {
                "key": "%s@%s" % (reviewer, at), "kind": "requested", "reviewer": reviewer,
                "opened_at": at, "closed_at": None, "closed_reason": None, "closed_by": None,
            }
            attempts.append(attempt)
            open_requested[reviewer] = attempt
        elif kind == "ready_for_review":
            if open_readiness:
                close(open_readiness, at, "superseded", None)
            open_readiness = {
                "key": "*@%s" % at, "kind": "readiness", "reviewer": None,
                "opened_at": at, "closed_at": None, "closed_reason": None, "closed_by": None,
            }
            attempts.append(open_readiness)
        elif kind == "review":
            if actor in open_requested:
                close(open_requested.pop(actor), at, "review", actor)
            if open_readiness and actor != author:
                close(open_readiness, at, "review", actor)
                open_readiness = None
    return sorted(attempts, key=lambda a: (a["opened_at"], a["key"]))


def _record(repo, node):
    login, author_type = _actor(node.get("author"))
    events = [e for e in map(_event, node["timelineItems"]["nodes"]) if e]
    events.sort(key=lambda e: e["at"])
    return {
        "repo": repo,
        "number": node["number"],
        "url": node["url"],
        "title": node["title"],
        "author": login,
        "author_type": author_type,
        "created_at": node["createdAt"],
        "merged_at": node["mergedAt"],
        "closed_at": node["closedAt"],
        "is_draft": node["isDraft"],
        "labels": [n["name"] for n in node["labels"]["nodes"]],
        "status": parse_operational_title(node["title"]),
        "timeline_complete": not node["timelineItems"]["pageInfo"]["hasNextPage"],
        "events": events,
        "attempts": _derive_attempts(events, login),
    }


def _search_pages(repo, search, runner, state):
    """Yield every PR node for one search query, following pageInfo; counts pages in state."""
    cursor = None
    while True:
        args = ["-f", "query=" + _QUERY, "-f", "search=" + search]
        if cursor:
            args += ["-f", "cursor=" + cursor]
        response = runner(args)
        if response.get("errors") and not (response.get("data") or {}).get("search"):
            raise RuntimeError(json.dumps(response["errors"])[:500])
        state["pages"] += 1
        result = response["data"]["search"]
        for node in result["nodes"]:
            if node.get("__typename") == "PullRequest":
                yield node
        if not result["pageInfo"]["hasNextPage"]:
            return
        cursor = result["pageInfo"]["endCursor"]


def collect(repos, cutoff, runner):
    """Collect PR records and per-repo health. Runs two search queries per repo: PRs updated in
    the last 14 days before cutoff, and every open PR regardless of age; deduplicates on
    (repo, number). A repo whose queries fail is reported with ok=False and keeps what it got."""
    if isinstance(cutoff, str):
        cutoff = parse_iso_utc(cutoff)
    since = format_iso_utc(cutoff - timedelta(days=14))
    records, health = {}, {}
    for repo in repos:
        state = {"pages": 0}
        health[repo] = {"ok": True, "pages": 0, "truncated_prs": [], "error": None}
        searches = (
            "repo:%s is:pr updated:>=%s" % (repo, since),
            "repo:%s is:pr is:open" % repo,
        )
        try:
            for search in searches:
                for node in _search_pages(repo, search, runner, state):
                    record = _record(repo, node)
                    seen = records.get((repo, record["number"]))
                    if seen is None or (record["timeline_complete"] and not seen["timeline_complete"]):
                        records[(repo, record["number"])] = record
        except Exception as error:  # a failed repo must degrade to INCOMPLETE, not abort the run
            health[repo]["ok"], health[repo]["error"] = False, str(error)[:500]
        health[repo]["pages"] = state["pages"]
        health[repo]["truncated_prs"] = sorted(
            r["number"] for (name, _), r in records.items() if name == repo and not r["timeline_complete"]
        )
    return [records[key] for key in sorted(records)], health



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
