#!/usr/bin/env python3
"""Dot Portfolio Coordinator CLI.

Entry point for portfolio collection, review validation, journal persistence,
budget reservations, notification binding resolution, and observation loops.
"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import math
import os
import signal
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add modules directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
MODULES_DIR = SCRIPT_DIR / "modules"
if str(MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.registry import SourceRegistry
from modules.collector import PortfolioCollector
from modules.model_admission import ModelAdmissionChecker
from modules.proposal_validator import ProposalValidator
from modules.beads_journal import BeadsControlJournal
from modules.authority_adapter import AuthorityAdapter
from modules.budget_ledger import BudgetLedger, BudgetError
from modules.publisher import RoadmapPublisher
from modules.sender_protocol import NotificationBindingManager


def get_caller_principal() -> str:
    """Resolves authenticated local OS caller principal.

    MANDATORY: Uses pwd.getpwuid(os.getuid()).pw_name only.
    Zero test switches or environment variable overrides allowed.
    """
    import pwd
    return pwd.getpwuid(os.getuid()).pw_name


def compute_dir_manifest(base_dir: Path) -> Dict[str, str]:
    manifest = {}
    for root, _, files in os.walk(base_dir):
        for f in sorted(files):
            if f.endswith((".py", ".sh", ".json", ".md")):
                full_path = Path(root) / f
                rel_path = full_path.relative_to(base_dir)
                try:
                    with open(full_path, "rb") as fp:
                        digest = hashlib.sha256(fp.read()).hexdigest()
                    manifest[str(rel_path)] = digest
                except Exception:
                    pass
    return manifest


def atomic_write_json(file_path: Path, data: Any, mode: int = 0o600) -> None:
    """Writes JSON data atomically with restricted permissions."""
    from modules.sender import _atomic_write
    _atomic_write(str(file_path), data, str(file_path.parent))


def private_run_directory(value: Optional[str]) -> Path:
    root = Path(value) if value else Path(tempfile.mkdtemp(prefix="dot-portfolio-", dir="/tmp"))
    if not root.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("run_directory_must_be_under_tmp")
    if root.is_symlink():
        raise ValueError("run_directory_symlink")
    root.mkdir(mode=0o700, parents=False, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("run_directory_must_be_owned_and_private")
    return root


def load_run_state(root: Path, binding: str, duration: int, started: float) -> Dict[str, Any]:
    from modules.sender import _read_json_file
    state, reason = _read_json_file(str(root / "run_state.json"), "state")
    if state is None:
        if reason != "state_missing":
            raise ValueError("run_state_corrupt_hold")
        state = {"binding": binding, "started_at_epoch": started,
                 "duration_secs": duration, "slots": {}, "dialogue": {}}
        atomic_write_json(root / "run_state.json", state)
    if (state.get("binding") != binding or state.get("duration_secs") != duration or
            not isinstance(state.get("slots"), dict) or not isinstance(state.get("dialogue"), dict) or
            type(state.get("started_at_epoch")) not in (int, float) or
            not math.isfinite(state["started_at_epoch"])):
        raise ValueError("run_state_binding_or_schema_mismatch")
    return state


def pilot_slots(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    slots = []
    for index, offset in enumerate(range(0, config["duration_secs"], 1200)):
        identity = f"{config['run_id']}:{index}"
        slots.append({"index": index, "account_index": index % 3,
                      "due_epoch": config["activated_at_epoch"] + offset,
                      "event_id": hashlib.sha256(identity.encode()).hexdigest()})
    return slots


def call_sender(argv: List[str], event_id: str, message: str) -> Dict[str, Any]:
    from modules.sender import run_sender_cli
    changes = {"COORDINATOR_CHANGE_ID": event_id, "COORDINATOR_CHANGE_SUMMARY": message,
               "DOT_NO_REMOTE": "1"}
    previous = {key: os.environ.get(key) for key in changes}
    output = io.StringIO()
    try:
        os.environ.update(changes)
        with contextlib.redirect_stdout(output):
            rc = run_sender_cli(argv)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    records = [json.loads(line.removeprefix("COORDINATOR_RESULT "))
               for line in output.getvalue().splitlines() if line.startswith("COORDINATOR_RESULT ")]
    if len(records) != 1:
        return {"outcome": "uncertain", "reason": "invalid_sender_receipt", "delivery_verified": False}
    result = records[0]
    return {"outcome": result.get("outcome"), "reason": result.get("reason"),
            "delivery_verified": rc == 0 and result.get("outcome") == "delivered"
            and result.get("delivery_verified") is True}


def load_pilot_config(path: str) -> Dict[str, Any]:
    from modules.sender import _read_json_file, ACCOUNT_RE, validate_operator_grant
    config, reason = _read_json_file(path, "pilot")
    if config is None:
        raise ValueError(reason)
    if (not isinstance(config.get("run_id"), str) or not config["run_id"] or
            config.get("task_id") != "dot-coordinator-separated-20261007" or
            not isinstance(config.get("authority"), str) or not config["authority"] or
            not isinstance(config.get("state_dir"), str) or not config["state_dir"] or
            type(config.get("duration_secs")) is not int or
            not 1 <= config["duration_secs"] <= 43200 or
            type(config.get("activated_at_epoch")) not in (int, float) or
            not math.isfinite(config["activated_at_epoch"])):
        raise ValueError("invalid_pilot_config")
    accounts = config.get("accounts")
    if not isinstance(accounts, list) or len(accounts) != 3:
        raise ValueError("pilot_requires_three_accounts")
    seen = set()
    for account in accounts:
        if (not isinstance(account, dict) or not isinstance(account.get("account"), str) or
                not ACCOUNT_RE.fullmatch(account["account"]) or account["account"] in seen):
            raise ValueError("invalid_or_duplicate_pilot_account")
        seen.add(account["account"])
        valid, _, grant = validate_operator_grant(account.get("grant_file"), account.get("grant_sha256"), account["account"])
        if not valid or grant["activated_at_epoch"] != config["activated_at_epoch"] or grant["expiry_epoch"] < config["activated_at_epoch"] + config["duration_secs"]:
            raise ValueError("pilot_grant_invalid_or_window_mismatch")
    return config


def run_pilot_slot(config: Dict[str, Any], slot: Dict[str, Any], state: Dict[str, Any],
                   snapshot: Dict[str, Any], root: Path, driver: str,
                   transport: str, deadline: float) -> Dict[str, Any]:
    from modules.driver_adapter import DriverAdapter
    from modules.process_utils import run_bounded_command
    account_index = slot["account_index"]
    account = config["accounts"][account_index]
    stage = state["dialogue"].get(str(account_index), "inventory")
    remaining = deadline - time.monotonic()
    if remaining < 180:
        return {"outcome": "deadline_hold", "delivery_verified": False}
    env = os.environ.copy()
    env["DOT_ROTATE_ON_LIMIT"] = "0"
    env["DOT_NO_REMOTE"] = "1"
    try:
        rc, reply, _ = run_bounded_command(
            [transport, "--account", account["account"], "read", "12000"],
            env=env, timeout_secs=min(180, int(remaining)))
    except Exception:
        return {"outcome": "read_unavailable", "delivery_verified": False}
    if rc != 0:
        return {"outcome": "read_unavailable", "delivery_verified": False}
    packet = {"task_id": config["task_id"], "event_id": slot["event_id"],
              "authority": {"instruction": config["authority"], "source": "local_operator_pilot"}, "snapshot": snapshot,
              "previous_dot_reply": reply, "dialogue_stage": stage}
    workspace = private_run_directory(str(root / ("driver-" + slot["event_id"])))
    remaining = deadline - time.monotonic()
    if remaining < 180:
        return {"outcome": "deadline_hold", "delivery_verified": False}
    decision = DriverAdapter(driver=driver).decide(packet, workspace, timeout_secs=min(600, int(remaining)))
    if decision.get("status") != "ok":
        return {"outcome": "driver_failed", "reason": decision.get("reason", "invalid_result"), "delivery_verified": False}
    guidance = (SCRIPT_DIR.parent / "references" / "dot-self-unblock.md").read_text()
    message = guidance + "\n\n" + decision["decision"]["message"]
    sender_root = private_run_directory(str(root / f"sender-{account_index}"))
    argv = ["--account", account["account"], "--state-dir", str(sender_root),
            "--grant-file", account["grant_file"], "--grant-sha256", account["grant_sha256"],
            "--transport-script", transport, "--full-rollup"]
    if deadline - time.monotonic() < 600:
        return {"outcome": "deadline_hold", "delivery_verified": False}
    result = call_sender(argv, slot["event_id"], message)
    if result["delivery_verified"]:
        state["dialogue"][str(account_index)] = "challenge" if stage == "inventory" else "inventory"
    return result


def cmd_reserve(args: argparse.Namespace, registry: SourceRegistry) -> None:
    caller = get_caller_principal()
    # Remote/model spend reserve remains capability_blocked pending genuine original grant+usage integration
    res = {
        "status": "rejected",
        "reason": "capability_blocked",
        "caller_principal": caller,
        "details": "Remote/model spend reserve capability_blocked pending genuine original grant+usage integration."
    }
    print(json.dumps(res, indent=2))
    sys.exit(2)


def cmd_settle(args: argparse.Namespace, registry: SourceRegistry) -> None:
    caller = get_caller_principal()
    # Remote/model spend settle remains capability_blocked pending genuine original grant+usage integration
    res = {
        "status": "rejected",
        "reason": "capability_blocked",
        "caller_principal": caller,
        "details": "Remote/model spend settle capability_blocked pending genuine original grant+usage integration."
    }
    print(json.dumps(res, indent=2))
    sys.exit(2)


def cmd_status(args: argparse.Namespace, registry: SourceRegistry) -> None:
    caller = get_caller_principal()
    res = {
        "status": "unknown_reservation",
        "reason": "capability_blocked",
        "reservation_id": args.reservation_id,
        "caller_principal": caller
    }
    print(json.dumps(res, indent=2))


def cmd_resolve_notification(args: argparse.Namespace, registry: SourceRegistry) -> None:
    bindings_file = getattr(args, "bindings_file", None) or str(SCRIPT_DIR.parent / "references" / "bindings.json")
    mgr = NotificationBindingManager(registry, bindings_file)
    resolved = mgr.resolve_notification(args.ref)
    if resolved:
        print(json.dumps(resolved, indent=2))
    else:
        print(json.dumps({"error": f"Binding reference {args.ref} not found"}), file=sys.stderr)
        sys.exit(1)


def cmd_collect(args: argparse.Namespace, registry: SourceRegistry) -> None:
    collector = PortfolioCollector(registry)
    result = collector.collect_all()
    out = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)


def process_due_slots(config, state, root, snapshot, driver, transport, deadline, now):
    for slot in pilot_slots(config):
        key = str(slot["index"])
        if key in state["slots"] or now < slot["due_epoch"]:
            continue
        if now >= slot["due_epoch"] + 1200:
            state["slots"][key] = {"outcome": "missed_slot", "delivery_verified": False}
            atomic_write_json(root / "run_state.json", state)
            continue
        state["slots"][key] = {"outcome": "in_progress_hold", "delivery_verified": False}
        atomic_write_json(root / "run_state.json", state)
        try:
            result = run_pilot_slot(config, slot, state, snapshot, root, driver, transport, deadline)
        except Exception:
            result = {"outcome": "slot_failed_hold", "delivery_verified": False}
        state["slots"][key] = result
        atomic_write_json(root / "run_state.json", state)


def cmd_observe(args: argparse.Namespace, registry: SourceRegistry) -> None:
    """Run one finite, restart-bound coordinator with independent heartbeats."""
    from modules.sender import _read_json_file
    if not 1 <= args.duration <= 43200 or not 1 <= args.interval <= 3600:
        raise ValueError("invalid_observation_duration_or_interval")
    config = load_pilot_config(args.pilot_config) if args.send_messages and args.pilot_config else None
    if args.send_messages and config is None:
        raise ValueError("active_mode_requires_pinned_pilot_config")
    if config is not None and not registry.sources:
        raise ValueError("active_mode_requires_registered_sources")
    if config and args.run_dir and Path(args.run_dir).resolve() != Path(config["state_dir"]).resolve():
        raise ValueError("pilot_state_directory_mismatch")
    root = private_run_directory(config["state_dir"] if config else args.run_dir)
    lock_fd = os.open(root / "coordinator.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    info = os.fstat(lock_fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(lock_fd)
        raise ValueError("invalid_coordinator_lock")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(lock_fd)
        raise ValueError("coordinator_already_running")
    stopped = threading.Event()
    heartbeat_failed = threading.Event()
    heartbeat_thread = None
    old_handlers = {}
    state = None
    stop_reason = "completed"
    totals = {"completed_cycles": 0, "partial_cycles": 0, "fault_cycles": 0}
    try:
        manifest = compute_dir_manifest(SCRIPT_DIR.parent)
        registry_hash = hashlib.sha256(Path(args.sources).read_bytes()).hexdigest()
        pilot_hash = hashlib.sha256(Path(args.pilot_config).read_bytes()).hexdigest() if config else None
        binding = hashlib.sha256(json.dumps({"manifest": manifest, "registry": registry_hash,
                                             "pilot": pilot_hash, "driver": args.driver}, sort_keys=True).encode()).hexdigest()
        duration = config["duration_secs"] if config else args.duration
        started = config["activated_at_epoch"] if config else time.time()
        state = load_run_state(root, binding, duration, started)
        if time.time() < state.get("last_observed_epoch", state["started_at_epoch"]):
            raise ValueError("clock_rollback_hold")
        deadline_epoch = state["started_at_epoch"] + duration
        deadline = time.monotonic() + max(0, deadline_epoch - time.time())
        atomic_write_json(root / "source_manifest.json", manifest)
        atomic_write_json(root / "registry_hash.json", {"sha256": registry_hash})
        prior, reason = _read_json_file(str(root / "latest_snapshot.json"), "snapshot")
        if prior is None and reason != "snapshot_missing":
            raise ValueError("snapshot_corrupt_hold")
        prior_snapshots = (prior or {}).get("snapshots", {})

        def heartbeat():
            try:
                while not stopped.is_set():
                    entry = {"event": "heartbeat", "timestamp_epoch": time.time(),
                             "elapsed_secs": max(0, time.time() - state["started_at_epoch"]),
                             "remaining_secs": max(0, deadline - time.monotonic())}
                    fd = os.open(root / "heartbeat.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "w") as stream:
                        info = os.fstat(stream.fileno())
                        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                            raise ValueError("invalid_heartbeat_file")
                        stream.write(json.dumps(entry) + "\n")
                    stopped.wait(min(60, args.interval))
            except Exception:
                heartbeat_failed.set()

        def stop_signal(sig, frame):
            raise KeyboardInterrupt

        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, stop_signal)
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
        transport = args.transport_script or str(SCRIPT_DIR.parent.parent / "dot/scripts/dot.sh")
        while time.monotonic() < deadline:
            if heartbeat_failed.is_set():
                stop_reason = "heartbeat_failed"
                break
            if (compute_dir_manifest(SCRIPT_DIR.parent) != manifest or
                    hashlib.sha256(Path(args.sources).read_bytes()).hexdigest() != registry_hash or
                    (config and hashlib.sha256(Path(args.pilot_config).read_bytes()).hexdigest() != pilot_hash)):
                stop_reason = "manifest_drift_detected"
                break
            state["last_observed_epoch"] = time.time()
            atomic_write_json(root / "run_state.json", state)
            try:
                collector = PortfolioCollector(registry)
                collected = collector.collect_all(prior_snapshots=prior_snapshots,
                                                  deadline_mono=min(deadline, time.monotonic() + 120))
                prior_snapshots = collected.get("snapshots", {})
                atomic_write_json(root / "latest_snapshot.json", collected)
                counter = "partial_cycles" if collected.get("unavailable_count") or collected.get("stale_count") else "completed_cycles"
                totals[counter] += 1
            except Exception:
                totals["fault_cycles"] += 1
                collected = {"snapshots": prior_snapshots, "coverage": "collection_failed"}
            if config:
                model_snapshot = {"coverage": {key: collected.get(key) for key in
                                  ("registered_count", "fresh_count", "stale_count", "unavailable_count")}, "sources": {}}
                for sid, source in collected.get("snapshots", {}).items():
                    model_snapshot["sources"][sid] = {"status": source.get("status"), "version": source.get("version"),
                        "items": [registry.filter_by_audience(sid, item, "model") for item in source.get("items", [])]}
                process_due_slots(config, state, root, model_snapshot, args.driver, transport, deadline, time.time())
            stopped.wait(min(args.interval, max(0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    except Exception:
        stop_reason = "failed"
        raise
    finally:
        stopped.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        if state is not None:
            outcomes = list(state["slots"].values())
            receipt = {"event": "observation_summary", "duration_secs": state["duration_secs"],
                       "elapsed_secs": max(0, time.time() - state["started_at_epoch"]),
                       "sent_messages": sum(item.get("delivery_verified") is True for item in outcomes),
                       "slots_accounted": len(outcomes), "expected_slots": len(pilot_slots(config)) if config else 0,
                       "stop_reason": stop_reason, "mode": "active" if config else "observe-only", **totals}
            atomic_write_json(root / "final_receipt.json", receipt)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def main() -> None:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--sources",
        default=argparse.SUPPRESS,
        help="Path to reviewed sources registry JSON"
    )

    parser = argparse.ArgumentParser(
        description="Dot Portfolio Coordinator - All-work tracking, review, and publication controller.",
        parents=[common_parser]
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # reserve
    p_res = subparsers.add_parser("reserve", parents=[common_parser], help="Reserve budget for execution attempt")
    p_res.add_argument("--request", required=True, help="JSON request payload")

    # settle
    p_set = subparsers.add_parser("settle", parents=[common_parser], help="Settle actual execution spend")
    p_set.add_argument("--request", required=True, help="JSON request payload")

    # status
    p_stat = subparsers.add_parser("status", parents=[common_parser], help="Get reservation status")
    p_stat.add_argument("--reservation-id", required=True, help="Reservation ID")

    # resolve-notification
    p_notif = subparsers.add_parser("resolve-notification", parents=[common_parser], help="Resolve notification authorization binding")
    p_notif.add_argument("--ref", required=True, help="Authorization ref (control/action/attempt)")
    p_notif.add_argument("--bindings-file", help="Explicit local binding file; lookup does not establish authority")

    # collect
    p_col = subparsers.add_parser("collect", parents=[common_parser], help="Collect snapshot across registered sources")
    p_col.add_argument("--output", help="Optional output JSON path")

    # observe
    p_obs = subparsers.add_parser("observe", parents=[common_parser], help="Run finite observation loop")
    p_obs.add_argument("--duration", type=int, default=43200, help="Duration in seconds (default: 43200 / 12h)")
    p_obs.add_argument("--interval", type=int, default=300, help="Heartbeat interval in seconds (default: 300)")
    p_obs.add_argument("--notification-interval", type=int, default=7200, help="Notification interval in seconds")
    p_obs.add_argument("--run-dir", help="Private run directory (created with mode 0700 if omitted)")
    p_obs.add_argument("--send-messages", action="store_true", help="Enable task-scoped message sending")
    p_obs.add_argument("--grant-file", help="Root operator grant file")
    p_obs.add_argument("--grant-sha256", help="Pinned SHA256 of grant file")
    p_obs.add_argument("--account", default="default", help="Legacy account option; active mode uses pilot config")
    p_obs.add_argument("--pilot-config", help="Private operator configuration binding three grants and the original run window")
    p_obs.add_argument("--driver", choices=("agy", "claude", "codex"), default="agy")
    p_obs.add_argument("--transport-script", help="Explicit trusted dot transport path")

    args = parser.parse_args()

    sources_path = getattr(args, "sources", str(SCRIPT_DIR.parent / "references" / "sources.json"))
    args.sources = sources_path
    registry = SourceRegistry.from_file(sources_path)

    if args.command == "reserve":
        cmd_reserve(args, registry)
    elif args.command == "settle":
        cmd_settle(args, registry)
    elif args.command == "status":
        cmd_status(args, registry)
    elif args.command == "resolve-notification":
        cmd_resolve_notification(args, registry)
    elif args.command == "collect":
        cmd_collect(args, registry)
    elif args.command == "observe":
        cmd_observe(args, registry)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        sys.exit(2)
