---
name: tdd
description: Develop features and fixes test-first with public-interface tests, a Superpowers TDD plan, and the 4layer minimal-repro ladder for blockers.
---

# Test-Driven Development

Use one behavior at a time: write a meaningful failing test, observe the expected
failure, then implement only enough to pass. A plan, historical failure, or old CI
run is not executed RED evidence.

Read the project's instructions, `CONTEXT.md` when present, relevant ADRs, existing
tests, and documented runner before choosing commands or interfaces. Preserve the
user's approved plan, constraints, execution method, and requested endpoint.

## Required companions

Before preparing a TDD plan or reproducing a blocker, read these definitions fully:
- [superpowers-writing-plans](../superpowers-writing-plans/SKILL.md): structure and
  self-check the plan's test-first tasks before implementation.
- [4layer](../4layer/SKILL.md): select and execute the ordered minimal-repro ladder
  for a bug or PR blocker, including its own mandatory companions.

Resolve these paths relative to this skill. In Hermes or a catalog-only runtime,
resolve the exact registered names `superpowers-writing-plans` and `4layer` and read
the returned definitions; do not assume a repository-relative path exists in an
installed home. If a required definition cannot be read, report the missing
companion and pause dependent planning/reproduction. Do not silently substitute a
similarly named workflow or claim the gate passed. Independent read-only inspection
may continue. Loading a skill does not authorize providers, publication, or changes
to shared state.

## Superpowers TDD plan

Use an existing approved plan in place. For a new multi-step request, use
`superpowers-writing-plans` to create the plan; for one small change, the same
per-task checklist can stay in the working plan without inventing a new document.
Respect the user's plan location, scope, checkpoints, and execution choice. Do not
restart brainstorming or replace a plan simply because TDD was invoked.

Each behavior-changing task must be independently testable and carry this sequence:
1. Write one failing test through the agreed public interface, with exact test path
   and assertions grounded in the requirement or independently known example.
2. Run its exact command and specify the expected behavioral RED result.
3. Implement the minimum behavior in the named production file/interface.
4. Rerun the focused test and relevant regressions; specify the GREEN result.
5. Commit the verified slice when commits are within the authorized endpoint.

Self-review the saved task against its requirements, interfaces, and project-wide
constraints. Repair omitted, reordered, or vague test steps before implementation.
Identify uncovered high-risk input classes and give each a test in its owning task.
For a genuinely non-behavioral task, record `TDD: N/A`, the reason, and a concrete
verification command instead of manufacturing a failure. Planning-only requests end
with the plan: unchecked steps describe intended work, never tests already run.

## 4layer reproduction

For a bug or blocker, apply the companion's exact order:
1. Unit tests
2. End-to-end tests
3. MCP/HTTP API tests
4. Browser tests

Start at Layer 1 and move upward only after the current layer passes. Stop at the
first layer that conclusively reproduces the blocker and keep the fix/regression
loop there; do not run unnecessary upper layers. A missing runner, fixture,
credential, or execution capability is `UNSUPPORTED ENVIRONMENT / NO REPRO`, not a
pass and not permission to skip a layer. Report checked paths and the blocker.
Discover project commands instead of copying illustrative runners blindly. Keep
provider/user isolation and existing spending/access limits. Layer labels are
triage hints, not proof of root cause. Follow 4layer's integration-claim gate when
claiming automatic integration, rather than treating a manual run as activation.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. A good
test reads like a specification and survives internal refactors. Before writing it,
name the production behavior change that would make it fail. Expected values come
from requirements or independent examples, not a restatement of implementation.
Read [tests.md](tests.md) for examples and [mocking.md](mocking.md) for boundary mocks.

A **seam** is the public boundary where behavior is observed. Write down the seams
under test and confirm them with the user before writing tests. An explicit seam in
an already-approved plan counts as agreement; do not ask again. If it is ambiguous,
ask which public interface should be tested. Avoid private methods, internal mocks,
and database side channels that bypass the agreed interface.

## Rules of the loop

- **RED:** Write one minimal test, then run it against the unfixed behavior. Confirm
  the failure is the expected assertion, not a typo, import error, or broken fixture.
  If it already passes, investigate the missing case; do not weaken the assertion or
  change production code just to manufacture RED. Historical CI is context only.
- **GREEN:** Implement only that behavior, rerun the same test, and verify relevant
  regressions. Keep tests honest; do not rewrite an expectation merely to pass.
- **Vertical slices:** One seam, one test, one minimal implementation per cycle.
  A risk matrix can guide coverage, but do not write an entire speculative matrix
  before the first implementation or demand that existing valid tests all fail.
- **Refactoring:** Keep unrelated cleanup out of the implementation cycle. Preserve
  this workflow's review-stage refactoring policy; use the available `code-review`
  skill for that stage and rerun tests after any approved refactor.
- **Completion:** Run the project's documented full suite, even when the change
  names a single test file. Report every observed failure by name, including
  pre-existing failures, and distinguish failed, unsupported, skipped, and not-run
  checks. A focused GREEN result is not a green suite. Do not fix unrelated failures
  without appropriate scope; report the remaining verification gap.

Record revision, command, working directory, environment, and fresh RED/GREEN evidence
paths. Report each attempted layer's result and leave unexecuted layers as not run.
Do not claim completion or activation from packaging, planning, or skipped checks.

## Upstream reference

Refreshed against Superpowers v7.0.0 at
`bb92a77741419a4ab5f06e711a283343f1ada0c3`:
[writing-plans](https://github.com/obra/superpowers/blob/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/writing-plans/SKILL.md)
and [test-driven-development](https://github.com/obra/superpowers/blob/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/test-driven-development/SKILL.md).
Use these for provenance and deeper rationale. The local companions and explicit
user constraints own execution; upstream defaults do not override them.
