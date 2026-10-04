#!/usr/bin/env python3
"""Semantic (parsed, per-id) comparison of two beads JSONL files.

Used by scripts/check_beads_jsonl_drift.sh to compare the tracked
`.beads/issues.jsonl` against a scratch `br sync --flush-only`
export of the same SQLite DB.

Deliberately does NOT do a byte/line diff: different `br` versions and the
repo's own `scripts/sort_beads_jsonl.py` use different (but semantically
equivalent) JSON separator styles (`", "` vs `","`), so a raw diff would
false-positive on every run. Instead this parses both files and compares
records by `id`, reporting:
  - duplicate ids within either file (the actual corruption signature from
    the unsafe union-association incidents)
  - ids present in one file but not the other
  - ids whose parsed record content differs between the two files

Exit code 0 = semantically identical (or only a benign field-order
difference such as list ordering that does not affect meaning -- currently
we still flag ALL diffs as an error, since the tracked file should always be
regenerable byte-for-content from the DB; this can be relaxed if false
positives show up in practice).
Exit code 1 = drift detected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_records(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse a JSONL file into {id: record}, tracking duplicate ids."""
    records: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"::error title=beads drift check::"
                    f"{path}:{line_number}: invalid JSON ({exc.msg})"
                )
                sys.exit(1)
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id.strip():
                print(
                    f"::error title=beads drift check::"
                    f"{path}:{line_number}: missing or invalid string id"
                )
                sys.exit(1)
            if record_id in records:
                duplicates.append(record_id)
            records[record_id] = record
    return records, duplicates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", required=True, help="Path to the tracked JSONL")
    parser.add_argument(
        "--canonical", required=True, help="Path to the DB-derived canonical JSONL"
    )
    args = parser.parse_args()

    tracked_path = Path(args.tracked)
    canonical_path = Path(args.canonical)

    tracked, tracked_dupes = load_records(tracked_path)
    canonical, canonical_dupes = load_records(canonical_path)

    errors: list[str] = []

    if tracked_dupes:
        errors.append(
            f"{len(tracked_dupes)} duplicate id(s) in tracked {tracked_path}: "
            f"{', '.join(tracked_dupes[:10])}"
        )
    if canonical_dupes:
        errors.append(
            f"{len(canonical_dupes)} duplicate id(s) in canonical export "
            f"(unexpected -- SQLite primary key should prevent this): "
            f"{', '.join(canonical_dupes[:10])}"
        )

    tracked_ids = set(tracked.keys())
    canonical_ids = set(canonical.keys())

    missing_from_tracked = sorted(canonical_ids - tracked_ids)
    missing_from_canonical = sorted(tracked_ids - canonical_ids)

    if missing_from_tracked:
        errors.append(
            f"{len(missing_from_tracked)} id(s) in DB but missing from tracked file: "
            f"{', '.join(missing_from_tracked[:10])}"
        )
    if missing_from_canonical:
        errors.append(
            f"{len(missing_from_canonical)} id(s) in tracked file but missing from DB: "
            f"{', '.join(missing_from_canonical[:10])}"
        )

    def _normalize_timestamps(value):
        """Normalize ISO-8601 timestamps: '+00:00' and 'Z' are equivalent UTC."""
        if isinstance(value, str) and len(value) >= 10 and value[4] == '-' and value[7] == '-':
            return value.replace("Z", "+00:00") if value.endswith("Z") else value
        if isinstance(value, dict):
            return {k: _normalize_timestamps(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_normalize_timestamps(v) for v in value]
        return value

    # br versions renamed the terminal status from "closed" to "done". Treat
    # the two as equivalent so the drift check does not false-positive when
    # the JSONL was written by a newer br and the canonical export is from
    # an older br (or vice versa).
    def _normalize_status(value):
        if isinstance(value, str) and value in ("closed", "done"):
            return "done"
        if isinstance(value, dict):
            return {k: _normalize_status(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_normalize_status(v) for v in value]
        return value

    # Fields that exist in the SQLite DB but are NOT exported by br's
    # JSONL output. Strip them from the canonical record before comparing,
    # so the drift check measures "is the JSONL a faithful representation
    # of the JSONL-relevant subset of the DB" rather than "is the JSONL
    # byte-identical to the DB row".
    _DB_INTERNAL_FIELDS = {
        "agent_context", "assignee", "close_reason", "closed_at", "closed_by_session",
        "compacted_at", "compacted_at_commit", "content_hash", "defer_until",
        "delete_reason", "deleted_at", "deleted_by", "design", "due_at", "ephemeral",
        "estimated_minutes", "is_template", "original_type", "owner", "pinned",
        "sender", "source_system",
    }

    def _strip_db_internal(record):
        if not isinstance(record, dict):
            return record
        return {k: v for k, v in record.items() if k not in _DB_INTERNAL_FIELDS}

    content_diffs = []
    for record_id in sorted(tracked_ids & canonical_ids):
        t_norm = _strip_db_internal(_normalize_status(_normalize_timestamps(tracked[record_id])))
        c_norm = _strip_db_internal(_normalize_status(_normalize_timestamps(canonical[record_id])))
        if t_norm != c_norm:
            content_diffs.append(record_id)

    if content_diffs:
        sample = ", ".join(content_diffs[:10])
        errors.append(
            f"{len(content_diffs)} id(s) have content that differs from the "
            f"DB-derived canonical export (first 10): {sample}"
        )

    if errors:
        print(
            "::error title=Beads JSONL drift detected::"
            "tracked .beads/issues.jsonl does not match the canonical "
            "DB-derived export. This is the corruption signature that "
            "the unsafe union association produced (PRs #7886, #7946, "
            "#8063). Fix: stop and restore a reviewed canonical DB export "
            "with `br sync --flush-only` only after the doctor/status health "
            "gates pass; do not force-sync or auto-reconcile."
        )
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"OK: {len(tracked)} beads in {tracked_path} match the DB-derived "
        f"canonical export (no drift, no duplicates)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
