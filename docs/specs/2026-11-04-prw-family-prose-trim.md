# Specification: trim the /prw skill family prose and resolve its contradictions

- **Outcome:** the `prw` install profile's skills (pr-lifecycle, evidence-standards, evidence-review, pr-green-definition, testing-layers, pr-workflow-manager, code-standards, ready, draft-first-pr) say the same rules in fewer words, with each duplicated rule kept once in its canonical owner. The six contradictions the trim surfaced are resolved by the owner-delegated decisions below, so each rule has one reading.
- **Non-goals:** changing any gate, threshold, quorum or authorization beyond the six decisions below; editing `advice` or `static-review` (owned by #681); editing `portable/skills/` copies; adding or removing `../<skill>/` or `skills/<skill>/` references, which would change install-profile closures and README/INSTALL counts; restructuring pr-lifecycle's overlapping small-change paths; moving the project-specific BigQuery traps out of `evidence-review`; changing scripts or tests.
- **Acceptance:**
  - Every removed sentence is either a duplicate whose rule survives in its canonical home, or covered by one of the decisions below.
  - The set of skill links in each changed file is unchanged, apart from the corrected `ui-bug-proof` anchor target.
  - All `§ <heading>` and `pr-lifecycle/SKILL.md#anchor` references still resolve.
  - The verdict set in `evidence-standards` and `evidence-review` is PASS / PARTIAL / FAIL / INCONCLUSIVE only.
  - The installer, catalog, command-closure, lifecycle-contract, portability and workflow-command-pair test modules pass.
- **User stories:** no user-facing change. These are agent instruction files. An agent running `/prw`, `/er`, `/es`, `/green` or `/cs` reads less text and meets no rule stated two incompatible ways.
- **Proof plan:** run the test modules listed in the PR body at head; word-diff every deletion against the new text; `/advice` (the diff is 50 or more lines) and an independent adversarial full-scope review, because agent instructions change.
- **Mock:** exempt. There is no UI.
- **Risk:** medium. A prose trim can drop a rule silently, and the decisions change how evidence is graded. Mitigations: deletions limited to duplicates with a named surviving home, the decisions recorded here, and independent review of the full diff.

## Owner-delegated decisions (2026-11-04)

1. **Verdict vocabulary.** `INSUFFICIENT` verdicts in `evidence-standards` (envelope rule, SDK-mock rule, Example 3) and `evidence-review` check 4 become `FAIL`. Other skills that use `INSUFFICIENT` are out of scope for this PR.
2. **Media hosting.** `evidence-standards` owns evidence classes and hosting. `evidence-review` check 5 defers to it: GCS is the default host, authorized private hosting is acceptable, evidence is never made public to pass a link check, and `releases/download/untagged-*` links are a red flag. The "public GitHub repository release required" grading is removed.
3. **Visual gates.** The Stage 5 `VISUAL APPROVED` approver in `pr-lifecycle` must be independent of the `/er` evidence seat, matching draft gate 4 (`/visual-verification`). An `/er` visual lane counts only when a seat other than the one that produced or reviewed the evidence runs it.
4. **Retained review integrations scope.** The broader, stricter canonical wording in `pr-lifecycle` stays: any missing integration leaves every dependent readiness or plan-approval gate unmet.
5. **code-standards.** `N-A` is allowed only with a one-line reason. Smoke-test mode triggers only when the argument is exactly `smoke-test`, matching `document-standards`.
6. **Broken anchor.** `ui-bug-proof` points at the `evidence-standards` heading that covers UI bug-fix proof and environment fidelity: "UI changes require a genuine implementation BEFORE/AFTER comparison".
