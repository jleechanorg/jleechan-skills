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
        self.assertIn("research-only output are not approval reviewers", advice)
        self.assertIn("combined scope covers the whole declared change", advice)
        self.assertIn("`COVERAGE: <files/diff scope actually read>`", advice)

    def test_web_advice_requires_real_browser_transport(self) -> None:
        web_adv = skill("web-advice")
        self.assertIn("COVERAGE: files, diff, evidence, or subject material actually read", web_adv)
        self.assertIn("Zero Aside Inference Invariant", web_adv)
        self.assertIn("NEVER use Aside inference", web_adv)
        self.assertIn("chrome_headless_cookies", web_adv)
        self.assertIn("playwright_mcp", web_adv)
        self.assertNotIn("fall back to a subagent", web_adv.lower())
        self.assertNotIn("fall back to subagent", web_adv.lower())

        workflow = (
            REPO_ROOT
            / "hermes"
            / "skills"
            / "workflow"
            / "apply-supplied-patch-and-open-pr"
            / "SKILL.md"
        ).read_text()
        self.assertNotIn("recorded CLI review via `codex exec`", workflow)
        self.assertNotIn("/web-advice (Codex)", workflow)

        evals = (
            SKILLS / "web-advice" / "evals" / "web_advice_evals.md"
        ).read_text()
        self.assertIn("authenticated Playwright fallback", evals)
        self.assertIn("Chrome cookie headless", evals)
        self.assertNotIn("the four ladder rungs", evals)

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

    def test_portable_and_orchestration_contracts_disclose_actual_behavior(self) -> None:
        history = skill("conversation-history-sparse")
        factory = skill("dark-factory")
        swarm = skill("swarm")

        self.assertIn('cwd_project_key = os.getcwd().replace("/", "-")', history)
        self.assertIn("skip auto-selection but not the\npre-run disclosure", factory)
        self.assertIn("The top-level session owns named visible lanes", swarm)


if __name__ == "__main__":
    unittest.main()
