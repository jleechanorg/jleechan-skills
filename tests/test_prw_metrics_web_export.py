"""Behavioural tests for the PRW web-dashboard snapshot export."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import prw_metrics_web_export as export  # noqa: E402


def metric(number, **overrides):
    row = {
        "repository": "acme/app",
        "pr_number": number,
        "pr_state": "MERGED",
        "created_at_utc": "2026-11-01 08:00:00-08",
        "merged_at_utc": "2026-11-01 10:00:00-08",
        "closed_at_utc": "2026-11-01 10:00:00-08",
        "pr_elapsed_seconds": 7200.0,
        "pr_elapsed_basis": "MERGED_AT",
        "head_branch": f"feature/{number}",
        "usage_status": "UNKNOWN_NO_DIRECT_USAGE",
        "branch_usage_status": "UNKNOWN_NO_CANONICAL_BRANCH_USAGE_ATTRIBUTION",
        "cost_status": "UNKNOWN_NO_DIRECT_USAGE",
        "human_coverage_status": "UNKNOWN",
    }
    row.update(overrides)
    return row


def query(metrics, scenarios=()):
    return {
        "snapshot_at_utc": "2026-11-09T21:25:21Z",
        "window_start_utc": "2026-10-26T21:25:21Z",
        "query_coverage": {"canonical_event_n": 1000, "validated_direct_attribution_event_n": 3},
        "pr_metrics": metrics,
        "metric_cohorts": [],
        "catalog_scenario_pr_metrics": list(scenarios),
    }


class TimestampTests(unittest.TestCase):
    def test_duckdb_offset_timestamp_becomes_utc(self):
        self.assertEqual(export.to_utc_iso("2026-11-01 08:57:47-08"), "2026-11-01T16:57:47Z")

    def test_iso_z_is_preserved(self):
        self.assertEqual(export.to_utc_iso("2026-11-09T21:25:21Z"), "2026-11-09T21:25:21Z")

    def test_half_hour_offset(self):
        self.assertEqual(export.to_utc_iso("2026-11-01 12:00:00+05:30"), "2026-11-01T06:30:00Z")

    def test_garbage_is_unknown_not_a_guess(self):
        for value in (None, "", "yesterday", 5, "2026-13-45 99:00:00Z"):
            self.assertIsNone(export.to_utc_iso(value))


class MissingIsNotZeroTests(unittest.TestCase):
    def test_pr_without_attribution_has_null_usage_cost_and_human(self):
        row = export.build_snapshot({}, query([metric(1)]), [])["prs"][0]
        self.assertIsNone(row["usage"])
        self.assertIsNone(row["cost"])
        self.assertIsNone(row["human"])
        self.assertIsNone(row["active_s"])
        self.assertIsNone(row["eligible_idle_s"])
        self.assertEqual(row["usage_status"], "UNKNOWN_NO_DIRECT_USAGE")

    def test_uncollected_all_zero_size_is_unknown(self):
        prs = [{"repo": "acme/app", "number": 1, "additions": 0, "deletions": 0, "changedFiles": 0}]
        self.assertIsNone(export.build_snapshot({}, query([metric(1)]), prs)["prs"][0]["size"])

    def test_observed_size_is_kept_including_a_real_zero_component(self):
        prs = [{"repo": "acme/app", "number": 1, "additions": 12, "deletions": 0, "changedFiles": 2}]
        self.assertEqual(
            export.build_snapshot({}, query([metric(1)]), prs)["prs"][0]["size"],
            {"additions": 12, "deletions": 0, "files": 2},
        )

    def test_sentinel_strings_and_booleans_are_not_numbers(self):
        row = export.build_snapshot(
            {}, query([metric(1, pr_elapsed_seconds="UNKNOWN", observed_active_wall_seconds=True)]), []
        )["prs"][0]
        self.assertIsNone(row["elapsed_s"])
        self.assertIsNone(row["active_s"])


class UsageAndCostTests(unittest.TestCase):
    def branch_metric(self):
        return metric(
            7,
            branch_usage_status="OBSERVED_SOURCE_BRANCH_ATTRIBUTION",
            branch_association_confidence="low",
            branch_total_tokens=1000.0,
            branch_uncached_input_tokens=100.0,
            branch_cache_read_input_tokens=850.0,
            branch_output_tokens=50.0,
            branch_usage_observation_count=4,
        )

    def test_branch_usage_is_labelled_with_its_basis_and_confidence(self):
        usage = export.build_snapshot({}, query([self.branch_metric()]), [])["prs"][0]["usage"]
        self.assertEqual((usage["basis"], usage["confidence"], usage["total"], usage["requests"]), ("source_branch", "low", 1000, 4))

    def test_direct_usage_wins_over_branch_usage(self):
        row = self.branch_metric()
        row.update(direct_total_tokens=40.0, direct_association_confidence="DIRECT_VALIDATED", direct_usage_observation_count=2)
        usage = export.build_snapshot({}, query([row]), [])["prs"][0]["usage"]
        self.assertEqual((usage["basis"], usage["total"]), ("direct", 40))

    def test_partial_price_rows_give_a_subtotal_but_no_full_estimate(self):
        scenarios = [
            {"pr": "acme/app#7", "known_component_subtotal_usd": "1.25", "scenario_cost_usd": None,
             "scenario_status": "PARTIAL_UNKNOWN_COMPONENTS", "event_n": 3, "fully_priced_event_n": 0,
             "unknown_event_n": 3, "model_id": "model-a", "attribution_method": "branch_associated"},
            {"pr": "acme/app#7", "known_component_subtotal_usd": "0.75", "scenario_cost_usd": "0.75",
             "scenario_status": "FULLY_PRICED", "event_n": 1, "fully_priced_event_n": 1,
             "unknown_event_n": 0, "model_id": "model-b", "attribution_method": "branch_associated"},
        ]
        cost = export.build_snapshot({}, query([self.branch_metric()], scenarios), [])["prs"][0]["cost"]
        self.assertEqual(cost["known_subtotal_usd"], 2.0)
        self.assertIsNone(cost["full_scenario_usd"])
        self.assertEqual((cost["event_n"], cost["fully_priced_event_n"]), (4, 1))
        self.assertEqual(cost["models"], ["model-a", "model-b"])

    def test_fully_priced_rows_give_a_full_estimate(self):
        scenarios = [{"pr": "acme/app#7", "known_component_subtotal_usd": "2.5", "scenario_cost_usd": "2.5",
                      "scenario_status": "FULLY_PRICED", "event_n": 2, "fully_priced_event_n": 2, "unknown_event_n": 0}]
        cost = export.build_snapshot({}, query([self.branch_metric()], scenarios), [])["prs"][0]["cost"]
        self.assertEqual(cost["full_scenario_usd"], 2.5)


class PayloadTests(unittest.TestCase):
    def test_private_text_is_not_copied(self):
        prs = [{"repo": "acme/app", "number": 1, "title": "Add thing", "body": "SECRET-BODY-TEXT",
                "url": "https://github.com/acme/app/pull/1", "isDraft": False}]
        summary = {"usage_summary": {"events": [{"prompt": "SECRET-PROMPT"}], "event_count": 1},
                   "human_summary": {"coverage": {"assigned_verified_messages": 2}, "per_pr": {"x": "SECRET-HUMAN"}}}
        text = json.dumps(export.build_snapshot(summary, query([metric(1)]), prs))
        for secret in ("SECRET-BODY-TEXT", "SECRET-PROMPT", "SECRET-HUMAN"):
            self.assertNotIn(secret, text)
        self.assertIn("Add thing", text)

    def test_gaps_report_observed_counts_for_this_snapshot(self):
        rows = [metric(1), metric(2, observed_active_wall_seconds=30.0)]
        gaps = {gap["key"]: gap for gap in export.build_snapshot({}, query(rows), [])["gaps"]}
        self.assertEqual((gaps["active"]["observed_n"], gaps["active"]["total_n"]), (1, 2))
        self.assertEqual((gaps["usage"]["observed_n"], gaps["size"]["observed_n"]), (0, 0))
        self.assertEqual((gaps["direct_attribution"]["observed_n"], gaps["direct_attribution"]["total_n"]), (3, 1000))

    def test_absent_inputs_yield_an_empty_valid_snapshot(self):
        snapshot = export.build_snapshot(None, None, None)
        self.assertEqual((snapshot["schema_version"], snapshot["prs"], snapshot["data_through"]), (1, [], None))

    def test_write_is_atomic_and_rejects_non_finite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "dashboard.json"
            export.write_snapshot(target, {"schema_version": 1, "prs": []})
            self.assertEqual(json.loads(target.read_text())["schema_version"], 1)
            with self.assertRaises(ValueError):
                export.write_snapshot(target, {"schema_version": 1, "bad": float("nan")})
            # A failed write leaves the last good snapshot in place.
            self.assertEqual(json.loads(target.read_text())["prs"], [])


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FrontendStatsTests(unittest.TestCase):
    def test_frontend_statistics(self):
        result = subprocess.run(
            ["node", "--test", str(REPO / "web" / "prw-dashboard" / "stats.test.cjs")],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
