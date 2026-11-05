#!/usr/bin/env python3
"""Private, expiry-aware /tmp cache for explicit reviewer quota responses."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
ROOT = Path("/tmp") / f"advice-quota-{os.getuid()}"
LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class UnsafeCache(Exception):
    pass


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError("expected ISO-8601 time") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return result.astimezone(timezone.utc)


@contextmanager
def locked(root):
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise UnsafeCache(type(error).__name__) from None
    try:
        info = root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise UnsafeCache("cache directory is not private and user-owned")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(root / ".lock", flags, 0o600)
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError as error:
        raise UnsafeCache(type(error).__name__) from None
    try:
        yield
    finally:
        os.close(fd)


def read_entry(path, digest, provider):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise UnsafeCache(type(error).__name__) from None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise UnsafeCache("cache entry is not private and user-owned")
    try:
        entry = json.loads(path.read_text())
        reset = parse_time(entry["reset_at_utc"])
        if (entry.get("version") != VERSION or entry.get("identity_sha256") != digest
                or entry.get("provider") != provider
                or entry.get("reason") != "quota" or not entry.get("provider")):
            raise ValueError
        return entry, reset
    except (OSError, ValueError, KeyError, TypeError, argparse.ArgumentTypeError):
        path.unlink(missing_ok=True)
        return None


def write_entry(path, entry):
    fd, temporary = tempfile.mkstemp(prefix=".quota-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(entry, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "record", "clear"))
    parser.add_argument("--identity", required=True,
                        help="stable non-secret account seat label, not a model or email")
    parser.add_argument("--provider", required=True, type=str,
                        help="verified provider/CLI seat label")
    parser.add_argument("--model", default="unknown")
    parser.add_argument("--reset-at", type=parse_time,
                        help="explicit provider-reported ISO-8601 reset time")
    if os.environ.get("ADVICE_QUOTA_CACHE_TESTING") == "1":
        parser.add_argument("--cache-root", type=Path, default=ROOT)
        parser.add_argument("--now", type=parse_time)
    args = parser.parse_args(argv)
    if (not LABEL.fullmatch(args.identity) or not LABEL.fullmatch(args.provider)
            or not LABEL.fullmatch(args.model)):
        parser.error("identity/provider/model must be short non-secret labels")
    if args.command == "record" and (not args.provider or not args.reset_at):
        parser.error("record requires provider and explicit reset time")
    if args.command != "record" and args.reset_at:
        parser.error("reset-at is only valid with record")

    digest = hashlib.sha256(f"{args.provider}\0{args.identity}".encode()).hexdigest()
    root = getattr(args, "cache_root", ROOT)
    path = root / f"{digest}.json"
    try:
        with locked(root):
            now = getattr(args, "now", None) or datetime.now(timezone.utc)
            if args.command == "clear":
                path.unlink(missing_ok=True)
                print("CLEARED")
            elif args.command == "record":
                if args.reset_at <= now:
                    path.unlink(missing_ok=True)
                    print("RESET_ALREADY_PASSED; cleared stale quota")
                else:
                    write_entry(path, {"version": VERSION, "identity_sha256": digest,
                        "provider": args.provider, "model": args.model,
                        "reason": "quota", "observed_at_utc": now.isoformat(),
                        "reset_at_utc": args.reset_at.isoformat()})
                    print(f"RECORDED provider={args.provider} reset_at={args.reset_at.isoformat()}")
            else:
                entry = read_entry(path, digest, args.provider)
                if entry and entry[1] > now:
                    print(f"QUOTA_BLOCKED provider={entry[0]['provider']} reset_at={entry[1].isoformat()}")
                    return 10
                if entry:
                    path.unlink(missing_ok=True)
                print("ELIGIBLE")
    except UnsafeCache as error:
        # This cache cannot deny an otherwise authorized reviewer attempt.
        print(f"CACHE_UNAVAILABLE: {error}; do not skip this seat", file=sys.stderr)
        print("ELIGIBLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
