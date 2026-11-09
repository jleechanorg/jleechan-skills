"""CLI-level checks for actual usage feed and rate-card wiring."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from scripts.prw_metrics import (
    _retained_usage_summary,
    MetricsAggregator,
    Publisher,
    aggregate_usage,
    load_rate_table,
    load_usage_events,
    parse_iso_utc,
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
        self.assertEqual(len(projected["rate_records"]), 5)
        self.assertIsNone(projected["events"][1]["known_cost_usd"])
        self.assertEqual(projected["known_cost_usd"], "17.6")
        serialized = json.dumps(projected)
        self.assertNotIn("MUST NOT APPEAR", serialized)
        self.assertNotIn(self.tempdir.name, serialized)
        self.assertIn('"price_per_million": "1"', serialized)

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


if __name__ == "__main__":
    unittest.main()
