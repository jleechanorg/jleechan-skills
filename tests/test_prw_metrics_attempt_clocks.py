"""Review clocks never combine across attempts; operation basis is rendered (PR #742 r9)."""

import unittest
from datetime import datetime, timezone

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator, _project_summary

REPO = "o/r"
HEAD = "a1" * 20
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def _snap(updated, **kw):
    pr = {"repo": REPO, "number": 3, "headRefOid": HEAD, "state": "MERGED", "updatedAt": updated,
          "createdAt": "2026-11-05T00:00:00Z", "mergedAt": "2026-11-06T00:00:00Z"}
    pr.update(kw)
    return Collector().normalize_pr_record(pr, default_repo=REPO)


class TestAttemptClocks(unittest.TestCase):
    def _merge(self, *snaps):
        (pr,) = Collector().deduplicate_prs(list(snaps))
        return pr

    def _pickup_row(self, pr):
        rows = MetricsAggregator(cutoff_dt=NOW).compute_handoff_breakdown([pr], total_cohort_n=1)
        return next(r for r in rows if r["name"] == "review_requested -> actual_review_started")

    def test_attempt_two_missing_request_stays_unknown(self):
        a1 = _snap("2026-11-05T10:00:00Z", attempt=1, review_requested_at="2026-11-05T10:00:00Z")
        a2 = _snap("2026-11-05T12:00:00Z", attempt=2, actual_review_started_at="2026-11-05T12:00:00Z")
        pr = self._merge(a1, a2)
        self.assertIsNone(pr["review_requested_at"])
        row = self._pickup_row(pr)
        self.assertEqual(row["status"], "UNKNOWN")
        self.assertEqual(row["observed_n"], 0)

    def test_partial_winner_without_attempt_ids_is_not_filled_field_by_field(self):
        old = _snap("2026-11-05T10:00:00Z", review_requested_at="2026-11-05T10:00:00Z")
        new = _snap("2026-11-05T12:00:00Z", actual_review_started_at="2026-11-05T12:00:00Z")
        pr = self._merge(old, new)
        self.assertIsNone(pr["review_requested_at"])
        self.assertEqual(self._pickup_row(pr)["status"], "UNKNOWN")

    def test_same_attempt_snapshots_are_merged(self):
        a = _snap("2026-11-05T10:00:00Z", attempt=2, review_requested_at="2026-11-05T11:00:00Z")
        b = _snap("2026-11-05T12:00:00Z", attempt=2, actual_review_started_at="2026-11-05T12:00:00Z")
        pr = self._merge(a, b)
        self.assertEqual(self._pickup_row(pr)["median_sec"], 3600.0)

    def test_refresh_without_clocks_inherits_whole_set_from_same_head(self):
        cached = _snap(
            "2026-11-05T10:00:00Z", attempt=1, review_requested_at="2026-11-05T10:00:00Z",
            actual_review_started_at="2026-11-05T10:30:00Z",
        )
        live = _snap("2026-11-05T12:00:00Z")
        pr = self._merge(cached, live)
        self.assertEqual(pr["review_requested_at"], "2026-11-05T10:00:00Z")
        self.assertEqual(pr["attempt"], 1)
        self.assertEqual(self._pickup_row(pr)["median_sec"], 1800.0)


class TestOperationBasisRendering(unittest.TestCase):
    def _summary(self, events):
        pr = {"repo": REPO, "number": 1, "state": "MERGED", "createdAt": "2026-11-05T09:00:00Z", "mergedAt": "2026-11-05T14:00:00Z"}
        return MetricsAggregator(cutoff_dt=NOW).aggregate_full_dataset(prs=[pr], time_semantics_pilot=events, now_dt=NOW)

    def _op(self, **kw):
        return dict({"repo": REPO, "pr_number": 1, "span_kind": "observed_operation_elapsed"}, **kw)

    def test_basis_label_rendered_next_to_duration(self):
        cases = {
            "TIMED_UNION": [self._op(start_at="2026-11-05T10:00:00Z", end_at="2026-11-05T11:00:00Z")],
            "DURATION_ONLY_SUM": [self._op(duration_sec=60.0)],
            "TIMED_UNION_PLUS_DURATION_ONLY_SUM": [
                self._op(start_at="2026-11-05T10:00:00Z", end_at="2026-11-05T11:00:00Z"), self._op(duration_sec=60.0)
            ],
        }
        for basis, events in cases.items():
            summary = self._summary(events)
            self.assertIn(f"({basis})", DashboardRenderer().render(summary), basis)
            projected = _project_summary(summary)
            self.assertEqual(projected["time_semantics_pilot"][0]["operation_elapsed_basis"], basis)

    def test_unknown_duration_has_no_label(self):
        md = DashboardRenderer().render(self._summary([self._op(duration_sec=-1)]))
        self.assertNotIn("BASIS UNKNOWN", md)


if __name__ == "__main__":
    unittest.main()
