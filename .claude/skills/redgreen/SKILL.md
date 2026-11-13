---
name: redgreen
description: "Strict test-first debugging for one reported bug: fresh behavioral RED, the smallest root-cause fix, same-test GREEN, and relevant regressions. Use for /redgreen or /rg; use /tdd for feature work."
---

# Red-green debug and fix

Use this workflow for one reported bug, not for a new feature. Preserve the
approved plan and project instructions. Read [tdd](../tdd/SKILL.md) for
test-first planning and [4layer](../4layer/SKILL.md) for the project's ordered
minimal-reproduction ladder; those companions own their detailed procedures.
Use [root-cause-first](../root-cause-first/SKILL.md) before changing prompts,
schemas, routing, or backend behavior. Run the phases in order and record the
commands and evidence as you go.

## RED — fresh behavioral reproduction

1. Locate the relevant existing test and the repository's documented runner
   before attempting an ad hoc reproduction. Choose the lowest sufficient test
   layer; do not duplicate coverage.
2. Run the test against the unfixed code. RED must be a fresh, real test
   execution in this session, before the production change, that fails on the
   expected behavioral assertion or matches the reported runtime/provider error
   signature. An unrelated import, setup, fixture, tool, provider, or environment
   failure is not RED.
3. If no existing test catches the report, add or update one minimal
   public-interface test. Ground its assertion in the requirement or an
   independent example; never weaken it or manufacture a failure.
4. Record the exact command, working directory, current git SHA, relevant
   environment/provider/model, timestamp, and concise failure signature/output.
5. If neither the behavioral assertion failure nor the reported error signature
   can be reproduced, stop before changing production code and report the
   missing proof as the blocker.

## CODE — smallest root-cause fix

1. Trace the shared cause with the repository's existing helpers and owners,
   then implement only the smallest change that addresses the reproduced
   behavior. Keep unrelated cleanup and refactoring out of this cycle.
2. Keep the test and expected values honest. Do not add a fallback, provider
   workaround, network retry, or extra model call to force GREEN.

## GREEN — same test and relevant regressions

1. Run the exact RED test and command again after the fix. It must pass on the
   intended behavioral assertion or stop producing the reported error signature,
   demonstrating that the original failure is resolved; do not rewrite the
   expectation to obtain GREEN.
2. Run the relevant regression checks selected by the repository's testing-layer
   owner, plus the original scenario when it is distinct. Do not run an
   unfiltered local suite when project policy assigns it elsewhere.
3. Record each command, result, current SHA, working directory, and relevant
   environment. Distinguish passed, failed, skipped, unsupported, and not-run
   checks; do not claim broader coverage than the evidence supports.

## ADVICE — mandatory Phase 4

After GREEN, run `/advice` for every invocation. It provides source review at
the exact target and records its target-bound verdict and findings. Keep that
source approval separate from the execution receipts: an `APPROVED` verdict
does not prove that RED ran before the change, that the same test passed after
it, or that relevant regressions passed. Those claims require their own
recorded commands, results, and tested revisions from the RED/GREEN workflow.
Record the advice result separately before declaring the fix complete. Follow the active
[advice](../advice/SKILL.md) skill for its review procedure.

## Review and naming

- Name a newly required regression test
  `test_regression_<issue-id>_<behavior>()` only when that convention fits the
  repository; do not add a duplicate test.

The non-negotiable loop is: fresh failure on the behavioral assertion or
reported error signature before the fix → smallest implementation → the same
test GREEN → relevant regression evidence. Historical reports, old CI results,
logs, stack traces, plans, and observations are context, not RED proof.
