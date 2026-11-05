#!/usr/bin/env python3
"""Private, expiry-aware /tmp cache for explicit reviewer quota responses."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
ROOT = Path("/tmp") / f"advice-quota-{os.getuid()}"
LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIR = getattr(os, "O_DIRECTORY", 0)
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


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
def locked(path):
    """Open and pin the cache directory, then do all mutations relative to its fd."""
    parent_fd = cache_fd = lock_fd = None
    try:
        parent_path = path.parent.resolve(strict=True)
        parent_fd = os.open(parent_path, os.O_RDONLY | DIR | NOFOLLOW)
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        cache_fd = os.open(path.name, os.O_RDONLY | DIR | NOFOLLOW, dir_fd=parent_fd)
        info = os.fstat(cache_fd)
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise UnsafeCache("cache directory is not private and user-owned")
        lock_fd = os.open(".lock", os.O_CREAT | os.O_RDWR | NOFOLLOW,
                          0o600, dir_fd=cache_fd)
        info = os.fstat(lock_fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise UnsafeCache("cache lock is not private and user-owned")
        # A stale or stuck caller must never stall an advice review indefinitely.
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield cache_fd
    except OSError as error:
        raise UnsafeCache(type(error).__name__) from None
    finally:
        for fd in (lock_fd, cache_fd, parent_fd):
            if fd is not None:
                os.close(fd)


def read_entry(directory_fd, name, digest, provider):
    try:
        fd = os.open(name, os.O_RDONLY | NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        os.close(fd)
        raise UnsafeCache("cache entry is not a private regular file owned by this user")
    try:
        with os.fdopen(fd, encoding="utf-8") as stream:
            entry = json.load(stream)
        event_time = parse_time(entry["observed_at_utc"])
        event_type = entry["event_type"]
        if event_type not in {"quota", "success"}:
            raise ValueError
        reset = parse_time(entry["reset_at_utc"]) if event_type == "quota" else None
        if (entry.get("version") != VERSION or entry.get("identity_sha256") != digest
                or entry.get("provider") != provider
                or (event_type == "quota" and reset is None)
                or (event_type == "success" and "reset_at_utc" in entry)):
            raise ValueError
        return entry, event_time, reset
    except (OSError, ValueError, KeyError, TypeError, argparse.ArgumentTypeError):
        os.unlink(name, dir_fd=directory_fd)
        return None


def write_entry(directory_fd, name, entry):
    temporary = ".quota-" + secrets.token_hex(8) + ".tmp"
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(entry, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "record", "clear"))
    parser.add_argument("--identity-sha256", required=True,
                        help="SHA-256 of the verified provider account identifier; never a model or guessed label")
    parser.add_argument("--provider", required=True, help="verified provider/CLI seat label")
    parser.add_argument("--model", default="unknown")
    parser.add_argument("--reset-at", type=parse_time,
                        help="explicit provider-reported ISO-8601 reset time")
    parser.add_argument("--observed-at", type=parse_time,
                        help="timestamp when this provider result was actually observed")
    if os.environ.get("ADVICE_QUOTA_CACHE_TESTING") == "1":
        parser.add_argument("--cache-root", type=Path, default=ROOT)
        parser.add_argument("--now", type=parse_time)
    args = parser.parse_args(argv)
    if (not SHA256.fullmatch(args.identity_sha256) or not LABEL.fullmatch(args.provider)
            or not LABEL.fullmatch(args.model)):
        parser.error("identity must be a lowercase SHA-256 digest; provider/model must be non-secret labels")
    if args.command in {"record", "clear"} and not args.observed_at:
        parser.error("record and clear require the actual result observation time")
    if args.command == "record" and not args.reset_at:
        parser.error("record requires an explicit reset time")
    if args.command != "record" and args.reset_at:
        parser.error("reset-at is only valid with record")

    digest = hashlib.sha256(f"{args.provider}\0{args.identity_sha256}".encode()).hexdigest()
    name = f"{digest}.json"
    root = getattr(args, "cache_root", ROOT)
    try:
        with locked(root) as directory_fd:
            now = getattr(args, "now", None) or datetime.now(timezone.utc)
            current = read_entry(directory_fd, name, digest, args.provider)
            if args.command == "clear":
                observed = args.observed_at
                if current and (observed < current[1]
                                or (observed == current[1] and current[0]["event_type"] == "success")):
                    print("STALE_SUCCESS_IGNORED")
                else:
                    write_entry(directory_fd, name, {
                        "version": VERSION, "identity_sha256": digest,
                        "provider": args.provider, "event_type": "success",
                        "observed_at_utc": observed.isoformat(),
                    })
                    print("CLEARED")
            elif args.command == "record":
                observed = args.observed_at
                event_type = "quota" if args.reset_at > now else "success"
                event_time = max(observed, args.reset_at) if event_type == "success" else observed
                if (current and (event_time < current[1]
                                 or (event_time == current[1] and current[0]["event_type"] == "success"))):
                    print("STALE_QUOTA_IGNORED")
                elif event_type == "success":
                    write_entry(directory_fd, name, {
                        "version": VERSION, "identity_sha256": digest,
                        "provider": args.provider, "event_type": "success",
                        "observed_at_utc": event_time.isoformat(),
                    })
                    print("RESET_ALREADY_PASSED; cleared stale quota")
                else:
                    write_entry(directory_fd, name, {
                        "version": VERSION, "identity_sha256": digest,
                        "provider": args.provider, "model": args.model, "event_type": "quota",
                        "observed_at_utc": observed.isoformat(),
                        "reset_at_utc": args.reset_at.isoformat(),
                    })
                    print(f"RECORDED provider={args.provider} reset_at={args.reset_at.isoformat()}")
            else:
                if current and current[0]["event_type"] == "success":
                    print("ELIGIBLE")
                elif current and current[2] > now:
                    print(f"QUOTA_BLOCKED provider={args.provider} reset_at={current[2].isoformat()}")
                    return 10
                elif current:
                    # Retain a watermark at the reset so a delayed pre-reset quota
                    # response cannot recreate the block after expiry.
                    write_entry(directory_fd, name, {
                        "version": VERSION, "identity_sha256": digest,
                        "provider": args.provider, "event_type": "success",
                        "observed_at_utc": max(current[1], current[2]).isoformat(),
                    })
                    print("ELIGIBLE")
                else:
                    print("ELIGIBLE")
    except (UnsafeCache, OSError) as error:
        # This cache is advisory: unsafe paths or filesystem failures must fail open.
        print(f"CACHE_UNAVAILABLE: {type(error).__name__}; do not skip this seat", file=sys.stderr)
        print("ELIGIBLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
