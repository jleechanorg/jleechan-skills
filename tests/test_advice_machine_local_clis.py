"""The advice skill resolves reviewer commands from machine-local env values only."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/advice/SKILL.md"


class AdviceMachineLocalCliTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_every_seat_resolves_from_an_env_variable_with_a_default(self):
        for name in ("ADVICE_CODEX_CMD", "ADVICE_CLAUDE_CMD", "ADVICE_CLAUDE_ALT_CMD", "ADVICE_EXTRA_CLIS"):
            self.assertIn(name, self.text, name)
        self.assertIn("falls back to the default", self.text)
        self.assertIn("so a bare machine still works", self.text)

    def test_extra_cli_registration_is_documented_with_safe_parsing(self):
        section = self.text.split("### `ADVICE_EXTRA_CLIS`", 1)[1].split("## 3.", 1)[0]
        self.assertIn("seats separated by `|`", section)
        self.assertIn("Split on `|`, then on the **first** `=`", section)
        self.assertIn("{prompt}", section)
        self.assertIn("No shell evaluation", section)
        self.assertIn("makes that seat `UNAVAILABLE`", section)
        self.assertIn("never becomes a second vote from the same identity", section)

    def test_no_machine_specific_configuration_is_committed(self):
        self.assertIn("Machine-specific configuration never lives in this repository", self.text)
        self.assertIn("belongs in", self.text)
        self.assertIn("never in a skill file, a PR or a document", self.text)
        # concrete machine paths, credential-store dirs and profile names must not appear
        for forbidden in (".claude-wa", "/Users/", "/home/", "user_data_dir", "CLAUDE_CONFIG_DIR="):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIsNone(re.search(r"\b[A-Za-z0-9_.-]+/roadmap(?:/|\b)", self.text))

    def test_wrapper_alternate_is_named_as_a_shape_not_a_path(self):
        self.assertIn("claudewa", self.text)
        self.assertIn("the attempt records the\nactual model it ran", self.text)


if __name__ == "__main__":
    unittest.main()
