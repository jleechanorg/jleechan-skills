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
                       "the shipped default",
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

    def test_resolution_order_is_an_explicit_list(self):
        for i, entry in enumerate(("1. `$DOT_REMINDERS_DIR/M.<account>.md`",
                                   "2. for `main` only: the legacy",
                                   "3. `$DOT_REMINDERS_DIR/M.md`",
                                   "4. the shipped default",
                                   "5. for `main` only: the built-in fallback"), start=1):
            self.assertIn(entry, self.text, entry)

    def test_footer_wins_rule_is_inside_the_outbound_footer(self):
        raw = SKILL.read_text(encoding="utf-8")
        proceed_footer = raw.split("## Proceed invariant footer (`footer-v1`)", 1)[1].split("## Main invariant footer", 1)[0]
        main_footer = raw.split("## Main invariant footer (`footer-v1`)", 1)[1].split("## When body and footer disagree", 1)[0]
        for footer, name in ((proceed_footer, "proceed"), (main_footer, "main")):
            self.assertIn("this footer", footer.lower(), name)
            self.assertIn("this footer wins", footer, name)

    def test_body_and_footer_disagreement_resolves_to_the_footer(self):
        self.assertIn("The footer wins", self.text)
        self.assertIn("the receiving Dot follows the footer and reports the conflict", self.text)

    def test_main_has_a_verbatim_footer_and_submit_appends_it(self):
        raw = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Main invariant footer (`footer-v1`)", raw)
        main_footer = raw.split("## Main invariant footer (`footer-v1`)", 1)[1].split("## When body and footer disagree", 1)[0]
        self.assertIn("resolved body **plus** its reviewed footer", " ".join(raw.split()))


if __name__ == "__main__":
    unittest.main()
