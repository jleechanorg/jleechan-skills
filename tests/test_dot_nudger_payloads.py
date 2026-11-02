"""The markdown-driven nudger: default payloads, marker validation, fail-closed selection.

Instruction-only change: these tests pin the shipped defaults and the contract text. Selection behaviour is proven by
a live run report naming the resolved path and its SHA256, not here.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/dot-coordinator/SKILL.md"
REMINDERS = ROOT / ".claude/skills/dot-coordinator/reminders"

PROCEED_INVARIANTS = ("Valid hold grounds:", "Turn Receipt", "IDLE: queue empty",
                     "This nudge grants no new execution")


class NudgerPayloadTest(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(SKILL.read_text(encoding="utf-8").split())

    def test_bodies_are_task_content_only_and_full_invariants_live_in_the_footer(self):
        for name in ("proceed", "main"):
            body = (REMINDERS / f"{name}.md").read_text(encoding="utf-8")
            size = (REMINDERS / f"{name}.md").stat().st_size
            self.assertLessEqual(size, 8192, name)
            self.assertGreater(size, 0, name)
            # the editable body must NOT be the place safety rules live
            self.assertNotIn("HOLD", body, name)
            self.assertNotIn("Turn Receipt", body, name)
        proceed_body = (REMINDERS / "proceed.md").read_text(encoding="utf-8")
        self.assertIn("Review the last four hours of this conversation", proceed_body)

    def test_footer_is_immutable_and_versioned(self):
        raw = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Proceed invariant footer (`footer-v1`)", raw)
        self.assertIn("never edited by an operator, never read from the payload dir", " ".join(raw.split()))
        self.assertIn("identified as `footer-v1` in the run report", " ".join(raw.split()))
        footer = raw.split("## Proceed invariant footer (`footer-v1`)", 1)[1].split("### Idle gate", 1)[0]
        for invariant in PROCEED_INVARIANTS:
            self.assertIn(invariant, footer, invariant)

    def test_payloads_carry_no_machine_specific_content(self):
        for path in REMINDERS.glob("*.md"):
            body = path.read_text(encoding="utf-8")
            for forbidden in ("/Users/", "/home/", "jeff-ubuntu", "jeffreys-macbook", ".claude-wa", "@gmail.com"):
                self.assertNotIn(forbidden, body, f"{path.name}: {forbidden}")

    def test_skill_documents_resolution_order_and_fail_closed_selection(self):
        for clause in ("Editable body", "Reviewed invariant footer", "$DOT_REMINDERS_DIR/M.<account>.md",
                       "$DOT_REMINDERS_DIR/M.md",
                       "repository default `reminders/M.md`",
                       "`proceed` has no built-in fallback",
                       "`payload-unavailable`",
                       "`payload-invalid`",
                       "never a symlink",
                       "at most 8 KiB",
                       "Markers are",
                       "never substitute another file",
                       "Record the resolved body path, its SHA256"):
            self.assertIn(clause, self.text, clause)

    def test_no_marker_based_safety_claim_remains(self):
        self.assertIn("Markers are not used to infer safety", self.text)
        self.assertIn("a string check cannot validate meaning", self.text)

    def test_only_the_main_fallback_blockquote_remains(self):
        raw = SKILL.read_text(encoding="utf-8")
        self.assertNotIn("> Read the last 20 messages", raw)
        # the sole embedded payload is main's documented last-resort fallback
        self.assertIn("### Exact fallback payload", raw)
        self.assertEqual(raw.count("> Review the last four hours of this conversation"), 1)
        self.assertIn("`proceed` has no built-in fallback", " ".join(SKILL.read_text().split()))

    def test_legacy_path_participates_in_main_resolution(self):
        self.assertIn("periodic-reminder.txt", self.text)
        self.assertIn("before `main.md`", self.text)


if __name__ == "__main__":
    unittest.main()
