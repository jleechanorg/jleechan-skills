#!/usr/bin/env python3
"""Deterministic admission check for the shared 2 complex + 2 short budget.

This is a read-only predicate, not a queue writer: it never mutates state, never
dispatches work and never replaces the designated-writer queue guard. Exit codes:

    0  BELOW_CAP   confirmed count below cap; not dispatch authority
    2  ERROR   bad input (unknown class, malformed state, duplicate id)
    3  REJECT  the requested class is already at its cap

Only entries with non-empty owner, current action and receipt strings are
counted. The caller must independently validate freshness, ownership and UNKNOWN
occupancy; this predicate cannot establish global admission. Queued, assigned, "busy",
messaged, awaiting-review or completed entries never consume capacity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CAPS = {"complex": 2, "short": 2}
EVIDENCE_FIELDS = ("owner", "action", "receipt")
NON_EXECUTING_STATES = frozenset(
    {"queued", "assigned", "busy", "messaged", "awaiting-review", "completed"}
)


class InputError(ValueError):
    pass


def load_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read state: {error}") from error
    if not isinstance(state, dict) or not isinstance(state.get("active"), list):
        raise InputError("state must be an object with an 'active' list")
    return state


def is_executing(item: object) -> bool:
    """Check row state and evidence shape; freshness and activity remain caller checks."""
    if not isinstance(item, dict):
        raise InputError("each active entry must be an object")
    if not isinstance(item.get("class"), str) or item.get("class") not in CAPS:
        raise InputError(f"unknown class: {item.get('class')!r}")
    state = item.get("state")
    if state is not None and not isinstance(state, str):
        raise InputError("state must be a string")
    if state == "UNKNOWN":
        raise InputError("UNKNOWN occupancy must be reconciled before this check")
    if state in NON_EXECUTING_STATES:
        return False
    if item.get("parked") is True:
        return False
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        return False
    return all(
        isinstance(evidence.get(field), str) and evidence[field].strip()
        for field in EVIDENCE_FIELDS
    )


def counts(state: dict) -> dict:
    tally = {name: 0 for name in CAPS}
    seen = set()
    for item in state["active"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise InputError("each active entry needs a non-empty string id")
        if item["id"] in seen:
            raise InputError(f"duplicate active id: {item['id']}")
        seen.add(item["id"])
        if is_executing(item):
            tally[item["class"]] += 1
    return tally


def decide(state: dict, wanted: str, candidate_id: str | None = None) -> tuple[bool, dict, int]:
    if wanted not in CAPS:
        raise InputError(f"unknown class: {wanted!r}")
    tally = counts(state)
    if candidate_id is not None and any(item["id"] == candidate_id for item in state["active"]):
        raise InputError(f"candidate id already present in active state: {candidate_id}")
    return tally[wanted] < CAPS[wanted], tally, CAPS[wanted]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", required=True, help="JSON state file with an 'active' list")
    parser.add_argument("--class", dest="wanted", choices=sorted(CAPS), help="class to admit")
    parser.add_argument("--id", help="id of the candidate being admitted (for the receipt line)")
    args = parser.parse_args(argv)
    try:
        state = load_state(Path(args.state).expanduser())
        if not args.wanted:
            print("COUNTS " + json.dumps(counts(state), sort_keys=True))
            return 0
        admit, tally, cap = decide(state, args.wanted, args.id)
        label = args.wanted if not args.id else f"{args.wanted}:{args.id}"
        verdict = "BELOW_CAP" if admit else "REJECT"
        print(f"{verdict} {label} active={tally[args.wanted]} cap={cap}")
        return 0 if admit else 3
    except InputError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
