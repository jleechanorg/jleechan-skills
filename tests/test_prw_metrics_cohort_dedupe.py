"""One observation per (PR, stage, interval); an empty W2 cohort stays empty (PR #742 r11)."""

import unittest
from datetime import datetime, timezone

from scripts.prw_metrics import DashboardRenderer, MetricsAggregator, _project_summary

REPO = "o/r"
STAGE = "stage:1-coding"
CUTOFF = datetime(2026, 11, 8, tzinfo=timezone.utc)


def _pr(number, merged="2026-11-07T00:00:00Z", **kw):
    return dict({"repo": REPO, "number": number, "state": "MERGED", "createdAt": "2026-11-01T00:00:00Z",
                 "mergedAt": merged, "labels": []}, **kw)


def _label_events(number, start, end, tag):
    base = {"repo": REPO, "pr_number": number, "label": STAGE}
    return [
        dict(base, id=f"{tag}-l", event="labeled", createdAt=start),
        dict(base, id=f"{tag}-u", event="unlabeled", createdAt=end),
    ]


class TestStageDwellDedupe(unittest.TestCase):
    def _row(self, prs, events):
        rows = MetricsAggregator(cutoff_dt=CUTOFF).compute_stage_dwell(prs, timeline_events=events)
        return next(r for r in rows if r["stage"] == STAGE)

    def test_transition_and_timeline_for_same_interval_count_once(self):
        transition = {"stage": STAGE, "start_at": "2026-11-05T10:00:00Z", "end_at": "2026-11-05T12:00:00Z"}
        prs = [_pr(1), _pr(2, stage_transitions=[transition])]
        events = (
            _label_events(1, "2026-11-04T00:00:00Z", "2026-11-04T06:00:00Z", "a")
            + _label_events(2, "2026-11-05T10:00:00Z", "2026-11-05T12:00:00Z", "b")
        )
        row = self._row(prs, events)
        self.assertEqual(row["median_h"], 4.0)
        self.assertEqual((row["n"], row["total_n"]), (2, 2))

    def test_duplicate_timeline_evidence_counts_once(self):
        prs = [_pr(1), _pr(2)]
        events = (
            _label_events(1, "2026-11-04T00:00:00Z", "2026-11-04T06:00:00Z", "a")
            + _label_events(2, "2026-11-05T10:00:00Z", "2026-11-05T12:00:00Z", "b")
            + _label_events(2, "2026-11-05T10:00:00Z", "2026-11-05T12:00:00Z", "b-dup")
        )
        self.assertEqual(self._row(prs, events)["median_h"], 4.0)

    def test_distinct_intervals_on_one_pr_are_kept(self):
        prs = [_pr(1)]
        events = (
            _label_events(1, "2026-11-04T00:00:00Z", "2026-11-04T02:00:00Z", "a")
            + _label_events(1, "2026-11-05T00:00:00Z", "2026-11-05T06:00:00Z", "b")
        )
        self.assertEqual(self._row(prs, events)["median_h"], 4.0)

    def test_repoless_timeline_event_reconciles_with_transition(self):
        transition = {"stage": STAGE, "start_at": "2026-11-05T10:00:00Z", "end_at": "2026-11-05T12:00:00Z"}
        events = [dict(e, repo=None) for e in _label_events(2, "2026-11-05T10:00:00Z", "2026-11-05T12:00:00Z", "b")]
        row = self._row([_pr(1), _pr(2, stage_transitions=[transition])], events)
        self.assertEqual(row["n"], 1)


class TestEmptyW2Cohort(unittest.TestCase):
    def _summary(self):
        prs = [
            _pr(1, merged="2026-10-29T00:00:00Z", initial_task_accepted_at="2026-10-27T00:00:00Z"),
            dict(_pr(2, merged=None), state="OPEN", mergedAt=None, createdAt="2026-11-05T00:00:00Z"),
        ]
        return MetricsAggregator(cutoff_dt=CUTOFF).aggregate_full_dataset(prs=prs, now_dt=CUTOFF)

    def test_historical_prs_are_not_substituted(self):
        summary = self._summary()
        self.assertEqual(summary["w2_merged_cohort_n"], 0)
        for row in summary["handoffs"]:
            self.assertEqual((row["observed_n"], row["total_n"], row["status"]), (0, 0, "UNKNOWN"), row["name"])
        for row in summary["stage_dwell"]:
            self.assertEqual((row["n"], row["total_n"]), (0, 0), row["stage"])
        self.assertEqual(summary["time_semantics_pilot"], [])

    def test_render_says_no_merges_in_window(self):
        md = DashboardRenderer().render(self._summary())
        self.assertIn("No merges in window W2", md)

    def test_summary_schema_keeps_cohort_size(self):
        self.assertEqual(_project_summary(self._summary())["w2_merged_cohort_n"], 0)

    def test_non_empty_cohort_has_no_empty_note(self):
        prs = [_pr(1, merged="2026-11-07T00:00:00Z", initial_task_accepted_at="2026-11-06T00:00:00Z")]
        summary = MetricsAggregator(cutoff_dt=CUTOFF).aggregate_full_dataset(prs=prs, now_dt=CUTOFF)
        self.assertEqual(summary["w2_merged_cohort_n"], 1)
        self.assertNotIn("No merges in window W2", DashboardRenderer().render(summary))


if __name__ == "__main__":
    unittest.main()
