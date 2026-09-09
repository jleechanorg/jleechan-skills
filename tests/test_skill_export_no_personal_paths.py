"""Contract test: exported skills must not carry personal absolute paths.

CLAUDE.md states "Keep project-specific configuration and personal paths out of
the export." Nothing enforced that for `.claude/skills/**`, so a live-to-repo
skill copy could ship a home-directory path into this public repository and
still pass CI. `test_document_standards_contract.py` guards the same string but
only over document-standards files, which left every skill uncovered.

Skills are exported to other machines and other users, so a hardcoded
`/Users/<name>/...` or `/home/<name>/...` is both a leak and a broken path for
every reader. The portable form is `${CLAUDE_HOME:-$HOME/.claude}` for
Claude-home paths, or a bare binary name resolved on PATH.

Scope: every non-binary file under `.claude/skills/`, plus symlink targets —
the first real leak caught outside the original Markdown glob was a Python
fixture string. This covers the skills tree only; personal paths elsewhere in
the repo (notably `.beads/`, which currently holds 83) are out of its declared
scope and are not claimed to be guarded here.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"

# No trailing slash required: `cd /Users/alice` and `(/home/bob)` leak just as
# much as `/Users/alice/x`. Case-insensitive because macOS resolves `/users`
# to `/Users`, so the lowercase spelling is a working path, not a typo. The
# Windows alternation catches `C:\Users\alice`.
PERSONAL_HOME = re.compile(
    r"(?:/(?:Users|home)/|[A-Za-z]:\\Users\\)([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

# Home-directory segments that are not a real person's account on a real
# machine, and so are not a leak. Anything outside this set fails the test.
ALLOWED_SEGMENTS = frozenset(
    {
        "user",  # generic placeholder in example command lines
        "USER",  # ditto, shell-variable styling
        "username",
        "youruser",
        "testuser",  # synthetic fixture data
        "REDACTED",  # already sanitized before export
        "runner",  # GitHub Actions runner home, genuinely that path in CI
        "...",  # elided path segment in illustrative output
    }
)

# Exact known hits inside vendored third-party skills, whose upstream examples
# use their own author's home path. Rewriting them would fork upstream text,
# and they are not this repo's paths to leak. Listed per-file rather than by
# directory prefix so a future upstream sync cannot smuggle in a new path under
# a blanket exemption.
VENDORED_ALLOWED_FILES = frozenset(
    {
        "superpowers-using-git-worktrees/SKILL.md",
    }
)


ALLOWED_LOWER = frozenset(s.lower() for s in ALLOWED_SEGMENTS)


def _scan_line(rel, lineno, line, offenders):
    for match in PERSONAL_HOME.finditer(line):
        # PERSONAL_HOME is IGNORECASE, so the segment check must be too,
        # or "/Users/USER" would slip past an exact-case allowlist.
        if match.group(1).lower() in ALLOWED_LOWER:
            continue
        offenders.append(f"{rel}:{lineno}: {match.group(0)}")


class SkillExportNoPersonalPathsTest(unittest.TestCase):
    """Every bypass closed here was found by an adversarial reviewer, not by CI.

    Deliberately avoided: suffix-based skipping (a personal path in a UTF-8 file
    named `.pdf` is still a leak), decode-error skipping (invalid UTF-8 is a
    bypass, not a reason to stop looking), and `is_file()` gating (a dangling
    symlink is not a file, but its *target string* leaks the path).
    """

    def test_no_personal_home_paths_in_exported_skills(self):
        self.assertTrue(SKILLS.is_dir(), f"skills tree missing: {SKILLS}")
        scanned = 0
        offenders = []
        for path in sorted(SKILLS.rglob("*")):
            rel_to_skills = path.relative_to(SKILLS).as_posix()
            if rel_to_skills in VENDORED_ALLOWED_FILES:
                continue
            rel = path.relative_to(REPO_ROOT)

            # A symlink's target is text we ship, whether or not it resolves.
            if path.is_symlink():
                _scan_line(rel, 0, os.readlink(path), offenders)
                continue
            if path.is_dir():
                continue

            scanned += 1
            raw = path.read_bytes()
            if b"\x00" in raw:
                continue  # genuinely binary: no reviewable text
            # errors="replace" rather than skipping: invalid UTF-8 must not be
            # a way to smuggle a path past the guard.
            text = raw.decode("utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                _scan_line(rel, lineno, line, offenders)

        self.assertGreater(
            scanned, 100, "scanned too few files -- the guard is not looking where it claims"
        )
        self.assertEqual(
            offenders,
            [],
            "Exported skills must not contain personal home paths. Use "
            "${CLAUDE_HOME:-$HOME/.claude} for Claude-home paths, or a bare "
            "binary name resolved on PATH. Offenders:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
