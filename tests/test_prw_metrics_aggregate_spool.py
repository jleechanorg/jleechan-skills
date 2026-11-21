"""Parity and bounded-output checks for the replay-only usage spool."""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.prw_metrics import aggregate_usage, parse_iso_utc


class AggregateUsageSpoolTests(unittest.TestCase):
    def setUp(self):
        self.start = parse_iso_utc("2026-11-01T00:00:00Z")
        self.end = parse_iso_utc("2026-11-08T00:00:00Z")
        self.events = [
            {
                "provider": "example", "sku": "model-a", "usage_id": "one",
                "session_id": "session-one", "timestamp": "2026-11-02T00:00:00Z",
                "input_tokens": 1000000, "output": 10, "output_tokens": 10,
                "input_uncached": 1000000, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
            {
                "provider": "example", "sku": "model-a", "usage_id": "two",
                "timestamp": "2026-11-02T00:00:00Z", "input_tokens": 4,
                "output_tokens": 0, "input_uncached": 4, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
            {
                "provider": "example", "sku": "model-a", "usage_id": "one",
                "session_id": "session-one", "timestamp": "2026-11-03T00:00:00Z",
                "input_tokens": 1000000, "output": 10, "output_tokens": 10,
                "input_uncached": 1000000, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
            {
                "provider": "example", "sku": "model-a", "usage_id": "three",
                "timestamp": "2026-11-08T00:00:00Z", "input_tokens": 8,
                "output_tokens": 0, "input_uncached": 8, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
            {
                "provider": "example", "sku": "model-a", "usage_id": "four",
                "timestamp": "2026-10-31T23:59:59Z", "input_tokens": 16,
                "output_tokens": 0, "input_uncached": 16, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
            {
                "provider": "example", "sku": "model-a", "usage_id": "five",
                "timestamp": "invalid", "input_tokens": 32, "output_tokens": 0,
                "input_uncached": 32, "cache_read": 0,
                "cache_write_5m": 0, "cache_write_1h": 0,
                "service_tier": "standard", "inference_geo": "global",
                "speed": "standard", "attributions": [],
            },
        ]

    def test_spool_matches_list_result_and_writes_replayable_jsonl(self):
        regular = aggregate_usage(
            self.events, [], self.start, self.end,
        )
        with tempfile.TemporaryDirectory() as temporary:
            bounded = aggregate_usage(
                (event for event in self.events), [], self.start, self.end,
                spool_dir=temporary,
            )
            for key in (
                "source_records", "event_count", "outside_window_count", "undated_count",
                "priced_event_count", "partially_priced_event_count", "unknown_event_count",
                "known_cost_usd", "unallocated", "tokens_by_bucket", "reasoning_tokens",
                "coverage", "prs", "pr_cost_distribution",
            ):
                self.assertEqual(bounded[key], regular[key], key)
            self.assertEqual(list(bounded["events"]), list(bounded["query_events"]))
            self.assertEqual(len(bounded["events"]), 2)
            self.assertTrue(Path(bounded["events"].path).is_file())
            self.assertEqual(len(list(bounded["events"])), 2)
            self.assertEqual(bounded["events"][0]["known_cost_usd"], regular["events"][0]["known_cost_usd"])
            self.assertEqual(
                list(bounded["events"].retained_rows()),
                [
                    {key: row[key] for key in (
                        "status", "known_cost_usd", "unknown_buckets", "tokens_by_bucket"
                    )}
                    for row in bounded["events"]
                ],
            )

    def test_spool_preserves_missing_id_and_conflict_semantics(self):
        missing = dict(self.events[0], usage_id=None, input_tokens=10, input_uncached=10)
        base = dict(self.events[0], usage_id="same", input_tokens=10, input_uncached=10)
        conflict = dict(base, input_tokens=11, input_uncached=11)
        with tempfile.TemporaryDirectory() as temporary:
            result = aggregate_usage([missing, base, conflict], [], spool_dir=temporary)
            rows = list(result["events"])
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]["request_id_present"])
        self.assertIn("usage_identity_missing", rows[0]["unknown_reasons"])
        self.assertIsNone(rows[1]["tokens_by_bucket"]["input_uncached"])
        self.assertTrue(rows[1]["dedup_conflict"])


if __name__ == "__main__":
    unittest.main()
