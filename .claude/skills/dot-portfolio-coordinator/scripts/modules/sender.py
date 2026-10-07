"""Receipt-safe sender bounded by a trusted local operator grant."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from modules.process_utils import run_bounded_command

WORKER_SHA = "dot-portfolio-coordinator-sender-v3"
COOLDOWN_SECS = 7200
MAX_GRANT_WINDOW_SECS = 43200
MAX_SUMMARY_CHARS = 32000
STANDALONE_VERIFIED_REGEX = re.compile(r"(?m)^DOT_SENT_VERIFIED\s*$")
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def emit_result(outcome: str, reason: str, account: str,
                delivery_verified: bool = False,
                event_id: Optional[str] = None) -> None:
    res = {"schema_version": 1, "account": account, "outcome": outcome,
           "reason": reason, "delivery_verified": delivery_verified,
           "worker_sha256": WORKER_SHA}
    if event_id:
        res["event_id"] = event_id
    print("COORDINATOR_RESULT " + json.dumps(res))


def _read_json_file(path: str, label: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Read a private, owner-owned regular file without following symlinks."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
                return None, f"{label}_invalid_owner_or_type"
            if st.st_mode & 0o077:
                return None, f"{label}_not_private"
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            return None, f"{label}_too_large"
        data = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non_finite_{value}")))
        if not isinstance(data, dict):
            return None, f"{label}_not_object"
        return data, "ok"
    except FileNotFoundError:
        return None, f"{label}_missing"
    except Exception:
        return None, f"{label}_corrupt_or_unreadable"


def validate_operator_grant(grant_file: str, expected_sha: str,
                            account: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Check a grant pinned by the trusted local operator invocation.

    The path and digest are caller-supplied pins; this does not authenticate the
    operator, the native dot client, or Slack delivery independently.
    """
    if not grant_file or not expected_sha:
        return False, "missing_grant_parameters", None
    try:
        grant_stat = os.lstat(grant_file)
        parent_stat = os.stat(os.path.dirname(os.path.abspath(grant_file)),
                              follow_symlinks=False)
        if (not stat.S_ISREG(grant_stat.st_mode) or
                grant_stat.st_uid != os.getuid() or grant_stat.st_mode & 0o077 or
                not stat.S_ISDIR(parent_stat.st_mode) or
                parent_stat.st_uid != os.getuid() or parent_stat.st_mode & 0o077):
            return False, "invalid_grant_owner_mode_or_type", None
        fd = os.open(grant_file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            grant_bytes = stream.read(1_000_001)
        if len(grant_bytes) > 1_000_000:
            return False, "grant_too_large", None
        if hashlib.sha256(grant_bytes).hexdigest() != expected_sha:
            return False, "grant_sha256_mismatch", None
        data = json.loads(grant_bytes, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non_finite_{value}")))
    except Exception:
        return False, "grant_invalid_or_unreadable", None
    if not isinstance(data, dict):
        return False, "grant_not_a_json_object", None
    if data.get("grant_version") != 1:
        return False, "grant_version_invalid", None
    if data.get("task_id") != "dot-coordinator-separated-20261007":
        return False, "grant_task_id_mismatch", None
    if data.get("account_id") != account:
        return False, "grant_account_mismatch", None
    if data.get("action") not in ("send_dot_test_message", "coordination_message"):
        return False, "grant_action_disallowed", None
    activated, expiry = data.get("activated_at_epoch"), data.get("expiry_epoch")
    maximum, interval = data.get("max_messages"), data.get("min_interval_secs")
    if (type(activated) not in (int, float) or not math.isfinite(activated) or
            type(expiry) not in (int, float) or not math.isfinite(expiry) or
            type(maximum) is not int or type(interval) not in (int, float) or
            not math.isfinite(interval)):
        return False, "grant_numeric_fields_invalid", None
    now = time.time()
    if activated > now or expiry <= now or expiry <= activated or expiry - activated > MAX_GRANT_WINDOW_SECS:
        return False, "grant_window_invalid_or_expired", None
    if maximum < 1 or maximum > 12:
        return False, "grant_max_messages_out_of_bounds", None
    if interval < 3600:
        return False, "grant_min_interval_too_short", None
    return True, "ok", data


def _atomic_write(path: str, data: Dict[str, Any], state_dir: str) -> None:
    fd, temp_path = tempfile.mkstemp(prefix=".sender-state-", dir=state_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        dir_fd = os.open(state_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def run_sender_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Receipt-safe dot delivery subcomponent")
    parser.add_argument("--account", default="default")
    parser.add_argument("--state-dir")
    parser.add_argument("--lock-file")
    parser.add_argument("--grant-file")
    parser.add_argument("--grant-sha256")
    parser.add_argument("--transport-script")
    parser.add_argument("--authorization-ref")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--full-rollup", action="store_true")
    parser.add_argument("--poll-reply", action="store_true")
    parser.add_argument("--no-poll", action="store_true")
    parser.add_argument("--reconcile-receipt")
    args = parser.parse_args(argv)
    account = args.account
    if not ACCOUNT_RE.fullmatch(account) or account in (".", ".."):
        emit_result("invalid", "invalid_account", account)
        return 2
    state_dir = args.state_dir
    account_file = os.path.join(state_dir, f"account_{account}.json") if state_dir else ""
    if args.status:
        state, reason = _read_json_file(account_file, "state") if account_file else (None, "state_missing")
        payload = {"schema_version": 1, "account": account,
                   "state_sha256": hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
                   if state is not None else ("corrupt" if reason != "state_missing" else None),
                   "last_sent_epoch": state.get("last_sent_epoch", 0) if state else 0,
                   "delivery_unverified": bool(state and state.get("pending_delivery")),
                   "pending_delivery": state.get("pending_delivery") if state else None,
                   "retained_event_ids": state.get("retained_event_ids", []) if state else [],
                   "worker_sha256": WORKER_SHA}
        if args.json:
            print("COORDINATOR_STATUS " + json.dumps(payload))
        return 0
    if args.poll_reply:
        emit_result("invalid", "unsupported_poll", account)
        return 2
    if args.reconcile_receipt:
        emit_result("invalid", "unsupported_reconcile", account)
        return 2
    if not state_dir:
        emit_result("invalid", "state_dir_required", account)
        return 2
    try:
        state_stat = os.lstat(state_dir)
        if (not stat.S_ISDIR(state_stat.st_mode) or state_stat.st_uid != os.getuid() or
                state_stat.st_mode & 0o077):
            raise ValueError
    except Exception:
        emit_result("invalid", "state_dir_must_be_private_existing_directory", account)
        return 2
    event_id = os.environ.get("COORDINATOR_CHANGE_ID", "").strip()
    summary = os.environ.get("COORDINATOR_CHANGE_SUMMARY", "").strip()
    urgent = os.environ.get("COORDINATOR_URGENT", "0").strip() in ("1", "true")
    if not event_id and not summary:
        emit_result("quiet", "no_input_event", account)
        return 0
    if not event_id or len(event_id) > 160 or "\n" in event_id:
        emit_result("invalid", "invalid_event_id", account)
        return 2
    if not summary or len(summary) > MAX_SUMMARY_CHARS:
        emit_result("invalid", "invalid_summary", account)
        return 2
    # Grant/hash must be pinned by the trusted operator command line, never environment.
    valid, reason, grant = validate_operator_grant(args.grant_file, args.grant_sha256, account)
    if not valid:
        emit_result("invalid", f"grant_validation_failed_{reason}", account)
        return 2
    transport = args.transport_script or os.environ.get("DOT_TRANSPORT_SCRIPT")
    if not transport:
        transport = str(Path(__file__).resolve().parent.parent.parent / "dot" / "scripts" / "dot.sh")
    lock_path = args.lock_file or os.path.join(state_dir, "sender.lock")
    if os.path.dirname(os.path.abspath(lock_path)) != os.path.abspath(state_dir):
        emit_result("invalid", "lock_must_be_in_state_dir", account)
        return 2
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        emit_result("deferred", "lock_contention_or_invalid_lock", account)
        return 0
    try:
        acc, state_reason = _read_json_file(account_file, "state")
        if acc is None and state_reason != "state_missing":
            emit_result("uncertain", "state_corrupt_hold", account)
            return 3
        if acc is None:
            acc = {"schema_version": 1, "grant_sha256": args.grant_sha256,
                   "attempted_count": 0, "last_attempt_epoch": 0,
                   "last_sent_epoch": 0, "retained_event_ids": [],
                   "pending_delivery": None}
        if acc.get("grant_sha256") != args.grant_sha256:
            emit_result("uncertain", "grant_binding_hold_new_run_required", account)
            return 3
        if acc.get("pending_delivery"):
            emit_result("uncertain", "receipt_hold", account)
            return 3
        retained = acc.get("retained_event_ids")
        if not isinstance(retained, list) or not all(isinstance(item, str) for item in retained):
            emit_result("uncertain", "state_corrupt_hold", account)
            return 3
        if event_id in retained:
            emit_result("duplicate", "already_received", account)
            return 0
        now = time.time()
        attempts = acc.get("attempted_count")
        last_attempt = acc.get("last_attempt_epoch")
        if type(attempts) is not int or type(last_attempt) not in (int, float):
            emit_result("uncertain", "state_corrupt_hold", account)
            return 3
        if attempts >= grant["max_messages"]:
            emit_result("deferred", "grant_message_limit", account)
            return 0
        if attempts and now - last_attempt < grant["min_interval_secs"]:
            emit_result("deferred", "grant_min_interval", account)
            return 0
        if not urgent and not args.full_rollup and not args.force and now - acc.get("last_sent_epoch", 0) < COOLDOWN_SECS:
            emit_result("deferred", "cooldown", account)
            return 0
        msg_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        acc["attempted_count"] = attempts + 1
        acc["last_attempt_epoch"] = now
        acc["pending_delivery"] = {"account": account, "event_id": event_id,
            "kind": "full_rollup" if args.full_rollup else "delta",
            "message_sha256": msg_hash, "attempt_timestamp": now,
            "grant_sha256": args.grant_sha256}
        _atomic_write(account_file, acc, state_dir)
        # Re-pin the grant directly before sending; if it changed, retain the hold.
        valid, reason, _ = validate_operator_grant(args.grant_file, args.grant_sha256, account)
        if not valid:
            emit_result("uncertain", f"grant_changed_after_reservation_{reason}", account)
            return 4
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=state_dir,
                                         prefix=".dot-message-") as message:
            os.fchmod(message.fileno(), 0o600)
            message.write(summary)
            message.flush()
            os.fsync(message.fileno())
            message_path = message.name
        try:
            valid, reason, _ = validate_operator_grant(
                args.grant_file, args.grant_sha256, account)
            if not valid:
                emit_result("uncertain", f"grant_changed_after_reservation_{reason}", account)
                return 4
            transport_env = os.environ.copy()
            transport_env["DOT_ROTATE_ON_LIMIT"] = "0"
            rc, stdout, _stderr = run_bounded_command(
                [transport, "--account", account, "send-once", message_path],
                env=transport_env, timeout_secs=600)
        except Exception:
            emit_result("uncertain", "send_unverified", account, event_id=event_id)
            return 4
        finally:
            if os.path.exists(message_path):
                os.unlink(message_path)
        if rc == 0 and STANDALONE_VERIFIED_REGEX.search(stdout):
            acc["pending_delivery"] = None
            acc["last_sent_epoch"] = time.time()
            retained.append(event_id)
            acc["retained_event_ids"] = retained
            _atomic_write(account_file, acc, state_dir)
            emit_result("delivered", "verified_by_transport", account,
                        delivery_verified=True, event_id=event_id)
            return 0
        emit_result("uncertain", "send_unverified", account, event_id=event_id)
        return 4
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


if __name__ == "__main__":
    sys.exit(run_sender_cli(sys.argv[1:]))
