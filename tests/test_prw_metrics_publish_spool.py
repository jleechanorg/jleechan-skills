import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts import prw_metrics as metrics


class PublisherSpoolTests(unittest.TestCase):
    def test_spooled_usage_parts_match_existing_bytes_and_manifest(self):
        records = [
            {"timestamp": f"2026-11-21T00:{index:02d}:00Z",
             "provider": "openai", "request_id": f"req-{index}",
             "attributions": [{"pr": "owner/repo#12", "weight": 1}]}
            for index in range(20)
        ]
        expected = metrics._usage_parts(records, max_bytes=900)

        with tempfile.TemporaryDirectory() as directory:
            actual = metrics._write_usage_parts(iter(records), directory, max_bytes=900)
            self.assertEqual(set(actual), set(expected))
            for name, old_content in expected.items():
                self.assertIsInstance(actual[name], Path)
                self.assertEqual(actual[name].read_bytes(), old_content.encode("utf-8"))

    def test_streamed_summary_is_byte_identical_to_legacy_snapshot(self):
        priced_rows = [
            {"status": "priced", "known_cost_usd": Decimal("0.001"),
             "unknown_buckets": [], "tokens_by_bucket": {"output": index}}
            for index in range(4)
        ]
        events = [metrics._retained_usage_event(row) for row in priced_rows]
        summary = {
            "w2_bounds": ["2026-11-20T00:00:00Z", "2026-11-21T00:00:00Z"],
            "status": "COMPLETE",
            "usage_summary": {
                "label": "test", "events": events,
                "rate_records": [{"provider": "openai", "sku": "model"}],
            },
        }
        expected = metrics._summary_parts(summary)["summary_snapshot.json"].encode("utf-8")
        retained = json.loads(json.dumps(summary))
        retained["usage_summary"].pop("events")

        with tempfile.TemporaryDirectory() as directory:
            actual = metrics._write_streamed_summary_parts(
                retained, iter(priced_rows), directory
            )["summary_snapshot.json"]
            self.assertIsInstance(actual, Path)
            self.assertEqual(actual.read_bytes(), expected)

    def test_large_streamed_summary_round_trips_through_existing_parts(self):
        events = [
            {"status": "priced", "known_cost_usd": "0.001",
             "unknown_buckets": [], "tokens_by_bucket": {"output": index}}
            for index in range(20)
        ]
        summary = {
            "w2_bounds": ["2026-11-20T00:00:00Z", "2026-11-21T00:00:00Z"],
            "status": "COMPLETE",
            "usage_summary": {
                "label": "test", "events": events,
                "rate_records": [{"provider": "openai", "sku": "model"}],
            },
        }
        retained = json.loads(json.dumps(summary))
        retained["usage_summary"].pop("events")

        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(metrics, "USAGE_SHARD_BYTES", 300):
            actual = metrics._write_streamed_summary_parts(
                retained, iter(events), directory
            )
            paths = {name: path.read_text() if isinstance(path, Path) else path
                     for name, path in actual.items()}
            restored = metrics._read_summary_bundle(paths, paths.__getitem__)
            self.assertEqual(restored, metrics._project_summary(summary))
            self.assertGreater(len(actual), 1)

    def test_gcs_upload_hashes_and_compresses_path_without_raw_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "usage_events.jsonl"
            source.write_bytes(b"{\"usage_id\":\"one\"}\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            zstd_inputs = []

            def copy_to_zstd(*args):
                zstd = Path(args[args.index("-o") + 1])
                source = Path(args[-1])
                zstd_inputs.append(source)
                shutil.copyfile(source, zstd)
                return mock.Mock(returncode=0, stderr=b"")

            with mock.patch.object(metrics, "_stored_object",
                                   side_effect=[None, (digest, 12)]), \
                 mock.patch.object(metrics, "_zstd", side_effect=copy_to_zstd), \
                 mock.patch.object(metrics, "_gcs",
                                   return_value=mock.Mock(returncode=0, stderr=b"")) as upload:
                entries = metrics._upload_window(
                    "20261121", {"usage_events.jsonl": source},
                    "gs://private-bucket/prw/telemetry",
                )

            self.assertEqual(upload.call_count, 1)
            self.assertEqual(entries[0]["bytes"], source.stat().st_size)
            self.assertEqual(entries[0]["sha256"], digest)
            self.assertEqual(zstd_inputs, [source])

    def test_bundle_writer_can_return_private_files_for_publish_without_string_copies(self):
        summary_events = [
            {"status": "priced", "known_cost_usd": "0.001",
             "unknown_buckets": [], "tokens_by_bucket": {"output": index}}
            for index in range(5)
        ]
        usage_events = [
            {"timestamp": f"2026-11-21T00:{index:02d}:00Z",
             "provider": "openai", "request_id": f"req-{index}"}
            for index in range(5)
        ]
        retained_summary = {
            "w2_bounds": ["2026-11-20T00:00:00Z", "2026-11-21T00:00:00Z"],
            "status": "COMPLETE",
            "usage_summary": {
                "label": "test", "events": summary_events,
                "rate_records": [{"provider": "openai", "sku": "model"}],
            },
        }
        without_events = json.loads(json.dumps(retained_summary))
        without_events["usage_summary"].pop("events")
        publisher = metrics.Publisher(repo_path="unused")
        expected = publisher.write_telemetry_bundle(
            retained_summary, usage_events=usage_events, window_slug="20261121"
        )
        with tempfile.TemporaryDirectory() as directory:
            actual = publisher.write_telemetry_bundle(
                without_events, usage_events=iter(usage_events),
                usage_summary_events=iter(summary_events), window_slug="20261121",
                spool_dir=directory,
            )
            self.assertEqual(set(actual), set(expected))
            for name, content in expected.items():
                payload = actual[name].read_bytes() if isinstance(actual[name], Path) else actual[name].encode()
                self.assertEqual(payload, content.encode(), name)
            self.assertTrue(all(isinstance(actual[name], Path) for name in (
                "dashboards/prw/telemetry/20261121/usage_events.jsonl",
                "dashboards/prw/telemetry/20261121/summary_snapshot.json",
            )))

    def test_publish_hashes_spooled_payloads_without_rebuilding_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, checkout, spool = root / "remote.git", root / "checkout", root / "spool"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                           capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(checkout)], check=True,
                           capture_output=True)

            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()

            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (checkout / "README.md").write_text("initial\n")
            git("add", "README.md")
            git("commit", "-m", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "-u", "origin", "main")
            spool.mkdir(mode=0o700)

            events = [
                {"status": "priced", "known_cost_usd": "0.01",
                 "unknown_buckets": [], "tokens_by_bucket": {"output": index}}
                for index in range(3)
            ]
            summary = {
                "status": "COMPLETE",
                "usage_summary": {"label": "fixture", "events": events},
            }
            retained = json.loads(json.dumps(summary))
            retained["usage_summary"].pop("events")
            expected = metrics._summary_parts(summary)["summary_snapshot.json"]

            with mock.patch.dict(os.environ, {"PRW_METRICS_TELEMETRY_BUCKET": ""}):
                result = metrics.publish_dashboard(
                    "# dashboard\n", str(checkout),
                    verify_private_fn=lambda _: True,
                    publish_telemetry=True,
                    summary_data=retained,
                    usage_summary_events=iter(events),
                    spool_dir=spool,
                )

            self.assertEqual(result["action"], "COMMITTED", result)
            commit = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            window = "20261121"
            content = subprocess.run(
                ["git", "--git-dir", str(remote), "show",
                 f"{commit}:dashboards/prw/telemetry/{window}/summary_snapshot.json"],
                check=True, capture_output=True, text=True,
            ).stdout
            self.assertEqual(content, expected)


if __name__ == "__main__":
    unittest.main()
