#!/usr/bin/env python3
"""Verify the curated portable manifest or a dedicated installation target."""

import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["format"] == "jleechan-portable-skills-v1", "Unknown manifest format"
    expected = manifest["files"]
    assert expected, "Empty package"
    assert not (root / "skills").is_symlink(), "Linked skills root refused"
    actual = set()
    for path in (root / "skills").rglob("*"):
        assert not path.is_symlink(), f"Symlink in package: {path}"
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    assert actual == set(expected), "Package inventory differs from manifest"
    for relative, digest in expected.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest, relative
    return manifest


def check_target(value):
    target = Path(value)
    assert value and target.is_absolute(), "PORTABLE_HOME must be an absolute dedicated directory"
    assert ".." not in target.parts, "Parent traversal is not a target"
    assert not any(p.is_symlink() for p in [target, *target.parents]), "Linked target/ancestor refused"
    assert target != Path.home() and len(target.parts) > 2, "Broad target refused"
    assert not any(part in {".claude", ".codex", ".agents"} for part in target.parts), "Use a dedicated package root, not an agent home"
    if target.exists():
        assert target.is_dir(), "Target must be a directory"
        if any(target.iterdir()):
            # Backups may preserve local edits, so verify ownership, not old hashes.
            manifest = json.loads((target / "manifest.json").read_text())
            assert manifest["format"] == "jleechan-portable-skills-v1", "Unowned nonempty target refused"
    return str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?")
    parser.add_argument("--target")
    args = parser.parse_args()
    try:
        if args.target is not None:
            print(check_target(args.target))
        else:
            parser.error("root required") if args.root is None else verify(args.root)
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Portable verification failed: {exc}\n")


if __name__ == "__main__":
    main()
