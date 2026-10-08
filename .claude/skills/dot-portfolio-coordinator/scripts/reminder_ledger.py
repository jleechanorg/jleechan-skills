"""One private SQLite authority; every state change is a short immediate transaction."""
import contextlib
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def marker(event):
    return '[event:'+digest(event)+']'


class Ledger:
    def __init__(self, path, config):
        self.path, self.config = Path(path), config
        self.accounts = {item['key']: item for item in config['accounts']}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise ValueError('private local database path required')
        self.path.parent.chmod(0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events(event_key TEXT PRIMARY KEY,account TEXT,host_role TEXT,due_epoch INTEGER,deadline_epoch INTEGER,token TEXT,phase TEXT,message_digest TEXT,original_outcome TEXT,receipt_json TEXT,reason TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS holds(account TEXT,event_key TEXT,PRIMARY KEY(account,event_key))')
            db.execute('CREATE TABLE IF NOT EXISTS resolutions(event_key TEXT PRIMARY KEY,kind TEXT,proof_digest TEXT,proof_json TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS imports(source_path TEXT,source_sha256 TEXT,record_key TEXT,event_key TEXT,PRIMARY KEY(source_path,source_sha256,record_key))')

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def proof(self, account, event, expected_digest, proof, now):
        try:
            observed = datetime.datetime.fromisoformat(proof['observed_at'].replace('Z', '+00:00')).timestamp()
            body = re.sub(r'[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+', ' ', proof['body']).strip(' ')
            return (proof['sender'] == account['sender'] and proof['room'] == account['room'] and
                    proof['marker'] == marker(event) and proof['marker'] in body and
                    proof['digest'] == expected_digest == digest(body) and
                    isinstance(proof['message_id'], str) and bool(proof['message_id']) and 0 < observed <= now+30)
        except (KeyError, TypeError, ValueError, AttributeError):
            return False

    def receipt(self, row, outcome, receipt, now):
        if receipt.get('kind') != outcome or outcome not in ('delivered', 'no_send', 'uncertain'):
            raise ValueError('typed receipt required')
        if row['phase'] == 'claimed':
            valid = outcome == 'no_send' and receipt.get('stage') == 'pre_dispatch' and receipt.get('before_click') is True
        else:
            clean = (receipt.get('natural_exit') is True and type(receipt.get('returncode')) is int and receipt['returncode'] == 0 and
                     receipt.get('cleanup_ok') is True and receipt.get('forced_cleanup') is False and
                     receipt.get('transport_fingerprint') == self.config['transport_fingerprint'])
            valid = outcome == 'uncertain' or (clean and (receipt.get('before_click') is True if outcome == 'no_send' else
                     self.proof(self.accounts[row['account']], row['event_key'], row['message_digest'], receipt, now)))
        if not valid:
            raise ValueError('forbidden phase or receipt')

    def finish(self, db, row, outcome, receipt, now):
        serialized = encoded(receipt)
        if row['phase'] == 'terminal':
            if row['original_outcome'] != outcome or row['receipt_json'] != serialized:
                raise ValueError('conflicting terminal receipt')
            return
        self.receipt(row, outcome, receipt, now)
        db.execute('UPDATE events SET phase=?,original_outcome=?,receipt_json=?,reason=? WHERE event_key=?',
                   ('terminal', outcome, serialized, receipt.get('reason', outcome), row['event_key']))
        if outcome != 'uncertain':
            db.execute('DELETE FROM holds WHERE account=? AND event_key=?', (row['account'], row['event_key']))

    def request(self, request, now=None):
        now = time.time() if now is None else now
        action, account = request['action'], request['account']
        if account not in self.accounts or action not in ('claim', 'status', 'begin_send', 'finish', 'reconcile'):
            raise ValueError('unknown account or RPC action')
        if len(encoded(request).encode()) > 65536 or not math.isfinite(now):
            raise ValueError('request or clock limit')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if action == 'status':
                rows = db.execute('SELECT e.* FROM events e JOIN holds h ON h.event_key=e.event_key WHERE h.account=?', (account,)).fetchall()
                recovered = 0
                for row in rows:
                    if row['phase'] == 'claimed' and now >= row['deadline_epoch']:
                        recovered += 1
                        self.finish(db, row, 'no_send', dict(kind='no_send', stage='pre_dispatch', before_click=True, reason='claim_expired'), now)
                result = {'held': [dict(row) for row in db.execute('SELECT e.* FROM events e JOIN holds h ON h.event_key=e.event_key WHERE h.account=?', (account,))], 'now': now, 'recovered': recovered}
                if request.get('event'):
                    target = db.execute('SELECT * FROM events WHERE event_key=? AND account=?', (request['event'], account)).fetchone()
                    result['event'] = dict(target) if target else None
                return result
            event, token = request['event'], request.get('token')
            row = db.execute('SELECT * FROM events WHERE event_key=?', (event,)).fetchone()
            if action == 'claim':
                if (self.path.parent/'STOP').exists():
                    raise ValueError('authority STOP')
                due, role = request['due'], request['role']
                offset = dict(mac=(0, 20, 40), linux=(30, 50, 10)).get(role)
                index = list(self.accounts).index(account)
                if (type(due) is not int or not offset or index >= 3 or due % 3600 != offset[index]*60 or
                        not 0 <= now-due <= 120 or abs(request['client_now']-now) > 30 or not math.isfinite(request['client_now']) or
                        event != encoded([self.config['schedule_version'], role, account, due]) or not isinstance(token, str) or not token):
                    raise ValueError('invalid slot, identity, clock or token')
                if row:
                    if row['token'] != token or row['account'] != account:
                        raise ValueError('claim token conflict')
                    return dict(row)
                if not self.accounts[account]['sources']:
                    raise ValueError('explicit historical sources required')
                for source in self.accounts[account]['sources']:
                    if not db.execute('SELECT 1 FROM imports WHERE source_path=? AND source_sha256=? AND record_key=?',
                                      (source['path'], source['sha256'], '@enrolled:'+account)).fetchone():
                        raise ValueError('historical enrollment missing')
                if db.execute('SELECT 1 FROM holds WHERE account=?', (account,)).fetchone():
                    raise ValueError('account held')
                db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)', (event, account, role, due, due+900, token, 'claimed', None, None, None, 'claimed'))
                db.execute('INSERT INTO holds VALUES(?,?)', (account, event))
            else:
                if not row or row['account'] != account or (action != 'reconcile' and row['token'] != token):
                    raise ValueError('unknown event or wrong token')
                if action == 'begin_send':
                    if (self.path.parent/'STOP').exists() or row['phase'] != 'claimed' or now >= row['deadline_epoch']:
                        raise ValueError('sending forbidden or expired')
                    if not re.fullmatch('[a-f0-9]{64}', request['digest']):
                        raise ValueError('invalid message digest')
                    db.execute('UPDATE events SET phase=?,message_digest=?,reason=? WHERE event_key=?', ('sending', request['digest'], 'sending', event))
                elif action == 'finish':
                    self.finish(db, row, request['outcome'], request['receipt'], now)
                else:
                    proof = request['proof']
                    if request['digest'] != row['message_digest'] or proof.get('kind') != 'positive_readback' or not self.proof(self.accounts[account], event, row['message_digest'], proof, now):
                        raise ValueError('invalid reconciliation proof')
                    self.resolve(db, row, 'positive_readback', proof)
            result = dict(db.execute('SELECT * FROM events WHERE event_key=?', (event,)).fetchone())
            if db.execute('SELECT 1 FROM resolutions WHERE event_key=? AND kind=?', (event, 'positive_readback')).fetchone():
                result['effective_status'] = 'delivered_reconciled'
            return result

    def resolve(self, db, row, kind, proof):
        serialized = encoded(proof)
        prior = db.execute('SELECT * FROM resolutions WHERE event_key=?', (row['event_key'],)).fetchone()
        if prior:
            if prior['kind'] != kind or prior['proof_json'] != serialized:
                raise ValueError('conflicting resolution')
            return
        if not db.execute('SELECT 1 FROM holds WHERE account=? AND event_key=?', (row['account'], row['event_key'])).fetchone():
            raise ValueError('event is not held')
        db.execute('INSERT INTO resolutions VALUES(?,?,?,?)', (row['event_key'], kind, digest(serialized), serialized))
        db.execute('DELETE FROM holds WHERE account=? AND event_key=?', (row['account'], row['event_key']))

    def release(self, account, event, attestation):
        if not all(isinstance(attestation.get(k), str) and attestation[k] for k in ('operator', 'reason', 'proof_digest', 'authorized_at', 'workers_stopped_at')):
            raise ValueError('fresh operator attestation and worker cessation required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM events WHERE event_key=? AND account=?', (event, account)).fetchone()
            if not row:
                raise ValueError('unknown release target')
            self.resolve(db, row, 'operator_release', attestation)

    def enroll(self, account):
        prepared = []
        for source in self.accounts[account]['sources']:
            raw = Path(source['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source['sha256']:
                raise ValueError('historical source hash mismatch')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('corrupt historical source')
            kind = source['kind']
            if kind == 'legacy':
                record = data['accounts'].get(account) if 'accounts' in data else data
                if not isinstance(record, dict) or record.get('account', account) != account or type(record.get('delivery_unverified', False)) is not bool:
                    raise ValueError('corrupt legacy account')
                records = [('legacy:'+account, record)] if record.get('delivery_unverified') or str(record.get('last_status', '')).startswith('UNVERIFIED_SEND') else []
            elif kind == 'pilot':
                pending = data.get('pending_delivery')
                if 'pending_delivery' not in data or (pending is not None and (not isinstance(pending, dict) or pending.get('account') != account)):
                    raise ValueError('corrupt pilot source')
                records = [('pending', pending)] if pending else []
            elif kind in ('exception_attempt', 'exception_result'):
                if not isinstance(data.get('event_id'), str) or (kind == 'exception_attempt' and data.get('account') != account):
                    raise ValueError('corrupt exception source')
                records = [(kind, data)] if kind == 'exception_attempt' or data.get('delivery_verified') is not True else []
            else:
                raise ValueError('unknown required historical schema')
            prepared.append((source, records))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for source, records in prepared:
                for key, record in records:
                    event = 'historical:'+digest(encoded([source['path'], source['sha256'], key]))
                    receipt = encoded({'kind': 'uncertain', 'raw_record_digest': digest(encoded(record)), 'reason': record.get('kind', record.get('last_status', 'historical_uncertainty'))})
                    db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)', (event, account, 'historical', 0, 0, '', 'terminal', None, 'uncertain', receipt, 'historical_uncertainty'))
                    if not db.execute('SELECT 1 FROM resolutions WHERE event_key=?', (event,)).fetchone():
                        db.execute('INSERT OR IGNORE INTO holds VALUES(?,?)', (account, event))
                    db.execute('INSERT OR IGNORE INTO imports VALUES(?,?,?,?)', (source['path'], source['sha256'], key, event))
                db.execute('INSERT OR IGNORE INTO imports VALUES(?,?,?,?)', (source['path'], source['sha256'], '@enrolled:'+account, ''))
