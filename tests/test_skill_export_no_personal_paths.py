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
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"

PERSONAL_HOME = re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)/")

# Home-directory segments that are not a real person's account on a real
# machine, and so are not a leak. Anything outside this set fails the test.
ALLOWED_SEGMENTS = frozenset(
    {
        "user",  # generic placeholder in example command lines
        "USER",  # ditto, shell-variable styling
        "username",
        "youruser",
        "REDACTED",  # already sanitized before export
        "runner",  # GitHub Actions runner home, genuinely that path in CI
        "...",  # elided path segment in illustrative output
    }
)

# Vendored third-party skills whose upstream examples use the author's own
# home path. Rewriting them would fork the upstream text; they are not this
# repo's secrets to leak.
VENDORED_PREFIXES = ("superpowers-", "superpowers/")


class SkillExportNoPersonalPathsTest(unittest.TestCase):
    def test_no_personal_home_paths_in_exported_skills(self):
        offenders = []
        for path in sorted(SKILLS.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT)
            skill_dir = path.relative_to(SKILLS).parts[0]
            if skill_dir.startswith(VENDORED_PREFIXES):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in PERSONAL_HOME.finditer(line):
                    if match.group(1) in ALLOWED_SEGMENTS:
                        continue
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
