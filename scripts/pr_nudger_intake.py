"""Durable target bookkeeping and host launch admission for the PR nudger."""

import json
import os
import platform
import re
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4


class RateLimited(OSError):
    """The current GitHub request bucket is exhausted until reset."""

    def __init__(self, until):
        self.until = until


def remember_binding(db, expected, owner, source):
    repo, number, head_repo, branch, _ = expected
    verified = dict(owner, binding_source=source, verified_at=time.time(), head_repo=head_repo)
    db.execute("INSERT OR REPLACE INTO binding VALUES (?, ?, ?, ?, ?)",
               (owner["cwd"], repo, number, branch, json.dumps(verified)))


class Intake:
    def __init__(self, db, state, now):
        self.db, self.state, self.now = db, state, now
        self._until = {}

    def prepare(self, keys):
        if self.db is None:
            return
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS target (
                repo TEXT, number INTEGER, next_action TEXT, observed_status TEXT,
                reason TEXT, attempts INTEGER DEFAULT 0, next_due REAL DEFAULT 0,
                head TEXT, observed_at REAL, stage TEXT, remote_push_at REAL,
                bootstrap TEXT, owner_session TEXT, PRIMARY KEY (repo, number));
            CREATE TABLE IF NOT EXISTS target_ci (
                repo TEXT, number INTEGER, head TEXT, status TEXT, observed_at REAL,
                PRIMARY KEY (repo, number));
            CREATE TABLE IF NOT EXISTS github_budget (
                bucket TEXT PRIMARY KEY, reset_at REAL NOT NULL);
        """)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.executemany(
                "INSERT OR IGNORE INTO target(repo, number, next_action)"
                " VALUES (?, ?, 'refresh_pr')", keys
            )
            self.db.execute("COMMIT")
        except sqlite3.Error:
            self.db.execute("ROLLBACK")
            raise

    def row(self, key):
        if self.db is None:
            return dict(attempts=0, next_due=0, head=None, observed_status=None,
                        bootstrap=None, owner_session=None)
        cursor = self.db.execute("SELECT * FROM target WHERE repo=? AND number=?", key)
        return dict(zip((column[0] for column in cursor.description), cursor.fetchone()))

    def set(self, key, **values):
        if self.db is not None:
            fields = ", ".join(f"{field}=?" for field in values)
            self.db.execute(f"UPDATE target SET {fields} WHERE repo=? AND number=?",
                            (*values.values(), *key))

    def observation(self, key, head, status, stage):
        old = self.row(key)
        changed = old["head"] != head or old["observed_status"] != status
        self.set(key, head=head, observed_status=status, observed_at=self.now, stage=stage,
                 **({"attempts": 0, "next_due": 0, "remote_push_at": None} if changed else {}))

    def ci_observation(self, key, head, status):
        if self.db is not None:
            self.db.execute("INSERT OR REPLACE INTO target_ci VALUES (?, ?, ?, ?, ?)",
                            (*key, head, status, time.time()))

    def schedule(self, key, reason, action, *, progress=False, earliest=0):
        row = self.row(key)
        if progress:
            attempts, due = 0, earliest
        elif row["next_due"] > self.now:
            attempts, due = row["attempts"], max(row["next_due"], earliest)
        else:
            attempts = row["attempts"] + 1
            due = max(self.now + (600, 1200, 2400, 3600)[min(attempts - 1, 3)], earliest)
        self.set(key, reason=reason, next_action=action, attempts=attempts, next_due=due)
        return dict(status=reason, next_action=action, attempts=attempts, next_due=due)

    def budget_until(self, bucket="core"):
        local = self._until.get(bucket, 0)
        if self.db is not None:
            row = self.db.execute("SELECT reset_at FROM github_budget WHERE bucket=?", (bucket,)).fetchone()
            return max(local, row[0] if row else 0)
        return local

    def rate_limit(self, until, bucket="core"):
        self._until[bucket] = max(self._until.get(bucket, 0), until)
        if self.db is not None:
            self.db.execute(
                "INSERT INTO github_budget VALUES (?, ?) ON CONFLICT(bucket)"
                " DO UPDATE SET reset_at=max(reset_at, excluded.reset_at)", (bucket, until)
            )

    def begin(self, key, expected, enrollment):
        if self.db is None or self.row(key)["bootstrap"]:
            return None
        descriptor, name = tempfile.mkstemp(prefix="bootstrap-", suffix=".jsonl", dir=self.state)
        os.close(descriptor)
        attempt = dict(id=str(uuid4()), events_path=name, started_at=self.now,
                       sha=expected[-1], identity=expected, enrollment=enrollment)
        self.set(key, bootstrap=json.dumps(attempt), next_action="reconcile_bootstrap")
        return Path(name)

    def bind(self, key, expected, owner):
        # Readers must not see a cleared attempt without the exact owner binding.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            remember_binding(self.db, expected, owner, "bootstrap")
            self.set(key, bootstrap=None, owner_session=owner["session"])
            self.db.execute("COMMIT")
        except sqlite3.Error:
            self.db.execute("ROLLBACK")
            raise


def _linux_cpu():
    fields = Path("/proc/stat").read_text().splitlines()[0].split()
    if fields[0] != "cpu":
        raise ValueError("missing aggregate CPU counters")
    ticks = [int(value) for value in fields[1:9]]
    return sum(ticks), ticks[3]


def launch_capacity():
    """The 5% threshold applies only when an adapter would start a process."""
    try:
        if platform.system() == "Linux":
            total, idle = _linux_cpu()
            time.sleep(0.1)
            later_total, later_idle = _linux_cpu()
            percent = 100 * (later_idle - idle) / (later_total - total)
            available = re.search(r"(?m)^MemAvailable:\s+(\d+) kB",
                                  Path("/proc/meminfo").read_text())
            return percent >= 5 and bool(available and int(available[1]) >= 4 * 1024**2)
        if platform.system() == "Darwin":
            top = subprocess.check_output(["top", "-l", "2", "-n", "0", "-s", "2"],
                                          text=True, timeout=10)
            samples = re.findall(r"CPU usage: [^\n]*?([\d.]+)% idle", top)
            if len(samples) < 2 or float(samples[-1]) < 5:
                return False
            memory = subprocess.check_output(["vm_stat"], text=True, timeout=3)
            size = re.search(r"page size of (\d+) bytes", memory)
            pages = re.findall(r"(?m)^Pages (?:free|inactive|speculative):\s+(\d+)\.", memory)
            return bool(size and pages and int(size[1]) * sum(map(int, pages)) >= 4 * 1024**3)
    except (OSError, ValueError, IndexError, ZeroDivisionError, subprocess.SubprocessError):
        pass
    return False
