"""The markdown-driven nudger: default payloads, marker validation, fail-closed selection.

Instruction-only change: these tests pin the shipped defaults and the contract text. Selection behaviour is proven by
a live run report naming the resolved path and its SHA256, not here.
"""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/dot-coordinator/SKILL.md"
REMINDERS = ROOT / ".claude/skills/dot-coordinator/reminders"

PROCEED_MARKERS = ("## Hold grounds", "## Turn Receipt", "## Preventable idle", "IDLE: queue empty")
MAIN_MARKERS = ("This reminder grants no new execution",)


class NudgerPayloadTest(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(SKILL.read_text(encoding="utf-8").split())

    def test_default_payloads_exist_are_small_and_carry_their_markers(self):
        proceed = (REMINDERS / "proceed.md").read_text(encoding="utf-8")
        main = (REMINDERS / "main.md").read_text(encoding="utf-8")
        for name, body, markers in (("proceed", proceed, PROCEED_MARKERS), ("main", main, MAIN_MARKERS)):
            size = (REMINDERS / f"{name}.md").stat().st_size
            self.assertLessEqual(size, 8192, name)
            self.assertGreater(size, 0, name)
            for marker in markers:
                self.assertIn(marker, body, f"{name}: {marker}")

    def test_payloads_carry_no_machine_specific_content(self):
        for path in REMINDERS.glob("*.md"):
            body = path.read_text(encoding="utf-8")
            for forbidden in ("/Users/", "/home/", "jeff-ubuntu", "jeffreys-macbook", ".claude-wa", "@gmail.com"):
                self.assertNotIn(forbidden, body, f"{path.name}: {forbidden}")

    def test_skill_documents_resolution_order_and_fail_closed_selection(self):
        for clause in ("$DOT_REMINDERS_DIR/M.<account>.md",
                       "$DOT_REMINDERS_DIR/M.md",
                       "repository default `reminders/M.md`",
                       "`proceed` has no built-in fallback",
                       "`payload-unavailable`",
                       "`payload-invalid`",
                       "never a symlink",
                       "at most 8 KiB",
                       "must contain its required markers",
                       "do not fall back to a different file",
                       "Record the resolved path, its SHA256"):
            self.assertIn(clause, self.text, clause)

    def test_required_markers_are_named_for_both_modes(self):
        for marker in PROCEED_MARKERS:
            self.assertIn(marker, self.text, marker)
        self.assertIn("This reminder grants no new execution", self.text)

    def test_only_the_main_fallback_blockquote_remains(self):
        raw = SKILL.read_text(encoding="utf-8")
        self.assertNotIn("> Read the last 20 messages", raw)
        # the sole embedded payload is main's documented last-resort fallback
        self.assertIn("### Exact fallback payload", raw)
        self.assertEqual(raw.count("> Review the last four hours of this conversation"), 1)
        self.assertIn("`proceed` has no built-in fallback", " ".join(SKILL.read_text().split()))

    def test_repository_defaults_are_hashed_not_machine_paths(self):
        for path in sorted(REMINDERS.glob("*.md")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(len(digest), 64, path.name)


if __name__ == "__main__":
    unittest.main()
