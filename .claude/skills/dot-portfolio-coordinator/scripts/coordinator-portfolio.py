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
                with open(full_path, "rb") as fp:
                    digest = hashlib.sha256(fp.read()).hexdigest()
                manifest[str(rel_path)] = digest
    return manifest


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
    bindings_file = os.environ.get(
        "DOT_PORTFOLIO_BINDINGS_FILE",
        str(SCRIPT_DIR.parent / "references" / "bindings.json")
    )
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
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write source manifest
    skill_root = SCRIPT_DIR.parent
    manifest = compute_dir_manifest(skill_root)
    manifest_path = run_dir / "source_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    hb_path = run_dir / "heartbeat.jsonl"

    interrupted = False

    def handle_signal(sig, frame):
        nonlocal interrupted
        interrupted = True
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "interrupted",
            "signal": sig
        }
        with open(hb_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    duration = int(args.duration)
    interval = int(args.interval)
    start_time = time.time()
    end_time = start_time + duration

    startup_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "observation_started",
        "duration_secs": duration,
        "interval_secs": interval,
        "run_dir": str(run_dir)
    }
    with open(hb_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(startup_entry) + "\n")

    tick = 0
    while time.time() < end_time and not interrupted:
        tick += 1
        now_ts = time.time()
        elapsed = int(now_ts - start_time)
        remaining = int(end_time - now_ts)

        hb_entry = {
            "tick": tick,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_secs": elapsed,
            "remaining_secs": remaining,
            "status": "healthy"
        }
        with open(hb_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(hb_entry) + "\n")

        sleep_time = min(interval, max(0.1, end_time - time.time()))
        if sleep_time > 0:
            time.sleep(sleep_time)

    completion_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "observation_completed",
        "total_ticks": tick
    }
    with open(hb_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(completion_entry) + "\n")


def main() -> None:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--sources",
        default=str(SCRIPT_DIR.parent / "references" / "sources.json"),
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
    p_obs.add_argument("--run-dir", default=f"/tmp/dot-portfolio-observe-{int(time.time())}", help="Private run directory")

    args = parser.parse_args()

    registry = SourceRegistry.from_file(args.sources)

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
