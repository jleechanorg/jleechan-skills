#!/usr/bin/env python3
"""Rename provably stale Chrome singleton files in configured Dot profiles.

A coordinator run that ends by terminating the browser can leave SingletonLock,
SingletonCookie and SingletonSocket behind. The launcher then fails closed for
every later run on that profile. This helper only acts when ownership of the
stale lock is provable, and it never deletes anything:

  * the lock's "hostname-pid" target names this host, and
  * that pid no longer exists, and
  * no live process references the profile directory.

Otherwise it leaves the profile untouched. Files are renamed to
<name>.stale-<UTC timestamp>, which keeps the evidence recoverable.
"""
import argparse
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

NAMES = ("SingletonLock", "SingletonCookie", "SingletonSocket")
LOCK = re.compile(r"(?P<host>.+)-(?P<pid>\d+)\Z")


def profile_roots(config_path):
    config = json.loads(Path(config_path).expanduser().read_text())
    for key, details in sorted(config.get("accounts", {}).items()):
        if isinstance(details, dict) and details.get("user_data_dir"):
            yield key, Path(os.path.abspath(os.path.expanduser(details["user_data_dir"])))


def processes_on(profile):
    """Return the pids of live processes whose command line names this profile."""
    hits = []
    for entry in Path("/proc").glob("[0-9]*") if Path("/proc").is_dir() else []:
        try:
            argv = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if str(profile) in argv:
            hits.append(int(entry.name))
    if hits or Path("/proc").is_dir():
        return hits
    import subprocess
    listing = subprocess.run(["ps", "-Ao", "pid=,args="], capture_output=True, text=True).stdout
    return [int(line.split(None, 1)[0]) for line in listing.splitlines()
            if str(profile) in line and int(line.split(None, 1)[0]) != os.getpid()]


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def reap(name, profile, apply):
    lock = profile / "SingletonLock"
    if not os.path.lexists(lock):
        return f"{name}: no lock"
    try:
        target = os.readlink(lock)
    except OSError:
        return f"{name}: lock is not a symlink; left untouched"
    match = LOCK.match(target)
    if not match:
        return f"{name}: unrecognised lock target; left untouched"
    if match.group("host") != socket.gethostname():
        return f"{name}: lock held by {match.group('host')}; left untouched"
    pid = int(match.group("pid"))
    if pid_alive(pid):
        return f"{name}: lock holder pid {pid} is alive; left untouched"
    holders = processes_on(profile)
    if holders:
        return f"{name}: pid {pid} dead but processes {holders} use the profile; left untouched"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    renamed = []
    for candidate in NAMES:
        path = profile / candidate
        if os.path.lexists(path):
            if apply:
                path.rename(profile / f"{candidate}.stale-{stamp}")
            renamed.append(candidate)
    return f"{name}: provably stale (pid {pid} dead, profile idle) -> {'renamed ' + ', '.join(renamed) if apply else 'would rename ' + ', '.join(renamed)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.environ.get("DOT_CONFIG_FILE", "~/.config/dot/config.json"))
    parser.add_argument("--apply", action="store_true", help="rename instead of only reporting")
    args = parser.parse_args()
    status = 0
    for name, profile in profile_roots(args.config):
        if not profile.is_dir() or profile.is_symlink():
            print(f"{name}: profile unavailable; left untouched")
            continue
        print(reap(name, profile, args.apply))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
