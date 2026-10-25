"""Contract tests: pr-lifecycle owns the coding lifecycle and sibling skills agree."""

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"


def read(name: str) -> str:
    """Skill text with whitespace collapsed so assertions ignore line wrapping."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    return " ".join(text.split())


class CodingLifecycleContract(unittest.TestCase):
    def test_generic_exceptions_preserve_opt_in_spec_and_review_route_scope(self):
        raw = (SKILLS / "pr-lifecycle" / "SKILL.md").read_text()
        self.assertIn("\n## Proportional exceptions and fast paths\n", raw)
        self.assertIn("In opted-in repositories, the seven-element specification", self.owner)
        self.assertIn("When /dot is necessary to satisfy the applicable route", self.owner)
        self.assertIn("small PRs need /advice OR independent /dot approval", self.owner)
        self.assertIn("this workflow policy cannot exempt its own review", self.owner)

    def test_lifecycle_precedence_keeps_domain_and_merge_boundaries(self):
        self.assertIn("## Precedence and scope", self.owner)
        self.assertIn("separate security, credential, source-ownership and merge-authority restrictions", self.owner)
        for name in ("evidence-review", "evidence-standards"):
            self.assertIn("../pr-lifecycle/SKILL.md#precedence-and-scope", read(name))
            self.assertNotIn("and take precedence on conflict", read(name))
        self.assertIn("cannot waive the delta-and-claim test", read("evidence-standards"))

    def test_old_name_is_only_a_compatibility_pointer(self):
        alias = read("draft-first-pr")
        self.assertIn("../pr-lifecycle/SKILL.md", alias)
        self.assertIn("defines no independent rules", alias)
        self.assertNotIn("stage:0-spec", alias)
        self.assertNotIn("## Canonical lifecycle", alias)
        self.assertLess(len(alias), 1200)
        self.assertIn("name: pr-lifecycle", read("pr-lifecycle"))
        self.assertIn("../pr-lifecycle/SKILL.md", read("pr-workflow-manager"))

    def setUp(self):
        self.owner = read("pr-lifecycle")
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
        for name in ("pr-lifecycle", "ready", "web-advice", "evidence-standards"):
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
        owner = read("pr-lifecycle")
        self.assertIn("(including a small code fix)", owner)
        self.assertIn("Runtime change or file count alone does not make a change non-small", owner)
        self.assertIn("A standalone plan review applies only to high-risk or user-required cases", owner)

    def test_mandatory_versus_skippable_is_stated_once_in_the_owner(self):
        owner = read("pr-lifecycle")
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
        self.assertNotIn("git diff --name-only <verdict-sha> HEAD", read("pr-lifecycle"))

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
        owner = read("pr-lifecycle")
        self.assertIn("may exempt defined low-risk classes", owner)
        self.assertIn("docs-only, test-only, or small non-production changes", owner)
        self.assertIn("default when the repo defines none", owner)
        self.assertIn("No `/er` exemption covers changes to approval, merge, review, evidence, or security rules", owner)

    def test_gate_entrypoints_delegate_applicability_to_owner(self):
        owner = read("pr-lifecycle")
        self.assertIn("accept these final gates, where applicable, in sequence", owner)
        self.assertIn("documentation-only class below or a repo-exempted class", owner)
        self.assertIn("outside any low-risk class the repo's own instructions exempt", read("evidence-review"))
        for name in ("ready", "advice"):
            self.assertIn("`pr-lifecycle`", read(name))
            self.assertIn("Advice applicability", read(name))
        self.assertNotIn("unless a repo-exempted class applies", owner)
        self.assertIn("security, permission, credential, or merge-path code", owner)
        command = " ".join((SKILLS.parent / "commands" / "ready.md").read_text().split())
        self.assertIn("draft-first-pr", command)
        self.assertNotIn("including repo-defined exemptions", command)

    def test_advice_boundary_counts_complete_diff_not_net_or_prod_only(self):
        self.assertIn("additions + deletions", self.owner)
        self.assertIn("complete PR diff", self.owner)
        self.assertIn("not net lines or production-only lines", self.owner)
        self.assertIn("actual base", self.owner)
        for example in ("+25/-24 = 49: optional", "+25/-25 = 50: required",
                        "+10/-0 code and +40/-0 docs = 50: required"):
            with self.subTest(example=example):
                self.assertIn(example, self.owner)
        self.assertIn("unknown or incomplete count does not qualify", self.owner)
        self.assertIn("Recompute after a head or base change", self.owner)

    def test_size_exception_does_not_relax_other_gates(self):
        self.assertIn("## Advice applicability", self.owner)
        section = self.owner.split("## Advice applicability", 1)[1].split(" ## ", 1)[0]
        # read() collapses whitespace before splitting; a raw-newline split is wrong here.
        self.assertNotIn("## Coding lifecycle", section)
        self.assertIn("every PR under 50 changed lines", section)
        self.assertIn("50 or more changed lines requires", section)
        self.assertIn("supersedes broader docs/test/non-production `/advice` exemptions", section)
        for gate in ("independent", "security", "evidence", "CI", "merge authorization"):
            self.assertIn(gate, section)
        self.assertNotIn("low-risk PRs under", section)

    def test_small_high_risk_change_keeps_named_code_review_without_forcing_advice(self):
        section = self.owner.split("## Advice applicability", 1)[1].split(" ## ", 1)[0]
        self.assertIn("every PR under 50 changed lines", section)
        self.assertIn("named independent full-diff code/safety reviewer", section)
        self.assertIn("not the author or orchestrator", section)
        self.assertIn("Evidence-only review does not satisfy this code-review gate", section)
        self.assertIn("Preserve stricter repository lanes and quorums", section)

    def test_two_phase_lifecycle_has_final_reviews_after_ready_work(self):
        self.assertIn("mark ready-for-review", self.owner)
        flow = self.owner.split("## Canonical lifecycle", 1)[1].split("## Advice applicability", 1)[0]
        ordered = ("DRAFT", "/es PASS", "/er PASS", "/advice APPROVED",
                   "mark ready-for-review", "/ready work", "final /er PASS",
                   "final /advice APPROVED", "READY", "separate merge authorization")
        cursor = 0
        for token in ordered:
            cursor = flow.index(token, cursor) + len(token)
        self.assertIn("Undrafting starts `/ready`; it does not establish completed readiness", self.owner)
        self.assertIn("final `/er`", read("ready"))
        self.assertIn("final `/advice`", read("ready"))

    def test_final_fix_reopens_affected_gates_without_destructive_freeze(self):
        self.assertIn("If a final review requires a fix", self.owner)
        self.assertIn("rerun affected checks/evidence", self.owner)
        self.assertIn("coordinated candidate SHA", self.owner)
        self.assertIn("not a branch lock", self.owner)
        self.assertIn("does not authorize resets, history rewrites, or discarded work", self.owner)
        self.assertIn("No cycle-count limit", self.owner)

    def test_early_repro_and_ci_diagnosis_precede_final_expensive_capture(self):
        self.assertIn("direct causal reproducer early", self.owner)
        self.assertIn("relevant code and checks have stabilized", self.owner)
        self.assertIn("Do not wait for green to diagnose a failed test", self.owner)
        self.assertNotIn("Get through every applicable draft gate first", self.owner)
        self.assertIn("local-equivalent exception", self.owner)

    def test_receipts_keep_original_tested_sha_and_reviewed_delta(self):
        self.assertIn("original tested SHA", self.owner)
        self.assertIn("current applicability", self.owner)
        self.assertIn("never relabel an old capture as a new run", self.owner)
        self.assertIn("relevant tests", self.owner)

    def test_web_advice_is_optional_and_missing_required_advice_stays_open(self):
        self.assertIn("`/wa` (`/web-advice`) is optional", self.owner)
        self.assertIn("`UNAVAILABLE`", self.owner)
        self.assertIn("leave any dependent readiness", self.owner)
        self.assertIn("`WITHHELD` does not satisfy", self.owner)

    def test_change_impact_distinguishes_initial_gate_from_rerun_depth(self):
        self.assertIn("## Change-impact review and test depth", self.owner)
        self.assertIn("Initial gate applicability", self.owner)
        for term in ("/4layer", "testing-layers", "single-file", "service boundary",
                     "prompt/schema", "browser/UI", "shared fixture", "CI config",
                     "non-production labels", "real-service-only"):
            with self.subTest(term=term):
                self.assertIn(term, self.owner)
        self.assertIn("lowest sufficient layer", self.owner)
        self.assertIn("does not prove model compliance, auth, persistence races, or browser behavior", self.owner)

    def test_every_review_receipt_keeps_gist_sha_and_honest_state(self):
        self.assertIn("## Review records in the PR description", self.owner)
        section = self.owner.split("## Review records in the PR description", 1)[1].split(" ## ", 1)[0]
        for term in ("every review type", "/es", "/er", "/advice", "/wa", "/cs",
                     "native", "gist URL", "exact reviewed SHA", "timestamp", "reviewer",
                     "FAILED", "PENDING", "UNAVAILABLE", "SUPERSEDED", "PUBLICATION BLOCKED"):
            with self.subTest(term=term):
                self.assertIn(term, section)
        self.assertIn("never invent a gist URL or passing verdict", section)
        self.assertIn("not private storage", section)
        self.assertIn("document hashes", section)

    def test_review_ledger_append_is_duplicate_free_and_preserves_evidence(self):
        self.assertIn("review type + phase + reviewed SHA + receipt identity", self.owner)
        self.assertIn("append a new record only when that key or status is new", self.owner)
        self.assertIn("unchanged key and unchanged status are a no-op", self.owner)
        self.assertIn("Preserve prior rounds and visual tables", self.owner)
        self.assertIn("current-applicability review", self.owner)
        self.assertIn("retain the original tested SHA", self.owner)

    def test_evidence_owners_use_claim_boundaries_not_blanket_size_exceptions(self):
        standards = read("evidence-standards")
        layers = read("testing-layers")
        self.assertIn("bounded deterministic claim", standards)
        self.assertIn("fresh focused unit RED/GREEN", standards)
        self.assertIn("not selected by line count alone", standards)
        self.assertNotIn("production changes under 100 delta lines", standards)
        self.assertNotIn("Mock (no `/es` credit)", layers)
        self.assertNotIn("only valid source of `/es` evidence", layers)
        self.assertNotIn("Unit/E2E tests** do not emit `/es` bundles", layers)
        for text in (standards, layers):
            self.assertIn("model compliance", text)
            self.assertIn("persistence races", text)
            self.assertIn("browser behavior", text)

    def test_ready_delegates_green_and_separate_live_merge_authority(self):
        ready = read("ready")
        self.assertNotIn("standing conditional", ready)
        self.assertNotIn("every current-head CI check green", ready)
        self.assertIn("separate live merge authorization", ready)
        self.assertIn("`pr-green-definition`", ready)

    def test_artifact_hosting_is_distinct_from_review_receipt_publication(self):
        standards = read("evidence-standards")
        self.assertIn("underlying evidence artifacts", standards)
        self.assertIn("separate sanitized review receipt", standards)
        self.assertIn("PUBLICATION BLOCKED", standards)
        self.assertNotIn('`Unit-only proof is NOT sufficient`', standards)

    def test_goal_instructions_and_template_use_claim_based_evidence(self):
        goal = read("write-goal")
        template = " ".join((SKILLS / "write-goal" / "templates" / "goal-spec.md").read_text().split())
        for text in (goal, template):
            with self.subTest(text=text[:40]):
                self.assertIn("lowest sufficient layer", text)
                self.assertIn("claims and boundaries", text)
                self.assertNotIn("<100 delta lines", text)
                self.assertNotIn("unit-only is INSUFFICIENT for production changes", text)
                self.assertNotIn("/er PASS (advisory)", text)
                self.assertIn("final", text)

    def test_unit_coverage_keeps_command_result_sha_proof(self):
        coverage = read("evidence-coverage")
        self.assertIn("commands, results, and tested SHA", coverage)
        self.assertIn("CI run/job link", coverage)
        self.assertIn("N/A is not a substitute", coverage)
        self.assertNotIn("layer doesn't require evidence", coverage)
        self.assertNotIn("CI (no local evidence needed)", coverage)

    def test_green_delegates_quality_to_draft_and_final_phases(self):
        green = read("pr-green-definition")
        self.assertIn("draft and ready/final phases", green)
        self.assertIn("do not restate that chain here", green)
        self.assertNotIn("Those quality checks happen in the **draft phase**", green)
        self.assertNotIn("the pre-green quality gates that now live in the draft phase", green)
        self.assertIn("exactly TWO gates", green)

    def test_current_evidence_marker_indexes_sanitized_receipt_without_erasing_history(self):
        self.assertIn("**Evidence**: <gist-url> (head <sha>)", self.owner)
        self.assertIn("one current marker", self.owner)
        self.assertIn("sanitized evidence-review receipt", self.owner)
        self.assertIn("preserve the historical ledger", self.owner)
        self.assertIn("original capture SHAs", self.owner)
        self.assertIn("current `**Evidence**` marker", read("ready"))


if __name__ == "__main__":
    unittest.main()

