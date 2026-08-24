#!/usr/bin/env python3
"""Classify entries under a skills root as proper, orphan, or duplicate.

proper    - directory holding SKILL.md with name/description frontmatter
orphan    - loose <name>.md with no sibling directory of the same name
duplicate - loose <name>.md shadowed by a sibling directory of the same name
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / ".claude" / "skills"
DELIMITER = "---"
REQUIRED_KEYS = ("name", "description")


def parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != DELIMITER:
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == DELIMITER:
            return fields
        key, separator, value = line.partition(":")
        if separator and not key.startswith((" ", "\t")):
            fields[key.strip()] = value.strip()
    return {}


def is_proper(directory: Path) -> bool:
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return False
    fields = parse_frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
    return all(fields.get(key) for key in REQUIRED_KEYS)


def scan(root) -> dict:
    root = Path(root)
    directories = set()
    loose = set()
    for entry in root.iterdir():
        if entry.is_dir():
            directories.add(entry.name)
        elif entry.suffix == ".md":
            loose.add(entry.stem)
    return {
        "proper": sorted(name for name in directories if is_proper(root / name)),
        "orphan": sorted(loose - directories),
        "duplicate": sorted(loose & directories),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify skill entries as proper, orphan, or duplicate."
    )
    parser.add_argument("root", nargs="?", default=DEFAULT_ROOT, type=Path)
    parser.add_argument("--check-orphans", action="store_true")
    parser.add_argument("--check-duplicates", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    result = scan(args.root)

    if args.json:
        report = {"root": str(args.root), "counts": {k: len(v) for k, v in result.items()}}
        report.update(result)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif not (args.check_orphans or args.check_duplicates):
        print(f"root: {args.root}")
        for bucket in ("proper", "orphan", "duplicate"):
            print(f"{bucket}: {len(result[bucket])}")

    if args.check_orphans and result["orphan"]:
        print(f"{len(result['orphan'])} orphan skill file(s)", file=sys.stderr)
        return 1
    if args.check_duplicates and result["duplicate"]:
        print(f"{len(result['duplicate'])} duplicate skill file(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
