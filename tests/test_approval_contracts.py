"""Regression contracts for portable approval and evidence-gate skills."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


class ApprovalContractsTest(unittest.TestCase):
    def test_advice_reviews_repository_before_approving(self) -> None:
        advice = skill("advice")
        self.assertIn("**Pointer**", advice)
        self.assertIn("Send the pointer, not a transcription.", advice)
        self.assertIn("A verdict built on a truncated inline artifact may not be `APPROVED`.", advice)
        self.assertIn("VERDICT: WITHHELD at <SHA>", advice)
        self.assertIn("COVERAGE", advice)
        self.assertIn("Independent reviewers that returned a verdict", advice)

    def test_evidence_review_separates_integrity_from_provenance(self) -> None:
        review = skill("evidence-review")
        self.assertIn("Checksums establish integrity, not provenance", review)
        self.assertIn("does not make a claim STRONG", review)

    def test_evidence_staleness_is_about_production_behavior(self) -> None:
        standards = skill("evidence-standards")
        self.assertIn("only PRODUCTION changes stale evidence", standards)
        self.assertIn("A moving HEAD does NOT invalidate evidence by itself.", standards)

    def test_draft_gate_requires_sha_bound_approval_not_withheld(self) -> None:
        draft_first = skill("draft-first-pr")
        self.assertIn("`WITHHELD at <SHA>`", draft_first)
        self.assertIn("does not satisfy the draft gate", draft_first)
        self.assertIn("SHA-binding rule", draft_first)


if __name__ == "__main__":
    unittest.main()
