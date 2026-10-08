"""Synthetic, local-only transactional reminder authority contract tests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / '.claude/skills/dot-portfolio-coordinator/scripts/reminder_ledger.py'
spec = importlib.util.spec_from_file_location('reminder_ledger', MODULE)
ledger_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger_module)
Ledger = ledger_module.Ledger
DUE = 1800000000  # Exact UTC hour: first configured account's Mac slot.


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'private' / 'authority.sqlite'
        self.source = self.root / 'legacy.json'
        self.source.write_text(json.dumps(dict(account='alpha', delivery_unverified=False, last_status='SUCCESS')))
        self.config = dict(schedule_version='v1', transport_fingerprint='a' * 64, accounts=[
            dict(key='alpha', sender='sender-a', room='room-a', sources=[self.source_descriptor(self.source)])])
        self.ledger = Ledger(self.path, self.config)
        self.ledger.enroll('alpha')
        self.event = json.dumps(['v1', 'mac', 'alpha', DUE], separators=(',', ':'))
        self.token = 'client-token-one'
        self.marker = '[event:' + digest(self.event) + ']'
        self.body = 'Automated reminder: continue authorized work. ' + self.marker
        self.body_digest = digest(self.body)

    def source_descriptor(self, path, kind='legacy'):
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), kind=kind)

    def request(self, action, now=DUE, **fields):
        base = dict(action=action, account='alpha')
        if action != 'status':
            base.update(event=self.event, token=self.token)
        base.update(fields)
        return self.ledger.request(base, now=now)

    def claim(self, now=DUE, **fields):
        request = dict(role='mac', due=DUE, client_now=now)
        request.update(fields)
        return self.request('claim', now=now, **request)

    def begin(self, now=DUE):
        return self.request('begin_send', now=now, digest=self.body_digest)

    def receipt(self, **changes):
        result = dict(kind='delivered', sender='sender-a', room='room-a', marker=self.marker,
                      digest=self.body_digest, body=self.body, message_id='message-123',
                      observed_at='2027-01-15T08:00:01+00:00', natural_exit=True, returncode=0,
                      cleanup_ok=True, forced_cleanup=False, transport_fingerprint='a' * 64)
        result.update(changes)
        return result

    def no_send(self, sending=False):
        result = dict(kind='no_send', stage='pre_dispatch', before_click=True, reason='generation_failed')
        if sending:
            result.update(transport_fingerprint='a' * 64, natural_exit=True, returncode=0,
                          cleanup_ok=True, forced_cleanup=False)
        return result

    def proof(self, **changes):
        proof = self.receipt(kind='positive_readback')
        for key in ('natural_exit', 'returncode', 'cleanup_ok', 'forced_cleanup', 'transport_fingerprint'):
            proof.pop(key)
        proof.update(changes)
        return proof

    def finish(self, outcome='uncertain', receipt=None, **fields):
        if receipt is None:
            receipt = dict(kind='uncertain', reason='lost output')
        return self.request('finish', outcome=outcome, receipt=receipt, **fields)

    def held(self, now=DUE):
        return self.request('status', now=now)['held']

    def snapshot(self):
        with sqlite3.connect(self.path) as connection:
            return {table: connection.execute('SELECT * FROM ' + table + ' ORDER BY 1').fetchall()
                    for table in ('events', 'holds', 'resolutions', 'imports')}

    def assert_rejected_unchanged(self, call):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            call()
        self.assertEqual(self.snapshot(), before)

    def test_claim_is_atomic_private_and_identical_retry_is_idempotent(self):
        first = self.claim()
        self.assertEqual(first['event_key'], self.event)
        self.assertEqual(first['phase'], 'claimed')
        self.assertEqual(first['deadline_epoch'], DUE + 900)
        self.assertEqual(self.claim(), first)
        self.assertEqual(len(self.held()), 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        self.assert_rejected_unchanged(lambda: self.claim(token='other-token'))

    def test_unenrolled_account_cannot_claim(self):
        self.ledger = Ledger(self.root / 'unenrolled' / 'db.sqlite', self.config)
        with self.assertRaises(ValueError):
            self.claim()

    def test_schedule_clock_and_event_identity_rejected(self):
        for fields in (dict(role='other'), dict(account='missing'), dict(due=DUE + 60),
                       dict(event='forged'), dict(client_now=DUE + 31), dict(client_now=DUE - 31),
                       dict(token=''), dict(due=True)):
            with self.subTest(fields=fields):
                self.assert_rejected_unchanged(lambda: self.claim(**fields))
        self.assert_rejected_unchanged(lambda: self.claim(now=DUE - 1))
        self.assert_rejected_unchanged(lambda: self.claim(now=DUE + 121))
        self.assertEqual(self.claim(now=DUE + 120)['deadline_epoch'], DUE + 900)

    def test_stop_blocks_claim_and_begin_send_without_settlement_block(self):
        stop = self.path.parent / 'STOP'
        stop.touch()
        self.assert_rejected_unchanged(self.claim)
        stop.unlink()
        self.claim()
        stop.touch()
        self.assert_rejected_unchanged(self.begin)
        self.finish('no_send', self.no_send())
        self.assertEqual(self.held(), [])

    def test_claimed_forbids_delivered_and_uncertain(self):
        self.claim()
        for outcome, receipt in [('delivered', self.receipt()), ('uncertain', dict(kind='uncertain', reason='lost output'))]:
            with self.subTest(outcome=outcome):
                self.assert_rejected_unchanged(lambda: self.finish(outcome, receipt))
        self.finish('no_send', self.no_send())
        self.assertEqual(self.held(), [])

    def test_claimed_no_send_requires_typed_pre_dispatch_proof(self):
        self.claim()
        for receipt in ({}, {'kind': 'no_send'}, self.no_send() | {'before_click': False},
                        self.no_send() | {'stage': 'after_dispatch'}, self.no_send() | {'kind': 'delivered'}):
            self.assert_rejected_unchanged(lambda: self.finish('no_send', receipt))

    def test_begin_send_requires_correct_event_owner_and_digest(self):
        self.claim()
        for fields in (dict(token='other'), dict(account='missing'), dict(event='missing'), dict(digest='bad')):
            self.assert_rejected_unchanged(lambda: self.request('begin_send', **({'digest': self.body_digest} | fields)))
        self.assertEqual(self.begin()['phase'], 'sending')
        self.assert_rejected_unchanged(self.begin)
        self.assert_rejected_unchanged(lambda: self.request('begin_send', digest='b' * 64))

    def test_sending_no_send_requires_pinned_before_click_process_proof(self):
        self.claim()
        self.begin()
        for receipt in (self.no_send(), self.no_send(True) | {'before_click': False},
                        self.no_send(True) | {'transport_fingerprint': 'b' * 64},
                        self.no_send(True) | {'cleanup_ok': False}):
            self.assert_rejected_unchanged(lambda: self.finish('no_send', receipt))
        self.finish('no_send', self.no_send(True))
        self.assertEqual(self.held(), [])

    def test_delivered_validates_every_identity_and_process_field(self):
        self.claim()
        self.begin()
        mutations = dict(kind='uncertain', sender='other', room='other', marker='[event:wrong]',
                         digest='b' * 64, body=self.body[:-5], message_id='', observed_at='not-a-time',
                         natural_exit=False, returncode=1, cleanup_ok=False, forced_cleanup=True,
                         transport_fingerprint='b' * 64)
        for key, value in mutations.items():
            with self.subTest(key=key):
                self.assert_rejected_unchanged(lambda: self.finish('delivered', self.receipt(**{key: value})))
                receipt = self.receipt()
                del receipt[key]
                self.assert_rejected_unchanged(lambda: self.finish('delivered', receipt))
        self.finish('delivered', self.receipt())
        self.assertEqual(self.held(), [])

    def test_finish_owner_and_outcome_label_do_not_override_receipt(self):
        self.claim()
        self.begin()
        for fields in (dict(token='other'), dict(account='missing'), dict(event='missing')):
            self.assert_rejected_unchanged(lambda: self.finish(**fields))
        for outcome, receipt in [('delivered', {'kind': 'uncertain'}), ('uncertain', self.receipt()),
                                 ('unknown', {'kind': 'unknown'}), ('no_send', self.receipt())]:
            self.assert_rejected_unchanged(lambda: self.finish(outcome, receipt))

    def test_terminal_finish_immutable_and_retries_exact(self):
        self.claim()
        self.begin()
        first = self.finish()
        before = self.snapshot()
        self.assertEqual(self.finish(), first)
        self.assertEqual(self.snapshot(), before)
        self.assert_rejected_unchanged(lambda: self.finish(receipt={'kind': 'uncertain', 'reason': 'changed'}))
        self.assert_rejected_unchanged(lambda: self.finish('delivered', self.receipt()))
        self.assertEqual(len(self.held()), 1)

    def test_expired_claim_recovers_but_never_expires_sending(self):
        self.claim()
        self.assertEqual(self.held(now=DUE + 901), [])
        self.assert_rejected_unchanged(lambda: self.begin(now=DUE + 901))
        with sqlite3.connect(self.path) as connection:
            phase, outcome = connection.execute('SELECT phase, original_outcome FROM events').fetchone()
        self.assertEqual((phase, outcome), ('terminal', 'no_send'))

    def test_lost_begin_reply_keeps_hold_across_process_restart_and_new_slot(self):
        self.claim()
        self.begin()
        self.ledger = Ledger(self.path, self.config)
        self.assertEqual(len(self.held(now=DUE + 100000)), 1)
        linux_event = json.dumps(['v1', 'linux', 'alpha', DUE + 1800], separators=(',', ':'))
        self.assert_rejected_unchanged(lambda: self.claim(now=DUE + 1800, role='linux', due=DUE + 1800,
                                                        event=linux_event, token='linux-token'))
        self.finish()
        self.assertEqual(len(self.held(now=DUE + 100000)), 1)

    def test_begin_at_deadline_cannot_race_expiry_into_a_send(self):
        self.claim()
        self.assert_rejected_unchanged(lambda: self.begin(now=DUE + 900))

    def test_reconciliation_preserves_original_and_is_immutable(self):
        self.claim()
        self.begin()
        self.finish()
        old_events = self.snapshot()['events']
        request = dict(digest=self.body_digest, proof=self.proof())
        first = self.request('reconcile', **request)
        self.assertEqual(self.snapshot()['events'], old_events)
        self.assertEqual(self.held(), [])
        self.assertEqual(self.request('reconcile', **request), first)
        self.assert_rejected_unchanged(lambda: self.request('reconcile', digest=self.body_digest,
                                                          proof=self.proof(message_id='different')))

    def test_reconcile_rejects_wrong_proof_and_missing_digest(self):
        self.claim()
        self.assert_rejected_unchanged(lambda: self.request('reconcile', digest=self.body_digest, proof=self.proof()))
        self.begin()
        self.finish()
        for key, value in dict(kind='not_found', sender='other', room='other', marker='wrong',
                              digest='b' * 64, body=self.body[:-5], message_id='', observed_at='bad').items():
            with self.subTest(key=key):
                self.assert_rejected_unchanged(lambda: self.request('reconcile', digest=self.body_digest,
                                                                  proof=self.proof(**{key: value})))
        self.assert_rejected_unchanged(lambda: self.request('reconcile', digest='b' * 64, proof=self.proof()))
        self.assertEqual(len(self.held()), 1)

    def child_prefix(self):
        return (f"import importlib.util,json,sys,time\ns=importlib.util.spec_from_file_location('ledger',{str(MODULE)!r})\n"
                f"m=importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\nl=m.Ledger({str(self.path)!r},{self.config!r})\n")

    def run_contenders(self, requests, now=DUE):
        gate = self.root / 'gate'
        code = self.child_prefix() + (f"from pathlib import Path\nwhile not Path({str(gate)!r}).exists(): time.sleep(.005)\n"
                                     f"try:\n print(json.dumps(l.request(json.loads(sys.argv[1]),now={now})))\n"
                                     "except ValueError as e:\n print(str(e));sys.exit(23)\n")
        processes = [subprocess.Popen([sys.executable, '-c', code, json.dumps(request)], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for request in requests]
        gate.touch()
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            outputs.append((process.returncode, stdout, stderr))
        return outputs

    def test_real_subprocess_claim_contention_has_one_owner(self):
        requests = [dict(action='claim', account='alpha', role='mac', due=DUE, event=self.event,
                         token='token-' + str(i), client_now=DUE) for i in range(6)]
        results = self.run_contenders(requests)
        self.assertEqual(sum(code == 0 for code, _, _ in results), 1, results)
        self.assertTrue(all(code in (0, 23) for code, _, _ in results), results)
        self.assertEqual(len(self.snapshot()['events']), 1)
        self.assertEqual(len(self.held()), 1)

    def test_real_subprocess_reconcile_contention_adds_one_resolution(self):
        self.claim()
        self.begin()
        self.finish()
        request = dict(action='reconcile', account='alpha', event=self.event,
                       digest=self.body_digest, proof=self.proof())
        results = self.run_contenders([request] * 4)
        self.assertTrue(all(code == 0 for code, _, _ in results), results)
        self.assertEqual(len(self.snapshot()['resolutions']), 1)
        self.assertEqual(self.held(), [])

    def test_rpc_never_exposes_operator_release_or_enrollment(self):
        for action in ('release', 'operator_release', 'enroll', 'import', '__getattribute__'):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    self.request(action, reason='operator approved')

    def test_multiple_legacy_holds_preserve_sources_and_provenance(self):
        paths = [self.root / ('uncertain-' + str(i) + '.json') for i in range(2)]
        for path in paths:
            path.write_text(json.dumps(dict(account='alpha', delivery_unverified=True, last_status='UNCERTAIN')))
        before = {str(path): path.read_bytes() for path in paths}
        config = copy.deepcopy(self.config)
        config['accounts'][0]['sources'] = [self.source_descriptor(path) for path in paths]
        self.path = self.root / 'imported' / 'db.sqlite'
        self.ledger = Ledger(self.path, config)
        self.ledger.enroll('alpha')
        self.assertEqual(len(self.held()), 2)
        self.assertEqual(len({row['event_key'] for row in self.held()}), 2)
        self.assertEqual(sum(bool(row[3]) for row in self.snapshot()['imports']), 2)
        initial = self.snapshot()
        self.ledger.enroll('alpha')
        self.assertEqual(self.snapshot(), initial)
        self.assert_rejected_unchanged(self.claim)
        self.assertEqual({str(path): path.read_bytes() for path in paths}, before)

    def test_required_source_missing_corrupt_or_hash_changed_cannot_enroll(self):
        for mode in ('missing', 'corrupt', 'hash_changed'):
            with self.subTest(mode=mode):
                path = self.root / (mode + '.json')
                path.write_text('{broken' if mode == 'corrupt' else self.source.read_text())
                config = copy.deepcopy(self.config)
                descriptor = self.source_descriptor(path)
                if mode == 'missing':
                    path.unlink()
                elif mode == 'hash_changed':
                    path.write_text(path.read_text() + '\n')
                config['accounts'][0]['sources'] = [descriptor]
                ledger = Ledger(self.root / mode / 'db.sqlite', config)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    ledger.enroll('alpha')
                with self.assertRaises(ValueError):
                    ledger.request(dict(action='claim', account='alpha', role='mac', due=DUE, event=self.event,
                                        token=self.token, client_now=DUE), now=DUE)


    def attestation(self, **changes):
        value = dict(operator='synthetic-operator', reason='explicit fixture authorization',
                     proof_digest='c' * 64, authorized_at='2027-01-15T08:00:01+00:00',
                     workers_stopped_at='2027-01-15T08:00:00+00:00')
        value.update(changes)
        return value

    def test_operator_release_is_local_exact_immutable_and_not_reconciliation(self):
        self.claim()
        self.begin()
        self.finish()
        for key in self.attestation():
            self.assert_rejected_unchanged(lambda: self.ledger.release('alpha', self.event, self.attestation(**{key: ''})))
        self.assert_rejected_unchanged(lambda: self.ledger.release('missing', self.event, self.attestation()))
        self.assert_rejected_unchanged(lambda: self.ledger.release('alpha', 'missing', self.attestation()))
        original = self.snapshot()['events']
        self.ledger.release('alpha', self.event, self.attestation())
        self.assertEqual(self.snapshot()['events'], original)
        self.assertEqual(self.held(), [])
        after = self.snapshot()
        self.ledger.release('alpha', self.event, self.attestation())
        self.assertEqual(self.snapshot(), after)
        self.assert_rejected_unchanged(lambda: self.ledger.release('alpha', self.event, self.attestation(reason='changed')))
        self.assert_rejected_unchanged(lambda: self.request('reconcile', digest=self.body_digest, proof=self.proof()))

    def test_positive_reconciliation_cannot_be_replaced_by_operator_release(self):
        self.claim()
        self.begin()
        self.finish()
        self.request('reconcile', digest=self.body_digest, proof=self.proof())
        self.assert_rejected_unchanged(lambda: self.ledger.release('alpha', self.event, self.attestation()))

    def test_sqlite_process_death_before_and_after_transaction_commit(self):
        # Instrument real SQLite connection exit, not a fake transaction or lock.
        for action in ('claim', 'finish', 'reconcile'):
            for boundary in ('before', 'after'):
                with self.subTest(action=action, boundary=boundary):
                    self.path = self.root / (action + '-' + boundary) / 'authority.sqlite'
                    self.ledger = Ledger(self.path, self.config)
                    self.ledger.enroll('alpha')
                    request = dict(action=action, account='alpha', event=self.event, token=self.token)
                    if action == 'claim':
                        request.update(role='mac', due=DUE, client_now=DUE)
                    else:
                        self.claim()
                        self.begin()
                        if action == 'finish':
                            request.update(outcome='delivered', receipt=self.receipt())
                        else:
                            self.finish()
                            request.update(digest=self.body_digest, proof=self.proof())
                    before = self.snapshot()
                    code = self.child_prefix() + ("import sqlite3,os\noriginal_connect=sqlite3.connect\n"
                        "class CrashConnection(sqlite3.Connection):\n def __exit__(self,*args):\n"
                        + ("  os._exit(71)\n" if boundary == 'before' else
                           "  result=super().__exit__(*args)\n  os._exit(72)\n")
                        + "m.sqlite3.connect=lambda *a,**kw: original_connect(*a,**kw,factory=CrashConnection)\n"
                        + f"l.request({request!r},now={DUE})\n")
                    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 71 if boundary == 'before' else 72, result.stderr)
                    if boundary == 'before':
                        self.assertEqual(self.snapshot(), before)
                    elif action == 'claim':
                        self.assertEqual(len(self.snapshot()['events']), 1)
                        self.assertEqual(len(self.held()), 1)
                    else:
                        self.assertEqual(self.held(), [])
                    # Recovery resubmits the exact transaction; never invokes transport.
                    self.ledger.request(request, now=DUE)
                    self.assertEqual(len(self.held()), 1 if action == 'claim' else 0)

    def test_multiple_imported_holds_release_individually_and_never_reappear(self):
        config = copy.deepcopy(self.config)
        source2 = self.root / 'pilot.json'
        source2.write_text(json.dumps({'pending_delivery': {'account': 'alpha', 'event_id': 'pilot-one'}}))
        self.source.write_text(json.dumps({'account': 'alpha', 'delivery_unverified': True, 'last_status': 'UNCERTAIN'}))
        config['accounts'][0]['sources'] = [self.source_descriptor(self.source), self.source_descriptor(source2, 'pilot')]
        self.path = self.root / 'mixed-imports' / 'authority.sqlite'
        self.ledger = Ledger(self.path, config)
        self.ledger.enroll('alpha')
        events = [row['event_key'] for row in self.held()]
        self.assertEqual(len(events), 2)
        self.ledger.release('alpha', events[0], self.attestation())
        self.assertEqual([row['event_key'] for row in self.held()], [events[1]])
        self.assert_rejected_unchanged(self.claim)
        self.ledger.enroll('alpha')
        self.assertEqual([row['event_key'] for row in self.held()], [events[1]])
        self.ledger.release('alpha', events[1], self.attestation())
        self.ledger.enroll('alpha')
        self.assertEqual(self.held(), [])
        self.claim()

    def test_valid_json_with_missing_legacy_schema_is_not_empty_history(self):
        path = self.root / 'invalid-schema.json'
        path.write_text('{}')
        config = copy.deepcopy(self.config)
        config['accounts'][0]['sources'] = [self.source_descriptor(path)]
        ledger = Ledger(self.root / 'invalid-schema' / 'db.sqlite', config)
        with self.assertRaises(ValueError):
            ledger.enroll('alpha')



    def test_expiry_and_begin_subprocess_contention_cannot_clear_sending_hold(self):
        self.claim()
        requests = [dict(action='status', account='alpha'),
                    dict(action='begin_send', account='alpha', event=self.event,
                         token=self.token, digest=self.body_digest)]
        results = self.run_contenders(requests, now=DUE + 900)
        self.assertEqual(results[0][0], 0, results)
        self.assertEqual(results[1][0], 23, results)
        self.assertEqual(self.held(now=DUE + 900), [])
        with sqlite3.connect(self.path) as connection:
            row = connection.execute('SELECT phase,message_digest,original_outcome FROM events').fetchone()
        self.assertEqual(row, ('terminal', None, 'no_send'))

    def test_exception_consumed_attempt_and_unverified_result_remain_held(self):
        config = copy.deepcopy(self.config)
        sources = []
        for kind, record in (
            ('exception_attempt', dict(account='alpha', event_id='exception-one', consumed=True)),
            ('exception_result', dict(event_id='exception-two', delivery_verified=False)),
            ('exception_result', dict(event_id='exception-three', delivery_verified=True))):
            path = self.root / (record['event_id'] + '.json')
            path.write_text(json.dumps(record))
            sources.append(self.source_descriptor(path, kind))
        config['accounts'][0]['sources'] = sources
        self.path = self.root / 'exception-imports' / 'authority.sqlite'
        self.ledger = Ledger(self.path, config)
        before = {source['path']: Path(source['path']).read_bytes() for source in sources}
        self.ledger.enroll('alpha')
        self.assertEqual(len(self.held()), 2)
        self.assert_rejected_unchanged(self.claim)
        self.assertEqual({source['path']: Path(source['path']).read_bytes() for source in sources}, before)

    def test_broken_account_enrollment_does_not_block_independent_account(self):
        config = copy.deepcopy(self.config)
        beta = self.root / 'beta.json'
        beta.write_text(json.dumps(dict(account='beta', delivery_unverified=False, last_status='SUCCESS')))
        config['accounts'].append(dict(key='beta', sender='sender-b', room='room-b',
                                       sources=[self.source_descriptor(beta)]))
        self.source.unlink()
        ledger = Ledger(self.root / 'independent' / 'db.sqlite', config)
        with self.assertRaises((ValueError, FileNotFoundError)):
            ledger.enroll('alpha')
        ledger.enroll('beta')
        due = DUE + 1200
        event = json.dumps(['v1', 'mac', 'beta', due], separators=(',', ':'))
        result = ledger.request(dict(action='claim', account='beta', role='mac', event=event,
                                     due=due, client_now=due, token='beta-token'), now=due)
        self.assertEqual(result['phase'], 'claimed')


if __name__ == '__main__':
    unittest.main()
