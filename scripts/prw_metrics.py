#!/usr/bin/env python3
"""PRW metrics: collect GitHub PR data, aggregate, render one Markdown dashboard, publish it.

Pipeline (pure-function core, Python 3 stdlib only):
    collect(repos, cutoff, runner) -> (records, health)
    load_usage_feeds(paths, remote, branch, cutoff) -> (feeds, problems) [optional; read only when --usage-feed/--usage-remote given]
    aggregate(records, health, annotations, cutoff, usage=None, usage_problems=()) -> metrics
    render(metrics) -> markdown
    publish(markdown, remote, branch, fallback_path, *, path, message) -> exit code

DATA CONTRACT (frozen by Task 0; fixtures in tests/fixtures/prw/ are the executable form)

All timestamps are ISO-8601 UTC strings "YYYY-MM-DDTHH:MM:SSZ". All durations are integer
seconds; None means UNKNOWN and is never rendered or computed as 0.

PR record (one per (repo, number); collect returns them sorted by (repo, number)):
  {repo, number, url, title, branch, author, author_type, created_at, merged_at, closed_at, is_draft,
   labels: [str], status: str|None, timeline_complete: bool,
   events: [{type, at, actor, actor_type, label?, reviewer?, review_state?, new_title?}],
   attempts: [{key, kind: "requested"|"readiness", reviewer: str|None, opened_at,
               closed_at: str|None, closed_reason: "review"|"superseded"|None,
               closed_by: str|None}]}
  - branch is the PR head branch (headRefName), str or None.
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

  usage: present ONLY when usage feeds are configured (aggregate(usage=[...]); absent otherwise).
    Input is a list of prw-local-usage.v1 feeds {schema, machine, generated_at, window, idle_gap_sec,
    sessions: [{tool, session_id, repo|None, branch|None, first_at, last_at, active_sec,
    models: {model: {input, output, cache_read, cache_write}}}]}. Only sessions whose
    [first_at, last_at] overlaps [cutoff-14d, cutoff) count.
    {machines: {machine: {generated_at, stale}}, problems: [str],
     per_repo: {repo|"unattributed": {sessions, active_sec, tokens: {input, output, cache_read,
       cache_write}, by_tool: {tool: {sessions, active_sec, output}}}},
     per_pr: {"<repo>#<n>": {active_sec, output, input, sessions}},
     unattributed: {sessions, active_sec, output}}
    stale = generated_at more than 12h before cutoff. A session is attributed to a PR when its
    branch is non-null, not in {main, master, trunk, develop}, equals the PR's branch, and its repo
    is null or equals the PR's repo; matches in more than one repo (null repo) are NOT attributed;
    several PRs of one repo (reused branch) go to the most recently created. per_repo counts every
    in-window session (key "unattributed" is a bucket for repo None, never a repo); the top-level
    unattributed totals are the sessions that matched no PR. per_pr.input is plain input tokens.

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
publish also takes keyword-only path (default the dashboard README) and commit message.
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

_TIMELINE_TYPES = """[READY_FOR_REVIEW_EVENT, REVIEW_REQUESTED_EVENT,
            PULL_REQUEST_REVIEW, PULL_REQUEST_COMMIT, ISSUE_COMMENT, LABELED_EVENT,
            UNLABELED_EVENT, RENAMED_TITLE_EVENT]"""
_TIMELINE_BODY = """{
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
"""

_QUERY = ("""
query($search: String!, $cursor: String) {
  search(query: $search, type: ISSUE, first: 25, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on PullRequest {
        id number url title headRefName createdAt mergedAt closedAt isDraft
        author { login __typename }
        labels(first: 50) { nodes { name } }
        timelineItems(first: 100, itemTypes: """ + _TIMELINE_TYPES + ") " + _TIMELINE_BODY + """
      }
    }
  }
}
""")

_NODE_QUERY = (
    "query($id: ID!, $cursor: String) { node(id: $id) { ... on PullRequest { timelineItems(first: 100, after: $cursor, itemTypes: "
    + _TIMELINE_TYPES + ") " + _TIMELINE_BODY + "} } }"
)
_MAX_EXTRA_TIMELINE_PAGES = 50

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
        if any(a.startswith("id=") for a in args):  # timeline continuation: unreadable in a replay
            return {"data": {"node": None}}
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
        "branch": node.get("headRefName"),
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


def _complete_timeline(node, runner):
    """Fetch the remaining timeline pages of a PR node in place; on any failure or after the page
    bound leave pageInfo.hasNextPage true so the record stays timeline_complete=False."""
    timeline = node["timelineItems"]
    for _ in range(_MAX_EXTRA_TIMELINE_PAGES):
        if not timeline["pageInfo"]["hasNextPage"]:
            return
        try:
            page = runner(["-f", "query=" + _NODE_QUERY, "-f", "id=" + node["id"],
                           "-f", "cursor=" + timeline["pageInfo"]["endCursor"]])
            more = page["data"]["node"]["timelineItems"]
            timeline["nodes"] += more["nodes"]
            timeline["pageInfo"] = more["pageInfo"]
        except Exception:
            return


def _search_pages(repo, search, runner, state):
    """Yield every PR node for one search query, following pageInfo; counts pages in state."""
    cursor, read, expected = None, 0, 0
    while True:
        args = ["-f", "query=" + _QUERY, "-f", "search=" + search]
        if cursor:
            args += ["-f", "cursor=" + cursor]
        response = runner(args)
        if response.get("errors") and not (response.get("data") or {}).get("search"):
            raise RuntimeError(json.dumps(response["errors"])[:500])
        state["pages"] += 1
        result = response["data"]["search"]
        expected = result.get("issueCount", expected)
        for node in result["nodes"]:
            if node.get("__typename") == "PullRequest":
                read += 1
                yield node
        if not result["pageInfo"]["hasNextPage"]:
            if read < expected:  # GitHub search caps results at 1000; never present a capped read as complete
                raise RuntimeError("search truncated: read %d of %d" % (read, expected))
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
                    _complete_timeline(node, runner)
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


_USAGE_SCHEMA = "prw-local-usage.v1"
_USAGE_REMOTE_DIR = "dashboards/prw/usage"
_FUTURE_SLACK = timedelta(minutes=5)
_SESSION_KEYS = ("tool", "session_id", "first_at", "last_at", "active_sec", "models")


def _count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _valid_session(s):
    try:
        return (isinstance(s, dict) and all(k in s for k in _SESSION_KEYS)
                and isinstance(s["tool"], str) and isinstance(s["session_id"], str)
                and all(s.get(k) is None or isinstance(s[k], str) for k in ("repo", "branch"))
                and _count(s["active_sec"]) and isinstance(s["models"], dict)
                and all(isinstance(m, dict) and all(_count(m.get(t)) for t in _TOKENS) for m in s["models"].values())
                and parse_iso_utc(s["first_at"]) <= parse_iso_utc(s["last_at"]))
    except (TypeError, ValueError, AttributeError):
        return False


def _read_feed(path, problems):
    name = Path(path).name
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("schema") != _USAGE_SCHEMA:
            problems.append("%s: not a %s feed" % (name, _USAGE_SCHEMA))
            return None
        missing = [k for k in ("machine", "generated_at", "sessions") if k not in doc]
        if missing or not isinstance(doc["sessions"], list) or not isinstance(doc["machine"], str):
            problems.append("%s: missing or invalid %s" % (name, ", ".join(missing) or "sessions"))
            return None
        parse_iso_utc(doc["generated_at"])
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        problems.append("%s: unreadable (%s)" % (name, type(exc).__name__))
        return None
    good = [s for s in doc["sessions"] if _valid_session(s)]
    if len(good) != len(doc["sessions"]):
        problems.append("%s: dropped %d invalid sessions" % (name, len(doc["sessions"]) - len(good)))
    return dict(doc, sessions=good)


def load_usage_feeds(paths, remote=None, branch="main", cutoff=None):
    """Load prw-local-usage.v1 feeds from files/directories (and, read-only, from a shallow clone of
    `remote`). Returns (feeds, problems); a bad feed is skipped and reported, never fatal. Only the
    newest feed per machine is kept, sorted by machine. With `cutoff`, a feed generated more than 5 minutes
    after it is a problem and ignored (it must not win "newest" or look fresh)."""
    problems, files = [], []
    for raw in paths or []:
        path = Path(raw)
        if path.is_dir():
            files += sorted(path.glob("*.json"))
        elif path.is_file():
            files.append(path)
        else:
            problems.append("%s: no such feed file or directory" % path.name)
    cloned = tempfile.TemporaryDirectory(prefix="prw-usage-") if remote else None
    try:
        if remote:
            try:
                done = _git(cloned.name, "clone", "--depth", "1", "--branch", branch, remote, ".")
            except (RuntimeError, OSError) as exc:  # OSError: git is not installed
                done = None
                problems.append("usage remote: %s" % exc)
            if done and done.returncode:
                problems.append("usage remote: clone failed")
            elif done:
                files += sorted(Path(cloned.name, _USAGE_REMOTE_DIR).glob("*.json"))
        newest = {}
        for path in files:
            feed = _read_feed(path, problems)
            if feed and cutoff and parse_iso_utc(feed["generated_at"]) > parse_iso_utc(cutoff) + _FUTURE_SLACK:
                problems.append("%s: generated_at is in the future, ignored" % Path(path).name)
                feed = None
            if feed and (feed["machine"] not in newest or parse_iso_utc(feed["generated_at"])
                         > parse_iso_utc(newest[feed["machine"]]["generated_at"])):
                newest[feed["machine"]] = feed
    finally:
        if cloned:
            cloned.cleanup()
    return [newest[m] for m in sorted(newest)], problems



# --- aggregate ---

_DAY = 86400
_DIST_KEYS = (("p50", 50), ("p75", 75), ("p90", 90), ("p99", 99))
_ACTIVITY_KEYS = {"comment": "comments", "review": "reviews", "commit": "commits"}


def _dist(values):
    out = {"n": len(values)}
    for key, p in _DIST_KEYS:
        out[key] = nearest_rank_percentile(values, p)
    return out


def _secs(delta):
    return int(delta.total_seconds())


def _window_of(merged_at, cutoff):
    """Return 'w1', 'w2' or None for a merge time; windows are half-open, start inclusive."""
    if merged_at is None or merged_at >= cutoff:
        return None
    if merged_at >= cutoff - timedelta(days=7):
        return "w2"
    if merged_at >= cutoff - timedelta(days=14):
        return "w1"
    return None


def _stage_number(label):
    head = label.split(":", 1)[1].split("-", 1)[0]
    return int(head) if head.isdigit() else 99


def _stage_intervals(record, cutoff):
    """Return ({label: dwell_seconds clipped to the horizon}, set of labels applied at cutoff)."""
    start = cutoff - timedelta(days=14)
    end = parse_iso_utc(record["closed_at"]) if record["closed_at"] else cutoff
    end = min(end, cutoff)
    opened, total = {}, {}

    def close(label, until):
        lo, hi = max(opened.pop(label), start), min(until, cutoff)
        if hi > lo:
            total[label] = total.get(label, 0) + _secs(hi - lo)

    events = sorted(record["events"], key=lambda e: e["at"])
    for ev in events:
        at = parse_iso_utc(ev["at"])
        label = ev.get("label") or ""
        if at >= cutoff or not label.startswith("stage:"):
            continue
        if ev["type"] == "labeled" and label not in opened:
            opened[label] = at
        elif ev["type"] == "unlabeled" and label in opened:
            close(label, at)
    applied = set(opened)
    for label in list(opened):
        close(label, end)
    return total, applied


def _measure_attempts(record, cutoff):
    """Yield (kind, status, seconds) per attempt opened in the horizon; status is
    'measured', 'open' or 'superseded'."""
    start = cutoff - timedelta(days=14)
    for att in record["attempts"]:
        opened = parse_iso_utc(att["opened_at"])
        if not start <= opened < cutoff:
            continue
        closed = parse_iso_utc(att["closed_at"]) if att["closed_at"] else None
        if closed is None or closed >= cutoff:
            yield att["kind"], "open", None
        elif att["closed_reason"] == "review":
            yield att["kind"], "measured", _secs(closed - opened)
        else:
            yield att["kind"], "superseded", None


TRIVIAL_BRANCHES = {"main", "master", "trunk", "develop"}  # also imported by prw_local_usage
_STALE_AFTER = 12 * 3600
HEARTBEAT_SEC = 6 * 3600  # an unchanged feed is still republished this often; must stay below _STALE_AFTER
_TOKENS = ("input", "output", "cache_read", "cache_write")


def _usage_metrics(feeds, problems, records, cutoff):
    start = cutoff - timedelta(days=14)
    by_branch = {}
    for rec in records:
        if rec.get("branch") and rec["branch"] not in TRIVIAL_BRANCHES:
            by_branch.setdefault(rec["branch"], []).append(rec)
    machines, per_repo, per_pr = {}, {}, {}
    loose = {"sessions": 0, "active_sec": 0, "output": 0}
    for feed in feeds:
        generated = parse_iso_utc(feed["generated_at"])
        machines[feed["machine"]] = {"generated_at": format_iso_utc(generated),
                                     "stale": _secs(cutoff - generated) > _STALE_AFTER}
        for s in feed["sessions"]:
            if not (parse_iso_utc(s["first_at"]) < cutoff and parse_iso_utc(s["last_at"]) >= start):
                continue
            tokens = {t: sum(m[t] for m in s["models"].values()) for t in _TOKENS}
            repo = (s.get("repo") or "").lower() or None
            slot = per_repo.setdefault(repo or "unattributed", {
                "sessions": 0, "active_sec": 0, "tokens": dict.fromkeys(_TOKENS, 0), "by_tool": {}})
            tool = slot["by_tool"].setdefault(s["tool"], {"sessions": 0, "active_sec": 0, "output": 0})
            for target in (slot, tool):
                target["sessions"] += 1
                target["active_sec"] += s["active_sec"]
            tool["output"] += tokens["output"]
            for t in _TOKENS:
                slot["tokens"][t] += tokens[t]
            matches = [r for r in by_branch.get(s.get("branch"), []) if repo is None or r["repo"].lower() == repo]
            if matches and len({r["repo"] for r in matches}) == 1:
                best = max(matches, key=lambda r: (r["created_at"], r["number"]))
                pr = per_pr.setdefault("%s#%d" % (best["repo"], best["number"]),
                                       {"active_sec": 0, "output": 0, "input": 0, "sessions": 0})
                pr["active_sec"] += s["active_sec"]
                pr["output"] += tokens["output"]
                pr["input"] += tokens["input"]
                pr["sessions"] += 1
            else:
                loose["sessions"] += 1
                loose["active_sec"] += s["active_sec"]
                loose["output"] += tokens["output"]
    return {"machines": dict(sorted(machines.items())), "problems": list(problems),
            "per_repo": dict(sorted(per_repo.items())), "per_pr": dict(sorted(per_pr.items())),
            "unattributed": loose}


def aggregate(records, health, annotations, cutoff, usage=None, usage_problems=()):
    """Pure aggregation of collected PR records into the metrics structure (see module docstring).
    `usage` (a list of loaded feeds) adds the optional metrics["usage"]; None leaves it absent."""
    cutoff_dt = parse_iso_utc(cutoff) if isinstance(cutoff, str) else cutoff
    horizon_start = cutoff_dt - timedelta(days=14)
    repos = sorted(health)
    by_repo = {repo: [] for repo in repos}
    for record in records:
        if record["repo"] in by_repo:
            by_repo[record["repo"]].append(record)

    merge_stats, elapsed, stage_dwell, handoff, activity = {}, {}, {}, {}, {}
    open_attention = []
    for repo in repos:
        samples = {w: {"all": [], "comparable": [], "backlog": []} for w in ("w1", "w2", "horizon")}
        dwell, counts = {}, {"requested": [], "readiness": [], "open": 0, "superseded": 0}
        acts = {t: {k: 0 for k in _ACTIVITY_KEYS.values()} for t in ("User", "Bot")}
        for rec in by_repo[repo]:
            created = parse_iso_utc(rec["created_at"])
            merged = parse_iso_utc(rec["merged_at"]) if rec["merged_at"] else None
            window = _window_of(merged, cutoff_dt)
            if window:
                took = _secs(merged - created)
                kind = "comparable" if took <= 7 * _DAY else "backlog"
                for win in (window, "horizon"):
                    samples[win]["all"].append(took)
                    samples[win][kind].append(took)
            closed = parse_iso_utc(rec["closed_at"]) if rec["closed_at"] else None
            is_open = created < cutoff_dt and (closed is None or closed >= cutoff_dt)
            complete = rec["timeline_complete"]
            applied = set()
            if complete:
                totals, applied = _stage_intervals(rec, cutoff_dt)
                for label, secs in totals.items():
                    dwell.setdefault(label, []).append(secs)
                for kind, status, secs in _measure_attempts(rec, cutoff_dt):
                    if status == "measured":
                        counts[kind].append(secs)
                    elif status == "open":
                        counts["open"] += 1
                    else:
                        counts["superseded"] += 1
                for ev in rec["events"]:
                    key = _ACTIVITY_KEYS.get(ev["type"])
                    at = parse_iso_utc(ev["at"])
                    if key and horizon_start <= at < cutoff_dt and ev["actor_type"] in acts:
                        acts[ev["actor_type"]][key] += 1
            if is_open:
                earliest = min(applied, key=lambda l: (_stage_number(l), l)) if applied else None
                open_attention.append({
                    "repo": repo, "number": rec["number"], "url": rec["url"], "title": rec["title"],
                    "owner": rec["author"], "age_sec": _secs(cutoff_dt - created),
                    "earliest_unmet": earliest, "status": rec["status"],
                })
        merge_stats[repo] = {w: {k: _dist(v) for k, v in parts.items()} for w, parts in samples.items()}
        elapsed[repo] = merge_stats[repo]["horizon"]["all"]
        stage_dwell[repo] = {label: _dist(dwell[label]) for label in sorted(dwell)}
        handoff[repo] = {"requested": _dist(counts["requested"]), "readiness": _dist(counts["readiness"]),
                         "open_attempts": counts["open"], "superseded_attempts": counts["superseded"]}
        activity[repo] = acts
    open_attention.sort(key=lambda r: (-r["age_sec"], r["repo"], r["number"]))

    status = annotations["status"]
    metrics = {
        "cutoff": format_iso_utc(cutoff_dt),
        "repos": repos,
        "annotations_status": status,
        "health": health,
        "windows": {
            "w1": {"start": format_iso_utc(horizon_start), "end": format_iso_utc(cutoff_dt - timedelta(days=7))},
            "w2": {"start": format_iso_utc(cutoff_dt - timedelta(days=7)), "end": format_iso_utc(cutoff_dt)},
        },
        "merge_stats": merge_stats,
        "elapsed": elapsed,
        "stage_dwell": stage_dwell,
        "handoff": handoff,
        "user_activity": activity,
        "episode_labels": dict(annotations["labels"]) if status == "OK" else {},
        "open_attention": open_attention,
    }
    if usage is not None:
        metrics["usage"] = _usage_metrics(usage, usage_problems, records, cutoff_dt)
    return metrics



# --- render ---

_STAGES = (
    ("stage:0-spec", "Stage 0 (Spec)"),
    ("stage:1-code", "Stage 1 (Code)"),
    ("stage:2-evidence", "Stage 2 (Evidence)"),
    ("stage:3-review", "Stage 3 (Review)"),
    ("stage:4-ci", "Stage 4 (CI/Undraft)"),
    ("stage:5-approval", "Stage 5 (Approval)"),
)
_INCOMPLETE = "INCOMPLETE"


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return lines


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _dur(dist, key):
    """Duration cell for a Dist; a missing Dist or an empty sample is UNKNOWN."""
    return format_duration(dist.get(key) if dist else None)


def _n(dist):
    return dist["n"] if dist else "UNKNOWN"


def _render_usage(usage, cutoff):
    if usage is None:
        return ["", "Local agent usage: no feed configured"]
    out = ["", "### Local agent usage (observed on contributing machines)", ""]
    rows = [[_cell(repo if repo != "unattributed" else "unattributed (no repo)"), v["sessions"],
             format_duration(v["active_sec"]), v["tokens"]["output"],
             sum(v["tokens"][k] for k in ("input", "cache_read", "cache_write"))]
            for repo, v in usage["per_repo"].items()]
    if rows:
        out += _table(["Repository", "Sessions", "Agent time (summed)", "Output tokens",
                       "Input tokens (incl. cache)"], rows)
    else:
        out.append("No sessions in the window.")
    ages = []
    for name, m in usage["machines"].items():
        age = format_duration(max(0, int((parse_iso_utc(cutoff) - parse_iso_utc(m["generated_at"])).total_seconds())))
        ages.append("%s (feed age %s%s)" % (_cell(name), age, ", STALE" if m["stale"] else ""))
    un = usage["unattributed"]
    out += ["", "Contributing machines: %s." % ("; ".join(ages) or "none"),
            "Not attributed to any PR: %d sessions, %s active, %d output tokens."
            % (un["sessions"], format_duration(un["active_sec"]), un["output"]),
            "Feed problems: %s." % ("; ".join(_cell(p) for p in usage["problems"]) or "none"),
            "",
            "Active time is summed per session (gaps between logged events up to the idle gap), so parallel agent sessions add up and the total can exceed wall-clock time; tokens are from"
            " local session logs on contributing machines only; machines without a feed are not counted."]
    return out


def render(metrics):
    """Render the seven-section GitHub-flavored Markdown dashboard (pure and deterministic)."""
    repos = metrics.get("repos") or []
    health = metrics.get("health") or {}
    bad = [r for r in repos if not (health.get(r) or {}).get("ok")]
    windows = metrics.get("windows") or {}
    out = ["# PRW Metrics Dashboard", ""]
    out.append("**Data cutoff (UTC)**: %s" % metrics.get("cutoff", "UNKNOWN"))
    out.append("**Repositories**: %s" % (", ".join(repos) or "UNKNOWN"))
    for name, label in (("w1", "W1 (prior 7d)"), ("w2", "W2 (recent 7d)")):
        win = windows.get(name)
        if win:
            out.append("**%s**: [%s, %s)" % (label, win["start"], win["end"]))
    if bad:
        out.append("**Collection health**: %s for %d of %d repositories (%s)"
                   % (_INCOMPLETE, len(bad), len(repos), ", ".join(bad)))
    else:
        out.append("**Collection health**: OK for all %d repositories" % len(repos))

    def row_for(repo, cells):
        if repo in bad:
            return [repo] + [_INCOMPLETE] * len(cells)
        return [repo] + cells

    # 1 repo comparison
    out += ["", "## 1. Repository Comparison (W1 prior vs W2 recent)", ""]
    rows = []
    for repo in repos:
        stats = (metrics.get("merge_stats") or {}).get(repo) or {}
        for wname in ("w1", "w2"):
            win = stats.get(wname) or {}
            all_, comp, back = win.get("all"), win.get("comparable"), win.get("backlog")
            cells = [wname.upper(), _n(all_), _n(comp), _n(back),
                     _dur(all_, "p50"), _dur(all_, "p75"), _dur(all_, "p90")]
            rows.append([repo] + ([cells[0]] + [_INCOMPLETE] * 6 if repo in bad else cells))
    out += _table(["Repository", "Window", "Merged (all)", "Merged (<=7d)", "Backlog merged (>7d)",
                   "Median created->merged", "p75", "p90"], rows)

    # 2 stage dwell
    out += ["", "## 2. Stage Dwell (elapsed label time, p50 per PR)", ""]
    rows = []
    for repo in repos:
        dwell = (metrics.get("stage_dwell") or {}).get(repo) or {}
        rows.append(row_for(repo, [_dur(dwell.get(key), "p50") for key, _ in _STAGES]))
    out += _table(["Repository"] + [label for _, label in _STAGES], rows)

    # 3 time semantics
    out += ["", "## 3. Time Semantics", ""]
    rows = []
    for repo in repos:
        el = (metrics.get("elapsed") or {}).get(repo)
        rows.append(row_for(repo, [_n(el), _dur(el, "p50"), _dur(el, "p75"),
                                   "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"]))
    out += _table(["Repository", "Operation elapsed (n)", "Median", "p75", "Active wall time",
                   "Agent effort", "Waiting time", "Residual"], rows)
    out += _render_usage(metrics.get("usage"), metrics.get("cutoff"))

    # 4 handoff
    out += ["", "## 4. Handoff Delays (review requested/readiness -> review)", ""]
    rows = []
    for repo in repos:
        ho = (metrics.get("handoff") or {}).get(repo) or {}
        for key, label in (("requested", "Review request -> review"),
                           ("readiness", "Ready for review -> review")):
            d = ho.get(key)
            cells = [label, _n(d), _dur(d, "p50"), _dur(d, "p75"), _dur(d, "p90"),
                     ho.get("open_attempts", "UNKNOWN"), ho.get("superseded_attempts", "UNKNOWN")]
            rows.append([repo] + ([cells[0]] + [_INCOMPLETE] * 6 if repo in bad else cells))
    out += _table(["Repository", "Metric", "n", "Median", "p75", "p90", "Open attempts",
                   "Superseded attempts"], rows)

    # 5 user activity and episodes
    out += ["", "## 5. User Activity and Episodes", "",
            "User-login activity (includes agents acting as the user), counts in the last 14 days.", ""]
    rows = []
    for repo in repos:
        act = (metrics.get("user_activity") or {}).get(repo)
        cells = []
        for who in ("User", "Bot"):
            part = (act or {}).get(who)
            for k in ("comments", "reviews", "commits"):
                cells.append(part[k] if part else "UNKNOWN")
        rows.append(row_for(repo, cells))
    out += _table(["Repository", "User comments", "User reviews", "User commits",
                   "Bot comments", "Bot reviews", "Bot commits"], rows)
    out.append("")
    status = metrics.get("annotations_status")
    if status == "OK":
        labels = metrics.get("episode_labels") or {}
        counts = {k: 0 for k in ("good", "bad", "mixed")}
        for entry in labels.values():
            counts[entry.get("label")] = counts.get(entry.get("label"), 0) + 1
        out.append("Episode labels (from annotations): good %d, bad %d, mixed %d."
                   % (counts["good"], counts["bad"], counts["mixed"]))
    else:
        out.append("Episode labels: UNKNOWN (annotations %s)." % (status or "UNKNOWN"))

    # 6 open PR attention
    out += ["", "## 6. Open PR Attention", ""]
    rows = []
    for pr in metrics.get("open_attention") or []:
        repo = pr["repo"]
        rows.append([_cell(repo), "[#%s](%s)" % (pr["number"], pr["url"]), _cell(pr["title"]),
                     _cell(pr["owner"]), format_duration(pr.get("age_sec")),
                     _cell(pr.get("earliest_unmet") or "UNKNOWN"), _cell(pr.get("status") or "UNKNOWN"),
                     _INCOMPLETE if repo in bad else "OK"])
    if rows:
        out += _table(["Repository", "PR", "Title", "Owner", "Age", "Earliest unmet stage", "Status",
                       "Repo data"], rows)
    else:
        out.append("No open PRs at cutoff.")

    # 7 notes
    out += ["", "## 7. Notes", ""]
    for repo in repos:
        h = health.get(repo) or {}
        state = "OK" if h.get("ok") else "%s (%s)" % (_INCOMPLETE, h.get("error") or "no collection health")
        trunc = h.get("truncated_prs") or []
        out.append("- %s: collection %s, %s pages, %d PRs with truncated timelines%s"
                   % (repo, state, h.get("pages", "UNKNOWN"), len(trunc),
                      " (" + ", ".join("#%s" % n for n in trunc) + ")" if trunc else ""))
    out.append("- Annotations: %s." % (status or "UNKNOWN"))
    out += [
        "- INCOMPLETE repositories failed collection; their figures are withheld, not zero.",
        "- UNKNOWN means not observed; it is never zero. PRs whose timeline could not be fully read are"
        " excluded from timeline-derived metrics.",
        "- Comparable = merged within 7 days of creation; backlog = more than 7 days.",
        "- Stage dwell is label-event time (labeled to unlabeled), clipped to the 14-day horizon.",
        "- Handoff measures only attempts closed by a review before cutoff; open and superseded"
        " attempts are counted, not measured.",
        "- Operation elapsed is created-to-merged; active wall time, agent effort, waiting time and"
        " residual are not collected and stay UNKNOWN.",
        "- Telemetry retention, usage cost and web views were removed from this dashboard.",
    ]
    if metrics.get("usage") is not None:
        out.append("- Local agent usage is attributed to a PR only when the session branch equals the PR head"
                   " branch (and the repository matches when known); other sessions count per repository only.")
    return "\n".join(out) + "\n"


# --- publish ---

_README_PATH = "dashboards/prw/README.md"
_IDENTITY = ["-c", "user.name=prw-metrics", "-c", "user.email=prw-metrics@localhost"]


def _state_dir():
    return os.environ.get("PRW_METRICS_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "share", "prw-metrics-slim"
    )


_SSH_CONFIGURED = None  # per process: does the user already choose their own ssh (GIT_SSH_COMMAND, GIT_SSH, core.sshCommand)?


def _user_ssh_configured(cwd):
    global _SSH_CONFIGURED
    if _SSH_CONFIGURED is None:
        _SSH_CONFIGURED = bool(os.environ.get("GIT_SSH_COMMAND") or os.environ.get("GIT_SSH"))
        if not _SSH_CONFIGURED:
            try:
                done = subprocess.run(["git", "config", "--get", "core.sshCommand"], cwd=cwd, capture_output=True,
                                      text=True, timeout=5)
                _SSH_CONFIGURED = bool((done.stdout or "").strip())
            except (OSError, subprocess.TimeoutExpired):
                pass
    return _SSH_CONFIGURED


def _git(cwd, *args):
    env = dict(os.environ, LC_ALL="C", GIT_TERMINAL_PROMPT="0")  # LC_ALL: push-rejection detection matches English git output
    if not _user_ssh_configured(cwd):  # never override the user's own ssh setup; only add a no-prompt default
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o ConnectTimeout=20"
    try:
        timeout = float(os.environ.get("PRW_METRICS_GIT_TIMEOUT_SEC") or 120)
    except ValueError:
        timeout = 120
    try:
        return subprocess.run(["git", *_IDENTITY, *args], cwd=cwd, capture_output=True, text=True, env=env,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("git %s timed out" % args[0]) from None


def embeds_credentials(url):
    """True if a remote URL carries a secret: any user:pass@, or a bare token@ on an http(s)-style scheme."""
    url = url or ""
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://([^/]*)", url)
    if not m:
        user = re.match(r"^([^@/]*)@", url)
        return bool(user and ":" in user.group(1))
    if "@" not in m.group(2):
        return False
    user = m.group(2).rsplit("@", 1)[0]
    return ":" in user or m.group(1).lower().split("+")[-1] in ("http", "https")


def _push_once(clone, branch):
    return _git(clone, "push", "origin", "HEAD:refs/heads/%s" % branch)


def _stable(markdown):
    """Dashboard text without the per-run cutoff line (or a JSON feed without generated_at and window), so an unchanged file is detected."""
    try:
        doc = json.loads(markdown)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and "generated_at" in doc:
        doc.pop("generated_at")
        doc.pop("window", None)  # a rolling window moves every run; the sessions are the content
        return json.dumps(doc, sort_keys=True)
    return "\n".join(l for l in markdown.split("\n") if not l.startswith("**Data cutoff (UTC)**"))


def _heartbeat_due(old, new):
    """True when both texts are JSON feeds and `new` was generated at least HEARTBEAT_SEC after `old`, so an idle machine keeps looking alive."""
    try:
        return (parse_iso_utc(json.loads(new)["generated_at"]) - parse_iso_utc(json.loads(old)["generated_at"])
                ).total_seconds() >= HEARTBEAT_SEC
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def _publish_to_clone(markdown, remote, branch, clone, path, message):
    """Return 0 on success or no change; raise RuntimeError(message) on any git failure."""
    done = _git(clone, "clone", "--depth", "1", "--branch", branch, remote, ".")
    if done.returncode:
        raise RuntimeError("clone failed: " + done.stderr.strip())
    target = Path(clone, path)
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current is not None and _stable(current) == _stable(markdown) and not _heartbeat_due(current, markdown):
        print("no change")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    for step in (("add", "--", path), ("commit", "-m", message, "--", path)):
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
    print("published %s to %s" % (path, branch))
    return 0


def publish(markdown, remote, branch, fallback_path, *, path=_README_PATH,
            message="chore(prw-metrics): update PRW dashboard"):
    """Shallow-clone remote@branch, update `path` (default the dashboard), push. 0 ok/no change, 2 no remote, 3 failure."""
    if not remote:
        print("publish requested but no roadmap remote configured", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="prw-publish-") as clone:
        try:
            return _publish_to_clone(markdown, remote, branch, clone, path, message)
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
    p.add_argument("--usage-feed", action="append", default=[p for p in os.environ.get("PRW_METRICS_USAGE_FEEDS", "").split(":") if p],
                   help="local usage feed file or directory (repeatable; env PRW_METRICS_USAGE_FEEDS, colon-separated)")
    p.add_argument("--usage-remote", default=os.environ.get("PRW_METRICS_USAGE_REMOTE", ""),
                   help="git remote whose dashboards/prw/usage/*.json feeds are read (env PRW_METRICS_USAGE_REMOTE); feeds are read only when this or --usage-feed is given")
    p.add_argument("--annotations", default=os.path.join(_state_dir(), "annotations.json"))
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("no repos given (--repos or PRW_METRICS_REPOS)", file=sys.stderr)
        return 2
    if (args.publish and embeds_credentials(args.roadmap_remote)) or embeds_credentials(args.usage_remote):
        print("remotes must not embed credentials; use an SSH remote or a credential helper", file=sys.stderr)
        return 2
    if args.publish and not args.roadmap_remote:
        print("publish requested but no roadmap remote configured (--roadmap-remote)", file=sys.stderr)
        return 2
    cutoff = format_iso_utc(parse_iso_utc(args.cutoff) if args.cutoff else datetime.now(timezone.utc))
    runner = replay_runner(args.input_dir) if args.input_dir else gh_runner
    records, health = collect(repos, cutoff, runner)
    extra = {}
    if args.usage_feed or args.usage_remote:
        feeds, problems = load_usage_feeds(args.usage_feed, args.usage_remote or None, args.roadmap_branch,
                                           cutoff=cutoff)
        extra = {"usage": feeds, "usage_problems": problems}
    metrics = aggregate(records, health, load_annotations(args.annotations), cutoff, **extra)
    markdown = render(metrics)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    if not any(h["ok"] for h in health.values()):
        print("every repository failed collection; not publishing", file=sys.stderr)
        return 1
    if args.publish:
        fallback = args.output or os.path.join(_state_dir(), "last-dashboard.md")
        return publish(markdown, args.roadmap_remote, args.roadmap_branch, fallback)
    if not args.output:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
