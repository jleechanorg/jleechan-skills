import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / '.claude/skills/dot-portfolio-coordinator/scripts/reminder_journal.py'
spec = importlib.util.spec_from_file_location('reminder_journal', MODULE)
journal_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal_module)
Journal = journal_module.Journal


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'client-events'
        self.journal = Journal(self.path)
        self.record = dict(event='["v1","mac","alice",1]', account='alice', token='token', stage='claim_ready')

    def test_private_record_and_canonical_key(self):
        self.journal.write(self.record)
        path = self.path / (hashlib.sha256(self.record['event'].encode()).hexdigest() + '.json')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.journal.read(self.record['event'])['token'], 'token')
        self.assertIsNone(self.journal.read('absent'))

    def test_retry_and_restart_preserve_identity(self):
        self.journal.write(self.record)
        initial = self.journal.read(self.record['event'])
        self.journal.write(self.record)
        self.assertEqual(self.journal.read(self.record['event'])['created_at'], initial['created_at'])
        for key in ('account', 'token'):
            with self.assertRaises(ValueError):
                self.journal.write(dict(self.record, **{key: 'different'}))
        for stage in ('operation_started', 'sending', 'receipt_ready', 'acked'):
            self.journal.write(dict(self.record, stage=stage))
            self.assertEqual(Journal(self.path).read(self.record['event'])['stage'], stage)
        with self.assertRaises(ValueError):
            self.journal.write(self.record)

    def test_immutable_receipt_digest_and_account_recovery(self):
        ready = dict(self.record, stage='receipt_ready', receipt={'outcome': 'uncertain'}, message_digest='abc')
        self.journal.write(ready)
        self.journal.write(dict(ready, stage='acked'))
        for key, value in [('receipt', {'outcome': 'delivered'}), ('message_digest', 'def')]:
            with self.assertRaises(ValueError):
                self.journal.write(dict(ready, stage='acked', **{key: value}))
        self.journal.write(dict(self.record, event='second', stage='sending'))
        self.journal.write(dict(self.record, event='third', account='bob'))
        self.assertEqual([r['event'] for r in Journal(self.path).pending('alice')], ['second'])

    def test_invalid_and_oversized_records_never_replace(self):
        self.journal.write(self.record)
        for update in ({'stage': 'bad'}, {'token': ''}, {'receipt': 'x' * 65536}, {'updated_at': float('nan')}):
            with self.assertRaises((ValueError, TypeError)):
                self.journal.write(dict(self.record, **update))
        self.assertEqual(self.journal.read(self.record['event'])['stage'], 'claim_ready')

    def test_before_replace_crash_preserves_old(self):
        self.journal.write(self.record)
        code = self.child_prefix() + "\nm.os.replace=lambda *args: os._exit(71)\nj.write(dict(record,stage='sending'))"
        self.assertEqual(subprocess.run([sys.executable, '-c', code]).returncode, 71)
        self.assertEqual(self.journal.read(self.record['event'])['stage'], 'claim_ready')
        self.assertEqual(len(self.journal.pending('alice')), 1)

    def test_after_replace_crash_exposes_new(self):
        self.journal.write(self.record)
        code = self.child_prefix() + "\noriginal=m.os.replace\ndef replace(*args):\n original(*args)\n os._exit(72)\nm.os.replace=replace\nj.write(dict(record,stage='sending'))"
        self.assertEqual(subprocess.run([sys.executable, '-c', code]).returncode, 72)
        self.assertEqual(self.journal.read(self.record['event'])['stage'], 'sending')

    def child_prefix(self):
        return f"import importlib.util,os\ns=importlib.util.spec_from_file_location('m',{str(MODULE)!r})\nm=importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\nj=m.Journal({str(self.path)!r})\nrecord={self.record!r}"

    def test_file_then_directory_fsync(self):
        seen = []
        original = os.fsync
        with patch.object(journal_module.os, 'fsync', side_effect=lambda fd: (seen.append(os.fstat(fd).st_mode), original(fd))[-1]):
            self.journal.write(self.record)
        import stat
        self.assertEqual([stat.S_ISDIR(mode) for mode in seen], [False, True])

    def test_lock_blocks_same_account_but_not_another(self):
        marker = Path(self.temp.name) / 'acquired'
        started = Path(self.temp.name) / 'started'
        code = self.child_prefix() + f"\nopen({str(started)!r},'w').write('ready')\nwith j.lock('alice'):\n open({str(marker)!r},'w').write('yes')"
        with self.journal.lock('alice'):
            process = subprocess.Popen([sys.executable, '-c', code])
            try:
                deadline = time.monotonic() + 5
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(started.exists())
                with self.journal.lock('bob'):
                    time.sleep(.05)
                    self.assertFalse(marker.exists())
                    self.assertIsNone(process.poll())
            except BaseException:
                process.kill()
                process.wait()
                raise
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertTrue(marker.exists())

    def test_prune_only_old_acked(self):
        for event, stage, updated in [('old', 'acked', 1), ('pending', 'sending', 1), ('fresh', 'acked', 604801)]:
            self.journal.write(dict(self.record, event=event, stage=stage, created_at=1, updated_at=updated))
        self.journal.prune(604802)
        self.assertIsNone(self.journal.read('old'))
        self.assertIsNotNone(self.journal.read('pending'))
        self.assertIsNotNone(self.journal.read('fresh'))

    def test_receipt_is_immutable_even_when_python_values_compare_equal(self):
        self.journal.write(dict(self.record, receipt={'flag': True}))
        with self.assertRaises(ValueError):
            self.journal.write(dict(self.record, receipt={'flag': 1}))

    def test_symlink_records_and_wrong_filenames_fail_closed(self):
        self.journal.write(self.record)
        path = next(self.path.glob('*.json'))
        content = path.read_bytes()
        path.unlink()
        target = Path(self.temp.name) / 'external'
        target.write_bytes(content)
        path.symlink_to(target)
        with self.assertRaises(OSError):
            self.journal.pending('alice')
        path.unlink()
        (self.path / 'wrong.json').write_bytes(content)
        with self.assertRaises(ValueError):
            self.journal.prune(time.time())

    def test_outbox_survives_restart_with_identical_receipt(self):
        receipt = {'outcome': 'uncertain', 'reason': 'lost_output'}
        self.journal.write(dict(self.record, stage='receipt_ready', receipt=receipt, message_digest='abc'))
        recovered = Journal(self.path).pending('alice')[0]
        self.assertEqual(recovered['receipt'], receipt)
        self.assertEqual(recovered['token'], 'token')
        self.journal.write(dict(self.record, stage='acked'))
        self.assertEqual(self.journal.read(self.record['event'])['receipt'], receipt)

    def test_corruption_fails_closed(self):
        self.journal.write(self.record)
        next(self.path.glob('*.json')).write_text('{')
        with self.assertRaises(ValueError):
            self.journal.pending('alice')


if __name__ == '__main__':
    unittest.main()
