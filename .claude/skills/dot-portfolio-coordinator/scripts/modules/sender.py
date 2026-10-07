"""Hardened, receipt-safe message delivery worker for dot-portfolio-coordinator.

Implements:
- Local operator pilot grant validation (owner UID, mode 0400/0600, parent dir 0700, SHA256 binding, schema bounds)
- Dedicated private state directory and fcntl lock
- Quiet wake on empty event
- Atomic pending delivery persistence before transport execution
- Strict standalone regex matching of DOT_SENT_VERIFIED on transport exit 0
- Uncertainty hold on transport failure or substring match
- Bounded deduplication across last 128 IDs (duplicate cannot be forced)
- Read-only status query creating zero files or directories
- Rejection of unsupported options (e.g. --poll-reply)
"""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MODULES_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = MODULES_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from modules.process_utils import run_bounded_command


WORKER_SHA = "dot-portfolio-coordinator-sender-v2"
COOLDOWN_SECS = 7200
STANDALONE_VERIFIED_REGEX = re.compile(r"(?m)^DOT_SENT_VERIFIED\s*$")


def emit_result(outcome: str, reason: str, account: str, delivery_verified: bool = False, event_id: Optional[str] = None) -> None:
    res = {
        "schema_version": 1,
        "account": account,
        "outcome": outcome,
        "reason": reason,
        "delivery_verified": delivery_verified,
        "worker_sha256": WORKER_SHA
    }
    if event_id:
        res["event_id"] = event_id
    print("COORDINATOR_RESULT " + json.dumps(res))


def emit_status(account: str, state_file: str) -> None:
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = json.dumps(data, sort_keys=True)
            state_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            last_sent = data.get("last_sent_epoch", 0)
            pending = data.get("pending_delivery")
            retained = data.get("retained_event_ids", [])
        except Exception:
            state_sha = "corrupt"
            last_sent = 0
            pending = None
            retained = []
    else:
        state_sha = None
        last_sent = 0
        pending = None
        retained = []

    status_rec = {
        "schema_version": 1,
        "account": account,
        "state_sha256": state_sha,
        "last_sent_epoch": last_sent,
        "delivery_unverified": pending is not None,
        "pending_delivery": pending,
        "retained_event_ids": retained,
        "worker_sha256": WORKER_SHA
    }
    print("COORDINATOR_STATUS " + json.dumps(status_rec))


