"""Regression test for bd-m7n: command-research skill files must exist in source.

The slash command `.claude/commands/extended-library/command-research.md` references:
- `~/.claude/skills/command-research/SKILL.md`
- `~/.claude/skills/command-research/scripts/count_command_usage_unified.py`

If a fresh `install-claude-commands.sh --merge` is run on a clean machine, the
target `~/.claude/skills/command-research/` must be populated from this source.
Those files were missing from main for ~3 days (worked locally because the
user's home had been installed from an earlier branch tip); this test prevents
the source-tracking gap from regressing.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    # Slash command reads SKILL.md; scanner wrapper shells out to the scanner.
    REPO_ROOT / ".claude/skills/command-research/SKILL.md",
    REPO_ROOT / ".claude/skills/command-research/scripts/count_command_usage_unified.py",
    # Mirror the user-home test layout; the scanner ships its own pytest target.
    REPO_ROOT / ".claude/skills/command-research/scripts/test_count_command_usage_unified.py",
)


class CommandResearchSkillSourcePathsTest(unittest.TestCase):
    def test_required_source_files_exist_and_are_non_empty(self):
        missing = [str(p) for p in REQUIRED_FILES if not p.is_file()]
        self.assertEqual(missing, [], f"missing or non-file under .claude/skills/command-research/: {missing}")
        empty = [str(p) for p in REQUIRED_FILES if p.is_file() and p.stat().st_size == 0]
        self.assertEqual(empty, [], f"empty source files under .claude/skills/command-research/: {empty}")

    def test_scanner_script_is_executable_python(self):
        scanner = REPO_ROOT / ".claude/skills/command-research/scripts/count_command_usage_unified.py"
        head = scanner.read_text(encoding="utf-8")[:64]
        self.assertTrue(head.startswith("#!/usr/bin/env python3"), f"scanner missing shebang: {head!r}")

    def test_skill_md_has_required_frontmatter(self):
        skill_md = REPO_ROOT / ".claude/skills/command-research/SKILL.md"
        body = skill_md.read_text(encoding="utf-8")
        self.assertTrue(body.startswith("---\n"), "SKILL.md missing YAML frontmatter")
        # The slash command mentions these directives; presence is enough to keep the chain alive.
        for required in ("name:", "description:"):
            self.assertIn(required, body[:512], f"SKILL.md frontmatter missing {required}")


if __name__ == "__main__":
    unittest.main()
