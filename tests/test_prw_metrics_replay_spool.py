"""The scheduled reader may release each usage row after validating its bytes."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.native_usage_collector import load_normalized_history


class StreamingReplayTest(unittest.TestCase):
    def test_callback_receives_usage_without_retaining_export_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.jsonl"
            usage = {"record_type": "usage", "request_id": "one", "provider": "openai",
                     "timestamp": "2026-11-18T00:00:00Z", "raw_usage": {}}
            human = {"record_type": "human", "event_id": "two", "provider": "openai",
                     "timestamp": usage["timestamp"]}
            path.write_text("".join(json.dumps(r) + "\n" for r in (usage, human, usage)))
            kwargs = dict(cutoff="2026-11-19T00:00:00Z")
            baseline = load_normalized_history(path, **kwargs)
            received = []

            def consume(row):
                duplicate = row in received
                received.append(row)
                return duplicate

            streamed = load_normalized_history(path, on_usage=consume, **kwargs)
            self.assertEqual(baseline["usage_records"], received)
            self.assertEqual(baseline["human_records"], streamed["human_records"])
            self.assertEqual(baseline["stats"], streamed["stats"])
            self.assertEqual([], streamed["usage_records"])
            self.assertEqual([], streamed["export_records"])
