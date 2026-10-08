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
# and they are not this repo's paths to leak. Pinned per (file, matched-path)
# occurrence -- NOT a whole-file exemption -- so a new personal path added
# anywhere else in that file, even a different author's, still fails.
VENDORED_ALLOWED_OCCURRENCES = frozenset(
    {
        ("superpowers-using-git-worktrees/SKILL.md", "/Users/jesse"),
    }
)


ALLOWED_LOWER = frozenset(s.lower() for s in ALLOWED_SEGMENTS)


def _decode_text(raw):
    """Return the file's text, or None if it is a genuine binary (image,
    archive, etc.) with no reviewable text.

    NUL bytes alone are not proof of binary -- UTF-16 text is dense with
    them, so a raw `b"\\x00" in raw` check let a UTF-16 file carrying a
    personal path skip scanning entirely. Detect the encoding by BOM/codec
    probing instead: UTF-16 (with or without a BOM) is decoded and scanned;
    only content that fails to decode as recognizable text is treated as
    binary.
    """
    for bom, codec in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if raw.startswith(bom):
            return raw[len(bom):].decode(codec, errors="replace")
    if b"\x00" not in raw:
        # errors="replace" rather than skipping: invalid UTF-8 must not be
        # a way to smuggle a path past the guard.
        return raw.decode("utf-8", errors="replace")
    # NUL bytes with no BOM: could be UTF-16 without a BOM, or a genuine
    # binary. Try both UTF-16 byte orders and only trust a decode that
    # looks like real text (not dominated by the Unicode replacement
    # character); otherwise this is binary, not text we can review.
    for codec in ("utf-16-le", "utf-16-be"):
        try:
            candidate = raw.decode(codec)
        except UnicodeDecodeError:
            continue
        if candidate.count("�") * 4 < len(candidate):
            return candidate
    return None  # genuinely binary: no reviewable text


def _is_vendored_allowed(rel_to_skills, matched):
    return (rel_to_skills, matched) in VENDORED_ALLOWED_OCCURRENCES


def _scan_line(rel, rel_to_skills, lineno, line, offenders):
    for match in PERSONAL_HOME.finditer(line):
        # PERSONAL_HOME is IGNORECASE, so the segment check must be too,
        # or "/Users/USER" would slip past an exact-case allowlist.
        if match.group(1).lower() in ALLOWED_LOWER:
            continue
        if _is_vendored_allowed(rel_to_skills, match.group(0)):
            continue
        offenders.append(f"{rel}:{lineno}: {match.group(0)}")


def _scan_boundary(rel, rel_to_skills, lineno, line, next_line, offenders):
    """Catch a personal path split by a line break exactly at the boundary,
    e.g. `/Users/` ending one line and `alice/.claude` starting the next --
    invisible to pure line-by-line scanning. Only matches that actually
    straddle the boundary are reported; matches fully inside one side are
    already caught by `_scan_line`.
    """
    boundary = line + next_line
    split = len(line)
    for match in PERSONAL_HOME.finditer(boundary):
        if match.start() >= split or match.end() <= split:
            continue
        if match.group(1).lower() in ALLOWED_LOWER:
            continue
        if _is_vendored_allowed(rel_to_skills, match.group(0)):
            continue
        offenders.append(
            f"{rel}:{lineno}-{lineno + 1}: {match.group(0)} (split across line break)"
        )


class SkillExportNoPersonalPathsTest(unittest.TestCase):
    """Every bypass closed here was found by an adversarial reviewer, not by CI.

    Deliberately avoided: suffix-based skipping (a personal path in a UTF-8 file
    named `.pdf` is still a leak), decode-error skipping (invalid UTF-8 is a
    bypass, not a reason to stop looking), `is_file()` gating (a dangling
    symlink is not a file, but its *target string* leaks the path), a raw NUL
    check for binary detection (UTF-16 text is dense with NULs and was
    skipped whole), pure line-by-line scanning (a path split by a line break
    exactly at a slash was invisible to both halves), and a whole-file
    vendored exemption (a new path added anywhere else in that file would
    have been invisible too -- the allowlist is pinned per occurrence).
    """

    def test_no_personal_home_paths_in_exported_skills(self):
        self.assertTrue(SKILLS.is_dir(), f"skills tree missing: {SKILLS}")
        scanned = 0
        offenders = []
        for path in sorted(SKILLS.rglob("*")):
            rel_to_skills = path.relative_to(SKILLS).as_posix()
            rel = path.relative_to(REPO_ROOT)

            # A symlink's target is text we ship, whether or not it resolves.
            if path.is_symlink():
                _scan_line(rel, rel_to_skills, 0, os.readlink(path), offenders)
                continue
            if path.is_dir():
                continue

            scanned += 1
            text = _decode_text(path.read_bytes())
            if text is None:
                continue  # genuinely binary: no reviewable text
            text_lines = text.splitlines()
            for lineno, line in enumerate(text_lines, start=1):
                _scan_line(rel, rel_to_skills, lineno, line, offenders)
            for lineno in range(1, len(text_lines)):
                _scan_boundary(
                    rel, rel_to_skills, lineno, text_lines[lineno - 1], text_lines[lineno], offenders
                )

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
