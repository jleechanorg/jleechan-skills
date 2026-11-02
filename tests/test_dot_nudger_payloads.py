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

    def test_contract_text_names_every_resolution_and_failure_mode(self):
        for clause in ("1. a literal body path supplied in owner-provided launch context",
                       "2. `$DOT_REMINDERS_DIR/M.<account>.md`",
                       "3. the legacy fixed paths",
                       "proceed-reminder.txt", "periodic-reminder.txt",
                       "4. `$DOT_REMINDERS_DIR/M.md`",
                       "5. the shipped default", "6. for `main` only: the built-in fallback",
                       "`proceed` has no built-in fallback", "`payload-unavailable`", "`payload-invalid`",
                       "never a symlink", "at most 8 KiB", "Markers are", "never substitute another file",
                       "Record the resolved body path, its SHA256", "The footer wins"):
            self.assertIn(clause, self.text, clause)

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



    def test_only_the_main_fallback_blockquote_remains(self):
        raw = SKILL.read_text(encoding="utf-8")
        self.assertNotIn("> Read the last 20 messages", raw)
        # the sole embedded payload is main's documented last-resort fallback
        self.assertIn("### Exact fallback payload", raw)
        self.assertEqual(raw.count("> Review the last four hours of this conversation"), 1)
        self.assertIn("`proceed` has no built-in fallback", " ".join(SKILL.read_text().split()))


    def test_footer_wins_rule_is_inside_the_outbound_footer(self):
        raw = SKILL.read_text(encoding="utf-8")
        proceed_footer = raw.split("## Proceed invariant footer (`footer-v1`)", 1)[1].split("## Main invariant footer", 1)[0]
        main_footer = raw.split("## Main invariant footer (`footer-v1`)", 1)[1].split("## When body and footer disagree", 1)[0]
        for footer, name in ((proceed_footer, "proceed"), (main_footer, "main")):
            self.assertIn("this footer", footer.lower(), name)
            self.assertIn("this footer wins", footer, name)


    def test_comparisons_include_the_footer(self):
        flat = " ".join(SKILL.read_text(encoding="utf-8").split())
        self.assertIn("everything below it equals the resolved body **plus its reviewed footer**", flat)
        self.assertIn("**whole payload** is everything below the `Sent:` line", flat)



if __name__ == "__main__":
    unittest.main()
