import json
from pathlib import Path

from scripts import prw_metrics as m

FIXTURES = Path(__file__).parent / "fixtures" / "prw"
CUTOFF = "2026-11-14T00:00:00Z"
REPO = "org/repo"
HEALTH = {REPO: {"ok": True, "pages": 1, "truncated_prs": [], "error": None}}
ABSENT = {"labels": {}, "status": "ABSENT"}
HOUR = 3600
DAY = 86400


def pr(number, created="2026-11-01T00:00:00Z", merged=None, **over):
    record = {
        "repo": REPO, "number": number, "url": "https://example.test/%d" % number,
        "title": "[working] t%d" % number, "author": "dev", "author_type": "User",
        "created_at": created, "merged_at": merged, "closed_at": merged, "is_draft": False,
        "labels": [], "status": "working", "timeline_complete": True, "events": [], "attempts": [],
    }
    record.update(over)
    return record


def event(kind, at, actor_type="User", **extra):
    return dict({"type": kind, "at": at, "actor": "x", "actor_type": actor_type}, **extra)


def attempt(opened, closed, reason, kind="requested"):
    return {"key": "k@" + opened, "kind": kind, "reviewer": None if kind == "readiness" else "r",
            "opened_at": opened, "closed_at": closed, "closed_reason": reason,
            "closed_by": "r" if reason == "review" else None}


def run(records, health=HEALTH, annotations=ABSENT):
    return m.aggregate(records, health, annotations, CUTOFF)


def test_half_open_window_boundaries():
    records = [
        pr(1, "2026-11-06T00:00:00Z", "2026-11-07T00:00:00Z"),  # exactly cutoff-7d -> W2
        pr(2, "2026-10-30T00:00:00Z", "2026-10-31T00:00:00Z"),  # exactly cutoff-14d -> W1
        pr(3, "2026-11-12T00:00:00Z", "2026-11-14T00:00:00Z"),  # exactly cutoff -> excluded
    ]
    stats = run(records)["merge_stats"][REPO]
    assert (stats["w1"]["all"]["n"], stats["w2"]["all"]["n"], stats["horizon"]["all"]["n"]) == (1, 1, 2)


def test_backlog_partition_7d():
    records = [
        pr(1, "2026-11-01T00:00:00Z", "2026-11-08T00:00:00Z"),  # exactly 7d -> comparable
        pr(2, "2026-11-01T00:00:00Z", "2026-11-08T00:00:01Z"),  # 7d + 1s -> backlog
    ]
    h = run(records)["merge_stats"][REPO]["horizon"]
    assert (h["all"]["n"], h["comparable"]["n"], h["backlog"]["n"]) == (2, 1, 1)
    assert h["comparable"]["p50"] == 7 * DAY and h["backlog"]["p50"] == 7 * DAY + 1


def test_handoff_uses_attempts_only():
    reviews_only = pr(1, events=[event("review_requested", "2026-11-10T00:00:00Z", reviewer="r"),
                                 event("review", "2026-11-10T01:00:00Z")])
    assert run([reviews_only])["handoff"][REPO]["requested"]["n"] == 0
    with_attempt = pr(2, attempts=[attempt("2026-11-10T00:00:00Z", "2026-11-10T02:00:00Z", "review")])
    requested = run([with_attempt])["handoff"][REPO]["requested"]
    assert requested["n"] == 1 and requested["p50"] == 2 * HOUR


def test_unobserved_interval_is_none_not_zero():
    metrics = run([])
    empty = {"n": 0, "p50": None, "p75": None, "p90": None, "p99": None}
    assert metrics["elapsed"][REPO] == empty
    assert metrics["handoff"][REPO]["requested"] == empty
    assert metrics["merge_stats"][REPO]["w2"]["comparable"] == empty
    assert metrics["stage_dwell"][REPO] == {}


def test_stage_dwell_from_label_events():
    events = [
        event("labeled", "2026-11-10T00:00:00Z", label="stage:1-code"),
        event("unlabeled", "2026-11-10T06:00:00Z", label="stage:1-code"),
        event("labeled", "2026-11-11T00:00:00Z", label="stage:1-code"),
        event("unlabeled", "2026-11-11T03:00:00Z", label="stage:1-code"),
        event("labeled", "2026-11-12T00:00:00Z", label="stage:4-ci"),  # still applied, open PR
        event("labeled", "2026-10-01T00:00:00Z", label="stage:0-spec"),  # clipped to horizon start
    ]
    dwell = run([pr(1, "2026-10-01T00:00:00Z", events=sorted(events, key=lambda e: e["at"]))])["stage_dwell"][REPO]
    assert dwell["stage:1-code"]["n"] == 1 and dwell["stage:1-code"]["p50"] == 9 * HOUR
    assert dwell["stage:4-ci"]["p50"] == 2 * DAY
    assert dwell["stage:0-spec"]["p50"] == 14 * DAY
    assert "stage:2-evidence" not in dwell


def test_stage_ignores_title():
    record = pr(1, title="[working][stage:3-review] titled only", labels=["stage:3-review"])
    metrics = run([record])
    assert metrics["stage_dwell"][REPO] == {}
    assert metrics["open_attention"][0]["earliest_unmet"] is None


