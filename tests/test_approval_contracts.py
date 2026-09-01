"""Regression contracts for portable approval and evidence-gate skills."""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
COMMANDS = REPO_ROOT / ".claude" / "commands"


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


class ApprovalContractsTest(unittest.TestCase):
    def test_superpowers_quick_delegates_recommended_choices_and_finishes_documents(self) -> None:
        command = (COMMANDS / "superpowers-quick.md").read_text()
        quick = skill("superpowers-quick")

        self.assertIn("~/.claude/skills/superpowers-quick/SKILL.md", command)
        self.assertNotIn("superpowers:brainstorming", command)
        self.assertNotIn("superpowers:writing-plans", command)
        self.assertIn("superpowers:brainstorming", quick)
        self.assertIn("superpowers:writing-plans", quick)
        self.assertIn("disable-model-invocation: false", quick)
        self.assertIn("recommended", quick.lower())
        self.assertIn("invocation is the user's explicit authorization", quick.lower())
        self.assertIn("do not ask the user", quick.lower())
        self.assertIn("docs/superpowers/specs/", quick)
        self.assertIn("docs/superpowers/plans/", quick)
        self.assertIn("terminal condition", quick.lower())

    def test_superpowers_quick_resolves_portable_dependencies_and_overrides_child_pauses(self) -> None:
        quick = skill("superpowers-quick")

        for dependency in ("superpowers-brainstorming", "superpowers-writing-plans"):
            dependency_path = SKILLS / dependency / "SKILL.md"
            self.assertTrue(dependency_path.is_file(), dependency_path)
            self.assertIn(f"~/.claude/skills/{dependency}/SKILL.md", quick)

        self.assertIn("Do not offer the visual companion", quick)
        self.assertIn("Do not pause for user review", quick)
        self.assertIn("Do not commit or push", quick)
        self.assertIn("Skip its execution handoff", quick)
        self.assertIn("Terminate immediately after", quick)
        self.assertIn("takes precedence over every child instruction", quick)
        self.assertIn("write either artifact to a different path", quick)
        self.assertIn("still write and self-review both documents", quick)
        self.assertNotIn("stop with the exact blocker", quick)

    def test_superpowers_quick_reports_autopicks_and_advice_without_unapproved_disclosure(self) -> None:
        quick = skill("superpowers-quick")

        self.assertIn(
            "question, the auto-picked answer, and the underlying rationale",
            quick,
        )
        self.assertIn("both the design specification and implementation plan", quick)
        self.assertIn(
            "A bare `/superpowers-quick` invocation does not authorize external browser review",
            quick,
        )
        self.assertIn("Do not run a second standalone `/web-advice`", quick)
        self.assertIn("Do not pause or ask the user to log in", quick)
        self.assertIn(
            "Reviewer D /web-advice is disabled; do not invoke it or any external browser transport",
            quick,
        )
        self.assertIn(
            "lists Reviewer D as `unavailable (disabled by parent authorization boundary)`",
            quick,
        )
        self.assertIn(
            "Retry `/advice` once only for a transient transport or reviewer-launch failure",
            quick,
        )
        self.assertIn(
            "permits the terminal report but prohibits claiming that advice passed or approved the documents",
            quick,
        )
        self.assertIn(
            "record `/web-advice` as `FAILED` with the attempted-submission reason",
            quick,
        )
        self.assertIn(
            "When no external attempt occurred and explicit authorization is absent",
            quick,
        )
        self.assertIn(
            "Retry the whole `/advice` invocation only when it failed before any reviewer launched",
            quick,
        )
        self.assertIn(
            "Any Reviewer D attempt consumes the single `/web-advice` run",
            quick,
        )
        self.assertIn(
            "Only when `/advice` did not attempt Reviewer D",
            quick,
        )
        self.assertIn("`/advice`: `RAN | FAILED`", quick)
        self.assertIn(
            "`/web-advice`: `RAN | SKIPPED | UNAVAILABLE | FAILED`",
            quick,
        )
        self.assertIn("<repo-root>/docs/superpowers/specs/", quick)
        self.assertIn("<repo-root>/docs/superpowers/plans/", quick)
        self.assertIn("advice attempts and required status records are complete", quick)

    def test_advice_reviews_repository_before_approving(self) -> None:
        advice = skill("advice")
        command = (COMMANDS / "advice.md").read_text()
        readme = (REPO_ROOT / "README.md").read_text()
        self.assertIn("**Pointer**", advice)
        self.assertIn("Send the pointer, not a transcription.", advice)
        self.assertIn("A verdict built on a truncated inline artifact may not be `APPROVED`.", advice)
        self.assertIn("VERDICT: WITHHELD at <SHA>", advice)
        self.assertIn("COVERAGE", advice)
        self.assertIn("research-only output are not approval reviewers", advice)
        self.assertIn("combined scope covers the whole declared change", advice)
        self.assertIn("`COVERAGE: <files/diff scope actually read>`", advice)
        self.assertIn("Codex + Opus CLI", command)
        self.assertIn("/research", command)
        self.assertIn("/extended-library:secondo", command)
        self.assertNotIn("/web-advice", command)
        self.assertNotIn("/web-advice", advice)
        self.assertNotIn("Reviewer D", advice)
        self.assertIn("up to four reviewers concurrently", readme)
        self.assertIn("`/extended-library:secondo`", readme)
        self.assertNotIn("up to four reviewers concurrently: an Opus subagent", readme)

    def test_ready_requires_advice_without_web_advice_fanout(self) -> None:
        ready = skill("ready")
        draft_first = skill("draft-first-pr")
        advice = skill("advice")
        web_advice_command = (COMMANDS / "web-advice.md").read_text()

        self.assertIn("/advice\napproved", (COMMANDS / "ready.md").read_text())
        self.assertIn("**/advice**", ready)
        self.assertIn("→ /advice APPROVED @ SHA", draft_first)
        self.assertNotIn("/web-advice", advice)
        self.assertNotIn("Reviewer D", advice)
        self.assertIn("canonical skill", web_advice_command)

    def test_web_advice_requires_real_browser_transport(self) -> None:
        web_adv = skill("web-advice")
        self.assertIn(
            "COVERAGE: exact filenames from the attached packet actually read",
            web_adv,
        )
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

    def test_documentation_only_draft_gate_skips_evidence_review(self) -> None:
        draft_first = skill("draft-first-pr")
        evidence_review = skill("evidence-review")
        green = skill("pr-green-definition")
        readme = (REPO_ROOT / "README.md").read_text()

        self.assertIn("Documentation-only exception", draft_first)
        self.assertIn("do not run `/er`", draft_first)
        self.assertIn("`README.md`", draft_first)
        self.assertIn("`docs/**`", draft_first)
        self.assertIn("`.claude/**`", draft_first)
        self.assertRegex(draft_first, r"still require `/es` and\s+`/advice`")
        allowlist = re.search(
            r"is documentation-only only when every changed path is one of:\n\n"
            r"(?P<paths>(?:- `[^`]+`\n)+)",
            draft_first,
        )
        self.assertIsNotNone(allowlist)
        self.assertEqual(
            re.findall(r"- `([^`]+)`", allowlist.group("paths")),
            ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "docs/**"],
        )
        self.assertIn("Documentation-only exception", evidence_review)
        self.assertIn("`/er` is not run", evidence_review)
        receipt = "`/er: NOT REQUIRED — documentation-only (<changed paths>)`"
        self.assertIn(receipt, draft_first)
        self.assertIn(receipt, evidence_review)
        self.assertRegex(
            draft_first,
            r"Any\s+mixed diff uses the normal `/er` gate",
        )
        self.assertRegex(
            evidence_review,
            r"Mixed diffs and every path outside that allowlist follow the normal gate",
        )
        self.assertIn("Every PR outside that exception requires `/er` = **PASS**", evidence_review)
        self.assertNotIn("Acceptable for `/green` on NON_PRODUCTION", evidence_review)
        self.assertIn("when `/er` is required by that lifecycle", green)
        self.assertNotIn("DRAFT → `/es` → `/er` → `/advice`", green)
        self.assertIn("draft-phase gate", readme)
        self.assertIn("Documentation-only PRs skip `/er`", readme)
        self.assertNotIn("production-tier `/green` requires PASS", readme)

    def test_portable_and_orchestration_contracts_disclose_actual_behavior(self) -> None:
        history = skill("conversation-history-sparse")
        factory = skill("dark-factory")
        swarm = skill("swarm")

        self.assertIn('cwd_project_key = os.getcwd().replace("/", "-")', history)
        self.assertIn("skip auto-selection but not the\npre-run disclosure", factory)
        self.assertIn("The top-level session owns named visible lanes", swarm)


if __name__ == "__main__":
    unittest.main()