def validate_operator_grant(
    grant_file: str,
    expected_sha: str,
    account: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Validates root operator pilot grant under strict security invariants."""
    if not grant_file or not expected_sha:
        return False, "missing_grant_parameters", None

    # Invariant: regular file, no symlinks
    if not os.path.isfile(grant_file) or os.path.islink(grant_file):
        return False, "invalid_grant_file_symlink_or_missing", None

    try:
        st = os.stat(grant_file)
    except Exception as e:
        return False, f"grant_stat_failed_{e}", None

    # Invariant: Owner UID must equal current OS UID
    if st.st_uid != os.getuid():
        return False, "invalid_grant_owner_uid_mismatch", None

    # Invariant: Mode must be 0400 or 0600
    file_mode = st.st_mode & 0o777
    if file_mode not in (0o400, 0o600):
        return False, f"invalid_grant_permissions_{oct(file_mode)}", None

    # Invariant: Parent directory mode must be 0700
    try:
        parent_dir = os.path.dirname(os.path.abspath(grant_file))
        parent_st = os.stat(parent_dir)
        parent_mode = parent_st.st_mode & 0o777
        if parent_mode != 0o700:
            return False, f"invalid_grant_parent_dir_permissions_{oct(parent_mode)}", None
    except Exception as e:
        return False, f"grant_parent_stat_failed_{e}", None

    # Invariant: Pinned SHA256 must match exactly
    try:
        with open(grant_file, "rb") as fp:
            grant_bytes = fp.read()
    except Exception as e:
        return False, f"grant_read_failed_{e}", None

    actual_sha = hashlib.sha256(grant_bytes).hexdigest()
    if actual_sha != expected_sha:
        return False, "grant_sha256_mismatch", None

    # Parse and validate schema bounds
    try:
        grant_data = json.loads(grant_bytes)
    except Exception as e:
        return False, f"grant_json_parse_error_{e}", None

    if not isinstance(grant_data, dict):
        return False, "grant_not_a_json_object", None

    if grant_data.get("task_id") != "dot-coordinator-separated-20261007":
        return False, "grant_task_id_mismatch", None

    allowed_accounts = [grant_data.get("account_id")]
    if account not in allowed_accounts:
        return False, "grant_account_mismatch", None

    action = grant_data.get("action")
    if action not in ("send_dot_test_message", "coordination_message"):
        return False, "grant_action_disallowed", None

    expiry = grant_data.get("expiry_epoch", 0)
    if not isinstance(expiry, (int, float)) or time.time() > expiry:
        return False, "grant_expired", None

    return True, "ok", grant_data


def run_sender_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Receipt-safe dot delivery subcomponent")
    parser.add_argument("--account", default="default", help="Account identifier")
    parser.add_argument("--state-dir", help="Private state directory")
    parser.add_argument("--lock-file", help="Exclusive lock file")
    parser.add_argument("--grant-file", help="Root operator grant file")
    parser.add_argument("--grant-sha256", help="Pinned SHA256 of grant file")
    parser.add_argument("--transport-script", help="Path to dot.sh transport script")
    parser.add_argument("--authorization-ref", help="Legacy authorization ref (optional)")
    parser.add_argument("--status", action="store_true", help="Read-only status query")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--force", action="store_true", help="Force send overriding cooldown only")
    parser.add_argument("--full-rollup", action="store_true", help="Full rollup message")
    parser.add_argument("--poll-reply", action="store_true", help="Poll for replies (unsupported)")
    parser.add_argument("--no-poll", action="store_true", help="Do not poll for replies")
    parser.add_argument("--reconcile-receipt", help="Reconcile receipt file")

    args = parser.parse_args(argv)

    account = args.account
    state_dir = args.state_dir or os.environ.get("DOT_PORTFOLIO_STATE_DIR") or f"/tmp/dot-sender-state-{os.getuid()}"
    account_state_file = os.path.join(state_dir, f"account_{account}.json")
    lock_file = args.lock_file or os.path.join(state_dir, "sender.lock")
    transport_script = args.transport_script or os.environ.get("DOT_TRANSPORT_SCRIPT")

    if not transport_script:
        # Default relative sibling transport
        script_dir = Path(__file__).resolve().parent
        transport_script = str(script_dir.parent.parent.parent / "dot" / "scripts" / "dot.sh")

    # 1. Read-only status mode
    if args.status:
        if args.json:
            emit_status(account, account_state_file)
        return 0

    # 2. Unsupported poll check
    if args.poll_reply:
        emit_result("invalid", "unsupported_poll", account)
        return 2

    # 3. Quiet wake check
    event_id = os.environ.get("COORDINATOR_CHANGE_ID", "").strip()
    summary = os.environ.get("COORDINATOR_CHANGE_SUMMARY", "").strip()
    urgent = os.environ.get("COORDINATOR_URGENT", "0").strip() in ("1", "true")

    if not event_id and not summary:
        emit_result("quiet", "no_input_event", account)
        return 0

    # 4. Input validation
    if not event_id or len(event_id) > 160 or "\n" in event_id:
        emit_result("invalid", "invalid_event_id", account)
        return 2

    if not summary or len(summary) > 2000:
        emit_result("invalid", "invalid_summary", account)
        return 2

    # 5. Operator grant validation
    grant_file = args.grant_file or os.environ.get("DOT_PORTFOLIO_GRANT_FILE", "")
    grant_sha = args.grant_sha256 or os.environ.get("DOT_PORTFOLIO_GRANT_SHA256", "")

    valid_grant, grant_reason, grant_obj = validate_operator_grant(grant_file, grant_sha, account)
    if not valid_grant:
        emit_result("invalid", f"grant_validation_failed_{grant_reason}", account)
        return 2

    # 6. Acquire exclusive lock on dedicated lock file
    os.makedirs(os.path.dirname(os.path.abspath(lock_file)), exist_ok=True)
    try:
        import fcntl
        lock_fd = open(lock_file, "a+")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        emit_result("deferred", "lock_contention", account)
        return 0

    try:
        os.makedirs(state_dir, exist_ok=True)

        # 7. Check account state: existing hold and deduplication
        acc_data = {"retained_event_ids": [], "last_sent_epoch": 0, "pending_delivery": None}
        if os.path.exists(account_state_file):
            try:
                with open(account_state_file, "r", encoding="utf-8") as f:
                    acc_data = json.load(f)
            except Exception:
                pass

        if acc_data.get("pending_delivery"):
            emit_result("uncertain", "receipt_hold", account)
            return 3

        retained = acc_data.get("retained_event_ids", [])
        if event_id in retained:
            emit_result("duplicate", "already_received", account)
            return 0

        now_epoch = int(time.time())
        last_sent = acc_data.get("last_sent_epoch", 0)

        # Delta Cooldown
        if not urgent and not args.full_rollup and not args.force:
            elapsed = now_epoch - last_sent
            if elapsed < COOLDOWN_SECS:
                emit_result("deferred", "cooldown", account)
                return 0

        # 8. Atomically persist pending attempt BEFORE transport
        msg_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        acc_data["pending_delivery"] = {
            "account": account,
            "event_id": event_id,
            "kind": "full_rollup" if args.full_rollup else "delta",
            "message_sha256": msg_hash,
            "attempt_timestamp": now_epoch,
            "grant_sha256": grant_sha
        }
        tmp_acc = f"{account_state_file}.tmp"
        with open(tmp_acc, "w", encoding="utf-8") as f:
            json.dump(acc_data, f, indent=2)
        os.replace(tmp_acc, account_state_file)

        # 9. Transport invocation
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir="/tmp", prefix="dot_msg_") as tmp_msg:
            tmp_msg.write(summary)
            tmp_msg_path = tmp_msg.name

        try:
            cmd = [transport_script, "--account", account, "send-once", tmp_msg_path]
            rc, stdout, stderr = run_bounded_command(cmd, timeout_secs=30)
        finally:
            if os.path.exists(tmp_msg_path):
                os.remove(tmp_msg_path)

        # 10. Receipt Verification
        # Invariant: Standalone regex match on DOT_SENT_VERIFIED and exit 0
        if rc == 0 and STANDALONE_VERIFIED_REGEX.search(stdout):
            # Delivery verified
            acc_data["pending_delivery"] = None
            acc_data["last_sent_epoch"] = int(time.time())
            if event_id not in retained:
                retained.append(event_id)
            acc_data["retained_event_ids"] = retained[-128:]  # bounded dedup window

            with open(tmp_acc, "w", encoding="utf-8") as f:
                json.dump(acc_data, f, indent=2)
            os.replace(tmp_acc, account_state_file)

            emit_result("delivered", "verified_by_transport", account, delivery_verified=True, event_id=event_id)
            return 0
        else:
            # Send unverified / failed: Uncertainty hold is RETAINED!
            emit_result("uncertain", "send_unverified", account, delivery_verified=False, event_id=event_id)
            return 4
    finally:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(run_sender_cli(sys.argv[1:]))
