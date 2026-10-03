#!/usr/bin/env python3
"""Verify the curated portable manifest or a dedicated installation target."""

import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["format"] != "jleechan-portable-skills-v1":
        raise ValueError("Unknown manifest format")
    expected = manifest["files"]
    if not expected:
        raise ValueError("Empty package")
    if (root / "skills").is_symlink():
        raise ValueError("Linked skills root refused")
    skills = manifest["skills"]
    directories = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
    if (not isinstance(skills, list) or not all(isinstance(name, str) for name in skills)
            or len(skills) != len(set(skills)) or set(skills) != directories):
        raise ValueError("Skill list differs from package directories")
    for name in skills:
        if not (root / "skills" / name / "SKILL.md").is_file():
            raise ValueError(f"Missing SKILL.md: {name}")
    actual = set()
    for path in (root / "skills").rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink in package: {path}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(expected):
        raise ValueError("Package inventory differs from manifest")
    for relative, digest in expected.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(relative)
    return manifest


def check_target(value, canonical_home=None):
    target = Path(value)
    if not value or not target.is_absolute():
        raise ValueError("PORTABLE_HOME must be an absolute dedicated directory")
    if ".." in target.parts:
        raise ValueError("Parent traversal is not a target")
    if any(p.is_symlink() for p in [target, *target.parents]):
        raise ValueError("Linked target/ancestor refused")
    if target == Path.home() or len(target.parts) <= 2:
        raise ValueError("Broad target refused")
    if any(part in {".claude", ".codex", ".agents"} for part in target.parts):
        raise ValueError("Use a dedicated package root, not an agent home")
    if canonical_home is not None and target.resolve() == Path(canonical_home).resolve():
        raise ValueError("Portable target equals configured CLAUDE_HOME")
    if target.exists():
        if not target.is_dir():
            raise ValueError("Target must be a directory")
        if any(target.iterdir()):
            # Backups may preserve local edits, so verify ownership, not old hashes.
            manifest = json.loads((target / "manifest.json").read_text())
            if manifest["format"] != "jleechan-portable-skills-v1":
                raise ValueError("Unowned nonempty target refused")
    return str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?")
    parser.add_argument("--target")
    parser.add_argument("--canonical-home")
    args = parser.parse_args()
    try:
        if args.target is not None:
            print(check_target(args.target, args.canonical_home))
        else:
            parser.error("root required") if args.root is None else verify(args.root)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Portable verification failed: {exc}\n")


if __name__ == "__main__":
    main()
