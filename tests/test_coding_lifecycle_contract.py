"""Contract tests: draft-first-pr owns the coding lifecycle and sibling skills agree."""

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"


def read(name: str) -> str:
    """Skill text with whitespace collapsed so assertions ignore line wrapping."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    return " ".join(text.split())


class CodingLifecycleContract(unittest.TestCase):
    def setUp(self):
        self.owner = read("draft-first-pr")
        self.section = self.owner.split("## Coding lifecycle", 1)[1].split(" ## ", 1)[0]

    def test_wording_only_small_changes_skip_spec_and_plan(self):
        self.assertIn("Wording-only / small low-risk", self.section)
        self.assertIn("Skip standalone spec, plan, and plan-review cycle", self.section)

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
        self.assertIn("executing owner or started tool before reporting `Working`", self.section)
        self.assertIn("report `Blocked` or `Waiting`", self.section)
        self.assertIn("a blocker never makes it `Working`", self.section)
        self.assertIn("not execution", self.section)

    def test_docs_only_sha_move_is_reaffirmed_by_delta(self):
        ready = read("ready")
        self.assertNotIn("re-run after every head move", ready)
        self.assertIn("may instead be reaffirmed at the new SHA", ready)
        self.assertIn("is not stale: re-affirm at the new SHA", read("web-advice"))

    def test_reaffirmation_never_depends_on_path_category_alone(self):
        self.assertIn("never by path category", self.owner)
        for name in ("draft-first-pr", "ready", "web-advice", "evidence-standards"):
            text = read(name)
            self.assertNotIn("docs, tests, skills, ordinary pr-policy", text.lower())
            self.assertNotIn("test-only or otherwise non-behavioral", text)
            self.assertNotIn("non-behavioral paths is not stale", text)
            self.assertNotIn("test-only, docs-only", text)
        self.assertIn("actual delta", read("web-advice"))
        self.assertIn("actual delta", read("ready"))

    def test_changed_assertion_driver_or_behavioral_skill_edit_invalidates_proof(self):
        # Counterexamples: tests, drivers, and skill instructions are not auto-reaffirmed.
        self.assertIn(
            "a changed assertion, driver, or behavioral instruction invalidates", self.owner
        )
        hint = read("evidence-standards").split("Path category is a starting hint only", 1)[1][:400]
        for cls in ("test", "evidence driver/capture", "prompt", "contract", "schema", "skill"):
            self.assertIn(cls, hint)
        self.assertIn("assertion, driver, or executable instruction changed", hint)
        self.assertIn("changed assertion/driver requires a fresh run", read("ready"))

    def test_production_behavior_change_requires_fresh_evidence(self):
        self.assertIn("A production behavior change still requires fresh evidence", self.owner)

    def test_no_undefined_reviewer_d(self):
        self.assertNotIn("Reviewer D", read("superpowers-quick"))
        self.assertNotIn("Reviewer D", read("advice"))

    def test_write_goal_has_no_cycle_count_stop_or_dual_er_status(self):
        goal = read("write-goal")
        self.assertNotIn("Same score 2 iterations = STALLED", goal)
        self.assertIn("No cycle- or repeated-score count stops work", goal)
        self.assertIn("draft-phase gate", goal)

    def test_ready_advice_reaffirmation_is_delta_based_and_keeps_quorum(self):
        ready = read("ready")
        self.assertIn("The same delta-based reaffirmation applies here", ready)
        self.assertIn("never reduces the two-reviewer quorum", ready)

    def test_sq_stays_planning_only_with_explicit_caller_continuation(self):
        sq = read("superpowers-quick")
        self.assertIn("planning-only: it never starts implementation", sq)
        self.assertIn("calling workflow must continue explicitly", sq)

    def test_worldai_code_standards_scales_by_substance_not_line_count(self):
        path = SKILLS.parents[2] / "worldarchitect.ai" / ".claude" / "skills" / "code-standards" / "SKILL.md"
        if not path.is_file():
            self.skipTest("worldarchitect.ai checkout not alongside this repo")
        cs = " ".join(path.read_text(encoding="utf-8").split())
        self.assertIn("never to a line count", cs)
        self.assertIn("apply the four standards inline", cs)
        self.assertIn("always the full independent lanes", cs)
        self.assertIn("Required final independent approvals", cs)
        self.assertNotIn("independent review lanes** every time", cs)

    def test_goal_and_ironclad_entrypoints_delegate_instead_of_applying_universally(self):
        goal = read("write-goal")
        self.assertNotIn("no optional skips", goal)
        self.assertNotIn("Run all of these at completion", goal)
        self.assertIn("execute the phases that apply", goal)
        self.assertIn("Run the applicable gates at completion", goal)
        iron = read("ironclad")
        self.assertIn("applicability follows `draft-first-pr` § Coding lifecycle", iron)
        self.assertIn("never waives user-required, high-risk, approval/merge, or real-proof gates", iron)

    def test_small_code_fix_is_eligible_for_the_proportional_path(self):
        iron = read("ironclad")
        self.assertNotIn("a nontrivial plan means a runtime", iron)
        self.assertNotIn("multiple coordinated steps or files", iron)
        self.assertIn("A small low-risk change, including a small code fix, takes the proportional path", iron)
        self.assertIn("runtime change or file count alone never triggers this gate", iron)
        # Explicit and high-risk gates survive.
        for term in ("explicitly required review", "data-integrity", "permission", "deployment"):
            self.assertIn(term, iron)
        owner = read("draft-first-pr")
        self.assertIn("(including a small code fix)", owner)
        self.assertIn("Runtime change or file count alone does not make a change non-small", owner)
        self.assertIn("A standalone plan review applies only to high-risk or user-required cases", owner)

    def test_mandatory_versus_skippable_is_stated_once_in_the_owner(self):
        owner = read("draft-first-pr")
        self.assertIn("Mandatory regardless of class", owner)
        self.assertIn("Skippable by class", owner)
        self.assertIn("none may apply universally", owner)
        self.assertIn("high-risk/security", read("write-goal"))
        for name in ("write-goal", "ironclad"):
            self.assertIn("real-proof", read(name))

    def test_evidence_standards_canonical_section_has_no_path_only_rule(self):
        std = read("evidence-standards")
        self.assertNotIn("only PRODUCTION changes stale evidence", std)
        self.assertNotIn("required only when a production change exists", std)
        self.assertNotIn("git diff --name-only <evidence-sha> HEAD", std)
        self.assertIn("the delta and the claim decide, not the path", std)
        self.assertIn("a changed test assertion, evidence driver/capture", std)
        self.assertNotIn("git diff --name-only <verdict-sha> HEAD", read("draft-first-pr"))

    def test_staleness_gates_read_content_diffs_including_tests(self):
        er = read("evidence-review")
        self.assertNotIn("git diff --name-only", er)
        self.assertNotIn("only a material production-behavior diff", er)
        self.assertIn("assertion, driver, or executable instruction a claim depends on", er)
        cov = read("evidence-coverage")
        self.assertNotIn("git diff <evidence_sha>..HEAD --name-only", cov)
        self.assertIn("Read the full diff, including test files", cov)
        std = read("evidence-standards")
        self.assertIn("cannot waive the delta-and-claim test", std)
        self.assertNotIn("a production-behavior file in the evidenced path changed", std)
        self.assertIn("delta-and-claim test above: the delta changes production behavior, or any test assertion", std)

    def test_repo_defined_low_risk_review_exemptions_are_honored(self):
        owner = read("draft-first-pr")
        self.assertIn("may exempt defined low-risk classes", owner)
        self.assertIn("docs-only, test-only, or small non-production changes", owner)
        self.assertIn("default when the repo defines none", owner)
        self.assertIn("No exemption covers changes to approval, merge, review, evidence, or security rules", owner)

    def test_gate_entrypoints_respect_repo_exemptions(self):
        owner = read("draft-first-pr")
        self.assertIn("accept these final gates, where applicable, in sequence", owner)
        self.assertIn("documentation-only class below or a repo-exempted class", owner)
        self.assertIn("unless a repo-exempted class applies", owner)
        self.assertIn("outside any low-risk class the repo's own instructions exempt", read("evidence-review"))
        ready = read("ready")
        self.assertIn("/er and /advice where `draft-first-pr` (including repo-defined exemptions) requires them", ready)
        self.assertNotIn("Final acceptance remains /es → /er → /advice at the current SHA;", ready)
        command = " ".join((SKILLS.parent / "commands" / "ready.md").read_text().split())
        self.assertIn("/er and /advice where `draft-first-pr` (including repo-defined exemptions) requires them", command)


if __name__ == "__main__":
    unittest.main()
