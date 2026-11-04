"""The markdown-driven nudger: shipped default payload files are well-formed and portable."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMINDERS = ROOT / ".claude/skills/dot-coordinator/reminders"


class NudgerPayloadTest(unittest.TestCase):
    def test_every_default_body_begins_with_the_agent_ask_label(self):
        for mode in ("main", "proceed"):
            body = (REMINDERS / f"{mode}.md").read_text(encoding="utf-8")
            self.assertTrue(body.startswith("[Agent ask] "), (mode, body[:40]))

    def test_bodies_are_nonempty_and_within_size_limit(self):
        for name in ("proceed", "main"):
            size = (REMINDERS / f"{name}.md").stat().st_size
            self.assertLessEqual(size, 8192, name)
            self.assertGreater(size, 0, name)

    def test_payloads_carry_no_machine_specific_content(self):
        for path in REMINDERS.glob("*.md"):
            body = path.read_text(encoding="utf-8")
            for forbidden in ("/Users/", "/home/", "jeff-ubuntu", "jeffreys-macbook", ".claude-wa", "@gmail.com"):
                self.assertNotIn(forbidden, body, f"{path.name}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
