# Fixture and installed-CLI boundary guardrails

## Outcome

Prevent recorded payloads and capable stubs from being mistaken for actual
SDK/transport or installed-runner proof. Extend only the existing canonical
end2end-testing and self-hosted-runner-preflight skills and their offline tests.
Preserve fixture-source order and project-local authority; do not duplicate
native-proof policy or the pending generic capability skill.

## Non-goals

No application changes, captures, provider calls, runner repair, host installation,
cleanup, credentials, workflow dispatch or release retry. These wording tests do
not implement application runtime CI guards or prove actual CLI support.

## Acceptance

- The exact candidate test file fails its new instruction assertions against
  baseline 69bce8f4d47d325dfd58343682bdff0ce3903670 and passes on the candidate.
- The existing installer copies both candidate skills byte-identically into an
  isolated temporary CLAUDE_HOME; a 30-second timeout fails with diagnostics.
- Existing CI discovery includes the new test without a new workflow or live job.
- Review verifies no fabricated fixture provenance, executable capability claim,
  personal data, new host operation or unrelated legacy-recipe rewrite.

## User stories

No user-facing application change — this updates engineering instructions only.
As a test author, I need preserved response provenance separated from SDK behavior
qualification so a realistic payload cannot hide a transport ownership defect.
As a runner maintainer, I need exact installed-command evidence and fail-closed
negative tests so a capable stub cannot establish release readiness.
The acceptance checks above cover these instruction changes; application-owned
runtime tests and original execution receipts remain separate follow-ups.

## Proof plan

Run `python3 -m unittest discover -s tests -p test_failure_boundary_skill_contract.py -v`
against baseline and candidate, retaining original START/END/EXIT receipts. The
assertions protect required wording, not semantic correctness of an implementation.
Check patch application and run applicable installer tests. A broad installer
suite in an incomplete staged checkout is incomplete, never a green full suite.

## Mock or justified exemption

UI mock exemption: no UI, visual layout, application flow or displayed data changes.
The installer test uses isolated temporary filesystem inputs with the real
installer; it neither installs on an operator host nor models an SDK/runner.
Recorded application fixtures and runtime negative controls are not supplied here.

## Risk

Additional prose can be mistaken for tested behavior; retain the explicit runtime
proof limits. Revert only these additive sections/tests if needed. Legacy runner
cleanup, Gate 8 and token recipes are outside this change and must not be executed
for this task. Missing behavior proof remains unverified, not implied green.
