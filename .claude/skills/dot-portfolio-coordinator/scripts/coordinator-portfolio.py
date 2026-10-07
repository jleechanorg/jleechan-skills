#!/usr/bin/env python3
"""Dot Portfolio Coordinator CLI.

Entry point for portfolio collection, review validation, journal persistence,
budget reservations, notification binding resolution, and observation loops.
"""
import argparse
import hashlib
import json
import os
import signal
import sys
import tempfile
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
    tmp_path = file_path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(str(tmp_path), mode)
    os.replace(str(tmp_path), str(file_path))


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


def cmd_observe(args: argparse.Namespace, registry: SourceRegistry) -> None:
    """Runs explicit finite observation caller with private /tmp state, heartbeats, and source hashes."""
    # 1. Private directory creation and validation
    if args.run_dir:
        run_dir = Path(args.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(run_dir), 0o700)
    else:
        run_dir = Path(tempfile.mkdtemp(prefix="dot-portfolio-observe-", dir="/tmp"))
        os.chmod(str(run_dir), 0o700)

    # Invariant: Directory owner must be current UID and mode 0700
    dir_st = os.stat(str(run_dir))
    if dir_st.st_uid != os.getuid():
        print(json.dumps({"error": f"Run dir owner UID {dir_st.st_uid} does not match current UID {os.getuid()}"}), file=sys.stderr)
        sys.exit(1)

    if getattr(args, "send_messages", False):
        if not getattr(args, "grant_file", None) or not getattr(args, "grant_sha256", None):
            print(json.dumps({"error": "--send-messages requires --grant-file and --grant-sha256"}), file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.grant_file):
            print(json.dumps({"error": f"Grant file {args.grant_file} does not exist"}), file=sys.stderr)
            sys.exit(1)

    # 2. Write initial source manifest and registry hash
    skill_root = SCRIPT_DIR.parent
    manifest_start = compute_dir_manifest(skill_root)
    atomic_write_json(run_dir / "source_manifest.json", manifest_start, mode=0o600)

    with open(args.sources, "rb") as fp:
        reg_hash_start = hashlib.sha256(fp.read()).hexdigest()

    reg_hash_file = run_dir / "registry_hash.txt"
    with open(reg_hash_file, "w", encoding="utf-8") as fp:
        fp.write(reg_hash_start)
    os.chmod(str(reg_hash_file), 0o600)

    hb_path = run_dir / "heartbeat.jsonl"
    interrupted = False
    stop_reason = None

    def handle_signal(sig, frame):
        nonlocal interrupted, stop_reason
        interrupted = True
        stop_reason = f"signal_{sig}"
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "interrupted",
            "signal": sig
        }
        with open(hb_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        try:
            os.chmod(str(hb_path), 0o600)
        except Exception:
            pass

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    duration = max(1, int(args.duration))
    interval = max(1, int(args.interval))
    notification_interval = max(1, int(getattr(args, "notification_interval", 7200)))
    start_mono = time.monotonic()
    deadline_mono = start_mono + duration

    startup_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "observation_started",
        "duration_secs": duration,
        "interval_secs": interval,
        "mode": "active" if getattr(args, "send_messages", False) else "observe-only",
        "run_dir": str(run_dir)
    }
    with open(hb_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(startup_entry) + "\n")
    os.chmod(str(hb_path), 0o600)

    prior_snapshots: Dict[str, Any] = {}
    completed_cycles = 0
    partial_cycles = 0
    fault_cycles = 0
    sent_messages = 0
    last_notification_time = 0.0
    tick = 0

    while time.monotonic() < deadline_mono and not interrupted:
        tick += 1
        now_mono = time.monotonic()
        elapsed = int(now_mono - start_mono)
        remaining = max(0, int(deadline_mono - now_mono))

        # 3. Check for manifest or registry drift
        curr_manifest = compute_dir_manifest(skill_root)
        try:
            with open(args.sources, "rb") as fp:
                curr_reg_hash = hashlib.sha256(fp.read()).hexdigest()
        except Exception:
            curr_reg_hash = ""

        if curr_manifest != manifest_start or curr_reg_hash != reg_hash_start:
            stop_reason = "manifest_drift_detected"
            interrupted = True
            break

        # 4. Real collection each cycle
        collector = PortfolioCollector(registry)
        cycle_status = "healthy"
        try:
            coll_res = collector.collect_all(prior_snapshots=prior_snapshots)
            prior_snapshots = coll_res.get("snapshots", {})
            atomic_write_json(run_dir / "latest_snapshot.json", coll_res, mode=0o600)

            if coll_res.get("unavailable_count", 0) > 0 or coll_res.get("stale_count", 0) > 0:
                cycle_status = "partial"
                partial_cycles += 1
            else:
                cycle_status = "fresh"
                completed_cycles += 1
        except Exception as e:
            cycle_status = "fault"
            fault_cycles += 1
            coll_res = {"error": str(e)}

        # 5. Active messaging path if explicitly requested
        if getattr(args, "send_messages", False):
            if (now_mono - last_notification_time) >= notification_interval:
                prompt_path = SCRIPT_DIR.parent / "references" / "dot-self-unblock.md"
                prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Continue authorized work."
                summary_msg = f"{prompt_text[:1500]}\nTracking: {coll_res.get('fresh_count', 0)} fresh, {coll_res.get('unavailable_count', 0)} unavailable."
                ev_id = f"ev_obs_{int(time.time())}_{tick}"

                from modules.sender import run_sender_cli
                sender_argv = [
                    "--account", getattr(args, "account", "default"),
                    "--state-dir", str(run_dir / "sender_state"),
                    "--grant-file", getattr(args, "grant_file", "") or "",
                    "--grant-sha256", getattr(args, "grant_sha256", "") or ""
                ]
                os.environ["COORDINATOR_CHANGE_ID"] = ev_id
                os.environ["COORDINATOR_CHANGE_SUMMARY"] = summary_msg
                try:
                    s_rc = run_sender_cli(sender_argv)
                    if s_rc == 0:
                        sent_messages += 1
                        last_notification_time = now_mono
                except Exception:
                    pass

        # 6. Heartbeat record
        hb_entry = {
            "tick": tick,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_secs": elapsed,
            "remaining_secs": remaining,
            "status": cycle_status
        }
        with open(hb_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(hb_entry) + "\n")
        os.chmod(str(hb_path), 0o600)

        sleep_time = min(interval, max(0.1, deadline_mono - time.monotonic()))
        if sleep_time > 0 and time.monotonic() < deadline_mono and not interrupted:
            time.sleep(sleep_time)

    # 7. Final receipt
    if not stop_reason:
        stop_reason = "interrupted" if interrupted else "completed"

    elapsed_total = int(time.monotonic() - start_mono)
    receipt_data = {
        "event": "observation_summary",
        "duration_secs": duration,
        "elapsed_secs": elapsed_total,
        "completed_cycles": completed_cycles,
        "partial_cycles": partial_cycles,
        "fault_cycles": fault_cycles,
        "sent_messages": sent_messages,
        "stop_reason": stop_reason,
        "mode": "active" if getattr(args, "send_messages", False) else "observe-only"
    }
    atomic_write_json(run_dir / "final_receipt.json", receipt_data, mode=0o600)


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
    p_obs.add_argument("--account", default="default", help="Account identifier")

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
    main()
