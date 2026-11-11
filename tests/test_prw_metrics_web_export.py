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

    def test_weighted_token_totals_keep_their_fraction(self):
        # The query sums tokens times an attribution weight, so totals can be fractional.
        row = export.build_snapshot(None, query([metric(
            1, usage_status="OBSERVED_DIRECT_ATTRIBUTION", direct_total_tokens=1.5,
            direct_uncached_input_tokens=0.5, direct_output_tokens=1.0, direct_usage_observation_count=1,
        )]), [])["prs"][0]
        self.assertEqual((row["usage"]["total"], row["usage"]["uncached_input"], row["usage"]["requests"]), (1.5, 0.5, 1))

    def test_partial_price_rows_give_a_subtotal_but_no_full_estimate(self):
        scenarios = [
            {"pr": "acme/app#7", "known_component_subtotal_usd": "1.25", "scenario_cost_usd": None,
             "scenario_status": "PARTIAL_UNKNOWN_COMPONENTS", "event_n": 3, "fully_priced_event_n": 0,
             "unknown_event_n": 3, "model_id": "model-a", "attribution_method": "branch_associated"},
            {"pr": "acme/app#7", "known_component_subtotal_usd": "0.75", "scenario_cost_usd": "0.75",
             "scenario_status": "COMPLETE", "event_n": 1, "fully_priced_event_n": 1,
             "unknown_event_n": 0, "model_id": "model-b", "attribution_method": "branch_associated"},
        ]
        cost = export.build_snapshot({}, query([self.branch_metric()], scenarios), [])["prs"][0]["cost"]
        self.assertEqual(cost["known_subtotal_usd"], 2.0)
        self.assertIsNone(cost["full_scenario_usd"])
        self.assertEqual((cost["event_n"], cost["fully_priced_event_n"]), (4, 1))
        self.assertEqual(cost["models"], ["model-a", "model-b"])

    def test_fully_priced_rows_give_a_full_estimate(self):
        scenarios = [{"pr": "acme/app#7", "known_component_subtotal_usd": "2.5", "scenario_cost_usd": "2.5",
                      "scenario_status": "COMPLETE", "event_n": 2, "fully_priced_event_n": 2, "unknown_event_n": 0}]
        cost = export.build_snapshot({}, query([self.branch_metric()], scenarios), [])["prs"][0]["cost"]
        self.assertEqual(cost["full_scenario_usd"], 2.5)

    def test_one_request_matched_two_ways_is_costed_once(self):
        both = {"pr": "acme/app#7", "known_component_subtotal_usd": "0.15", "scenario_cost_usd": "0.15",
                "scenario_status": "COMPLETE", "event_n": 1, "fully_priced_event_n": 1, "unknown_event_n": 0,
                "model_id": "model-a"}
        scenarios = [dict(both, attribution_method="direct"), dict(both, attribution_method="branch_associated")]
        cost = export.build_snapshot({}, query([self.branch_metric()], scenarios), [])["prs"][0]["cost"]
        self.assertEqual((cost["known_subtotal_usd"], cost["full_scenario_usd"], cost["event_n"]), (0.15, 0.15, 1))
        self.assertEqual(cost["attribution_methods"], ["direct"])


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

    def test_source_paths_and_errors_are_not_copied(self):
        summary = {"sources": {"prs": {"status": "FAILED", "count": 0, "path": "/private/input/prs.json",
                                       "error": "boom at /private/input"}}}
        snapshot = export.build_snapshot(summary, query([metric(1)]), [])
        self.assertEqual(snapshot["sources"], {"prs": {"status": "FAILED", "count": 0}})

    def test_non_finite_pass_through_values_become_null_and_write(self):
        summary = {"repo_comparison": [{"repo": "acme/app", "all_p50_hours": float("nan")}],
                   "stage_dwell": [{"stage": "coding", "median_h": float("inf")}]}
        snapshot = export.build_snapshot(summary, query([metric(1)]), [])
        self.assertIsNone(snapshot["repo_comparison"][0]["all_p50_hours"])
        self.assertIsNone(snapshot["stage_dwell"][0]["median_h"])
        with tempfile.TemporaryDirectory() as directory:
            export.write_snapshot(Path(directory) / "dashboard.json", snapshot)

    def test_handoffs_follow_the_collector_rules(self):
        record = {"repo": "acme/app", "number": 1, "authority_ready_at": "2026-11-01T00:00:00Z",
                  "mergedAt": "2026-11-01T02:00:00Z", "review_completed_at": "2026-10-31T00:00:00Z",
                  "next_substantive_action_at": "2026-10-31T00:10:00Z"}
        handoffs = export.build_snapshot({}, query([metric(1)]), [record])["prs"][0]["handoffs"]
        self.assertNotIn("authority_to_merge", handoffs)  # no final_ready / merge_authority facts
        self.assertEqual(handoffs["review_return_to_next_action"], 600.0)
        ready = dict(record, final_ready=True, merge_authority=True)
        handoffs = export.build_snapshot({}, query([metric(1)]), [ready])["prs"][0]["handoffs"]
        self.assertEqual(handoffs["authority_to_merge"], 7200.0)

    def test_credentials_in_titles_and_summary_fields_are_redacted(self):
        token = "ghp_" + "A1b2C3d4E5" * 3 + "F6g7H8"
        prs = [{"repo": "acme/app", "number": 1, "title": "fix " + token, "url": "https://github.com/acme/app/pull/1"}]
        summary = {"repo_comparison": [{"repo": "acme/app", "private_note": "kept out"}]}
        text = json.dumps(export.build_snapshot(summary, query([metric(1, head_branch="feat/" + token)]), prs))
        self.assertNotIn(token, text)
        self.assertNotIn("private_note", text)

    def test_gaps_report_observed_counts_for_this_snapshot(self):
        rows = [metric(1), metric(2, observed_active_wall_seconds=30.0)]
        gaps = {gap["key"]: gap for gap in export.build_snapshot({}, query(rows), [])["gaps"]}
        self.assertEqual((gaps["active"]["observed_n"], gaps["active"]["total_n"]), (1, 2))
        self.assertEqual((gaps["usage"]["observed_n"], gaps["size"]["observed_n"]), (0, 0))
        self.assertEqual((gaps["direct_attribution"]["observed_n"], gaps["direct_attribution"]["total_n"]), (3, 1000))

    def test_absent_inputs_yield_an_empty_valid_snapshot(self):
        snapshot = export.build_snapshot(None, None, None)
        self.assertEqual((snapshot["schema_version"], snapshot["prs"], snapshot["data_through"]), (1, [], None))

    def test_data_through_is_the_collectors_freshness_not_the_query_cutoff(self):
        summary = {"status": "STALE", "data_through": "2026-11-08T00:00:00Z"}
        snapshot = export.build_snapshot(summary, query([metric(1)]), [])
        self.assertEqual(snapshot["data_through"], "2026-11-08T00:00:00Z")
        self.assertEqual(snapshot["window_end"], "2026-11-09T21:25:21Z")
        # No collector summary: freshness is unknown; the reporting window is still known.
        bare = export.build_snapshot(None, query([metric(1)]), [])
        self.assertEqual((bare["data_through"], bare["window_end"]), (None, "2026-11-09T21:25:21Z"))
        unknown = export.build_snapshot({"data_through": "UNKNOWN"}, query([metric(1)]), [])
        self.assertIsNone(unknown["data_through"])

    def test_write_is_atomic_and_rejects_non_finite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "dashboard.json"
            export.write_snapshot(target, {"schema_version": 1, "prs": []})
            self.assertEqual(json.loads(target.read_text())["schema_version"], 1)
            with self.assertRaises(ValueError):
                export.write_snapshot(target, {"schema_version": 1, "bad": float("nan")})
            # A failed write leaves the last good snapshot in place.
            self.assertEqual(json.loads(target.read_text())["prs"], [])
            # No temporary file is left behind, and none has a name another writer would share.
            self.assertEqual([path.name for path in target.parent.iterdir()], ["dashboard.json"])

    def test_writers_do_not_share_a_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dashboard.json"
            # A stale file at the old fixed temporary name must not be reused or replaced.
            (Path(directory) / "dashboard.json.tmp").write_text("other writer")
            export.write_snapshot(target, {"schema_version": 1, "prs": []})
            self.assertEqual((Path(directory) / "dashboard.json.tmp").read_text(), "other writer")
            self.assertEqual(json.loads(target.read_text())["schema_version"], 1)


