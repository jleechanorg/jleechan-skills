"""The scheduled reader may release each usage row after validating its bytes."""

from contextlib import redirect_stdout
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import prw_metrics as metrics
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

    def test_cli_replay_publishes_nonzero_priced_summary_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, checkout = root / "remote.git", root / "roadmap"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                           capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(checkout)], check=True,
                           capture_output=True)

            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()

            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (checkout / "README.md").write_text("initial\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-m", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "-u", "origin", "main")

            replay = root / "replay.jsonl"
            replay.write_text(json.dumps({
                "record_type": "usage", "provider": "openai", "request_id": "req-1",
                "session_id": "session-1", "timestamp": "2026-11-01T00:00:00Z",
                "model": "model-a", "raw_usage": {
                    "input_tokens": 0, "cache_read_input_tokens": 0,
                    "output_tokens": 1000, "service_tier": "standard",
                    "inference_geo": "global", "speed": "standard",
                },
            }) + "\n", encoding="utf-8")
            rates = root / "rates.json"
            rates.write_text(json.dumps({"rates": [{
                "provider": "openai", "sku": "model-a", "bucket": "output",
                "price_per_million": "1", "currency": "USD",
                "source_url": "https://example.invalid/rates",
                "rate_basis": "standard_global_public_list_price", "unit": "token",
                "service_tier": "standard", "inference_geo": "global", "speed": "standard",
                "retrieved_at": "2026-11-01T00:00:00Z",
                "effective_from": "2026-10-01T00:00:00Z", "effective_to": None,
            }]}, indent=2), encoding="utf-8")

            args = [
                "prw_metrics.py", "--offline", "--history-replay", str(replay),
                "--usage-rates", str(rates), "--cutoff", "2026-11-02T00:00:00Z",
                "--publish", "--roadmap-repo", str(checkout),
            ]
            with redirect_stdout(io.StringIO()), \
                    mock.patch.dict(os.environ, {"PRW_METRICS_TELEMETRY_BUCKET": ""}), \
                    mock.patch.object(metrics.Publisher, "_verify_destination_is_private",
                                      return_value=True), \
                    mock.patch.object(metrics.Collector, "collect_all", return_value={
                        "prs": [], "timeline": [], "sources": {}, "status": "COMPLETE",
                        "handoff_records": [], "usage_events": [],
                    }), \
                    mock.patch("sys.argv", args):
                metrics.main()

            commit = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            paths = subprocess.run(
                ["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", commit],
                check=True, capture_output=True, text=True,
            ).stdout.splitlines()
            snapshot_path = next(path for path in paths if path.endswith("/summary_snapshot.json"))
            snapshot = subprocess.run(
                ["git", "--git-dir", str(remote), "show",
                 f"{commit}:{snapshot_path}"],
                check=True, capture_output=True, text=True,
            ).stdout
            usage = json.loads(snapshot)["usage_summary"]
            self.assertEqual(usage["known_cost_usd"], "0.001")
            self.assertEqual(usage["events"][0]["known_cost_usd"], "0.001")
            self.assertEqual(usage["events"][0]["status"], "partial")
