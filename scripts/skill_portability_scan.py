#!/usr/bin/env python3
"""Classify entries under a skills root as proper, improper, orphan, or duplicate.

proper    - directory holding SKILL.md with name/description frontmatter
improper  - directory holding SKILL.md with invalid/missing name or description
            frontmatter, mapped to a reason string (never silently dropped)
orphan    - loose <name>.md with no sibling directory of the same name
duplicate - loose <name>.md shadowed by a sibling directory of the same name
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / ".claude" / "skills"
DELIMITER = "---"
REQUIRED_KEYS = ("name", "description")


PLACEHOLDER_USERS = {"user", "username", "you", "me", "testuser", "example", "..."}
PERSONAL_PATTERNS = (
    ("home path", re.compile(r"(?:/home|/Users)/([A-Za-z0-9_.-]+)")),
    ("email", re.compile(r"[A-Za-z0-9._+-]+@(?!example\.|users\.noreply\.github\.com)(?:gmail|googlemail|outlook|hotmail|yahoo|icloud|proton(?:mail)?)\.[a-z.]+")),
    ("slack id", re.compile(r"\b[CUAW]0[A-Z0-9]{8,}\b")),
    ("personal hostname", re.compile(r"\b[a-z]+s-(?:macbook|mbp|imac|mac-?mini)(?:-[a-z0-9]+)*\b", re.I)),
    ("private lan ip", re.compile(r"\b192\.168\.\d+\.\d+\b")),
    ("tailnet ip", re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+\b")),
    ("named ssh key", re.compile(r"\.ssh/id_(?!(?:rsa|ed25519|ecdsa|dsa)\b)[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*")),
    # A hardcoded phone in a skill is somebody's real contact detail. On 2026-11-09/10 a
    # contact's number shipped as a script default and 46 self-test messages reached it;
    # this scanner did not look at phone numbers at all.
    #
    # NANP reserves 555-0100..555-0199 for fiction, so a document that shows a phone must
    # use that block. Excluding it keeps the guard on real digits and stops a doc example
    # from failing CI. The lookbehind rejects arithmetic/path context (the Chrome-epoch
    # `+11644473600` in dot/tests is a constant, not a phone); the lookahead rejects
    # longer digit runs.
    ("phone number", re.compile(r"(?<![\w)\]/*+=.])\+1(?!555)[2-9]\d{9}(?!\d)")),
    # The `\(?` inside the lookahead matters: it runs BEFORE the optional open paren is
    # consumed, so a bare `(?!555)` lets a parenthesized "(555) ..." area code slip
    # through and only spares the bare "555 ..." form.
    ("phone number", re.compile(r"(?<![\d.])\(?(?!\(?555)\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")),
)


def find_personal_identifiers(text: str) -> list:
    """Return (kind, match) pairs for personal paths, emails, Slack IDs and LAN IPs."""
    hits = []
    for kind, pattern in PERSONAL_PATTERNS:
        for m in pattern.finditer(text):
            if kind == "home path" and m.group(1) in PLACEHOLDER_USERS:
                continue
            hits.append((kind, m.group(0)))
    return hits


def changed_files(root: Path, base: str = "origin/main") -> list:
    """Files under root changed on HEAD relative to base; raises RuntimeError if git/base is unavailable."""
    root = Path(root).resolve()
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", str(root)],
            capture_output=True, text=True, check=True,
        ).stdout
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot list files changed against {base}: {exc}") from exc
    return [Path(top) / line for line in out.splitlines() if line]


def scan_personal(paths) -> dict:
    found = {}
    for path in paths:
        try:
            hits = find_personal_identifiers(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if hits:
            found[str(path)] = hits
    return found


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


def frontmatter_issue(fields: dict) -> str:
    """Return a reason string if required frontmatter keys are missing/empty, else ""."""
    issues = []
    for key in REQUIRED_KEYS:
        if key not in fields:
            issues.append(f"missing {key}")
        elif not fields[key]:
            issues.append(f"empty {key}")
    return ", ".join(issues)


def is_proper(directory: Path) -> bool:
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return False
    fields = parse_frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
    return not frontmatter_issue(fields)


def scan(root) -> dict:
    root = Path(root)
    directories = set()
    loose = set()
    for entry in root.iterdir():
        if entry.is_dir():
            directories.add(entry.name)
        elif entry.suffix == ".md":
            loose.add(entry.stem)

    proper = []
    improper = {}
    for name in sorted(directories):
        skill_file = root / name / "SKILL.md"
        if not skill_file.is_file():
            continue
        fields = parse_frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
        issue = frontmatter_issue(fields)
        if issue:
            improper[name] = issue
        else:
            proper.append(name)

    return {
        "proper": proper,
        "improper": improper,
        "orphan": sorted(loose - directories),
        "duplicate": sorted(loose & directories),
    }


MARKETPLACE_MANIFEST = ".claude-plugin/marketplace.json"


def owner_roots(repo_root=None) -> list:
    """Skill roots an install can select: the default export, then each plugin
    source declared in the marketplace manifest.

    The manifest is the declared-owner registry, so a skill that moved into an
    opt-in plugin is still resolved against the root that now owns it.
    """
    repo_root = Path(repo_root) if repo_root is not None else DEFAULT_ROOT.parent.parent
    roots = [repo_root / ".claude" / "skills"]
    manifest = repo_root / MARKETPLACE_MANIFEST
    if manifest.is_file():
        for plugin in json.loads(manifest.read_text(encoding="utf-8")).get("plugins", []):
            source = plugin.get("source")
            if isinstance(source, str):
                root = repo_root / source / "skills"
                if root.is_dir():
                    roots.append(root)
    return roots


def scan_owners(repo_root=None) -> dict:
    """Union of `scan()` over `owner_roots()`, using the same classifier."""
    result = {"proper": [], "improper": {}, "orphan": [], "duplicate": []}
    for root in owner_roots(repo_root):
        found = scan(root)
        for bucket in ("proper", "orphan", "duplicate"):
            result[bucket] += [name for name in found[bucket] if name not in result[bucket]]
        for name, reason in found["improper"].items():
            result["improper"].setdefault(name, reason)
    for bucket in ("proper", "orphan", "duplicate"):
        result[bucket].sort()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify skill entries as proper, improper, orphan, or duplicate."
    )
    parser.add_argument("root", nargs="?", default=DEFAULT_ROOT, type=Path)
    parser.add_argument("--check-orphans", action="store_true")
    parser.add_argument("--check-duplicates", action="store_true")
    parser.add_argument("--check-improper", action="store_true")
    parser.add_argument("--check-personal", action="store_true",
                        help="opt-in: fail on personal identifiers in files changed vs --base")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    result = scan(args.root)
    checks_requested = args.check_orphans or args.check_duplicates or args.check_improper

    if args.json:
        report = {"root": str(args.root), "counts": {k: len(v) for k, v in result.items()}}
        report.update(result)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif not checks_requested:
        print(f"root: {args.root}")
        for bucket in ("proper", "improper", "orphan", "duplicate"):
            print(f"{bucket}: {len(result[bucket])}")

    if args.check_personal:
        try:
            files = changed_files(args.root, args.base)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        found = scan_personal(files)
        for path, hits in sorted(found.items()):
            print(f"{path}: {hits[:3]}", file=sys.stderr)
        if found:
            return 1
    if args.check_orphans and result["orphan"]:
        print(f"{len(result['orphan'])} orphan skill file(s)", file=sys.stderr)
        return 1
    if args.check_duplicates and result["duplicate"]:
        print(f"{len(result['duplicate'])} duplicate skill file(s)", file=sys.stderr)
        return 1
    if args.check_improper and result["improper"]:
        print(f"{len(result['improper'])} improper skill package(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
