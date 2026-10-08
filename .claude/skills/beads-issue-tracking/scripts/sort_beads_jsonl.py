#!/usr/bin/env python3
"""Check export ID order without rewriting or deduplicating the canonical ledger."""
import argparse
from pathlib import Path
from validate_beads_issues_jsonl import records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        identities = [row['id'] for row in records(args.path)]
        if identities != sorted(identities):
            raise ValueError('export IDs are not sorted')
    except (OSError, ValueError) as error:
        parser.exit(1, f'Beads export order check failed: {error}\n')
