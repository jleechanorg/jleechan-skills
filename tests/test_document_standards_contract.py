"""Focused contract tests for document-standards thin commands and canonical skill."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"
SKILLS = REPO_ROOT / ".claude" / "skills"


class DocumentStandardsContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cmd_path = COMMANDS / "document-standards.md"
        self.alias_path = COMMANDS / "ds.md"
        self.skill_path = SKILLS / "document-standards" / "SKILL.md"

    def test_portability_and_claude_home_resolution(self) -> None:
        for path in (self.cmd_path, self.alias_path, self.skill_path):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("/Users/jleechan", content)
                self.assertNotIn("/home/", content)


if __name__ == "__main__":
    unittest.main()
