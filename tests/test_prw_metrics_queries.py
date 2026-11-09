"""Focused contracts for the local PRW per-PR query layer."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.prw_metrics import aggregate_usage
from scripts.prw_metrics_queries import run_query

try:
    import duckdb
except ImportError:
    duckdb = None


@unittest.skipUnless(
    duckdb is not None, "DuckDB is installed in the query task environment"
)
class TestPRWMetricsQueries(unittest.TestCase):
    CUTOFF = "2026-11-09T03:34:00Z"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.events_path = self.root / "query_events.jsonl"
        self.prs_path = self.root / "pr_snapshots.jsonl"
        self.human_path = self.root / "human_summary.json"
        self.attempts_path = self.root / "review_attempts.jsonl"

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_jsonl(self, path, records):
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    @staticmethod
    def _event(event_id, pr, tokens, request_duration, *, cost="0.0001000"):
        token_values = list(tokens.values()) if tokens is not None else []
        total = (
            sum(token_values)
            if token_values and all(
                isinstance(value, int) and not isinstance(value, bool)
                and value >= 0
                for value in token_values
            )
            else 0 if tokens == {} else None
        )
        return {
            "event_id": event_id,
            "request_id_present": True,
            "provider": "anthropic",
            "model": "model-a",
            "timestamp": "2026-11-02T10:00:00Z",
            "session_id_hash": "sha256:session-a",
            "request_duration_seconds": request_duration,
            "tokens_by_bucket": tokens,
            "total_tokens": total,
            "token_complete": total is not None,
            "list_equivalent_cost_usd": cost,
            "observed_cost_usd": None,
            "cost_currency": "USD" if cost is not None else None,
            "cost_basis": "public model-list equivalent" if cost is not None else None,
            "price_catalog_version": "sha256:rate-card-a" if cost is not None else None,
            "cost_status": "priced" if cost is not None else "UNKNOWN_NO_RATE_CARD",
            "status": "priced" if cost is not None else "unknown",
            "unknown_buckets": {},
            "validated_attributions": [{
                "pr": pr,
                "weight": "1",
                "method": "direct",
                "basis": "separable_breakdown",
                "convention_ref": None,
                "receipt_refs": ["sha256:receipt-a"],
            }],
        }

    def _base_files(self, events=None, prs=None, human_summary=None, attempts=None):
        self._write_jsonl(self.events_path, events or [])
        self._write_jsonl(self.prs_path, prs or [])
        self.human_path.write_text(
            json.dumps(human_summary or {"coverage": {}, "per_pr": []}),
            encoding="utf-8",
        )
        self._write_jsonl(self.attempts_path, attempts or [])

    def _query(self):
        return run_query(
            events_path=self.events_path,
            pr_snapshots_path=self.prs_path,
            human_summary_path=self.human_path,
            attempt_observations_path=self.attempts_path,
            snapshot_at_utc=self.CUTOFF,
        )

    def test_one_row_per_pr_with_direct_tokens_and_source_reviewed_branch_counts(self):
        pr1 = "example-org/repo-alpha#1"
        pr2 = "example-org/repo-alpha#2"
        events = [
            self._event(
                "sha256:event-1", pr1,
                {"input_uncached": 10, "cache_read": 2, "cache_write_5m": 3,
                 "cache_write_1h": 0, "output": 5},
                1.0,
            ),
            self._event(
                "sha256:event-2", pr1,
                {"input_uncached": 30, "cache_read": 4, "cache_write_5m": 6,
                 "cache_write_1h": 0, "output": 20},
                3.0,
            ),
            self._event(
                "sha256:event-3", pr2,
                {"input_uncached": 40, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 60},
                5.0,
            ),
        ]
        prs = [
            {
                "repo": "example-org/repo-alpha", "number": 1, "state": "MERGED",
                "createdAt": "2026-11-02T00:00:00Z", "mergedAt": "2026-11-02T10:00:00Z",
                "closedAt": "2026-11-02T10:00:00Z", "headRefName": "feature/one",
                "headRefOid": "a1", "commit_shas": ["a1"],
            },
            {
                "repo": "example-org/repo-alpha", "number": 2, "state": "MERGED",
                "createdAt": "2026-10-24T08:00:00Z", "mergedAt": "2026-11-01T16:00:00Z",
                "closedAt": "2026-11-01T16:00:00Z", "headRefName": "feature/two",
                "headRefOid": "b2", "commit_shas": ["b2"],
            },
            {
                "repo": "example-org/repo-alpha", "number": 3, "state": "OPEN",
                "createdAt": "2026-11-01T00:00:00Z", "mergedAt": None, "closedAt": None,
                "headRefName": "feature/open", "headRefOid": "c3",
                "commit_shas": ["c3"],
            },
        ]
        human_summary = {
            "coverage": {
                "status": "OBSERVED_SCOPE_ONLY",
                "branch_metadata_coverage": "PARTIAL",
            },
            "per_pr": [
                {
                    "pr": pr1,
                    "raw_verified_messages": 3,
                    "direct_verified_messages": 2,
                    "branch_associated_verified_messages": 0,
                    "initial_requests": 1,
                    "verified_followup_messages": 2,
                    "followup_episodes": 1,
                    "episodes_by_quality": {
                        "good": 1, "bad": 0, "mixed": 0, "unknown": 0,
                    },
                    "association_basis": ["direct"],
                    "association_confidence": "direct",
                    "coverage_status": "OBSERVED_SCOPE_ONLY",
                },
                {
                    "pr": pr2,
                    "raw_verified_messages": 2,
                    "direct_verified_messages": 0,
                    "branch_associated_verified_messages": 2,
                    "initial_requests": 1,
                    "verified_followup_messages": 1,
                    "followup_episodes": 0,
                    "episodes_by_quality": {
                        "good": 0, "bad": 0, "mixed": 0, "unknown": 0,
                    },
                    "association_basis": ["repo_branch_unique"],
                    "association_confidence": "branch",
                    "coverage_status": "OBSERVED_SCOPE_ONLY",
                },
            ],
        }
        attempts = [
            {
                "repo": "example-org/repo-alpha", "pr_number": 1, "attempt_id": "a1",
                "transition": "review", "duration_seconds": 4.0,
                "basis": "observed attempt",
            },
            {
                "repo": "example-org/repo-alpha", "pr_number": 1, "attempt_id": "a2",
                "transition": "review", "duration_seconds": 8.0,
                "basis": "observed attempt",
            },
            {
                "repo": "example-org/repo-alpha", "pr_number": 2, "attempt_id": "b1",
                "transition": "review", "duration_seconds": 100.0,
                "basis": "observed attempt",
            },
        ]
        self._base_files(events, prs, human_summary, attempts)

        result = self._query()
        rows = result["pr_metrics"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {(row["repository"], row["pr_number"]) for row in rows},
            {("example-org/repo-alpha", 1), ("example-org/repo-alpha", 2),
             ("example-org/repo-alpha", 3)},
        )
        pr1_row = next(row for row in rows if row["pr_number"] == 1)
        self.assertEqual(pr1_row["pr_elapsed_seconds"], 36000.0)
        self.assertEqual(pr1_row["pr_elapsed_basis"], "MERGED_AT")
        self.assertEqual(pr1_row["direct_usage_observation_count"], 2)
        self.assertEqual(pr1_row["direct_association_method"], "direct")
        self.assertEqual(pr1_row["direct_association_basis"], "separable_breakdown")
        self.assertEqual(pr1_row["direct_uncached_input_tokens"], 40)
        self.assertEqual(pr1_row["direct_cache_read_input_tokens"], 6)
        self.assertEqual(pr1_row["direct_output_tokens"], 25)
        self.assertEqual(pr1_row["direct_total_tokens"], 80)
        self.assertEqual(pr1_row["verified_initial_human_message_count"], 1)
        self.assertEqual(pr1_row["verified_followup_human_message_count"], 2)
        self.assertEqual(pr1_row["reviewed_followup_episode_count"], 1)
        self.assertEqual(pr1_row["direct_request_total_tokens_average"], 40.0)
        self.assertEqual(pr1_row["direct_request_total_tokens_p50"], 20)
        self.assertEqual(pr1_row["direct_request_total_tokens_p90"], 60)
        self.assertEqual(pr1_row["direct_request_total_tokens_p99"], 60)
        self.assertEqual(pr1_row["direct_request_total_tokens_n"], 2)
        self.assertEqual(pr1_row["direct_request_duration_average_seconds"], 2.0)
        self.assertEqual(pr1_row["direct_request_duration_p50_seconds"], 1.0)
        self.assertEqual(pr1_row["direct_request_duration_p90_seconds"], 3.0)
        self.assertEqual(pr1_row["review_attempt_duration_average_seconds"], 6.0)
        self.assertEqual(pr1_row["review_attempt_duration_p50_seconds"], 4.0)
        self.assertEqual(pr1_row["review_attempt_duration_p90_seconds"], 8.0)
        self.assertEqual(pr1_row["review_attempt_duration_n"], 2)
        self.assertAlmostEqual(
            float(pr1_row["direct_list_equivalent_cost_amount"]), 0.0002
        )
        self.assertIsNone(pr1_row["observed_cost_amount"])
        self.assertIsNone(pr1_row["branch_uncached_input_tokens"])
        self.assertEqual(
            pr1_row["branch_usage_status"],
            "UNKNOWN_NO_CANONICAL_BRANCH_USAGE_ATTRIBUTION",
        )
        self.assertNotIn("pr_elapsed_p50", pr1_row)

        pr2_row = next(row for row in rows if row["pr_number"] == 2)
        self.assertEqual(pr2_row["branch_associated_verified_human_message_count"], 2)
        self.assertEqual(pr2_row["association_confidence"], "direct")
        self.assertEqual(pr2_row["human_association_confidence"], "branch")
        self.assertIsNone(pr2_row["branch_usage_observation_count"])
        self.assertIsNone(pr2_row["branch_uncached_input_tokens"])

        open_row = next(row for row in rows if row["pr_number"] == 3)
        self.assertEqual(open_row["pr_elapsed_basis"], "SNAPSHOT_AT_RIGHT_CENSORED")
        self.assertEqual(open_row["pr_elapsed_seconds"], 8 * 86400 + 3 * 3600 + 34 * 60)

        cohort = next(
            row for row in result["metric_cohorts"]
            if row["metric_family"] == "pr_elapsed"
            and row["cohort_definition"] == "all_14d_merges"
        )
        self.assertEqual(cohort["average"], (36000 + 720000) / 2)
        self.assertEqual(cohort["p50"], 36000)
        self.assertEqual(cohort["p90"], 720000)
        self.assertEqual(cohort["p99"], 720000)
        self.assertEqual(cohort["observation_n"], 2)
        self.assertEqual(cohort["distinct_pr_n"], 2)

        request_cohort = next(
            row for row in result["metric_cohorts"]
            if row["metric_family"] == "direct_request"
            and row["measure"] == "total_tokens"
            and row["cohort_definition"] == "all_14d_merges"
        )
        self.assertEqual(request_cohort["average"], 60.0)
        self.assertEqual(request_cohort["p50"], 60)
        self.assertEqual(request_cohort["p90"], 100)
        self.assertEqual(request_cohort["p99"], 100)
        self.assertEqual(request_cohort["observation_n"], 3)
        self.assertEqual(request_cohort["cohort_pr_n"], 2)
        self.assertEqual(request_cohort["distinct_pr_n"], 2)
        attempt_cohort = next(
            row for row in result["metric_cohorts"]
            if row["metric_family"] == "review_attempt"
            and row["measure"] == "attempt_duration_seconds"
            and row["cohort_definition"] == "all_14d_merges"
        )
        self.assertEqual(attempt_cohort["average"], (4 + 8 + 100) / 3)
        self.assertEqual(attempt_cohort["p50"], 8)
        self.assertEqual(attempt_cohort["p90"], 100)
        self.assertEqual(attempt_cohort["p99"], 100)
        self.assertEqual(attempt_cohort["observation_n"], 3)
        self.assertEqual(attempt_cohort["distinct_pr_n"], 2)
        self.assertEqual(result["query_coverage"]["canonical_event_n"], 3)
        self.assertEqual(result["query_coverage"]["missing_request_id_n"], 0)
        self.assertEqual(result["query_coverage"]["dedup_conflict_event_n"], 0)

    def test_complete_zero_unknown_and_empty_cohorts_remain_distinct(self):
        pr = "example-org/repo-empty#4"
        prs = [{
            "repo": "example-org/repo-empty", "number": 4, "state": "OPEN",
            "createdAt": "2026-11-01T00:00:00Z", "mergedAt": None, "closedAt": None,
        }]
        zero = self._event(
            "sha256:zero", pr,
            {"input_uncached": 0, "cache_read": 0, "cache_write_5m": 0,
             "cache_write_1h": 0, "output": 0},
            0.0,
            cost=None,
        )
        incomplete = self._event(
            "sha256:incomplete", pr,
            {"input_uncached": 0, "cache_read": None, "cache_write_5m": 0,
             "cache_write_1h": 0, "output": 0},
            None,
            cost=None,
        )
        incomplete["total_tokens"] = None
        incomplete["token_complete"] = False
        self._base_files([zero, incomplete], prs)

        row = self._query()["pr_metrics"][0]
        self.assertEqual(row["direct_usage_observation_count"], 2)
        self.assertEqual(row["direct_token_complete_observation_n"], 1)
        self.assertEqual(row["direct_request_total_tokens_n"], 1)
        self.assertEqual(row["direct_request_total_tokens_average"], 0.0)
        self.assertEqual(row["direct_request_total_tokens_p50"], 0)
        self.assertEqual(row["direct_request_total_tokens_p90"], 0)
        self.assertEqual(row["direct_request_total_tokens_p99"], 0)
        self.assertIsNone(row["observed_cost_amount"])
        self.assertEqual(row["cost_status"], "UNKNOWN_NO_RATE_CARD")

        empty = next(
            item for item in self._query()["metric_cohorts"]
            if item["metric_family"] == "review_attempt"
            and item["measure"] == "attempt_duration_seconds"
            and item["cohort_definition"] == "all_14d_merges"
        )
        self.assertEqual(empty["observation_n"], 0)
        self.assertIsNone(empty["average"])
        self.assertIsNone(empty["p50"])
        self.assertIsNone(empty["p90"])
        self.assertIsNone(empty["p99"])

    def test_source_ambiguous_branch_is_preserved_without_pr_token_allocation(self):
        pr = "example-org/repo-alpha#9"
        self._base_files(
            [],
            [{
                "repo": "example-org/repo-alpha", "number": 9, "state": "OPEN",
                "createdAt": "2026-11-01T00:00:00Z", "mergedAt": None, "closedAt": None,
                "headRefName": "main",
            }],
            {
                "coverage": {"status": "OBSERVED_SCOPE_ONLY"},
                "per_pr": [{
                    "pr": pr,
                    "raw_verified_messages": 2,
                    "direct_verified_messages": 0,
                    "branch_associated_verified_messages": 0,
                    "branch_associated_candidates": 2,
                    "initial_requests": 0,
                    "followup_episodes": 0,
                    "episodes_by_quality": {
                        "good": 0, "bad": 0, "mixed": 0, "unknown": 0,
                    },
                    "association_basis": ["repo_branch_multiple_candidates"],
                    "association_confidence": "ambiguous",
                    "coverage_status": "CANDIDATE_ONLY",
                }],
            },
        )

        result = self._query()
        row = result["pr_metrics"][0]
        self.assertEqual(row["association_confidence"], "ambiguous")
        self.assertEqual(row["branch_associated_candidates"], 2)
        self.assertEqual(row["branch_associated_verified_human_message_count"], 0)
        self.assertIsNone(row["branch_usage_observation_count"])
        self.assertIsNone(row["branch_total_tokens"])

    def test_conflicting_snapshot_rows_stay_one_unknown_pr_row(self):
        self._base_files(
            [],
            [
                {
                    "repo": "example-org/repo-alpha", "number": 11, "state": "OPEN",
                    "createdAt": "2026-11-01T00:00:00Z",
                    "mergedAt": None, "closedAt": None,
                    "headRefName": "feature/old", "headRefOid": "old",
                },
                {
                    "repo": "example-org/repo-alpha", "number": 11, "state": "OPEN",
                    "createdAt": "2026-11-02T00:00:00Z",
                    "mergedAt": None, "closedAt": None,
                    "headRefName": "feature/new", "headRefOid": "new",
                },
            ],
        )

        rows = self._query()["pr_metrics"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metadata_coverage"], "CONFLICT")
        self.assertIsNone(rows[0]["head_branch"])
        self.assertIsNone(rows[0]["created_at_utc"])
        self.assertIsNone(rows[0]["pr_elapsed_seconds"])

    def test_canonical_aggregate_event_export_feeds_query_without_rereading_raw_usage(
        self,
    ):
        receipt = "sha256:" + ("d" * 64)
        pr = "example-org/repo-alpha#12"
        aggregate = aggregate_usage([
            {
                "provider": "anthropic", "sku": "model-a", "usage_id": "req-query",
                "timestamp": "2026-11-08T20:00:00Z", "session_id": "session-query",
                "input_tokens": 10, "cache_read_tokens": 2, "cache_write_5m_tokens": 0,
                "cache_write_1h_tokens": 0, "output_tokens": 3,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard",
                "attributions": [{
                    "pr": pr, "weight": 1, "method": "direct",
                    "basis": "separable_breakdown", "receipt_refs": [receipt],
                    "has_rationale": True,
                }],
            },
        ], [])
        self._base_files(
            aggregate["query_events"],
            [{
                "repo": "example-org/repo-alpha", "number": 12, "state": "MERGED",
                "createdAt": "2026-11-08T19:00:00Z", "mergedAt": "2026-11-08T21:00:00Z",
                "closedAt": "2026-11-08T21:00:00Z", "headRefName": "feature/query",
                "headRefOid": "d12", "commit_shas": ["d12"],
            }],
        )

        row = self._query()["pr_metrics"][0]
        self.assertEqual(row["direct_usage_observation_count"], 1)
        self.assertEqual(row["direct_total_tokens"], 15)
        self.assertEqual(row["direct_token_complete_observation_n"], 1)
        self.assertEqual(row["cost_status"], "UNKNOWN_NO_RATE_CARD")
        self.assertIsNone(row["list_equivalent_cost_amount"])
        self.assertIsNone(row["observed_cost_amount"])


if __name__ == "__main__":
    unittest.main()
