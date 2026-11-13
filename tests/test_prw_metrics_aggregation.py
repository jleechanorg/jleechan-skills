"""Aggregation and collection regressions for PR #742 review items B6, B8-B11."""

import json
import subprocess
import unittest
from datetime import datetime, timezone
from unittest import mock

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator

ALPHA = "a/repo"
BETA = "b/repo"


def _task_event(repo, number):
    ev = {
        "event_type": "task_accepted",
        "event_id": f"ev-{repo}-{number}",
        "occurred_at": "2026-11-01T00:00:00Z",
    }
    if repo is not None:
        ev["repo"] = repo
    if number is not None:
        ev["pr_number"] = number
    return ev


class TestB6ExactRepoIdentity(unittest.TestCase):
    def test_collision_foreign_repoless_and_prless_events(self):
        agg = MetricsAggregator(cutoff_dt=datetime(2026, 11, 7, tzinfo=timezone.utc))
        prs = [
            {"repo": ALPHA, "number": 42, "state": "MERGED", "mergedAt": "2026-11-06T00:00:00Z"},
            {"repo": BETA, "number": 42, "state": "MERGED", "mergedAt": "2026-11-06T00:00:00Z"},
        ]
        events = [
            _task_event(ALPHA, 42),
            _task_event("foreign/repo", 42),
            _task_event(None, 42),
            _task_event(ALPHA, None),
        ]
        data = agg.aggregate_full_dataset(prs=prs, time_semantics_pilot=events, now_dt=agg.cutoff_dt)
        with_task = [r for r in data["time_semantics_pilot"] if r.get("task_elapsed_sec") is not None]
        self.assertEqual(len(with_task), 1)
        self.assertEqual(with_task[0]["task_elapsed_sec"], 432000.0)
        self.assertIn(f"{ALPHA}/pull/42", json.dumps(with_task[0]))
        self.assertNotIn(f"{BETA}/pull/42", json.dumps(with_task[0]))

    def test_repo_less_event_alone_fabricates_nothing(self):
        agg = MetricsAggregator(cutoff_dt=datetime(2026, 11, 7, tzinfo=timezone.utc))
        prs = [{"repo": BETA, "number": 42, "state": "MERGED", "mergedAt": "2026-11-06T00:00:00Z"}]
        data = agg.aggregate_full_dataset(prs=prs, time_semantics_pilot=[_task_event(None, 42)], now_dt=agg.cutoff_dt)
        for row in data["time_semantics_pilot"]:
            self.assertIsNone(row.get("task_elapsed_sec"))


class TestB8HandoffDedupeAcrossSources(unittest.TestCase):
    def _pr(self, **extra):
        pr = {
            "repo": ALPHA,
            "number": 1,
            "headRefOid": "sha1",
            "evidence_ready_at": "2026-11-05T10:00:00Z",
            "review_requested_at": "2026-11-05T11:00:00Z",
        }
        pr.update(extra)
        return pr

    def _receipt(self, **extra):
        rec = {
            "name": "evidence_ready -> review_requested",
            "repo": ALPHA,
            "number": 1,
            "candidate_sha": "sha1",
            "attempt_number": 1,
            "source_receipt": "r1",
            "duration_sec": 3600.0,
        }
        rec.update(extra)
        return rec

    def _row(self, prs, records):
        data = MetricsAggregator().compute_handoff_breakdown(prs, handoff_records=records, total_cohort_n=len(prs))
        return next(r for r in data if r["name"] == "evidence_ready -> review_requested")

    def test_pr_field_and_same_receipt_count_once(self):
        row = self._row([self._pr()], [self._receipt()])
        self.assertEqual(row["observed_n"], 1)
        self.assertEqual(row["sample_n"], 1)
        self.assertEqual(row["total_n"], 1)

    def test_additional_attempts_add_samples_not_coverage(self):
        records = [self._receipt(attempt_number=2, duration_sec=7200.0, source_receipt="r2")]
        row = self._row([self._pr()], records)
        self.assertEqual(row["sample_n"], 2)
        self.assertEqual(row["observed_n"], 1)
        self.assertEqual(row["status"], "COMPLETE")

    def test_duplicates_do_not_complete_a_larger_cohort(self):
        prs = [self._pr(), {"repo": ALPHA, "number": 2, "headRefOid": "sha2"}]
        row = self._row(prs, [self._receipt(), self._receipt()])
        self.assertEqual(row["observed_n"], 1)
        self.assertEqual(row["total_n"], 2)
        self.assertEqual(row["status"], "PARTIAL")


