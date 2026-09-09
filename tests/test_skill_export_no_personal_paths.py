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

Scope: every text file under `.claude/skills/`, not just Markdown — the first
real leak this test caught outside its original glob was a Python fixture
string. This covers the skills tree only; personal paths elsewhere in the repo
(notably `.beads/`) are out of its declared scope and are not claimed to be
guarded here.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"

# No trailing slash required: `cd /Users/alice` and `(/home/bob)` leak just as
# much as `/Users/alice/x`.
PERSONAL_HOME = re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)")

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

# Binary/large artifacts that are not reviewable text.
SKIP_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".mp4", ".mov", ".zip", ".ico"}
)


class SkillExportNoPersonalPathsTest(unittest.TestCase):
    def test_no_personal_home_paths_in_exported_skills(self):
        offenders = []
        for path in sorted(SKILLS.rglob("*")):
            if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            rel_to_skills = path.relative_to(SKILLS).as_posix()
            if rel_to_skills in VENDORED_ALLOWED_FILES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, ValueError):
                continue  # binary payload, nothing to review
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in PERSONAL_HOME.finditer(line):
                    if match.group(1) in ALLOWED_SEGMENTS:
                        continue
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{lineno}: {match.group(0)}")

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
