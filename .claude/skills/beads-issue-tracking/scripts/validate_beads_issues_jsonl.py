#!/usr/bin/env python3
"""Read-only validation of the portable exporter's JSON objects and unique IDs."""
import argparse
import json
from pathlib import Path


def records(path):
    rows = []
    seen = set()
    with Path(path).open(encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'line {number}: invalid JSON') from error
            identity = row.get('id') if isinstance(row, dict) else None
            if not isinstance(identity, str) or not identity.strip() or identity in seen:
                raise ValueError(f'line {number}: invalid or duplicate ID')
            seen.add(identity)
            rows.append(row)
    if not rows:
        raise ValueError('empty export cannot establish canonical ledger integrity')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        records(args.path)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Beads export validation failed: {error}\n')
