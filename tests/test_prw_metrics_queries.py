"""Focused contracts for the local PRW per-PR query layer."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.prw_metrics import (
    _merge_pr_branch_metadata, aggregate_usage, load_rate_table,
    render_prw_query_summary,
)
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
        self.catalog_path = self.root / "rate_catalog.json"

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

    def _query_with_catalog(self, catalog):
        self.catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        return run_query(
            events_path=self.events_path,
            pr_snapshots_path=self.prs_path,
            snapshot_at_utc=self.CUTOFF,
            human_summary_path=self.human_path,
            attempt_observations_path=self.attempts_path,
            rate_catalog_path=self.catalog_path,
        )

    def test_catalog_scenarios_use_exact_model_protocol_tiers_and_unknowns(self):
        prs = [
            {"repo": "example-org/repo-alpha", "number": n, "state": "OPEN",
             "createdAt": "2026-11-01T00:00:00Z", "mergedAt": None, "closedAt": None}
            for n in (21, 22, 23, 24)
        ]
        event1 = {
            **self._event("sha256:catalog-1", "example-org/repo-alpha#21",
                {"input_uncached": 512000, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 1000}, 1, cost=None),
            "provider": "anthropic", "model": "MiniMax-M3",
        }
        event2 = {
            **self._event("sha256:catalog-2", "example-org/repo-alpha#22",
                {"input_uncached": 512001, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 1000}, 1, cost=None),
            "provider": "anthropic", "model": "MiniMax-M3",
        }
        event3 = {
            **self._event("sha256:catalog-3", "example-org/repo-alpha#23",
                {"input_uncached": 10, "cache_read": 2, "cache_write_5m": 4,
                 "cache_write_1h": 0, "output": 3}, 1, cost=None),
            "provider": "anthropic", "model": "MiniMax-M3.1-Flash",
            "validated_attributions": [{
                "pr": "example-org/repo-alpha#23", "weight": "1",
                "method": "convention",
            }],
            "branch_attributions": [{
                "pr": "example-org/repo-alpha#23", "weight": "1",
                "basis": "repo_branch_unique", "confidence": "low",
            }],
        }
        event4 = {
            **self._event("sha256:catalog-4", "example-org/repo-alpha#24",
                {"input_uncached": 256000, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 1000}, 1, cost=None),
            "provider": "anthropic", "model": "MiniMax-M3",
        }
        mismatch = {
            **self._event("sha256:mismatch", "example-org/repo-alpha#21",
                {"input_uncached": 1, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 1}, 1, cost=None),
            "provider": "openai", "model": "MiniMax-M3",
        }
        unpriced = {
            **self._event("sha256:unpriced", "example-org/repo-alpha#22",
                {"input_uncached": 1, "cache_read": 0, "cache_write_5m": 0,
                 "cache_write_1h": 0, "output": 1}, 1, cost=None),
            "provider": "anthropic", "model": "unknown-model",
        }
        self._base_files([event1, event2, event3, event4, mismatch, unpriced], prs)
        catalog = {
            "schema_version": 1, "retrieved_at_utc": "2026-11-09T06:45:27Z",
            "basis": "current_provider_published_standard_public_api_rate",
            "rates": [
                {"model_id": "MiniMax-M3", "model_vendor": "MiniMax",
                 "source_protocol": "anthropic", "status": "priced_with_context_tiers",
                 "tiers": [
                    {"condition": "prompt_input_tokens <= 512000",
                     "input_uncached": 0.45, "cache_read": 0.09,
                     "cache_write_5m": None, "cache_write_1h": None, "output": 1.8},
                    {"condition": "prompt_input_tokens > 512000",
                     "input_uncached": 0.9, "cache_read": 0.18,
                     "cache_write_5m": None, "cache_write_1h": None, "output": 3.6},
                 ]},
                {"model_id": "MiniMax-M3.1-Flash", "model_vendor": "MiniMax",
                 "source_protocol": "anthropic", "status": "priced_flat",
                 "input_uncached": 0.15, "cache_read": 0.015,
                 "cache_write_5m": None, "cache_write_1h": None, "output": 0.6},
                {"model_id": "unknown-model", "model_vendor": None,
                 "source_protocol": "anthropic", "status": "unpriced"},
            ],
        }

        result = self._query_with_catalog(catalog)
        rows = result["catalog_scenario_pr_metrics"]
        minimax = [
            row for row in rows
            if row["model_id"] == "MiniMax-M3" and row["price_tier"] != "UNKNOWN"
        ]
        self.assertEqual(len(minimax), 3)
        self.assertEqual(
            {row["price_tier"] for row in minimax},
            {"prompt_input_tokens <= 512000", "prompt_input_tokens > 512000"},
        )
        self.assertTrue(all(row["scenario_status"] == "COMPLETE" for row in minimax))
        self.assertTrue(all(row["observed_cost_usd"] is None for row in minimax))
        first_pr = next(row for row in minimax if row["pr"].endswith("#21"))
        self.assertEqual(first_pr["token_totals_by_bucket"]["input_uncached"], "512000")
        self.assertTrue(all(row["catalog_version"] == "2026-11-09T06:45:27Z"
                            for row in minimax))
        other = [row for row in rows if row["model_id"] == "MiniMax-M3.1-Flash"]
        self.assertEqual({row["attribution_method"] for row in other},
                         {"convention", "branch_associated"})
        self.assertEqual(
            {row["association_confidence"] for row in other}, {None, "low"}
        )
        self.assertTrue(all(row["scenario_status"] == "PARTIAL_UNKNOWN_COMPONENTS"
                            for row in other))
        self.assertTrue(all(row["scenario_cost_usd"] is None for row in other))
        self.assertTrue(
            all(row["unknown_buckets"] == ["cache_write_5m"] for row in other),
            repr([row["unknown_buckets"] for row in other]),
        )
        unknown = [row for row in rows if row["price_tier"] == "UNKNOWN"]
        self.assertEqual(len(unknown), 2)
        self.assertEqual(
            {row["scenario_status"] for row in unknown},
            {"UNKNOWN_NO_EXACT_MODEL_PROTOCOL_RATE", "UNKNOWN_UNPRICED_MODEL"},
        )
        self.assertTrue(all(row["scenario_cost_usd"] is None for row in unknown))
        self.assertTrue(all(row["known_component_subtotal_usd"] is None
                            for row in unknown))
        cohorts = result["catalog_scenario_cohorts"]
        self.assertEqual(len(cohorts), 2)
        lower_tier = next(row for row in cohorts
                          if row["price_tier"] == "prompt_input_tokens <= 512000")
        self.assertEqual(lower_tier["observation_n"], 2)
        self.assertAlmostEqual(float(lower_tier["average"]), 0.1746)
        self.assertAlmostEqual(float(lower_tier["p50"]), 0.117)
        self.assertAlmostEqual(float(lower_tier["p90"]), 0.2322)
        self.assertAlmostEqual(float(lower_tier["p99"]), 0.2322)
    def test_catalog_context_boundaries_use_native_prompt_totals(self):
        records = []
        prs = []
        specifications = [
            ("anthropic", "claude-haiku-5-5", 99999, 1, 0, 0, 0,
             "prompt_input_tokens <= 100000"),
            ("anthropic", "claude-haiku-5-5", 100000, 1, 0, 0, 0,
             "prompt_input_tokens > 100000"),
            ("openai", "gpt-6-sol", 272000, 0, 0, 0, 0,
             "prompt_input_tokens <= 272000"),
            ("openai", "gpt-6-sol", 272001, 0, 0, 0, 0,
             "prompt_input_tokens > 272000"),
        ]
        for i, (protocol, model, uncached, cache_read, write_5m, write_1h,
                output, expected_tier) in enumerate(specifications, 31):
            pr = f"example-org/repo-alpha#{i}"
            records.append({
                **self._event(
                    f"sha256:tier-{i}", pr,
                    {"input_uncached": uncached, "cache_read": cache_read,
                     "cache_write_5m": write_5m, "cache_write_1h": write_1h,
                     "output": output}, 1, cost=None,
                ),
                "provider": protocol, "model": model,
            })
            prs.append({
                "repo": "example-org/repo-alpha", "number": i, "state": "OPEN",
                "createdAt": "2026-11-01T00:00:00Z", "mergedAt": None, "closedAt": None,
            })
        self._base_files(records, prs)
        catalog = {
            "schema_version": 1, "retrieved_at_utc": "tier-boundary-fixture",
            "basis": "current_provider_published_standard_public_api_rate",
            "rates": [
                {"model_id": "claude-haiku-5-5", "model_vendor": "Anthropic",
                 "source_protocol": "anthropic", "status": "priced_with_context_tiers",
                 "tiers": [
                    {"condition": "prompt_input_tokens <= 100000",
                     "input_uncached": 0.1, "cache_read": 0.01,
                     "cache_write_5m": 0.125, "cache_write_1h": 0.2, "output": 0.5},
                    {"condition": "prompt_input_tokens > 100000",
                     "input_uncached": 0.5, "cache_read": 0.05,
                     "cache_write_5m": 0.625, "cache_write_1h": 1.0, "output": 2.5},
                 ]},
                {"model_id": "gpt-6-sol", "model_vendor": "OpenAI",
                 "source_protocol": "openai", "status": "priced_with_long_context_tier",
                 "standard_short": {
                     "input_uncached": 2.0, "cache_read": 0.2,
                     "cache_write_30m": 2.5, "cache_write_12h": 5.0, "output": 10.0,
                 },
                 "long_context_over_272k": {
                     "input_uncached": 4.0, "cache_read": 0.4,
                     "cache_write_30m": 5.0, "cache_write_12h": 10.0, "output": 15.0,
                 }},
            ],
        }

        result = self._query_with_catalog(catalog)
        rows = result["catalog_scenario_pr_metrics"]
        self.assertEqual(
            {row["price_tier"] for row in rows},
            {tier for *_, tier in specifications},
        )
        haiku = [row for row in rows if row["model_id"] == "claude-haiku-5-5"]
        self.assertTrue(all(row["scenario_status"] == "COMPLETE" for row in haiku))
        openai = [row for row in rows if row["model_id"] == "gpt-6-sol"]
        self.assertTrue(all(row["scenario_status"] == "PARTIAL_UNKNOWN_COMPONENTS"
                            for row in openai))
        self.assertTrue(all({"cache_write_30m", "cache_write_12h"}
                            == set(row["unknown_buckets"]) for row in openai))

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

    def test_openai_known_quantity_reaches_query_with_incomplete_write_pricing(self):
        pr = "example-org/repo-alpha#13"
        aggregate = aggregate_usage([
            {
                "provider": "openai", "sku": "gpt-test", "usage_id": "req-openai",
                "timestamp": "2026-11-08T20:00:00Z", "session_id": "session-openai",
                "source": "native_usage_jsonl",
                "input_tokens": 60, "cache_read_tokens": 40, "output_tokens": 30,
                "cache_write_input_tokens": 10,
                "cache_write_5m_tokens": None, "cache_write_1h_tokens": None,
                "reasoning_tokens": 8,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard",
                "attributions": [{
                    "pr": pr, "weight": 1, "method": "direct",
                    "basis": "separable_breakdown", "receipt_refs": ["receipt-openai"],
                    "has_rationale": True,
                }],
            },
        ], load_rate_table({
            "provider": "openai", "currency": "USD",
            "effective_from": "2026-11-01T00:00:00Z",
            "observed_current_at": "2026-11-08T00:00:00Z",
            "source_url": "https://example.invalid/rates",
            "rate_basis": "standard_global_public_list_price",
            "rates": {"gpt-test": {
                "input_tokens": "1", "cache_read_input_tokens": "0.1",
                "output_tokens": "2", "write_5m": "3", "write_1h": "4",
            }},
        }))
        event = aggregate["query_events"][0]
        self.assertEqual(event["total_tokens"], 130)
        self.assertTrue(event["token_complete"])
        self.assertEqual(event["cache_write_input_tokens"], 10)
        self.assertEqual(event["cost_status"], "partial")
        self.assertEqual(
            set(event["unknown_buckets"]), {"cache_write_5m", "cache_write_1h"}
        )
        self.assertEqual(event["list_equivalent_cost_usd"], "0.000124")
        query_events = json.loads(json.dumps(aggregate["query_events"], default=str))
        self._base_files(
            query_events,
            [{
                "repo": "example-org/repo-alpha", "number": 13, "state": "MERGED",
                "createdAt": "2026-11-08T19:00:00Z", "mergedAt": "2026-11-08T21:00:00Z",
                "closedAt": "2026-11-08T21:00:00Z", "headRefName": "feature/openai",
                "headRefOid": "d13", "commit_shas": ["d13"],
            }],
        )
        row = self._query()["pr_metrics"][0]
        self.assertEqual(row["direct_total_tokens"], 130)
        self.assertEqual(row["direct_token_complete_observation_n"], 1)
        self.assertEqual(row["cost_status"], "PARTIAL")

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


    def test_renderer_keeps_gfm_tables_structural_and_four_columns_max(self):
        markdown = render_prw_query_summary({
            "snapshot_at_utc": self.CUTOFF,
            "window_start_utc": "2026-10-26T03:34:00Z",
            "pr_metrics": [{
                "repository": "example/repo", "pr_number": 5,
                "direct_uncached_input_tokens": 10,
                "direct_cache_read_input_tokens": 2, "direct_output_tokens": 3,
                "direct_cache_write_5m_input_tokens": 1,
                "direct_cache_write_1h_input_tokens": 0,
                "direct_total_tokens": 16, "direct_usage_observation_count": 1,
                "direct_request_total_tokens_average": 16,
                "direct_request_total_tokens_p50": 16,
                "direct_request_total_tokens_p90": 16,
                "direct_request_total_tokens_p99": 16,
                "direct_request_total_tokens_n": 1,
                "raw_verified_human_message_count": 3,
                "verified_initial_human_message_count": 1,
                "reviewed_followup_episode_count": 2,
            }],
            "metric_cohorts": [{
                "cohort_definition": "all_14d_merges", "metric_family": "direct_usage",
                "measure": "total_tokens", "average": 16, "p50": 16,
                "p90": 16, "p99": 16, "observation_n": 1,
            }],
            "catalog_scenario_pr_metrics": [{
                "pr": "example/repo#5", "model_id": "model-a",
                "scenario_status": "PARTIAL_UNKNOWN_COMPONENTS",
                "known_component_subtotal_usd": "0.000001",
                "scenario_cost_usd": None,
            }],
        })
        self.assertIn("Average / p50", markdown)
        self.assertIn("PARTIAL_UNKNOWN_COMPONENTS", markdown)
        self.assertIn("0.000001", markdown)
        lines = markdown.splitlines()
        for index, line in enumerate(lines[:-1]):
            if not line.startswith("|") or not lines[index + 1].startswith("|---"):
                continue
            columns = line.count("|") - 1
            self.assertLessEqual(columns, 4)
            row_index = index + 2
            while row_index < len(lines) and lines[row_index].startswith("|"):
                self.assertEqual(lines[row_index].count("|") - 1, columns)
                row_index += 1

    def test_query_accepts_canonical_in_memory_events_and_human_summary(self):
        pr = "example-org/repo-alpha#1"
        events = [self._event(
            "sha256:in-memory", pr,
            {"input_uncached": 10, "cache_read": 0, "cache_write_5m": 0,
             "cache_write_1h": 0, "output": 5},
            2.0,
        )]
        prs = [{
            "repo": "example-org/repo-alpha", "number": 1, "state": "MERGED",
            "createdAt": "2026-11-02T00:00:00Z",
            "mergedAt": "2026-11-02T10:00:00Z",
        }]
        result = run_query(
            events_path=events, pr_snapshots_path=prs,
            human_summary_path={"coverage": {}, "per_pr": []},
            snapshot_at_utc=self.CUTOFF,
        )
        row = result["pr_metrics"][0]
        self.assertEqual(row["direct_uncached_input_tokens"], 10)
        self.assertEqual(row["direct_total_tokens"], 15)
        self.assertEqual(row["direct_request_total_tokens_n"], 1)



    def test_pr_lookup_fills_missing_fields_without_replacing_primary_snapshot(self):
        primary = [{
            "repo": "example/repo", "number": 7, "state": "OPEN",
            "headRefName": "live-branch", "createdAt": "2026-11-01T00:00:00Z",
        }]
        cached = [{
            "repo": "example/repo", "number": 7, "state": "CLOSED",
            "headRefName": "cached-branch", "headRefOid": "cached-sha",
            "createdAt": "2026-10-01T00:00:00Z", "closedAt": "2026-10-02T00:00:00Z",
        }, {
            "repo": "example/repo", "number": 8, "state": "OPEN",
            "createdAt": "2026-11-02T00:00:00Z",
        }]
        merged = _merge_pr_branch_metadata(primary, cached)
        pr7 = next(row for row in merged if row["number"] == 7)
        pr8 = next(row for row in merged if row["number"] == 8)
        self.assertEqual(pr7["state"], "OPEN")
        self.assertEqual(pr7["headRefName"], "live-branch")
        self.assertEqual(pr7["createdAt"], "2026-11-01T00:00:00Z")
        self.assertEqual(pr7["headRefOid"], "cached-sha")
        self.assertEqual(pr8["state"], "OPEN")



if __name__ == "__main__":
    unittest.main()
