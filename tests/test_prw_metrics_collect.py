import copy
import json
from pathlib import Path

from scripts import prw_metrics as m

FIXTURES = Path(__file__).parent / "fixtures" / "prw"
REPO = "example-org/example-repo"
CUTOFF = m.parse_iso_utc("2026-11-15T00:00:00Z")


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def params(args):
    """Turn gh-style ['-f', 'k=v', ...] arguments into a dict."""
    return dict(a.split("=", 1) for a in args if "=" in a)


class FakeRunner:
    """Serves fixture pages: the open query gets `open_pages`, the updated query `updated_pages`.

    Within a query, pages are served by cursor: no cursor is the first page and cursor
    `cursor_of[i]` (the previous page's endCursor) is page i+1.
    """

    def __init__(self, updated_pages, open_pages):
        self.updated = updated_pages
        self.open = open_pages
        self.calls = []

    def __call__(self, args):
        p = params(args)
        self.calls.append(p)
        pages = self.open if "is:open" in p["search"] else self.updated
        cursor = p.get("cursor")
        if not cursor:
            return pages[0]
        for index, page in enumerate(pages[:-1]):
            if page["data"]["search"]["pageInfo"]["endCursor"] == cursor:
                return pages[index + 1]
        raise AssertionError("unknown cursor %r" % cursor)


def fixture_runner():
    return FakeRunner(
        [load("graphql_page1.json"), load("graphql_page2.json")], [load("open_stale_pr.json")]
    )


def user(login, typename="User"):
    return {"login": login, "__typename": typename}


def synthetic_pr(number, timeline, author="alice-dev", **extra):
    node = {
        "__typename": "PullRequest",
        "number": number,
        "url": "https://github.com/%s/pull/%d" % (REPO, number),
        "title": "[working] synthetic %d" % number,
        "createdAt": "2026-11-01T00:00:00Z",
        "mergedAt": None,
        "closedAt": None,
        "isDraft": False,
        "author": user(author),
        "labels": {"nodes": []},
        "timelineItems": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": timeline,
        },
    }
    node.update(extra)
    return node


def page_of(*nodes):
    return {
        "data": {
            "search": {
                "issueCount": len(nodes),
                "pageInfo": {"hasNextPage": False, "endCursor": "END"},
                "nodes": list(nodes),
            }
        }
    }


def requested(reviewer, at):
    return {
        "__typename": "ReviewRequestedEvent",
        "createdAt": at,
        "actor": user("alice-dev"),
        "requestedReviewer": user(reviewer),
    }


def ready(at):
    return {"__typename": "ReadyForReviewEvent", "createdAt": at, "actor": user("alice-dev")}


def reviewed(reviewer, at, typename="User"):
    return {
        "__typename": "PullRequestReview",
        "submittedAt": at,
        "author": user(reviewer, typename),
        "state": "COMMENTED",
    }


def collect_attempts(*timeline):
    runner = FakeRunner([page_of(synthetic_pr(9, list(timeline)))], [page_of()])
    records, health = m.collect([REPO], CUTOFF, runner)
    assert health[REPO]["ok"]
    return records[0]["attempts"]


def consistent_page(page):
    page["data"]["search"]["issueCount"] = len(page["data"]["search"]["nodes"])
    return page


def test_search_truncation_marks_repo_not_ok():
    page = load("graphql_page2.json")  # issueCount 5 but only 2 nodes and no next page
    records, health = m.collect([REPO], CUTOFF, FakeRunner([page], [page_of()]))
    assert health[REPO]["ok"] is False
    assert "search truncated" in health[REPO]["error"]


def test_collect_normalizes_graphql_page():
    runner = FakeRunner([consistent_page(load("graphql_page2.json"))], [page_of()])
    records, health = m.collect([REPO], CUTOFF, runner)
    expected = {r["number"]: r for r in load("records_fixture.json")}
    assert [r["number"] for r in records] == [101, 102]
    for record in records:
        assert record == expected[record["number"]]
    assert health[REPO] == {"ok": True, "pages": 2, "truncated_prs": [], "error": None}


def test_collect_follows_pagination():
    runner = fixture_runner()
    records, health = m.collect([REPO], CUTOFF, runner)
    cursors = [c.get("cursor") for c in runner.calls if "is:open" not in c["search"]]
    assert cursors == [None, "CURSOR_PAGE_1"]
    assert {r["number"] for r in records} >= {101, 102, 103, 104, 105}
    assert health[REPO]["pages"] == 3


def test_timeline_truncation_recorded_in_health():
    page = load("truncated_timeline.json")
    records, health = m.collect([REPO], CUTOFF, FakeRunner([page], [page]))
    assert [r["number"] for r in records] == [107]
    assert records[0]["timeline_complete"] is False
    assert health[REPO]["truncated_prs"] == [107]
    assert health[REPO]["ok"] is True


