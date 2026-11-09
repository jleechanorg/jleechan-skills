"""Bounded retained usage publication through real local Git and replay readers."""
import json
import subprocess
import tempfile
import unittest
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
