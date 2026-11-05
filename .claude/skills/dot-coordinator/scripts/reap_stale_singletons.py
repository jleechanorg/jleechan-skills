#!/usr/bin/env python3
"""Rename provably stale Chrome singleton files in configured Dot profiles.

A coordinator run that ends by terminating the browser can leave SingletonLock,
SingletonCookie and SingletonSocket behind. The launcher then fails closed for
every later run on that profile. This helper only acts when ownership of the
stale lock is provable, and it never deletes anything:

  * the lock's "hostname-pid" target names this host, and
  * that pid no longer exists, and
  * no live process references the profile directory.

Residual limitation, stated rather than denied: the liveness checks and the renames are separate
operations, so a Chrome launch that starts inside that loop can lose its fresh lock. Userland
cannot make check-then-act atomic against a process that does not cooperate with our lock, and
the alternatives - deleting the files, or leaving the launcher blocked forever - are strictly
worse. Mitigations that do exist, stated precisely: the loop touches only files whose lock still names
this host with a dead pid; each publish claims its destination with a kernel-enforced no-replace
link, so prior evidence is never overwritten; a filesystem without that primitive fails closed
instead of falling back to a replace-capable rename; and the launcher fails closed rather than
scrambling on an unreadable lock. One residual remains and is not claimed away: if Chrome replaces
the source between the link and the unlink, the unlink can remove Chrome's fresh file, which was
never preserved under a stale name. The only real mitigation is scheduling - run the reaper on a
short timer and never concurrently with a coordinator slot, so nothing is launching.

Otherwise it leaves the profile untouched. Files are renamed to
<name>.stale-<UTC timestamp>, which keeps the evidence recoverable.
"""
import argparse
import json
import os
import re
import socket
import subprocess
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
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            # An unreadable process's arguments cannot be cleared: treat the profile as in use so
            # the caller fails closed instead of reaping a lock a live process may need.
            hits.append(int(entry.name))
            continue
        if str(profile) in raw.replace(b"\0", b" ").decode(errors="replace"):
            hits.append(int(entry.name))
    if hits or Path("/proc").is_dir():
        return hits
    completed = subprocess.run(["ps", "-Ao", "pid=,args="], capture_output=True, text=True)
    if completed.returncode != 0:
        # Unknown process state must never be reported as an idle profile.
        return [os.getpid()]
    return [int(line.split(None, 1)[0]) for line in completed.stdout.splitlines()
            if str(profile) in line and int(line.split(None, 1)[0]) != os.getpid()]


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def publish_stale(source, profile, candidate, stamp):
    """Move `source` to a fresh <name>.stale-<stamp>[-n] name with no overwrite window.

    `os.link` fails with FileExistsError instead of replacing a destination, so the
    destination name is claimed atomically by the kernel. The source is unlinked only
    after its link exists, so a failure at any point leaves recoverable state and never
    destroys prior evidence. Returns the destination path.
    """
    base = f"{candidate}.stale-{stamp}"
    index = 0
    while True:
        destination = profile / (base if index == 0 else f"{base}-{index}")
        try:
            os.link(source, destination, follow_symlinks=False)
            break
        except FileExistsError:
            index += 1
            if index > 1000:
                raise
        except OSError as error:
            # No atomic no-replace primitive on this filesystem. Fail closed: a rename would
            # reopen the overwrite window this function exists to eliminate.
            raise OSError(
                f"cannot publish {destination} atomically ({error}); "
                "refusing to fall back to a replace-capable rename"
            ) from error
    try:
        os.unlink(source)
    except OSError:
        pass
    return destination


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
    # Re-check immediately before acting: a Chrome launch can replace the lock between the
    # inspection above and the rename. If the lock is no longer the one we judged stale, stop.
    try:
        current = os.readlink(lock)
    except OSError:
        return f"{name}: lock vanished before rename; left untouched"
    if current != target:
        return f"{name}: lock changed during inspection ({current}); left untouched"
    if pid_alive(pid) or processes_on(profile):
        return f"{name}: lock became live before rename; left untouched"
    renamed = []
    for candidate in NAMES:
        path = profile / candidate
        if os.path.lexists(path):
            if apply:
                publish_stale(path, profile, candidate, stamp)
            renamed.append(candidate)
    return f"{name}: provably stale (pid {pid} dead, profile idle) -> {'renamed ' + ', '.join(renamed) if apply else 'would rename ' + ', '.join(renamed)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.environ.get("DOT_CONFIG_FILE", "~/.config/dot/config.json"))
    parser.add_argument("--apply", action="store_true", help="rename instead of only reporting")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be renamed without touching anything (the default)")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run
    status = 0
    for name, profile in profile_roots(args.config):
        if not profile.is_dir() or profile.is_symlink():
            print(f"{name}: profile unavailable; left untouched")
            continue
        print(reap(name, profile, apply))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
