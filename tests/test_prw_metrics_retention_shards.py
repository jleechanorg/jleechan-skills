"""Bounded retained usage publication through real local Git and replay readers."""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import prw_metrics as m


class RetainedUsageShards(unittest.TestCase):
    def rows(self, count):
        return [{"provider": "example", "request_id": f"req-{i}", "session_id": "session",
                 "timestamp": "2026-11-09T00:00:00Z", "model": "model",
                 "raw_usage": {"input_tokens": i, "output_tokens": 2},
                 "usage_conflict": i == 1, "attributions": [], "raw_message": "private text"}
                for i in range(count)]

    def test_exact_byte_boundary_roundtrip_privacy_and_integrity(self):
        rows = self.rows(5)
        # Sanitizer intentionally admits ASCII labels only. A synthetic sanitized
        # Unicode value isolates UTF-8 byte accounting without widening that policy.
        with mock.patch.object(m, "_sanitize_usage_event_record", side_effect=lambda x: x):
            unicode_rows = [{"value": "é"}, {"value": "界"}]
            limit = len((json.dumps(unicode_rows[0], ensure_ascii=False) + "\n").encode())
            with self.assertRaises(ValueError):
                m._usage_parts(unicode_rows, max_bytes=limit)
            limit = len((json.dumps(unicode_rows[1], ensure_ascii=False) + "\n").encode())
            parts = m._usage_parts(unicode_rows, max_bytes=limit)
            self.assertEqual(m._read_usage_bundle(parts, parts.__getitem__), unicode_rows)
            self.assertTrue(all(len(v.encode()) <= limit for k, v in parts.items() if k.endswith('.jsonl')))
        with mock.patch.object(m, "USAGE_SHARD_BYTES", 1500):
            parts = m._usage_parts(rows)
            self.assertGreater(len(parts), 2)
            self.assertTrue(all(len(v.encode()) <= 1500 for k, v in parts.items() if k.endswith('.jsonl')))
            expected = [m._sanitize_usage_event_record(r) for r in rows]
            self.assertEqual(m._read_usage_bundle(parts, parts.__getitem__), expected)
            self.assertNotIn('private text', ''.join(parts.values()))
            for name, content in parts.items():
                self.assertEqual(m.sanitize_telemetry_file('dashboards/prw/telemetry/20261109/' + name, content), content)
            for broken in (dict(parts, **{'usage_events.jsonl': ''}),
                           {k: v for k, v in parts.items() if k != 'usage_events.part-000001.jsonl'},
                           dict(parts, **{'usage_events.part-000000.jsonl': '{}\n'})):
                with self.assertRaises(ValueError):
                    m._read_usage_bundle(broken, broken.__getitem__)
        with self.assertRaises(ValueError):
            m._usage_parts(rows, max_bytes=1)
        with self.assertRaises(ValueError):
            m.sanitize_telemetry_file('dashboards/prw/telemetry/20261109/usage_events.part-../x.jsonl', '{}')
        with self.assertRaises(ValueError):
            m._read_usage_bundle({'usage_events.part-000000.jsonl'}, lambda _: '{}\n')

    def export_fixture(self, root):
        repo = root / "repo"
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)
        git('init', '-q'); git('config', 'user.name', 'Test Bot')
        git('config', 'user.email', 'test@example.invalid')
        git('add', '.'); git('commit', '-qm', 'retained fixture')
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        exported = root / 'exported'
        self.assertTrue(m.export_published_telemetry(str(repo), str(exported)))
        return exported

    def test_crlf_tampering_rejected_before_and_after_git_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / 'repo/dashboards/prw/telemetry/20261109'
            bundle.mkdir(parents=True)
            with mock.patch.object(m, 'USAGE_SHARD_BYTES', 1500):
                parts = m._usage_parts(self.rows(5))
            for name, content in parts.items():
                (bundle / name).write_bytes(content.encode())
            part = 'usage_events.part-000000.jsonl'
            original = (bundle / part).read_bytes()
            tampered = original.replace(b'\n', b'\r\n')
            self.assertNotEqual(tampered, original)
            (bundle / part).write_bytes(tampered)
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                m.Collector().load_retained_telemetry(str(bundle))
            exported = self.export_fixture(root) / '20261109'
            self.assertEqual((exported / part).read_bytes(), tampered)
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                m.Collector().collect_all(telemetry_dir=str(exported), offline=True)

    def test_malformed_part_names_survive_discovery_export_and_fail_closed(self):
        malformed = 'usage_events.part-00000.jsonl'
        with self.assertRaisesRegex(ValueError, 'unexpected retained usage filename'):
            m._read_usage_bundle({malformed}, lambda _: b'{}\n')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for window in ['20261108', '20261109']:
                bundle = root / 'repo/dashboards/prw/telemetry' / window
                bundle.mkdir(parents=True)
                (bundle / malformed).write_bytes(b'{}\n')
                if window == '20261109':
                    (bundle / 'usage_events.jsonl').write_bytes(b'{}\n')
                self.assertIn(str(bundle), m.retained_telemetry_dirs(str(bundle)))
                with self.assertRaisesRegex(ValueError, 'unexpected retained usage filename'):
                    m.Collector().load_retained_telemetry(str(bundle))
            exported = self.export_fixture(root)
            for window in ['20261108', '20261109']:
                bundle = exported / window
                self.assertEqual((bundle / malformed).read_bytes(), b'{}\n')
                with self.assertRaisesRegex(ValueError, 'unexpected retained usage filename'):
                    m.Collector().collect_all(telemetry_dir=str(bundle), offline=True)

    def test_summary_transport_raw_integrity_and_unexpected_files(self):
        summary = {"usage_summary": {"events": [{"status": "UNKNOWN", "known_cost_usd": None,
                    "tokens_by_bucket": {"é": i}} for i in range(20)]}, "private": "excluded"}
        with mock.patch.object(m, 'USAGE_SHARD_BYTES', 800):
            parts = m._summary_parts(summary)
            self.assertEqual(m._read_summary_bundle(parts, parts.__getitem__), m._project_summary(summary))
            part = 'summary_snapshot.part-000000.jsonl'
            for broken in (dict(parts, **{part: parts[part].replace('\n', '\r\n')}),
                           {k:v for k,v in parts.items() if k != part},
                           dict(parts, **{'summary_snapshot.part-00000.jsonl': '{}'})):
                with self.assertRaises(ValueError):
                    m._read_summary_bundle(broken, broken.__getitem__)

    def test_oversized_manifests_block_before_any_git_publication(self):
        # Separate injected part and hard-blob budgets: parts fit, metadata does
        # not. Production defaults are independently both 32 MiB.
        summary = {"w2_bounds": ["2026-11-02T00:00:00Z", "x"],
                   "usage_summary": {"events": [{"status": "UNKNOWN"} for _ in range(300)]}}
        cases = [
            ({"summary_data": summary}, "summary_snapshot.manifest.json"),
            ({"summary_data": {"w2_bounds": summary["w2_bounds"]},
              "usage_events": m.load_usage_events(self.rows(100))}, "usage_events.manifest.json"),
        ]
        for kwargs, manifest_name in cases:
            with self.subTest(manifest=manifest_name), tempfile.TemporaryDirectory() as temp:
                publisher = m.Publisher(temp)
                with mock.patch.object(m, "USAGE_SHARD_BYTES", 900), \
                     mock.patch.object(m, "TELEMETRY_BLOB_BYTES", 1100, create=True), \
                     mock.patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess(
                         [], 0, stdout="synthetic-hash\n", stderr="")) as git_calls:
                    bundle = publisher.write_telemetry_bundle(**kwargs)
                    manifest = next(content for path, content in bundle.items() if path.endswith(manifest_name))
                    self.assertGreater(len(manifest.encode()), 1100)
                    self.assertTrue(all(len(content.encode()) <= 900 for path, content in bundle.items()
                                        if ".part-" in path))
                    result = publisher.publish("# Dashboard\n", verify_private_fn=lambda _: True,
                                               publish_telemetry=True, **kwargs)
                    self.assertEqual(result["action"], "BLOCKED", result)
                    self.assertFalse(result["committed"])
                    self.assertIn(manifest_name, result["reason"])
                    git_calls.assert_not_called()
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_ownership_publication_excludes_local_paths(self):
        pr_id = "acme/app#12"
        url = "https://github.com/acme/app/pull/12"
        versioned = {
            "record_type": "transition_event", "schema_version": 1,
            "pr_id": pr_id, "pr_url": url, "event_id": "evt-2", "repo": "acme/app", "sequence": 2,
            "source": ".scratch/private/session.jsonl",
            "result_receipt": r"C:\private\driver.log",
            "wait_reason": "worktrees/customer-x/transcripts/run.jsonl",
            "state": "private/states/current.json",
            "preceding_event_id": "evt-1", "continuity_from_event_id": "evt-1",
            "owner_id": "driver:abc-1",
            "continuity_receipt": {
                "receipt_id": "../local/driver.log", "owner_id": "driver:abc-1", "pr_id": pr_id,
                "covers_to": "internal/run/close.log",
            },
        }
        earlier = dict(versioned, event_id="evt-1", source="driver-session-1",
                       result_receipt=url, continuity_receipt=None, wait_reason=None)
        legacy = dict(versioned, event_id="legacy")
        del legacy["schema_version"]
        future = dict(versioned, event_id="future", schema_version=2)
        records = [earlier, versioned, legacy, future]
        with tempfile.TemporaryDirectory() as temp:
            bundle = m.Publisher(temp).write_telemetry_bundle(
                {}, window_slug="20261109", handoff_records=records
            )
        path = "dashboards/prw/telemetry/20261109/retained_handoffs.jsonl"
        first, second, retained_legacy, retained_future = map(json.loads, bundle[path].splitlines())
        for field in ("source", "result_receipt", "wait_reason", "state"):
            self.assertIsNone(second.get(field))
        self.assertIsNone(second["continuity_receipt"].get("receipt_id"))
        self.assertIsNone(second["continuity_receipt"].get("covers_to"))
        self.assertIsNone(retained_future.get("source"))
        self.assertEqual(retained_future["schema_version"], 2)
        self.assertEqual(second["continuity_receipt"]["owner_id"], second["owner_id"])
        self.assertEqual(second["continuity_receipt"]["pr_id"], second["pr_id"])
        self.assertEqual(second["preceding_event_id"], first["event_id"])
        self.assertEqual(second["continuity_from_event_id"], first["event_id"])
        self.assertEqual(first["source"], "driver-session-1")
        self.assertEqual(first["result_receipt"], url)
        self.assertEqual(second["pr_url"], url)
        self.assertEqual(second["repo"], "acme/app")
        self.assertEqual(second["sequence"], 2)
        self.assertEqual(retained_legacy["source"], legacy["source"])
        raw = "\n".join(map(json.dumps, records))
        self.assertEqual(m.sanitize_telemetry_file(path, raw), bundle[path])
        self.assertEqual(m.sanitize_telemetry_file(path, bundle[path]), bundle[path])

    def test_redacted_pickup_proof_cannot_become_valid_on_replay(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        cutoff = start + timedelta(minutes=16)
        repo = "acme/app"
        url = f"https://github.com/{repo}/pull/7"
        scope = {"pr_id": f"{repo}#7", "candidate_sha": "a" * 40,
                 "obligation_id": "follow-up", "owner_id": "driver", "attempt_number": 1}
        pr = {"repo": repo, "number": 7, "state": "OPEN", "headRefOid": scope["candidate_sha"],
              "createdAt": m.format_iso_utc(start), "url": url, "labels": []}
        fixture = []
        for sequence, (minute, event_type, executing) in enumerate([
            (0, "action_observed", False), (2, "worker_acknowledged", False),
            (5, "worker_started", True), (12, "worker_returned", False),
            (13, "wake_fired", False), (15, "next_action_started", True),
            (16, "window_observed", True),
        ], 1):
            event_id = f"event-{sequence}"
            row = dict(scope, record_type="transition_event", schema_version=1,
                       sequence=sequence, source="driver", event_id=event_id, event_type=event_type,
                       occurred_at=m.format_iso_utc(start + timedelta(minutes=minute)),
                       state="executing" if executing else "actionable_unowned",
                       result_receipt=f"result-{sequence}")
            if executing:
                row["worker_id"] = "worker"
            if fixture:
                preceding = fixture[-1]
                row["preceding_event_id"] = row["continuity_from_event_id"] = preceding["event_id"]
                row["continuity_receipt"] = dict(
                    scope, receipt_id=f"coverage-{sequence}",
                    covers_from=preceding["occurred_at"], covers_to=row["occurred_at"],
                )
            fixture.append(row)

        def metrics(records):
            summary = m.MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                [pr], handoff_records=records, now_dt=cutoff
            )
            attention = (summary["open_prs_known_idle"] + summary["open_prs_unknown_idle"])[0]
            return tuple(attention[field] for field in (
                "ownership_status", "ownership_unattended_sec_lower_bound", "ownership_unknown_sec",
                "review_return_to_pickup_sample_n", "wake_to_pickup_sample_n",
            ))

        pickup = fixture[5]

        def with_receipt(identity):
            return dict(pickup, continuity_receipt=dict(pickup["continuity_receipt"], receipt_id=identity))

        short, long = with_receipt("Bearer x"), with_receipt("Bearer syntheticvalue")
        mask = with_receipt("Bearer [REDACTED]")
        old_short_mask = with_receipt("Bearer [REDA...")
        display = dict(pickup, pr_url="Bearer syntheticvalue", source_receipt="Bearer x")
        cases = [
            ("clean", [pickup], True), ("optional display redacted", [display], True),
            ("distinct credentials", [short, long], False),
            ("distinct credentials reversed", [long, short], False),
            ("mixed duplicate", [pickup, long], False),
            ("mixed duplicate reversed", [long, pickup], False),
            ("existing mask", [mask], False), ("old truncated mask", [old_short_mask], False),
        ]
        path = "dashboards/prw/telemetry/20261109/retained_handoffs.jsonl"
        with tempfile.TemporaryDirectory() as temp:
            publisher = m.Publisher(temp)
            for name, variants, clean in cases:
                with self.subTest(name=name):
                    records = fixture[:5] + variants + fixture[6:]
                    expected = ("COMPLETE", 480.0, 0.0, 1, 1) if clean else ("PARTIAL", 360.0, 180.0, 0, 0)
                    content = publisher.write_telemetry_bundle(
                        {}, window_slug="20261109", handoff_records=records
                    )[path]
                    replay = m.sanitize_telemetry_file(path, content)
                    self.assertNotIn("Bearer", replay)
                    self.assertEqual(content, replay)
                    self.assertEqual(metrics(records), expected)
                    self.assertEqual(metrics(list(map(json.loads, replay.splitlines()))), expected)

    def test_retained_full_record_index_preserves_equality_and_scales(self):
        class CountedRecord(dict):
            comparisons = 0
            def __eq__(self, other):
                CountedRecord.comparisons += 1
                return super().__eq__(other)
        # Same request ID with differing usage/conflict/nested array order must
        # survive. Python's historical bool/int/float equivalence must remain.
        small = [
            {"request_id": "same", "raw_usage": {"input_tokens": 1}, "nested": [1, None]},
            {"nested": [True, None], "raw_usage": {"input_tokens": 1.0}, "request_id": "same"},
            {"request_id": "same", "raw_usage": {"input_tokens": 2}, "nested": [1, None]},
            {"request_id": "same", "raw_usage": {"input_tokens": 2}, "nested": [None, 1]},
            {"request_id": "same", "raw_usage": {"input_tokens": 2}, "usage_conflict": True},
            {"request_id": "same", "raw_usage": {"input_tokens": "1"}, "nested": [1, None]},
        ]
        expected = []
        for row in small:
            if row not in expected:
                expected.append(row)
        large = [CountedRecord(request_id=str(i), raw_usage={"input_tokens": i}) for i in range(4000)]
        records = small + large + [CountedRecord(row) for row in large]
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'usage_events.jsonl').write_text('')
            collector = m.Collector()
            with mock.patch.object(collector, 'load_retained_telemetry', return_value={"usage_events": records}):
                loaded = collector.collect_all(telemetry_dir=temp, offline=True)['usage_events']
        # Count dictionary comparisons rather than wall time: linear membership
        # indexing must not regress to a full scan of every prior distinct row.
        self.assertLess(CountedRecord.comparisons, len(records) * 4)
        self.assertEqual(loaded, expected + large)

    def test_opt_in_retained_usage_spool_preserves_window_order_and_json_equality(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "telemetry"
            rows = self.rows(4)
            # JSON decoding historically deduplicates numerically equal bool/int/float
            # values while retaining the first record and full-record conflicts.
            rows[0]["raw_usage"]["input_tokens"] = 1
            numerically_equal = dict(rows[0], raw_usage={"input_tokens": 1.0, "output_tokens": 2})
            later_unique = dict(rows[0], raw_usage={"input_tokens": 9, "output_tokens": 2})
            large_integer = 2**53 + 1
            rounded_float = float(large_integer)
            self.assertNotEqual(large_integer, rounded_float)
            large_value = {"boundary": large_integer}
            rounded_value = {"boundary": rounded_float}
            first = root / "20261108"
            second = root / "20261109"
            first.mkdir(parents=True)
            second.mkdir()
            with mock.patch.object(m, "USAGE_SHARD_BYTES", 1150):
                for directory, bundle in (
                    (first, m._usage_parts([rows[0], rows[1], rows[2]])),
                    (second, m._usage_parts([numerically_equal, later_unique, large_value, rounded_value])),
                ):
                    for name, content in bundle.items():
                        (directory / name).write_text(content)

            expected = m.Collector().collect_all(
                telemetry_dir=str(root), offline=True
            )["usage_events"]
            spool_root = Path(temp) / "spool"
            actual = m.Collector().collect_all(
                telemetry_dir=str(root), offline=True, usage_spool_dir=str(spool_root)
            )["usage_events"]

            self.assertIsInstance(actual, m.RetainedUsageEventSpool)
            self.assertEqual(list(actual), expected)
            self.assertEqual(list(actual), expected)  # a later consumer may replay the spool
            self.assertEqual(len(actual), len(expected))
            self.assertTrue(actual._sealed)
            self.assertTrue(actual.path.is_file())
            actual.close()
            self.assertEqual(list(actual), expected)
            actual.cleanup()
            self.assertFalse(actual.path.exists())

    def test_retained_usage_spool_rolls_back_a_corrupt_window(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "20261109"
            directory.mkdir()
            with mock.patch.object(m, "USAGE_SHARD_BYTES", 700):
                bundle = m._usage_parts(self.rows(3))
            self.assertIn(m._USAGE_MANIFEST, bundle)
            for name, content in bundle.items():
                (directory / name).write_text(content)
            part = next(name for name in bundle if name.startswith("usage_events.part-"))
            (directory / part).write_bytes((directory / part).read_bytes() + b"tamper")

            spool = m.RetainedUsageEventSpool(Path(temp) / "spool")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                spool.ingest_bundle(os.listdir(directory), directory)
            self.assertEqual(list(spool), [])
            self.assertEqual(len(spool), 0)
            path = spool.path
            spool.cleanup()
            self.assertFalse(path.exists())

    def test_real_git_publish_reload_shrink_empty_and_legacy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); remote = root/'remote.git'; local = root/'local'
            def git(repo, *args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.PIPE)
            subprocess.run(['git', 'init', '-q', '--bare', str(remote)], check=True)
            git(remote, 'symbolic-ref', 'HEAD', 'refs/heads/main')
            subprocess.run(['git', 'clone', '-q', str(remote), str(local)], check=True, stderr=subprocess.PIPE)
            git(local, 'config', 'user.name', 'Test Bot'); git(local, 'config', 'user.email', 'test@example.invalid')
            (local/'README.md').write_text('unrelated\n')
            legacy = local/'dashboards/prw/telemetry/20261101'; legacy.mkdir(parents=True)
            legacy_row = m._sanitize_usage_event_record(self.rows(1)[0])
            (legacy/'usage_events.jsonl').write_text(json.dumps(legacy_row)+'\n')
            git(local, 'add', '.'); git(local, 'commit', '-qm', 'seed'); git(local, 'push', '-q', 'origin', 'main')
            (local/'README.md').write_text('uncommitted user change\n')
            (local/'untracked').write_text('keep\n')
            old_blob = git(remote, 'rev-parse', 'main:dashboards/prw/telemetry/20261101/usage_events.jsonl').strip()
            # Large -> fewer parts -> singleton -> empty, same window each time.
            previous_payloads = None
            for count in (9, 9, 7, 5, 1, 0):
                rows = self.rows(count)
                summary = {"w2_bounds": ["2026-11-02T00:00:00Z", "x"],
                           "usage_summary": {"events": [{"status": "UNKNOWN", "known_cost_usd": None,
                               "tokens_by_bucket": {"input": i}, "unknown_buckets": {"é": i},
                               "private_note": "must not survive"} for i in range(count * 20)]},
                           "raw_private": "must not survive"}
                with mock.patch.object(m, 'USAGE_SHARD_BYTES', 1500, create=True):
                    kwargs = ({"telemetry_files": {"dashboards/prw/telemetry/20261102/usage_events.jsonl":
                               "".join(json.dumps(row) + "\n" for row in rows),
                               "dashboards/prw/telemetry/20261102/summary_snapshot.json": json.dumps(summary)}} if count == 7 else
                              {"publish_telemetry": True,
                               "summary_data": summary,
                               "usage_events": m.load_usage_events(rows)})
                    if count == 5:
                        kwargs['telemetry_files'] = {
                            'dashboards/prw/telemetry/20261102/summary_snapshot.json': '{}',
                            'dashboards/prw/telemetry/20261102/usage_events.jsonl': ''}
                    result = m.publish_dashboard(
                        '# Dashboard\n', str(local), verify_private_fn=lambda _: True,
                        **kwargs)
                    self.assertTrue(result['committed'], result)
                    tree = git(remote, 'ls-tree', '-r', '-l', 'main', '--', 'dashboards/prw/telemetry/20261102')
                    for entry in tree.splitlines():
                        metadata, name = entry.split('\t', 1)
                        self.assertLessEqual(int(metadata.split()[3]), m.TELEMETRY_BLOB_BYTES)
                        if name.endswith('/summary_snapshot.json') or '.part-' in name:
                            self.assertLessEqual(int(metadata.split()[3]), 1500)
                    exported = root/f'export-{count}'
                    self.assertTrue(m.export_published_telemetry(str(local), str(exported)))
                    current = exported/'20261102'
                    payloads = {p.name: p.read_text() for p in current.iterdir() if p.name.startswith('usage_events.')}
                    self.assertTrue(all(len(v.encode()) <= 1500 for k,v in payloads.items() if k.endswith('.jsonl')))
                    if count == 9 and previous_payloads is not None:
                        self.assertEqual(payloads, previous_payloads)
                    previous_payloads = payloads
                    summary_payloads = {p.name: p.read_bytes() for p in current.iterdir()
                                        if p.name.startswith('summary_snapshot.')}
                    self.assertTrue(summary_payloads)
                    self.assertTrue(all(len(v) <= 1500 for k, v in summary_payloads.items()
                                        if not k.endswith('manifest.json')))
                    self.assertEqual(m._read_summary_bundle(summary_payloads, summary_payloads.__getitem__),
                                     m._project_summary(summary))
                    retained = m.Collector().load_retained_telemetry(str(exported))
                    self.assertIn(m._project_summary(summary), retained['summary_snapshots'])
                    loaded = retained['usage_events']
                    self.assertEqual(len(loaded), count + 1)
                    expected = ([m._sanitize_usage_event_record(r) for r in rows] if count == 7 else
                                [m._sanitize_usage_event_record(m._usage_event_record(e)) for e in m.load_usage_events(rows)])
                    self.assertEqual(m._read_usage_bundle(payloads, payloads.__getitem__), expected)
                    self.assertTrue(all('raw_message' not in r for r in loaded))
                self.assertEqual(git(remote, 'rev-parse', 'main:dashboards/prw/telemetry/20261101/usage_events.jsonl').strip(), old_blob)
                self.assertEqual(git(remote, 'show', 'main:README.md'), 'unrelated\n')
                self.assertEqual((local/'README.md').read_text(), 'uncommitted user change\n')
                self.assertEqual((local/'untracked').read_text(), 'keep\n')
            self.assertEqual(list(payloads), ['usage_events.jsonl'])
            self.assertEqual(payloads['usage_events.jsonl'], '')


if __name__ == '__main__':
    unittest.main()
