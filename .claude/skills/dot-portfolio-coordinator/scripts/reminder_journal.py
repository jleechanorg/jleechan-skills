"""Private, durable reminder outbox; callers hold the account lock while recovering/writing."""
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

STAGES = ('claim_ready', 'operation_started', 'sending', 'receipt_ready', 'acked')


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise ValueError('journal directory cannot be a symlink')
        self.directory.chmod(0o700)

    def _path(self, value, suffix='.json'):
        return self.directory / (hashlib.sha256(value.encode('utf-8')).hexdigest() + suffix)

    @contextlib.contextmanager
    def lock(self, account):
        fd = os.open(self._path(account, '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def read(self, event):
        return self._read_path(self._path(event))

    def _read_path(self, path):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, 'rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('journal record exceeds 64 KiB')
        record = json.loads(raw)
        self._validate(record)
        if self._path(record['event']) != path:
            raise ValueError('event filename mismatch')
        return record

    def _validate(self, record):
        if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k] for k in ('event', 'account', 'token')):
            raise ValueError('missing event identity')
        if record.get('stage') not in STAGES:
            raise ValueError('invalid journal stage')
        if any(type(record.get(k)) not in (int, float) or not math.isfinite(record[k]) for k in ('created_at', 'updated_at')):
            raise ValueError('invalid journal timestamp')

    def write(self, record):
        record = dict(record)
        old = self.read(record['event'])
        record.setdefault('created_at', old['created_at'] if old else time.time())
        record.setdefault('updated_at', time.time())
        self._validate(record)
        if old:
            if any(record[k] != old[k] for k in ('event', 'account', 'token', 'created_at')) or STAGES.index(record['stage']) < STAGES.index(old['stage']):
                raise ValueError('journal identity change or stage regression')
            for key in ('receipt', 'message_digest'):
                if key in old:
                    if key in record and json.dumps(record[key], sort_keys=True) != json.dumps(old[key], sort_keys=True):
                        raise ValueError('conflicting immutable ' + key)
                    record[key] = old[key]
        raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(raw) > 65536:
            raise ValueError('journal record exceeds 64 KiB')
        fd, name = tempfile.mkstemp(prefix='.pending-', dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self._path(record['event']))
            self._sync_directory()
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def pending(self, account):
        records = (self._read_path(path) for path in self.directory.glob('*.json'))
        return sorted((r for r in records if r and r['account'] == account and r['stage'] != 'acked'),
                      key=lambda r: (r['created_at'], r['event']))

    def prune(self, now):
        for path in self.directory.glob('*.json'):
            record = self._read_path(path)
            if record and record['stage'] == 'acked' and now - record['updated_at'] > 7 * 86400:
                path.unlink()
                self._sync_directory()
