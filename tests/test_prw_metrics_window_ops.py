"""Mixed operation accounting and episode window/repo scope (PR #742 round 5, P1-1/P1-2)."""

import unittest
from datetime import datetime, timedelta, timezone

from scripts.prw_metrics import MetricsAggregator, format_iso_utc

REPO = "o/r"
PR = {"repo": REPO, "number": 1, "createdAt": "2026-11-05T09:00:00Z", "mergedAt": "2026-11-05T14:00:00Z"}


def _op(**kw):
    return dict({"repo": REPO, "pr_number": 1, "span_kind": "observed_operation_elapsed"}, **kw)


class TestOperationAccounting(unittest.TestCase):
    def _ts(self, events):
        return MetricsAggregator().compute_time_semantics(PR, pilot_events=events)

    def test_timed_plus_duration_only_is_labelled_sum(self):
        out = self._ts([
            _op(start_at="2026-11-05T10:00:00Z", end_at="2026-11-05T11:00:00Z"),
            _op(duration_sec=60.0),
        ])
        self.assertEqual(out["observed_operation_elapsed_sec"], 3660.0)
        self.assertEqual(out["operation_elapsed_basis"], "TIMED_UNION_PLUS_DURATION_ONLY_SUM")

    def test_timed_only_and_duration_only_only(self):
        timed = self._ts([_op(start_at="2026-11-05T10:00:00Z", end_at="2026-11-05T11:00:00Z")])
        self.assertEqual((timed["observed_operation_elapsed_sec"], timed["operation_elapsed_basis"]), (3600.0, "TIMED_UNION"))
        untimed = self._ts([_op(duration_sec=60), _op(duration_sec=30)])
        self.assertEqual((untimed["observed_operation_elapsed_sec"], untimed["operation_elapsed_basis"]), (90.0, "DURATION_ONLY_SUM"))

    def test_overlapping_timed_ops_are_unioned(self):
        out = self._ts([
            _op(start_at="2026-11-05T10:00:00Z", end_at="2026-11-05T11:00:00Z"),
            _op(start_at="2026-11-05T10:30:00Z", end_at="2026-11-05T11:30:00Z"),
        ])
        self.assertEqual(out["observed_operation_elapsed_sec"], 5400.0)

    def test_negative_and_non_finite_durations_are_unknown(self):
        for bad in (-5.0, float("nan"), float("inf"), "60", True, None):
            out = self._ts([_op(duration_sec=bad)])
            self.assertIsNone(out["observed_operation_elapsed_sec"], bad)
            self.assertIsNone(out["operation_elapsed_basis"], bad)
        active = self._ts([{"repo": REPO, "pr_number": 1, "span_kind": "observed_active_execution", "duration_sec": -1}])
        self.assertIsNone(active["agent_effort_sec"])
        self.assertIsNone(MetricsAggregator().compute_time_semantics(PR, pilot_events=[
            _op(occurred_at="2026-11-05T10:00:00Z", duration_sec=float("nan"))
        ])["observed_operation_elapsed_sec"])


CUTOFF = datetime(2026, 11, 7, tzinfo=timezone.utc)
W1_START = CUTOFF - timedelta(days=14)


def _ep(i, ts, **kw):
    return dict({"episode_id": f"e{i}", "message_id": f"m{i}", "origin": "human", "timestamp": ts,
                 "label": "good", "pr_attribution": "unassigned"}, **kw)


class TestEpisodeScope(unittest.TestCase):
    def _summary(self, episodes):
        prs = [dict(PR, state="MERGED")]
        agg = MetricsAggregator(cutoff_dt=CUTOFF)
        return agg.aggregate_full_dataset(prs=prs, human_episodes=episodes, now_dt=CUTOFF)["human_interventions"]

    def test_exact_window_boundaries(self):
        episodes = [
            _ep(1, format_iso_utc(W1_START - timedelta(seconds=1))),
            _ep(2, format_iso_utc(W1_START)),
            _ep(3, format_iso_utc(CUTOFF - timedelta(seconds=1))),
            _ep(4, format_iso_utc(CUTOFF)),
            _ep(5, "2020-01-01T00:00:00Z"),
            _ep(6, "2099-01-01T00:00:00Z"),
        ]
        out = self._summary(episodes)
        self.assertEqual(out["qualifying_episodes"], 2)
        self.assertEqual(out["raw_human_messages"], 2)

    def test_repo_scope(self):
        inside = format_iso_utc(CUTOFF - timedelta(days=1))
        out = self._summary([
            _ep(1, inside, repo=REPO),
            _ep(2, inside, repo="other/repo"),
            _ep(3, inside),
        ])
        self.assertEqual(out["qualifying_episodes"], 2)

    def test_unplaceable_non_dot_episode_is_excluded_but_dot_tail_still_flags_coverage(self):
        out = self._summary([
            {"episode_id": "x", "origin": "human", "label": "good"},
            {"episode_id": "t", "origin": "dot_page_tail"},
        ])
        self.assertEqual(out["qualifying_episodes"], 0)
        self.assertEqual(out["dot_page_tail_partial_count"], 1)

    def test_out_of_window_dot_row_does_not_claim_coverage(self):
        row = {"episode_id": "d", "origin": "dot_history", "message_ids": ["m"], "timestamp": "2020-01-01T00:00:00Z"}
        out = self._summary([row])
        self.assertNotEqual(out["channel_coverage"]["dot_history"], "TESTED_CONNECTOR_OK")


if __name__ == "__main__":
    unittest.main()