class TestB9DotCoverage(unittest.TestCase):
    STRUCTURED = {
        "origin": "dot_history",
        "message_ids": ["m1"],
        "timestamp": "2026-11-05T10:00:00Z",
        "episode_id": "e1",
    }
    TAIL = {"origin": "dot_page_tail", "episode_id": "t1"}

    def _coverage(self, episodes, agg=None):
        agg = agg or MetricsAggregator()
        return agg.compute_human_interventions(episodes)["channel_coverage"]["dot_history"]

    def test_excluded_origin_with_partial_tail_stays_partial(self):
        out = MetricsAggregator().compute_human_interventions([self.STRUCTURED, self.TAIL])
        self.assertEqual(out["raw_human_messages"], 0)
        self.assertEqual(out["unverified_origin_excluded"], 1)
        self.assertEqual(out["channel_coverage"]["dot_history"], "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS")

    def test_unaudited_adapter_is_not_tested(self):
        self.assertEqual(self._coverage([self.STRUCTURED]), "UNTESTED_ADAPTER_PENDING")

    def test_verified_structured_row_is_tested(self):
        class Verified(MetricsAggregator):
            VERIFIED_HUMAN_ORIGINS = MetricsAggregator.VERIFIED_HUMAN_ORIGINS | {"dot_history"}

        self.assertEqual(self._coverage([self.STRUCTURED], Verified()), "TESTED_CONNECTOR_OK")

    def test_verified_structured_plus_tail_stays_partial(self):
        class Verified(MetricsAggregator):
            VERIFIED_HUMAN_ORIGINS = MetricsAggregator.VERIFIED_HUMAN_ORIGINS | {"dot_history"}

        self.assertEqual(
            self._coverage([self.STRUCTURED, self.TAIL], Verified()),
            "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS",
        )


class TestB10UnsupportedHandoffIdentity(unittest.TestCase):
    def _breakdown(self, prs, records):
        return {
            r["name"]: r
            for r in MetricsAggregator().compute_handoff_breakdown(prs, handoff_records=records, total_cohort_n=len(prs))
        }

    def test_scalar_without_candidate_or_attempt_is_unknown(self):
        prs = [{"repo": ALPHA, "number": 1, "headRefOid": "sha1"}]
        records = [
            {"name": "task_accepted -> merged", "repo": ALPHA, "number": 1, "duration_sec": 3600.0},
            {
                "name": "task_accepted -> merged", "repo": ALPHA, "number": 1,
                "duration_sec": 3600.0, "source_receipt": "r1",
            },
            {
                "name": "task_accepted -> merged", "repo": ALPHA, "number": 1,
                "candidate_sha": "sha1", "duration_sec": 3600.0, "source_receipt": "r1",
            },
        ]
        row = self._breakdown(prs, records)["task_accepted -> merged"]
        self.assertEqual(row["observed_n"], 0)
        self.assertEqual(row["status"], "UNKNOWN")

    def test_timestamp_without_authority_facts_is_unknown(self):
        pr = {
            "repo": ALPHA, "number": 1,
            "authority_ready_at": "2026-11-05T00:00:00Z", "mergedAt": "2026-11-06T00:00:00Z",
        }
        self.assertEqual(MetricsAggregator().derive_authority_ready(pr), "UNKNOWN")
        row = self._breakdown([pr], None)["authority_ready -> merged"]
        self.assertEqual(row["status"], "UNKNOWN")

    def test_authority_facts_make_interval_observable(self):
        pr = {
            "repo": ALPHA, "number": 1, "final_ready": True, "merge_authority": True,
            "authority_ready_at": "2026-11-05T00:00:00Z", "mergedAt": "2026-11-06T00:00:00Z",
        }
        row = self._breakdown([pr], None)["authority_ready -> merged"]
        self.assertEqual(row["median_sec"], 86400.0)


class TestB11TimelineFailurePropagates(unittest.TestCase):
    PR = {"number": 5, "state": "open", "head": {"sha": "s5"}, "created_at": "2099-01-01T00:00:00Z"}

    def _collect(self, run):
        collector = Collector(repos=[ALPHA])
        with mock.patch("scripts.prw_metrics.subprocess.run", side_effect=run):
            return collector.collect_all(
                fetch_page_fn=lambda repo, page, per_page: [dict(self.PR, repo=repo)] if page == 1 else []
            )

    @staticmethod
    def _proc(code, out="", err=""):
        return subprocess.CompletedProcess(args=[], returncode=code, stdout=out, stderr=err)

    def _assert_partial(self, res):
        self.assertEqual(res["status"], "PARTIAL_FAILURE")
        self.assertEqual(res["sources"][f"{ALPHA}:timeline"]["status"], "PARTIAL_FAILURE")
        self.assertEqual(res["sources"][ALPHA]["status"], "PARTIAL_FAILURE")

    def test_first_page_failure(self):
        res = self._collect(lambda *a, **k: self._proc(1, err="boom"))
        self._assert_partial(res)
        self.assertEqual(res["timeline"], [])

    def test_later_page_failure_drops_truncated_timeline(self):
        page_one = json.dumps([{"event": "labeled", "created_at": "2026-11-05T00:00:00Z"}] * 100)
        calls = []

        def run(cmd, *a, **k):
            calls.append(cmd)
            return self._proc(0, out=page_one) if len(calls) == 1 else self._proc(1, err="rate limited")

        res = self._collect(run)
        self._assert_partial(res)
        self.assertEqual(res["timeline"], [])

    def test_malformed_response(self):
        self._assert_partial(self._collect(lambda *a, **k: self._proc(0, out="<html>")))
        self._assert_partial(self._collect(lambda *a, **k: self._proc(0, out='{"message": "x"}')))

    def test_partial_status_renders(self):
        res = self._collect(lambda *a, **k: self._proc(1))
        summary = MetricsAggregator().aggregate_full_dataset(prs=res["prs"], sources=res["sources"])
        self.assertIn("PARTIAL_FAILURE", DashboardRenderer().render(summary))


if __name__ == "__main__":
    unittest.main()
