---
name: redgreen
description: "Debug a reported error with fresh red evidence, a minimal fix, and same-scenario green proof."
---

# Red–green debugging

Use for a specific reported error, distinct from general feature TDD. Search existing
tests first, choose the narrowest meaningful feedback loop, and capture a fresh failure
before changing implementation code. A historical report, old CI result, stack trace,
or observation in a transcript is context only and cannot satisfy the RED gate.

## RED

Parse the exact symptom and expected behavior. Locate relevant unit, integration, and
end-to-end tests. Use the accepted `diagnosing-bugs` feedback-loop procedure: the loop
must drive the actual bug code path and assert the user's exact symptom. Run it now
with the discovered project runner, and record command, revision, timestamp,
environment summary, and normalized signature (`ErrorType | key tokens | file:function`).

When existing tests do not catch the symptom, create or update the smallest meaningful
regression test at a seam that actually reaches it, within authorized scope. Run that
test to capture a fresh failing test before implementation changes. If no correct test
seam exists, document that finding and use a recorded symptom-reaching reproduction
command rather than a shallow proxy assertion.

Document why a new test was necessary and use the project's regression naming
convention; where none exists, use `test_regression_<issue-id>_<behavior>()` with a
valid language-specific identifier. Consider unit, fixture-based functional, and
real-service integration tests by the boundary involved, rather than choosing a test
label as proof of coverage. Capture reproduction, fix validation, and related
regression coverage without duplicating tests that already exercise the same case.

For model behavior, deterministic contract checks prove only their stated contract;
a prompt-string assertion cannot substitute for reproducing the behavioral symptom.
Use a live service/model run when the actual failure boundary requires it, and only
with an authorized isolated instrument. Do not treat missing capability as a pass.

For intermittent failures, measure the reproduction rate and retain failing inputs,
timing, and output. A characterized intermittent repro is valid evidence; do not impose
a fixed run count or probability threshold. If the loop is not yet red-capable, report
the missing evidence and attempts, then continue authorized source/trace inspection
and reversible diagnostic instrumentation to build it. Keep hypotheses provisional;
do not change behavior or claim a cause or fix without relevant failure evidence.
Ask only for unavailable capabilities, artifacts, or changes outside authorization.

## CODE and GREEN

Implement the smallest change that addresses the observed cause. Re-run the exact same
feedback loop and scenario, then related regression checks. Confirm the original signature is
gone, expected behavior is present, and no new failure appeared. Re-run enough times to
detect relevant flakiness; do not turn a flaky pass into certainty. A green result must
be tied to the same scenario and runner as RED.

Where relevant, retain seeds, clock controls, fixtures, and captured failing inputs
so RED and GREEN remain comparable. Inspect passing assertions and expected behavior;
absence of the old error alone is insufficient. Before concluding, audit the flow:
fresh symptom-reaching RED, minimal causal CODE, same-scenario GREEN, and related
regression results. If this review exposes a missing step, report it and complete the
authorized verification rather than presenting the workflow as finished.

## Contract

Report RED, CODE, GREEN, and remaining uncertainty with sanitized evidence paths. Do not
invoke a fixed provider, branch, remote, or interpreter by name when the repository
offers discovery. `/consensus` or an integration-verification skill is an optional
review dependency, not an automatic command or approval gate.
