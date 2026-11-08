"""Ledger exempt statuses and pilot/episode scope (PR #742 round 6, P1-1/P1-2)."""

import unittest
from datetime import datetime, timedelta, timezone

from scripts.prw_metrics import MetricsAggregator, format_iso_utc, parse_pr_body_record

LEDGER = """| Obligation | Required by | Status | Receipt | Candidate applicability |
|---|---|---|---|---|
| Source review quorum | Selected route | PASS | https://example.com/q | Current |
| Evidence review (/er) | Selected route | {er} | exemption | Reason |
| Visual approval | Changed claims | {visual} | none | Reason |
| CI and conflicts | Repo policy | PENDING | none | Current |
"""


class TestLedgerStatuses(unittest.TestCase):
    def _unmet(self, er, visual):
        return parse_pr_body_record(LEDGER.format(er=er, visual=visual)).get("earliest_unmet_obligation")

    def test_not_required_is_exempt(self):
        self.assertEqual(self._unmet("NOT REQUIRED", "NOT REQUIRED"), "CI and conflicts")

    def test_documented_terminal_statuses_normalize(self):
        self.assertEqual(self._unmet("`not  required`", "N/A"), "CI and conflicts")
        self.assertEqual(self._unmet("PASS", "pass"), "CI and conflicts")

    def test_unfinished_and_unlisted_statuses_stay_unmet(self):
        for status in ("OPEN", "PENDING", "FAILED", "UNAVAILABLE", "SUPERSEDED", "NOT_REQUIRED", "WAIVED"):
            self.assertEqual(self._unmet(status, "PASS"), "Evidence review (/er)", status)


CUTOFF = datetime(2026, 11, 7, tzinfo=timezone.utc)
W1_START = CUTOFF - timedelta(days=14)
REPO = "o/r"
PR = {"repo": REPO, "number": 1, "state": "MERGED", "createdAt": "2026-11-05T09:00:00Z", "mergedAt": "2026-11-05T14:00:00Z"}


def _ev(repo, n, ts, **kw):
    return dict({"repo": repo, "pr_number": n, "span_kind": "observed_operation_elapsed",
                 "occurred_at": ts, "duration_sec": 60.0, "event_id": f"{repo}-{n}-{ts}"}, **kw)


class TestPilotScope(unittest.TestCase):
    def _rows(self, events, prs=None, repos=None):
        agg = MetricsAggregator(cutoff_dt=CUTOFF, repos=repos)
        out = agg.aggregate_full_dataset(prs=prs if prs is not None else [PR], time_semantics_pilot=events, now_dt=CUTOFF)
        return out["time_semantics_pilot"]

    def test_out_of_scope_repo_never_synthesized(self):
        rows = self._rows([_ev("other/repo", 9, "2026-11-05T10:00:00Z"), _ev(REPO, 1, "2026-11-05T10:00:00Z")])
        self.assertEqual([r["pr_url"] for r in rows], ["https://github.com/o/r/pull/1"])

    def test_2020_and_2099_events_excluded(self):
        rows = self._rows([_ev(REPO, 1, "2020-01-01T00:00:00Z"), _ev(REPO, 1, "2099-01-01T00:00:00Z")])
        self.assertEqual(rows, [])

    def test_exact_window_boundaries(self):
        rows = self._rows([
            _ev(REPO, 1, format_iso_utc(W1_START - timedelta(seconds=1))),
            _ev(REPO, 2, format_iso_utc(W1_START)),
            _ev(REPO, 3, format_iso_utc(CUTOFF - timedelta(seconds=1))),
            _ev(REPO, 4, format_iso_utc(CUTOFF)),
        ])
        self.assertEqual(sorted(r["pr_url"][-1] for r in rows), ["2", "3"])

    def test_repoless_events_dropped(self):
        self.assertEqual(self._rows([_ev(None, 1, "2026-11-05T10:00:00Z")]), [])

    def test_configured_repo_with_zero_prs_keeps_its_events_and_episodes(self):
        events = [_ev(REPO, 5, "2026-11-05T10:00:00Z")]
        self.assertEqual(len(self._rows(events, prs=[], repos=[REPO])), 1)
        agg = MetricsAggregator(cutoff_dt=CUTOFF, repos=[REPO])
        ep = {"episode_id": "e", "message_id": "m", "origin": "human", "timestamp": "2026-11-05T10:00:00Z",
              "repo": REPO, "label": "good", "pr_attribution": "unassigned"}
        out = agg.aggregate_full_dataset(prs=[], human_episodes=[ep], now_dt=CUTOFF)
        self.assertEqual(out["human_interventions"]["qualifying_episodes"], 1)

    def test_configured_scope_overrides_pr_set_repos(self):
        rows = self._rows([_ev("other/repo", 1, "2026-11-05T10:00:00Z")], repos=["other/repo"])
        self.assertEqual(len(rows), 1)


HEAD = "a1" * 20
OLD = "b2" * 20
BODY = """| Obligation | Required by | Status | Receipt | Candidate applicability |
|---|---|---|---|---|
| Old required gate | Route | PENDING | https://example.com/old | Current |

```text
candidate: {cand}
owner: lane-x
```
"""
SHA_TABLE = """| Obligation | Status | Receipt | Candidate SHA |
|---|---|---|---|
| Old gate | PENDING | https://example.com/old | {old} |
| New gate | PENDING | https://example.com/new | {new} |
| Shared gate | PENDING | https://example.com/shared | affected |
"""


class TestCandidateApplicability(unittest.TestCase):
    def test_mismatched_record_candidate_voids_ledger_and_execution_fields(self):
        self.assertEqual(parse_pr_body_record(BODY.format(cand=OLD[:7]), HEAD), {})

    def test_matching_record_candidate_keeps_ledger(self):
        out = parse_pr_body_record(BODY.format(cand=HEAD[:7]), HEAD)
        self.assertEqual(out["earliest_unmet_obligation"], "Old required gate")
        self.assertEqual(out["receipt_links"], ["https://example.com/old"])
        self.assertEqual(out["owner"], "lane-x")

    def test_record_without_candidate_keeps_ledger(self):
        out = parse_pr_body_record(BODY.format(cand="<head-SHA>"), HEAD)
        self.assertEqual(out["earliest_unmet_obligation"], "Old required gate")

    def test_row_sha_column_is_respected_per_row(self):
        out = parse_pr_body_record(SHA_TABLE.format(old=OLD[:12], new=HEAD[:12]), HEAD)
        self.assertEqual(out["earliest_unmet_obligation"], "New gate")
        self.assertEqual(out["receipt_links"], ["https://example.com/new", "https://example.com/shared"])

    def test_rows_for_another_head_are_not_applicable(self):
        out = parse_pr_body_record(SHA_TABLE.format(old=OLD[:12], new=OLD[:9]), HEAD)
        self.assertEqual(out["earliest_unmet_obligation"], "Shared gate")
        self.assertEqual(out["receipt_links"], ["https://example.com/shared"])
        only_stale = SHA_TABLE.format(old=OLD[:12], new=OLD[:9]).replace("| affected |", "| " + OLD[:8] + " |")
        self.assertEqual(parse_pr_body_record(only_stale, HEAD), {})


if __name__ == "__main__":
    unittest.main()