def test_stale_open_pr_collected():
    runner = fixture_runner()
    records, _ = m.collect([REPO], CUTOFF, runner)
    stale = next(r for r in records if r["number"] == 100)
    assert stale["merged_at"] is None and stale["closed_at"] is None
    assert stale["created_at"] < "2026-11-01T00:00:00Z"
    updated_search = next(c["search"] for c in runner.calls if "is:open" not in c["search"])
    assert "updated:>=2026-11-01" in updated_search


def test_overlapping_queries_deduplicated():
    records, _ = m.collect([REPO], CUTOFF, fixture_runner())
    numbers = [r["number"] for r in records]
    assert numbers == sorted(set(numbers)) == [100, 101, 102, 103, 104, 105]


def test_requested_attempts_per_reviewer():
    attempts = collect_attempts(
        requested("reviewer-one", "2026-11-02T00:00:00Z"),
        reviewed("reviewer-one", "2026-11-02T05:00:00Z"),
    )
    assert attempts == [
        {
            "key": "reviewer-one@2026-11-02T00:00:00Z",
            "kind": "requested",
            "reviewer": "reviewer-one",
            "opened_at": "2026-11-02T00:00:00Z",
            "closed_at": "2026-11-02T05:00:00Z",
            "closed_reason": "review",
            "closed_by": "reviewer-one",
        }
    ]


def test_readiness_attempt_without_request():
    attempts = collect_attempts(
        ready("2026-11-02T00:00:00Z"), reviewed("review-bot", "2026-11-02T01:00:00Z", "Bot")
    )
    assert len(attempts) == 1
    assert attempts[0]["kind"] == "readiness"
    assert attempts[0]["key"] == "*@2026-11-02T00:00:00Z"
    assert attempts[0]["reviewer"] is None
    assert attempts[0]["closed_by"] == "review-bot"


def test_multiple_reviewers_independent_attempts():
    attempts = collect_attempts(
        requested("reviewer-one", "2026-11-02T00:00:00Z"),
        requested("reviewer-two", "2026-11-02T01:00:00Z"),
        reviewed("reviewer-two", "2026-11-02T02:00:00Z"),
    )
    by_reviewer = {a["reviewer"]: a for a in attempts}
    assert by_reviewer["reviewer-one"]["closed_at"] is None
    assert by_reviewer["reviewer-one"]["closed_reason"] is None
    assert by_reviewer["reviewer-two"]["closed_reason"] == "review"


def test_repeated_request_closes_prior_attempt():
    attempts = collect_attempts(
        requested("reviewer-one", "2026-11-02T00:00:00Z"),
        requested("reviewer-one", "2026-11-03T00:00:00Z"),
    )
    first, second = attempts
    assert first["closed_at"] == "2026-11-03T00:00:00Z"
    assert second["opened_at"] == "2026-11-03T00:00:00Z"
    assert second["closed_at"] is None


def test_one_review_closes_requested_and_readiness_attempts():
    attempts = collect_attempts(
        ready("2026-11-02T00:00:00Z"),
        requested("reviewer-one", "2026-11-02T00:00:00Z"),
        reviewed("reviewer-one", "2026-11-02T04:00:00Z"),
    )
    assert [a["kind"] for a in attempts] == ["readiness", "requested"]
    assert {a["closed_at"] for a in attempts} == {"2026-11-02T04:00:00Z"}
    assert {a["closed_by"] for a in attempts} == {"reviewer-one"}


def test_superseded_attempt_has_closed_reason_superseded():
    attempts = collect_attempts(
        ready("2026-11-02T00:00:00Z"),
        ready("2026-11-03T00:00:00Z"),
        reviewed("reviewer-one", "2026-11-03T02:00:00Z"),
    )
    first, second = attempts
    assert (first["closed_reason"], first["closed_by"]) == ("superseded", None)
    assert first["closed_at"] == "2026-11-03T00:00:00Z"
    assert (second["closed_reason"], second["closed_by"]) == ("review", "reviewer-one")


def test_collect_matches_records_fixture():
    records, _ = m.collect([REPO], CUTOFF, fixture_runner())
    assert records == load("records_fixture.json")


def test_parse_operational_title_status():
    parse = m.parse_operational_title
    assert parse("[Waiting][review requested] Add cache layer") == "waiting"
    assert parse("  [blocked] x") == "blocked"
    assert parse("[ready] [await merge] y") == "ready"
    assert parse("[weird] y") is None
    assert parse("no brackets [working]") is None
    assert parse("") is None
