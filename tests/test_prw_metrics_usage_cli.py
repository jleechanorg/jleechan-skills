"""CLI-level checks for actual usage feed and rate-card wiring."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.native_usage_collector import collect_native_history
from scripts.prw_metrics import (
    MetricsAggregator,
    Publisher,
    _retained_usage_summary,
    _summarize_observed_pr_costs,
    aggregate_usage,
    load_rate_table,
    load_usage_events,
    main,
    parse_iso_utc,
    render_usage_summary,
)


class UsageFeedCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.events_path = os.path.join(self.tempdir.name, "events.jsonl")
        self.rates_path = os.path.join(self.tempdir.name, "rates.json")
        event = {
            "request_id": "req-1", "timestamp": "2026-11-01T00:00:00Z", "model": "model-a",
            "raw_usage": {
                "input_tokens": 1000000, "cache_read_input_tokens": 1000000,
                "cache_creation_input_tokens": 2000000,
                "cache_creation": {"ephemeral_5m_input_tokens": 1000000, "ephemeral_1h_input_tokens": 1000000},
                "output_tokens": 1000000, "output_tokens_details": {"thinking_tokens": 100000},
                "service_tier": "standard", "inference_geo": "global", "speed": "standard",
                "prompt": "MUST NOT APPEAR",
            },
        }
        unsupported = {
            "request_id": "req-2", "timestamp": "2026-11-01T00:01:00Z", "model": "<synthetic>",
            "raw_usage": {"input_tokens": 0, "output_tokens": 0},
        }
        with open(self.events_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n" + json.dumps(unsupported) + "\n")
        rate_card = {
            "provider": "example-provider", "currency": "USD", "effective_from": "2026-10-22T00:00:00Z",
            "observed_current_at": "2026-11-01T00:00:00Z", "source_url": "https://example.invalid/rates",
            "rate_basis": "standard_global_public_list_price",
            "rates": {"model-a": {"input_tokens": "1", "cache_read_input_tokens": "0.1",
                                    "output_tokens": "10", "write_5m": "2.5", "write_1h": "4"}},
        }
        with open(self.rates_path, "w", encoding="utf-8") as stream:
            json.dump(rate_card, stream)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_actual_cli_prices_ttl_buckets_and_keeps_unknown_unallocated(self):
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "prw_metrics.py"))
        proc = subprocess.run(
            [sys.executable, script, "--offline", "--cutoff", "2026-11-02T00:00:00Z", "--usage-events", self.events_path,
             "--usage-rates", self.rates_path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        self.assertIn("Source records: 2; priced: 1; partially priced: 0; unknown: 1.", proc.stdout)
        self.assertIn("Known usage subtotal: $17.6000000 USD.", proc.stdout)
        self.assertIn("Unallocated known subtotal: $17.6000000 USD known subtotal across 2 events (1 with unknown cost)", proc.stdout)
        self.assertIn("`cache_write_5m` 1000000", proc.stdout)
        self.assertIn("`cache_write_1h` 1000000", proc.stdout)
        self.assertIn("Reasoning tokens: 100000 (included in output tokens; diagnostic subset).", proc.stdout)
        self.assertNotIn("MUST NOT APPEAR", proc.stdout)
        self.assertNotIn("| PR | Known subtotal", proc.stdout)

    def test_missing_rates_render_unknown_instead_of_zero(self):
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "prw_metrics.py"))
        proc = subprocess.run(
            [sys.executable, script, "--offline", "--cutoff", "2026-11-02T00:00:00Z", "--usage-events", self.events_path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        self.assertIn("Known usage subtotal: UNKNOWN (no priced usage).", proc.stdout)
        self.assertNotIn("Known usage subtotal: $0.0000000", proc.stdout)

    def test_rate_scope_mismatch_and_missing_metadata_remain_unknown(self):
        rates = load_rate_table(self.rates_path)
        for field, wrong in (("service_tier", "batch"), ("inference_geo", "us"), ("speed", "fast"),
                             ("service_tier", None), ("inference_geo", None), ("speed", None)):
            with self.subTest(field=field, value=wrong):
                metadata = {"service_tier": "standard", "inference_geo": "global", "speed": "standard"}
                if wrong is None:
                    metadata.pop(field)
                else:
                    metadata[field] = wrong
                event = {
                    "request_id": "req-scope", "timestamp": "2026-11-01T00:00:00Z", "model": "model-a",
                    "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, **metadata},
                }
                with open(self.events_path, "w", encoding="utf-8") as stream:
                    stream.write(json.dumps(event) + "\n")
                summary = aggregate_usage(load_usage_events(self.events_path, provider="example-provider"), rates)
                self.assertEqual(summary["unknown_event_count"], 1)
                self.assertEqual(summary["known_cost_usd"], 0)

    def test_rate_and_event_both_missing_scope_dimensions_remain_unknown(self):
        rates = load_rate_table(self.rates_path)
        rates = [dict(rate, service_tier=None, inference_geo=None, speed=None) for rate in rates]
        event = {
            "provider": "example-provider", "sku": "model-a", "usage_id": "req-no-scope",
            "timestamp": "2026-11-01T00:00:00Z", "input_tokens": 1000000, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
            "attributions": [],
        }
        summary = aggregate_usage([event], rates)
        self.assertEqual(summary["unknown_event_count"], 1)
        self.assertEqual(summary["known_cost_usd"], 0)

    def test_naive_event_timestamp_is_undated_and_excluded_from_window(self):
        event = {
            "provider": "example-provider", "sku": "model-a", "usage_id": "req-naive-time",
            "timestamp": "2026-11-01T00:00:00", "input_tokens": 1000000, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
            "service_tier": "standard", "inference_geo": "global", "speed": "standard",
            "attributions": [],
        }
        summary = aggregate_usage([event], load_rate_table(self.rates_path),
                                  window_start=parse_iso_utc("2026-10-25T00:00:00Z"),
                                  window_end=parse_iso_utc("2026-11-08T00:00:00Z"))
        self.assertEqual(summary["event_count"], 0)
        self.assertEqual(summary["undated_count"], 1)
        self.assertEqual(summary["outside_window_count"], 0)
        self.assertEqual(summary["known_cost_usd"], 0)

    def test_rate_effective_time_requires_timezone_and_currency_must_be_usd(self):
        card = {
            "provider": "example-provider", "currency": "EUR", "effective_from": "2026-10-22T00:00:00",
            "observed_current_at": "2026-11-01T00:00:00Z", "source_url": "https://example.invalid/rates",
            "rate_basis": "standard_global_public_list_price", "rates": {"model-a": {"input_tokens": "1"}},
        }
        with open(self.rates_path, "w", encoding="utf-8") as stream:
            json.dump(card, stream)
        with self.assertRaisesRegex(ValueError, "invalid price or effective interval"):
            load_rate_table(self.rates_path)
        card["effective_from"] = "2026-10-22T00:00:00Z"
        with open(self.rates_path, "w", encoding="utf-8") as stream:
            json.dump(card, stream)
        event = {
            "request_id": "req-eur", "timestamp": "2026-11-01T00:00:00Z", "model": "model-a",
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
        }
        with open(self.events_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        summary = aggregate_usage(load_usage_events(self.events_path, provider="example-provider"),
                                  load_rate_table(self.rates_path))
        self.assertEqual(summary["unknown_event_count"], 1)
        self.assertEqual(summary["known_cost_usd"], 0)

    def test_summary_retention_round_trip_keeps_only_numeric_usage_and_rates(self):
        events = load_usage_events(self.events_path, provider="example-provider")
        summary = aggregate_usage(events, load_rate_table(self.rates_path))
        summary["coverage"]["native_source"] = {
            "status": "COMPLETE",
            "runtime_coverage": "Claude and Codex configured roots; other runtimes not collected",
            "roots_requested": 1, "roots_available": 1, "missing_roots": 0,
            "files_scanned": 1, "duplicate_files": 0, "usage_records_in_window": 2,
            "duplicate_usage_records": 1, "outside_window_records": 0, "undated_records": 0,
            "human_candidates": 0, "human_verified": 0, "human_unannotated": 0,
            "pr_bound_usage_records": 0, "malformed_lines": 0, "read_errors": 0,
        }
        files = Publisher(repo_path=self.tempdir.name).write_telemetry_bundle({
            "usage_summary": _retained_usage_summary(summary), "w2_bounds": ["2026-11-01", "2026-11-08"],
        })
        snapshot = next(value for key, value in files.items() if key.endswith("/summary_snapshot.json"))
        projected = json.loads(snapshot)["usage_summary"]
        self.assertEqual(projected["source_records"], 2)
        self.assertEqual(projected["tokens_by_bucket"]["cache_write_5m"], 1000000)
        self.assertEqual(projected["tokens_by_bucket"]["cache_write_1h"], 1000000)
        self.assertEqual(projected["reasoning_tokens"], 100000)
        self.assertEqual(projected["coverage"]["service_tiers"], ["standard"])
        self.assertEqual(projected["coverage"]["regions"], ["global"])
        self.assertEqual(projected["coverage"]["native_source"]["status"], "COMPLETE")
        self.assertIn("other runtimes not collected",
                      projected["coverage"]["native_source"]["runtime_coverage"])
        self.assertEqual(projected["coverage"]["native_source"]["usage_records_in_window"], 2)
        self.assertEqual(len(projected["rate_records"]), 5)
        self.assertIsNone(projected["events"][1]["known_cost_usd"])
        self.assertEqual(projected["known_cost_usd"], "17.6")
        self.assertEqual(
            projected["pr_cost_distribution"],
            {"n": 0, "p50_usd": None, "p90_usd": None, "p99_usd": None},
        )
        serialized = json.dumps(projected)
        self.assertNotIn("MUST NOT APPEAR", serialized)
        self.assertNotIn(self.tempdir.name, serialized)
        self.assertIn('"price_per_million": "1"', serialized)

    def test_pr_cost_distribution_requires_explicit_fully_priced_pr_cohort(self):
        costs = {
            "example/repo#1": {
                "known_cost_usd": 1.0,
                "pricing_status": "observed-priced",
                "event_count": 1,
            },
            "example/repo#2": {
                "known_cost_usd": 2.0,
                "pricing_status": "observed-priced",
                "event_count": 2,
            },
            "example/repo#3": {
                "known_cost_usd": 4.0,
                "pricing_status": "observed-priced",
                "event_count": 1,
            },
            "example/repo#4": {
                "known_cost_usd": 100.0,
                "pricing_status": "partial",
                "event_count": 3,
            },
        }
        distribution = _summarize_observed_pr_costs(costs)
        self.assertEqual(
            distribution, {"n": 3, "p50_usd": 2.0, "p90_usd": 4.0, "p99_usd": 4.0}
        )
        empty = _summarize_observed_pr_costs({})
        self.assertEqual(
            empty, {"n": 0, "p50_usd": None, "p90_usd": None, "p99_usd": None}
        )
        rendered = render_usage_summary({
            "known_cost_usd": 7.0, "priced_event_count": 3,
            "partially_priced_event_count": 1,
            "unallocated": {
                "known_cost_usd": 0, "event_count": 0, "unknown_cost_events": 0,
            },
            "coverage": {"session_count": 0}, "rate_records": [],
            "label": "observed prices",
            "source_records": 4, "event_count": 4, "unknown_event_count": 0,
            "window_start": None, "window_end": None,
            "outside_window_count": 0, "undated_count": 0,
            "tokens_by_bucket": {}, "reasoning_tokens": 0, "prs": {},
            "pr_cost_distribution": distribution,
        })
        self.assertTrue(any(
            "n=3; p50=$2.0000000, p90=$4.0000000, p99=$4.0000000" in line
            for line in rendered
        ))

    def test_nonfinite_explicit_attribution_stays_unallocated_without_crashing(self):
        event = {
            "request_id": "req-nan", "timestamp": "2026-11-01T00:00:00Z", "model": "model-a",
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
            "attributions": [{"pr": "example/repo#1", "weight": "NaN", "method": "direct",
                              "receipt_refs": ["receipt-id"], "rationale": "recorded"}],
        }
        with open(self.events_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        events = load_usage_events(self.events_path, provider="example-provider")
        summary = aggregate_usage(events, load_rate_table(self.rates_path))
        self.assertEqual(summary["unallocated"]["known_cost_usd"], 1)
        self.assertEqual(summary["prs"]["example/repo#1"]["pricing_status"], "partial")

    def test_conflicted_usage_is_unknown_without_pricing_reported_tokens(self):
        event = {
            "provider": "example-provider", "request_id": "req-conflict", "model": "model-a",
            "timestamp": "2026-11-01T00:00:00Z", "usage_conflict": True,
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
            "attributions": [{"pr": "example/repo#4", "weight": 1, "method": "direct",
                              "receipt_refs": ["receipt-conflict"], "rationale": "recorded"}],
        }
        events = load_usage_events([event], provider="example-provider")
        summary = aggregate_usage(events, load_rate_table(self.rates_path))
        self.assertEqual(summary["priced_event_count"], 0)
        self.assertEqual(summary["partially_priced_event_count"], 0)
        self.assertEqual(summary["unknown_event_count"], 1)
        self.assertEqual(summary["known_cost_usd"], 0)
        self.assertEqual(summary["tokens_by_bucket"], {})
        self.assertEqual(summary["reasoning_tokens"], 0)
        self.assertEqual(summary["prs"]["example/repo#4"]["known_cost_usd"], 0)
        rates = load_rate_table(self.rates_path)
        bundle = Publisher(repo_path=self.tempdir.name).write_telemetry_bundle(
            None, usage_events=events, usage_rates=rates,
        )
        retained = next(v for k, v in bundle.items() if k.endswith("usage_events.jsonl"))
        retained_events = load_usage_events([json.loads(line) for line in retained.splitlines()],
                                            provider="example-provider")
        replayed = aggregate_usage(retained_events, rates)
        self.assertEqual(replayed["known_cost_usd"], 0)
        self.assertEqual(replayed["unknown_event_count"], 1)
        self.assertEqual(replayed["prs"]["example/repo#4"]["known_cost_usd"], 0)

    def test_query_events_export_canonical_identity_cost_and_validated_attribution(
        self,
    ):
        receipt = "sha256:" + ("a" * 64)
        source_id = "sha256:" + ("b" * 64)
        event = {
            "provider": "example-provider", "sku": "model-a",
            "usage_id": "request-secret",
            "timestamp": "2026-11-01T00:00:00Z", "session_id": "session-secret",
            "source_fingerprint": source_id, "input_tokens": 1000000,
            "cache_read_tokens": 2000000, "cache_write_5m_tokens": 0,
            "cache_write_1h_tokens": 0, "output_tokens": 1000000,
            "reasoning_tokens": 100000,
            "service_tier": "standard", "inference_geo": "global", "speed": "standard",
            "attributions": [{
                "pr": "example/repo#1", "weight": 1, "method": "direct",
                "basis": "separable_breakdown", "receipt_refs": [receipt],
                "has_rationale": True, "rationale": "private rationale",
            }],
        }
        summary = aggregate_usage(
            [event, dict(event)], load_rate_table(self.rates_path)
        )

        self.assertEqual(summary["event_count"], 1)
        self.assertIs(summary["query_events"], summary["events"])
        exported = summary["query_events"][0]
        self.assertEqual(exported["provider"], "example-provider")
        self.assertEqual(exported["model"], "model-a")
        self.assertEqual(exported["timestamp"], event["timestamp"])
        self.assertEqual(exported["source_id"], source_id)
        self.assertNotEqual(exported["event_id"], "request-secret")
        self.assertNotEqual(exported["session_id_hash"], "session-secret")
        self.assertEqual(exported["tokens_by_bucket"]["input_uncached"], 1000000)
        self.assertEqual(exported["tokens_by_bucket"]["output"], 1000000)
        self.assertEqual(exported["reasoning_output_tokens"], 100000)
        self.assertEqual(exported["total_tokens"], 4000000)
        self.assertFalse(exported["dedup_conflict"])
        self.assertFalse(exported["source_conflict"])
        self.assertEqual(exported["observed_cost_usd"], None)
        self.assertEqual(exported["list_equivalent_cost_usd"], "11.2")
        self.assertTrue(exported["price_catalog_version"].startswith("sha256:"))
        self.assertEqual(
            exported["validated_attributions"],
            [{
                "pr": "example/repo#1", "weight": "1", "method": "direct",
                "basis": "separable_breakdown", "convention_ref": None,
                "receipt_refs": [receipt],
            }],
        )
        serialized = json.dumps(exported, default=str)
        self.assertNotIn("request-secret", serialized)
        self.assertNotIn("session-secret", serialized)
        self.assertNotIn("private rationale", serialized)

        unpriced = aggregate_usage([event], [])
        unpriced_event = unpriced["query_events"][0]
        self.assertEqual(unpriced_event["cost_status"], "UNKNOWN_NO_RATE_CARD")
        self.assertIsNone(unpriced_event["list_equivalent_cost_usd"])
        self.assertIsNone(unpriced_event["observed_cost_usd"])

    def test_query_event_export_conflict_keeps_identity_but_unknown_tokens_and_cost(
        self,
    ):
        base = {
            "provider": "example-provider", "sku": "model-a",
            "usage_id": "same-secret-id",
            "timestamp": "2026-11-01T00:00:00Z", "input_tokens": 1000000,
            "cache_read_tokens": 0, "cache_write_5m_tokens": 0,
            "cache_write_1h_tokens": 0, "output_tokens": 0,
            "service_tier": "standard", "inference_geo": "global", "speed": "standard",
            "attributions": [],
        }
        conflict = dict(base, input_tokens=2000000)
        summary = aggregate_usage([base, conflict], load_rate_table(self.rates_path))
        self.assertEqual(summary["event_count"], 1)
        exported = summary["query_events"][0]
        self.assertEqual(exported["unknown_reasons"], ["conflicting_duplicate"])
        self.assertTrue(exported["dedup_conflict"])
        self.assertIsNone(exported["tokens_by_bucket"]["input_uncached"])
        self.assertIsNone(exported["total_tokens"])
        self.assertIsNone(exported["list_equivalent_cost_usd"])
        self.assertIsNone(exported["observed_cost_usd"])

    def test_receipt_reference_hash_is_stable_across_repeated_bundle_reloads(self):
        event = {
            "provider": "example-provider", "request_id": "req-attributed", "model": "model-a",
            "timestamp": "2026-11-01T00:00:00Z",
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
            "attributions": [{"pr": "example/repo#3", "weight": 1, "method": "direct",
                              "receipt_refs": ["receipt-id"], "rationale": "scoped receipt"}],
        }
        rates = load_rate_table(self.rates_path)
        initial = load_usage_events([event], provider="example-provider")
        publisher = Publisher(repo_path=self.tempdir.name)
        first = publisher.write_telemetry_bundle(None, usage_events=initial, usage_rates=rates)
        first_rows = [json.loads(line) for line in next(v for k, v in first.items() if k.endswith("usage_events.jsonl")).splitlines()]
        reloaded = load_usage_events(first_rows, provider="example-provider")
        second = publisher.write_telemetry_bundle(None, usage_events=reloaded, usage_rates=rates)
        second_rows = [json.loads(line) for line in next(v for k, v in second.items() if k.endswith("usage_events.jsonl")).splitlines()]
        self.assertEqual(first_rows, second_rows)
        combined = aggregate_usage(load_usage_events(first_rows + second_rows, provider="example-provider"), rates)
        self.assertEqual(combined["event_count"], 1)
        self.assertEqual(combined["unknown_event_count"], 0)
        self.assertEqual(combined["known_cost_usd"], 1)

    def test_supported_explicit_attribution_keeps_partial_pr_subtotal(self):
        event = {
            "request_id": "req-partial", "timestamp": "2026-11-01T00:00:00Z", "model": "model-a",
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 1000000, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
            "attributions": [{"pr": "example/repo#2", "weight": 1, "method": "direct",
                              "receipt_refs": ["receipt-id"], "rationale": "direct request scope"}],
        }
        with open(self.events_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        rate_card = {
            "provider": "example-provider", "currency": "USD", "effective_from": "2026-10-22T00:00:00Z",
            "observed_current_at": "2026-11-01T00:00:00Z", "source_url": "https://example.invalid/rates",
            "rate_basis": "standard_global_public_list_price",
            "rates": {"model-a": {"input_tokens": "1"}},
        }
        with open(self.rates_path, "w", encoding="utf-8") as stream:
            json.dump(rate_card, stream)
        summary = aggregate_usage(load_usage_events(self.events_path, provider="example-provider"),
                                  load_rate_table(self.rates_path))
        pr = summary["prs"]["example/repo#2"]
        self.assertEqual(pr["known_cost_usd"], 1)
        self.assertEqual(pr["pricing_status"], "partial")

    def test_timestamp_only_duplicate_preserves_one_known_usage_observation(self):
        base = {
            "provider": "example-provider", "sku": "model-a", "usage_id": "same-timestamp-id",
            "timestamp": "2026-11-01T00:00:00Z", "input_tokens": 1000000,
            "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
            "output_tokens": 0, "reasoning_tokens": 0, "service_tier": "standard",
            "inference_geo": "global", "speed": "standard", "attributions": [],
        }
        rates = load_rate_table(self.rates_path)
        later_observation = dict(base, timestamp="2026-11-01T00:00:01Z")
        deduplicated = aggregate_usage([base, later_observation], rates)
        self.assertEqual(deduplicated["source_records"], 2)
        self.assertEqual(deduplicated["event_count"], 1)
        self.assertEqual(deduplicated["priced_event_count"], 1)
        self.assertEqual(deduplicated["unknown_event_count"], 0)
        self.assertEqual(deduplicated["known_cost_usd"], 1)

        token_conflict = aggregate_usage(
            [base, dict(base, input_tokens=2000000)], rates
        )
        model_conflict = aggregate_usage([base, dict(base, sku="model-b")], rates)
        for conflict in (token_conflict, model_conflict):
            self.assertEqual(conflict["event_count"], 1)
            self.assertEqual(conflict["unknown_event_count"], 1)
            self.assertEqual(conflict["known_cost_usd"], 0)

    def test_identical_duplicate_is_counted_once_and_conflicting_duplicate_is_unknown(self):
        base = {
            "provider": "example-provider", "sku": "model-a", "usage_id": "same-id",
            "timestamp": "2026-11-01T00:00:00Z", "input_tokens": 1000000,
            "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
            "output_tokens": 0, "service_tier": "standard", "inference_geo": "global", "speed": "standard",
            "attributions": [],
        }
        rates = load_rate_table(self.rates_path)
        same = aggregate_usage([base, dict(base)], rates)
        self.assertEqual(same["event_count"], 1)
        self.assertEqual(same["known_cost_usd"], 1)
        conflict = aggregate_usage([base, dict(base, input_tokens=2000000)], rates)
        self.assertEqual(conflict["event_count"], 1)
        self.assertEqual(conflict["unknown_event_count"], 1)
        self.assertEqual(conflict["known_cost_usd"], 0)

    def test_missing_model_does_not_fall_back_to_requested_model_and_bad_pr_is_not_retained(self):
        event = {
            "request_id": "req-unsafe", "timestamp": "2026-11-01T00:00:00Z", "requested_model": "model-a",
            "raw_usage": {"input_tokens": 1000000, "output_tokens": 0, "service_tier": "standard",
                          "inference_geo": "global", "speed": "standard"},
            "attributions": [{"pr": "/Users/private/sk-secret", "weight": 1, "method": "direct",
                              "receipt_refs": ["receipt"], "rationale": "x"}],
        }
        with open(self.events_path, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        summary = aggregate_usage(load_usage_events(self.events_path, provider="example-provider"),
                                  load_rate_table(self.rates_path))
        self.assertEqual(summary["unknown_event_count"], 1)
        self.assertEqual(summary["prs"], {})
        retained = json.dumps(_retained_usage_summary(summary))
        self.assertNotIn("/Users/private", retained)
        self.assertNotIn("sk-secret", retained)

    def test_retained_feed_reloads_through_cli_without_feed_flags(self):
        cutoff = "2026-11-02T00:00:00Z"
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "prw_metrics.py"))
        first = subprocess.run(
            [sys.executable, script, "--offline", "--cutoff", cutoff, "--usage-events", self.events_path,
             "--usage-rates", self.rates_path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        events = load_usage_events(self.events_path, provider="example-provider")
        rates = load_rate_table(self.rates_path)
        aggregator = MetricsAggregator(cutoff_dt=parse_iso_utc(cutoff))
        summary = aggregate_usage(events, rates, window_start=aggregator.w1_start_dt, window_end=aggregator.cutoff_dt)
        bundle = Publisher(repo_path=self.tempdir.name).write_telemetry_bundle(
            {"usage_summary": _retained_usage_summary(summary), "w2_bounds": [cutoff, cutoff]},
            usage_events=events, usage_rates=rates,
        )
        telemetry_dir = os.path.join(self.tempdir.name, "telemetry")
        for relpath, content in bundle.items():
            prefix = "dashboards/prw/telemetry/"
            if not relpath.startswith(prefix):
                continue
            path = os.path.join(telemetry_dir, relpath[len(prefix):])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
        persisted_parts = []
        for root, _, names in os.walk(telemetry_dir):
            for name in names:
                with open(os.path.join(root, name), encoding="utf-8") as stream:
                    persisted_parts.append(stream.read())
        persisted = "\n".join(persisted_parts)
        self.assertNotIn("MUST NOT APPEAR", persisted)
        self.assertNotIn(self.tempdir.name, persisted)
        second = subprocess.run(
            [sys.executable, script, "--offline", "--cutoff", cutoff, "--telemetry-dir", telemetry_dir],
            check=True, capture_output=True, text=True, timeout=30,
        )
        for expected in ("Source records: 2; priced: 1; partially priced: 0; unknown: 1.",
                         "Known usage subtotal: $17.6000000 USD.", "cache_write_5m` 1000000",
                         "cache_write_1h` 1000000"):
            self.assertIn(expected, first.stdout)
            self.assertIn(expected, second.stdout)


class NativeClaudeUsageSourceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = self.root / "native"
        self.source.mkdir()
        self.events = self.source / "session.jsonl"
        self.rates = self.root / "rates.json"
        self.rates.write_text(json.dumps({
            "provider": "anthropic", "currency": "USD",
            "effective_from": "2026-11-01T00:00:00Z",
            "observed_current_at": "2026-11-08T00:00:00Z",
            "source_url": "https://example.invalid/rates",
            "rate_basis": "standard_global_public_list_price",
            "rates": {"claude-test": {
                "input_tokens": "1", "cache_read_input_tokens": "0.1",
                "output_tokens": "10", "write_5m": "2.5", "write_1h": "4",
            }},
        }), encoding="utf-8")
        self.script = Path(__file__).resolve().parents[1] / "scripts" / "prw_metrics.py"

    def tearDown(self):
        self.tempdir.cleanup()

    def _collect(self, *, check=True, telemetry_dir=None):
        command = [
            sys.executable, str(self.script), "--offline",
            "--cutoff", "2026-11-08T00:00:00Z",
            "--usage-source-dir", str(self.source),
            "--usage-rates", str(self.rates),
        ]
        if telemetry_dir:
            command.extend(["--telemetry-dir", str(telemetry_dir)])
        return subprocess.run(
            command, check=check, capture_output=True, text=True, timeout=30,
        )

    def _native_event(self, input_tokens=100):
        return {
            "type": "assistant", "timestamp": "2026-11-07T12:00:00Z",
            "requestId": "req-native-1",
            "message": {
                "id": "msg-native-1", "model": "claude-test",
                "usage": {
                    "input_tokens": input_tokens, "cache_read_input_tokens": 20,
                    "cache_creation": {
                        "ephemeral_5m_input_tokens": 30,
                        "ephemeral_1h_input_tokens": 40,
                    },
                    "output_tokens": 50,
                    "service_tier": "standard", "inference_geo": "global", "speed": "standard",
                },
                "content": [{"type": "text", "text": "PRIVATE_RESPONSE_MUST_NOT_LEAK"}],
            },
        }

    def test_new_native_request_is_seen_once_on_each_successive_collection(self):
        before = self._collect()
        self.assertIn("Source records: 0;", before.stdout)

        native = self._native_event()
        self.events.write_text(json.dumps(native) + "\n" + json.dumps(native) + "\n", encoding="utf-8")
        outputs = [self._collect().stdout for _ in range(2)]
        for output in outputs:
            self.assertIn("Source records: 2; priced: 1; partially priced: 0; unknown: 0.", output)
            self.assertIn("`input_uncached` 100", output)
            self.assertIn("`cache_read` 20", output)
            self.assertIn("`cache_write_5m` 30", output)
            self.assertIn("`cache_write_1h` 40", output)
            self.assertIn("`output` 50", output)
            self.assertIn("Reasoning tokens: 0", output)
            self.assertIn("Known usage subtotal: $0.0008370 USD.", output)
            self.assertIn("usage_records_in_window=2", output)
            self.assertIn("duplicate_usage_records=1", output)
            self.assertNotIn("PRIVATE_RESPONSE_MUST_NOT_LEAK", output)
            history = collect_native_history(
                [self.source], cutoff=datetime(2026, 11, 8, tzinfo=timezone.utc), days=14,
            )
            records, source_stats = history["usage_records"], history["stats"]
            self.assertEqual(len(records), 2)
            self.assertEqual({record["request_id"] for record in records}, {"req-native-1"})
            serialized = json.dumps(records)
            self.assertNotIn("PRIVATE_RESPONSE_MUST_NOT_LEAK", serialized)
            self.assertNotIn(str(self.source), serialized)
            self.assertEqual(records[0]["request_id"], "req-native-1")
            self.assertTrue(records[0]["source_fingerprint"].startswith("sha256:"))
            rates = load_rate_table(self.rates)
            normalized = load_usage_events(records, provider="anthropic")
            summary = aggregate_usage(normalized, rates)
            summary["coverage"]["native_source"] = source_stats
            bundle = Publisher(repo_path=str(self.root)).write_telemetry_bundle(
                {"usage_summary": _retained_usage_summary(summary)},
                usage_events=normalized,
                usage_rates=rates,
            )
            retained = json.dumps(bundle)
            self.assertNotIn("PRIVATE_RESPONSE_MUST_NOT_LEAK", retained)
            self.assertNotIn(str(self.source), retained)
            self.assertNotIn('"content"', retained)

    def test_conflicting_native_duplicate_is_unknown_instead_of_first_price(self):
        self.events.write_text(
            json.dumps(self._native_event(100)) + "\n"
            + json.dumps(self._native_event(200)) + "\n",
            encoding="utf-8",
        )
        output = self._collect().stdout
        self.assertIn("Source records: 2; priced: 0; partially priced: 0; unknown: 1.", output)
        self.assertIn("Known usage subtotal: UNKNOWN (no priced usage).", output)
        self.assertIn("Native source acquisition: COMPLETE", output)
        self.assertIn("other runtimes not collected", output)
        self.assertIn("usage_records_in_window=2", output)
        self.assertIn("duplicate_usage_records=1", output)

    def test_retained_native_requests_deduplicate_and_conflicts_remain_unknown(self):
        second = self._native_event(50)
        second["requestId"] = "req-native-2"
        second["message"]["id"] = "msg-native-2"
        second["timestamp"] = "2026-11-07T12:00:01Z"
        session_meta = {"type": "session_meta", "payload": {"id": "native-session-1"}}
        self.events.write_text(
            json.dumps(session_meta) + "\n"
            + json.dumps(self._native_event()) + "\n"
            + json.dumps(second) + "\n",
            encoding="utf-8",
        )
        annotations = self.root / "usage-annotations.jsonl"
        annotations.write_text(
            json.dumps({
                "provider": "anthropic", "request_id": "req-native-1",
                "pr_binding": {
                    "pr": "example/repo#9", "weight": 0.5, "method": "direct",
                    "basis": "separable_breakdown", "receipt_refs": ["receipt-1"],
                    "rationale": "verified request scope",
                },
            }) + "\n"
            + json.dumps({
                "provider": "anthropic", "request_id": "req-native-2",
                "pr_binding": {
                    "pr": "example/repo#9", "weight": "0.5", "method": "direct",
                    "basis": "separable_breakdown", "receipt_refs": ["receipt-2"],
                    "rationale": "verified request scope",
                },
            }) + "\n",
            encoding="utf-8",
        )
        history = collect_native_history(
            [self.source], cutoff=datetime(2026, 11, 8, tzinfo=timezone.utc),
            days=14, annotation_path=annotations,
        )
        self.assertEqual(len(history["usage_records"]), 2)
        self.assertEqual(
            {record["session_id"] for record in history["usage_records"]},
            {"native-session-1"},
        )
        rates = load_rate_table(self.rates)
        fresh = load_usage_events(history["usage_records"], provider="anthropic")
        bundle = Publisher(repo_path=self.tempdir.name).write_telemetry_bundle(
            None, usage_events=fresh, usage_rates=rates,
        )
        retained_jsonl = next(
            value for key, value in bundle.items() if key.endswith("usage_events.jsonl")
        )
        retained = load_usage_events(
            [json.loads(line) for line in retained_jsonl.splitlines()],
            provider="anthropic",
        )
        retained_by_id = {event["usage_id"]: event for event in retained}
        source_by_id = {event["usage_id"]: event for event in fresh}
        for request_id, retained_event in retained_by_id.items():
            with self.subTest(request_id=request_id, field="session_id"):
                self.assertEqual(
                    retained_event["session_id"], source_by_id[request_id]["session_id"]
                )
            with self.subTest(request_id=request_id, field="attributions"):
                self.assertEqual(
                    retained_event["attributions"], source_by_id[request_id]["attributions"]
                )

        combined = aggregate_usage(retained + fresh, rates)
        self.assertEqual(combined["event_count"], 2)
        self.assertEqual(combined["priced_event_count"], 2)
        self.assertEqual(combined["unknown_event_count"], 0)
        self.assertEqual(combined["tokens_by_bucket"]["input_uncached"], 150)

        changed = dict(fresh[0], input_tokens=fresh[0]["input_tokens"] + 1)
        conflict = aggregate_usage(retained + [changed, fresh[1]], rates)
        self.assertEqual(conflict["event_count"], 2)
        self.assertEqual(conflict["priced_event_count"], 1)
        self.assertEqual(conflict["unknown_event_count"], 1)

    def test_conflicting_retained_and_fresh_native_observations_reach_aggregator(self):
        telemetry = self.root / "telemetry"
        telemetry.mkdir()
        retained = {
            "provider": "anthropic", "request_id": "req-native-1",
            "message_id": "msg-native-1", "timestamp": "2026-11-07T12:00:00Z",
            "model": "claude-test",
            "raw_usage": {
                "input_tokens": 200, "cache_read_input_tokens": 20,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 30, "ephemeral_1h_input_tokens": 40,
                },
                "output_tokens": 50, "service_tier": "standard",
                "inference_geo": "global", "speed": "standard",
            },
        }
        (telemetry / "usage_events.jsonl").write_text(json.dumps(retained) + "\n", encoding="utf-8")
        self.events.write_text(json.dumps(self._native_event(100)) + "\n", encoding="utf-8")
        output = self._collect(telemetry_dir=telemetry).stdout
        self.assertIn("Source records: 2; priced: 0; partially priced: 0; unknown: 1.", output)
        self.assertIn("Known usage subtotal: UNKNOWN (no priced usage).", output)

    def test_publish_receives_failed_status_when_configured_native_source_is_missing(self):
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        collected = {
            "prs": [{
                "number": 1, "repo": "example/repo", "url": "https://example.invalid/pull/1",
                "headRefOid": "abcdef123456", "state": "OPEN", "title": "fresh fixture",
                "createdAt": now, "updatedAt": now, "labels": [],
            }],
            "timeline": [], "handoff_records": [],
            "sources": {"example/repo": {"status": "COMPLETE", "cutoff": now}},
            "status": "COMPLETE",
        }
        publish = mock.Mock(return_value={"action": "RETAINED_PRIOR", "committed": False})
        args = [
            str(self.script), "--offline", "--publish", "--roadmap-repo", str(self.root),
            "--usage-source-dir", str(self.root / "missing-source"),
            "--cutoff", now,
        ]
        with redirect_stdout(io.StringIO()), \
                mock.patch("scripts.prw_metrics.Collector.collect_all", return_value=collected), \
                mock.patch("scripts.prw_metrics.publish_dashboard", publish), \
                mock.patch("sys.argv", args):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 3)
        self.assertTrue(publish.called)
        self.assertEqual(publish.call_args.kwargs["status"], "FAILED")

    def test_partial_native_source_keeps_existing_publication_status(self):
        self.events.write_text("{malformed}\n", encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        collected = {
            "prs": [{
                "number": 1, "repo": "example/repo", "url": "https://example.invalid/pull/1",
                "headRefOid": "abcdef123456", "state": "OPEN", "title": "fresh fixture",
                "createdAt": now, "updatedAt": now, "labels": [],
            }],
            "timeline": [], "handoff_records": [],
            "sources": {"example/repo": {"status": "COMPLETE", "cutoff": now}},
            "status": "COMPLETE",
        }
        publish = mock.Mock(return_value={"action": "RETAINED_PRIOR", "committed": False})
        args = [
            str(self.script), "--offline", "--publish", "--roadmap-repo", str(self.root),
            "--usage-source-dir", str(self.source), "--cutoff", now,
        ]
        with redirect_stdout(io.StringIO()), \
                mock.patch("scripts.prw_metrics.Collector.collect_all", return_value=collected), \
                mock.patch("scripts.prw_metrics.publish_dashboard", publish), \
                mock.patch("sys.argv", args):
            main()
        self.assertEqual(publish.call_args.kwargs["status"], "FRESH")

    def test_missing_native_source_is_visible_and_returns_failure(self):
        self.source.rmdir()
        proc = self._collect(check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Native source acquisition: FAILED", proc.stdout)
        self.assertIn("missing_roots=1", proc.stdout)
        self.assertNotIn(str(self.source), proc.stdout)

    def test_scan_counts_malformed_and_unusable_rows_without_exposing_source_paths(self):
        self.events.write_text(
            "{malformed}\n"
            + json.dumps({
                "type": "assistant", "timestamp": "2026-11-07T12:00:00", "requestId": "req-bad",
                "message": {"model": "claude-test", "usage": {"input_tokens": 2}},
            }) + "\n",
            encoding="utf-8",
        )
        output = self._collect().stdout
        self.assertIn("Source records: 0;", output)
        self.assertIn("files_scanned=1", output)
        self.assertIn("malformed_lines=1", output)
        self.assertIn("undated_records=1", output)
        self.assertNotIn(str(self.source), output)


if __name__ == "__main__":
    unittest.main()
