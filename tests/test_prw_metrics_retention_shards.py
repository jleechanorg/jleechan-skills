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
                with mock.patch.object(m, 'USAGE_SHARD_BYTES', 1500, create=True):
                    kwargs = ({"telemetry_files": {"dashboards/prw/telemetry/20261102/usage_events.jsonl":
                               "".join(json.dumps(row) + "\n" for row in rows)}} if count == 7 else
                              {"publish_telemetry": True,
                               "summary_data": {"w2_bounds": ["2026-11-02T00:00:00Z", "x"]},
                               "usage_events": m.load_usage_events(rows)})
                    result = m.publish_dashboard(
                        '# Dashboard\n', str(local), verify_private_fn=lambda _: True,
                        **kwargs)
                    self.assertTrue(result['committed'], result)
                    exported = root/f'export-{count}'
                    self.assertTrue(m.export_published_telemetry(str(local), str(exported)))
                    current = exported/'20261102'
                    payloads = {p.name: p.read_text() for p in current.iterdir() if p.name.startswith('usage_events.')}
                    self.assertTrue(all(len(v.encode()) <= 1500 for k,v in payloads.items() if k.endswith('.jsonl')))
                    if count == 9 and previous_payloads is not None:
                        self.assertEqual(payloads, previous_payloads)
                    previous_payloads = payloads
                    loaded = m.Collector().load_retained_telemetry(str(exported))['usage_events']
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
