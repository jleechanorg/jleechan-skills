"""The never-stall contract: proven hold grounds, a turn receipt, and a mechanical stall check.

Instruction-only change, so these tests pin the contract text and the coordinator's duties.
Behaviour is proven on the live three-account table, not here.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOT = ROOT / ".claude/skills/dot/SKILL.md"
COORD = ROOT / ".claude/skills/dot-coordinator/SKILL.md"


class NeverStallContractTest(unittest.TestCase):
    def setUp(self):
        self.dot = " ".join(DOT.read_text(encoding="utf-8").split())
        self.coord = " ".join(COORD.read_text(encoding="utf-8").split())

    def test_valid_and_illegal_hold_grounds_are_enumerated(self):
        self.assertIn("Never stall (mandatory)", self.dot)
        self.assertIn("Valid hold grounds", self.dot)
        for ground in ("a literal `HOLD` or `STOP` instruction",
                       "an access denial or a non-zero exit **from this turn**",
                       "a read-only probe from this turn",
                       "a verified one-writer conflict on the *same mutable target*"):
            self.assertIn(ground, self.dot, ground)
        self.assertIn("Illegal grounds", self.dot)
        for illegal in ('"slot"', '"admission"', '"reservation"', "self-imposed budget or cost pacing",
                        "Unknown occupancy is not a blocker", "the rest of the lane keeps moving"):
            self.assertIn(illegal, self.dot, illegal)

    def test_turn_receipt_trailer_is_mandatory_and_complete(self):
        self.assertIn("### Turn Receipt", self.dot)
        for field in ("Mode: MUTATION | PROBE | BLOCKED", "Target:", "Artifact:", "Blocker: NONE"):
            self.assertIn(field, self.dot, field)
        self.assertIn("Work still in flight is not `BLOCKED`", self.dot)
        self.assertIn("next checkpoint", self.dot)
        self.assertIn("is a defect, not progress", self.dot)

    def test_goal_framing_and_escalation_markers(self):
        self.assertIn("no preventable idle time", self.dot)
        self.assertIn("UNBLOCK: <capability> - <exact request> - <owner>", self.dot)
        self.assertIn("IDLE: queue empty", self.dot)

    def test_coordinator_detects_stalls_and_relays_once(self):
        self.assertIn("Stall detection and the one-line relay", self.coord)
        self.assertIn("Unverified pause rejected. Execute the next diagnostic probe or produce a failing execution trace, then proceed on your branch.", self.coord)
        self.assertIn("Relay a blocker once", self.coord)
        self.assertIn("an unchanged repeat is noise", self.coord)
        self.assertIn("Proceed on your branch.", self.coord)
        self.assertIn("creates no slots, grants no capacity, and adjudicates no ownership", self.coord)

    def test_no_rule_permits_pausing_on_a_scheduling_state(self):
        for text, name in ((self.dot, "dot"), (self.coord, "coordinator")):
            for forbidden in ("wait for a slot", "wait for admission", "hold for a reservation",
                              "pause until admitted"):
                self.assertNotIn(forbidden, text.lower(), name)


if __name__ == "__main__":
    unittest.main()
