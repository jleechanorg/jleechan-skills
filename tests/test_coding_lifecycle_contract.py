"""Contract tests: draft-first-pr owns the coding lifecycle and sibling skills agree."""

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"


def read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


class CodingLifecycleContract(unittest.TestCase):
    def setUp(self):
        self.owner = read("draft-first-pr")
        self.section = self.owner.split("## Coding lifecycle", 1)[1].split("\n## ", 1)[0]

    def test_wording_only_small_changes_skip_spec_and_plan(self):
        self.assertIn("Wording-only / small low-risk", self.section)
        self.assertIn("Skip standalone spec and plan", self.section)

    def test_ordinary_feature_uses_tdd_and_checkpoint(self):
        self.assertIn("Ordinary feature", self.section)
        self.assertIn("TDD", self.section)
        self.assertIn("correctness checkpoint", self.section)

    def test_cross_service_requires_integration_test(self):
        self.assertIn("integration-layer test", self.section)

    def test_high_risk_keeps_full_chain(self):
        self.assertIn("No layer skipping", self.section)
        self.assertIn("independent final coverage", self.section)

    def test_large_change_checkpoint_is_optional_not_a_gate(self):
        self.assertIn("optional, never a gate", self.section)

    def test_execution_handoff_invariant(self):
        self.assertIn("Execution handoff invariant", self.section)
        self.assertIn("exact blocker plus resumption trigger", self.section)
        self.assertIn("not execution", self.section)

    def test_docs_only_sha_move_is_reaffirmed_everywhere(self):
        self.assertIn("re-affirmed", self.owner)
        ready = read("ready")
        self.assertNotIn("re-run after every head move", ready)
        self.assertIn("non-behavioral move is re-affirmed", ready)
        web = read("web-advice")
        self.assertIn("SHA-only move", web)
        self.assertIn("not stale", web)

    def test_changed_driver_evidence_is_invalidated(self):
        self.assertIn("A production behavior\nchange still requires fresh evidence", self.owner)
        self.assertIn("material", read("web-advice"))

    def test_no_undefined_reviewer_d(self):
        self.assertNotIn("Reviewer D", read("superpowers-quick"))
        self.assertNotIn("Reviewer D", read("advice"))

    def test_write_goal_has_no_cycle_count_stop_or_dual_er_status(self):
        goal = read("write-goal")
        self.assertNotIn("Same score 2 iterations = STALLED", goal)
        self.assertIn("No cycle- or repeated-score count stops work", goal)
        self.assertIn("draft-phase gate", goal)


if __name__ == "__main__":
    unittest.main()