class FlowTests(unittest.TestCase):
    """Final-stage reach and start-to-final timing used by the one-shot tiles."""

    def snapshot_row(self, record=None, **metric_overrides):
        prs = [dict(record, repo="acme/app", number=1)] if record is not None else []
        return export.build_snapshot({}, query([metric(1, **metric_overrides)]), prs)["prs"][0]

    def test_final_transition_gives_reach_and_minutes_source_timestamps(self):
        flow = self.snapshot_row({"stage_transitions": [
            {"stage": "stage:1-coding", "entered_at": "2026-11-01T10:00:00Z", "exited_at": "2026-11-01T11:00:00Z"},
            {"stage": "stage:0-spec", "entered_at": "2026-11-01T09:30:00Z", "exited_at": "2026-11-01T10:00:00Z"},
            {"stage": "stage:5-final-approval", "entered_at": "2026-11-01T12:00:00Z"},
        ]})["flow"]
        self.assertEqual(flow, {"reached_final": True, "started_at": "2026-11-01T09:30:00Z", "final_at": "2026-11-01T12:00:00Z"})

    def test_first_entry_into_final_is_used(self):
        flow = self.snapshot_row({"stage_transitions": [
            {"stage": "stage:5-final-approval", "start_at": "2026-11-01T14:00:00Z"},
            {"stage": "stage:1-coding", "start_at": "2026-11-01T09:00:00Z"},
            {"stage": "stage:5-final-approval", "start_at": "2026-11-01T12:00:00Z"},
        ]})["flow"]
        self.assertEqual(flow["final_at"], "2026-11-01T12:00:00Z")

    def test_final_stage_label_without_timestamp_is_reached_but_untimed(self):
        flow = self.snapshot_row({"legacy_stage": "stage:5-final-approval"})["flow"]
        self.assertEqual(flow, {"reached_final": True, "started_at": None, "final_at": None})

    def test_never_final_is_not_reached(self):
        flow = self.snapshot_row({"legacy_stage": "stage:1-coding", "stage_transitions": [
            {"stage": "stage:1-coding", "entered_at": "2026-11-01T10:00:00Z"}]})["flow"]
        self.assertEqual(flow, {"reached_final": False, "started_at": "2026-11-01T10:00:00Z", "final_at": None})

    def test_no_stage_evidence_is_unknown_not_false(self):
        self.assertIsNone(self.snapshot_row({"title": "t"})["flow"])
        self.assertIsNone(self.snapshot_row()["flow"])

    def test_steer_count_is_verified_followups_and_unknown_stays_null(self):
        known = self.snapshot_row(None, human_coverage_status="OBSERVED_SCOPE_ONLY", raw_verified_human_message_count=3,
                                  verified_initial_human_message_count=1, verified_followup_human_message_count=2)
        self.assertEqual(known["human"]["followup"], 2)
        zero = self.snapshot_row(None, human_coverage_status="OBSERVED_SCOPE_ONLY", raw_verified_human_message_count=1,
                                 verified_initial_human_message_count=1, verified_followup_human_message_count=0)
        self.assertEqual(zero["human"]["followup"], 0)
        self.assertIsNone(self.snapshot_row(None)["human"])


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
