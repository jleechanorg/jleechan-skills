"""The advice skill resolves reviewer commands from machine-local env values only."""
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/advice/SKILL.md"


class AdviceMachineLocalCliTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_no_machine_specific_configuration_is_committed(self):
        # concrete machine paths, credential-store dirs and profile names must not appear
        for forbidden in (".claude-wa", "/Users/", "/home/", "user_data_dir", "CLAUDE_CONFIG_DIR="):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIsNone(re.search(r"\b[A-Za-z0-9_.-]+/roadmap(?:/|\b)", self.text))


class MarkdownOnlyDecisionTest(unittest.TestCase):
    """The slimming decision: this skill stays markdown-first with no new runner code."""

    def test_the_skill_ships_no_runner_code(self):
        scripts = ROOT / ".claude/skills/advice/scripts"
        self.assertFalse((scripts / "run_primary_pair.py").exists(),
                         "the slimming decision removed the bundled runner")
        remaining = sorted(p.name for p in scripts.glob("*.py")) if scripts.is_dir() else []
        self.assertEqual(remaining, [], f"no runner code may return: {remaining}")


if __name__ == "__main__":
    unittest.main()