def test_open_attention_earliest_unmet():
    events = [event("labeled", "2026-11-10T00:00:00Z", label="stage:3-review"),
              event("labeled", "2026-11-11T00:00:00Z", label="stage:1-code")]
    records = [
        pr(1, "2026-11-10T00:00:00Z", events=events),
        pr(2, "2026-10-01T00:00:00Z"),
        pr(3, "2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"),  # merged, not open
        pr(4, "2026-11-13T00:00:00Z", status="blocked"),
    ]
    rows = run(records)["open_attention"]
    assert [r["number"] for r in rows] == [2, 1, 4]
    assert [r["earliest_unmet"] for r in rows] == [None, "stage:1-code", None]
    assert rows[0]["age_sec"] == 44 * DAY and rows[0]["owner"] == "dev"
    assert rows[2]["status"] == "blocked"


def test_incomplete_health_propagates():
    health = {REPO: {"ok": True, "pages": 2, "truncated_prs": [1], "error": None},
              "org/broken": {"ok": False, "pages": 0, "truncated_prs": [], "error": "boom"}}
    record = pr(1, "2026-11-08T00:00:00Z", "2026-11-09T00:00:00Z", timeline_complete=False,
                events=[event("comment", "2026-11-09T00:00:00Z"),
                        event("labeled", "2026-11-08T00:00:00Z", label="stage:1-code")],
                attempts=[attempt("2026-11-08T00:00:00Z", "2026-11-08T01:00:00Z", "review")])
    metrics = run([record], health)
    assert metrics["health"] == health
    assert metrics["repos"] == ["org/broken", REPO]
    assert metrics["merge_stats"][REPO]["w2"]["all"]["n"] == 1
    assert metrics["elapsed"][REPO]["n"] == 1
    assert metrics["handoff"][REPO]["requested"]["n"] == 0
    assert metrics["handoff"][REPO]["open_attempts"] == 0
    assert metrics["stage_dwell"][REPO] == {}
    assert metrics["user_activity"][REPO]["User"]["comments"] == 0


def test_user_activity_split_by_actor_type():
    events = [
        event("comment", "2026-11-10T00:00:00Z", "User"),
        event("comment", "2026-11-10T01:00:00Z", "Bot"),
        event("review", "2026-11-10T02:00:00Z", "Bot"),
        event("commit", "2026-10-31T00:00:00Z", "User"),  # start inclusive
        event("commit", "2026-10-30T23:59:59Z", "User"),  # before horizon
        event("labeled", "2026-11-10T03:00:00Z", "User", label="x"),  # not activity
    ]
    activity = run([pr(1, events=sorted(events, key=lambda e: e["at"]))])["user_activity"][REPO]
    assert activity["User"] == {"comments": 1, "reviews": 0, "commits": 1}
    assert activity["Bot"] == {"comments": 1, "reviews": 1, "commits": 0}


def test_annotations_absent_means_unknown():
    metrics = run([pr(1)])
    assert metrics["annotations_status"] == "ABSENT"
    assert metrics["episode_labels"] == {}


def test_invalid_annotations_set_status_and_unknown():
    metrics = run([pr(1)], annotations={"labels": {}, "status": "INVALID"})
    assert metrics["annotations_status"] == "INVALID"
    assert metrics["episode_labels"] == {}


def test_aggregate_matches_golden():
    records = json.loads((FIXTURES / "records_fixture.json").read_text())
    golden = json.loads((FIXTURES / "metrics_golden.json").read_text())
    got = m.aggregate(records, golden["health"], {"labels": {}, "status": "ABSENT"}, golden["cutoff"])
    assert got == golden


def test_open_attempts_counted_not_measured():
    records = [pr(1, attempts=[
        attempt("2026-11-10T00:00:00Z", None, None),
        attempt("2026-11-11T00:00:00Z", "2026-11-14T00:00:00Z", "review"),  # review at cutoff -> open
        attempt("2026-10-01T00:00:00Z", "2026-11-10T00:00:00Z", "review"),  # opened before range
    ])]
    handoff = run(records)["handoff"][REPO]
    assert handoff["open_attempts"] == 2 and handoff["requested"]["n"] == 0


def test_superseded_attempts_counted_not_measured():
    records = [pr(1, attempts=[
        attempt("2026-11-10T00:00:00Z", "2026-11-11T00:00:00Z", "superseded"),
        attempt("2026-11-12T00:00:00Z", "2026-11-14T00:00:00Z", "superseded", kind="readiness"),
    ])]
    handoff = run(records)["handoff"][REPO]
    assert handoff["superseded_attempts"] == 1
    assert handoff["requested"]["n"] == 0 and handoff["readiness"]["n"] == 0


def test_events_after_cutoff_ignored():
    record = pr(1, "2026-11-12T00:00:00Z", events=[
        event("labeled", "2026-11-13T00:00:00Z", label="stage:3-review"),
        event("unlabeled", "2026-11-14T06:00:00Z", label="stage:3-review"),
        event("comment", "2026-11-14T00:00:00Z"),
        event("commit", "2026-11-15T00:00:00Z"),
    ], attempts=[attempt("2026-11-13T00:00:00Z", "2026-11-14T01:00:00Z", "review")])
    metrics = run([record])
    assert metrics["stage_dwell"][REPO]["stage:3-review"]["p50"] == DAY
    assert metrics["user_activity"][REPO]["User"] == {"comments": 0, "reviews": 0, "commits": 0}
    assert metrics["handoff"][REPO]["open_attempts"] == 1
    assert metrics["handoff"][REPO]["requested"]["n"] == 0
    assert metrics["open_attention"][0]["earliest_unmet"] == "stage:3-review"
