---
name: tdd
description: Develop features and fixes test-first with public-interface tests, a Superpowers TDD plan, and the 4layer minimal-repro ladder for blockers.
---

# Test-Driven Development

Use this workflow for behavior changes. Read the project instructions, `CONTEXT.md` when present, relevant ADRs and tests, and the documented runner before choosing interfaces or commands. Preserve the approved plan, constraints, execution method, and requested endpoint.

## Required companions

Before preparing a TDD plan or reproducing a blocker, read these definitions completely:
- [superpowers-writing-plans](../superpowers-writing-plans/SKILL.md)
- [4layer](../4layer/SKILL.md)

In Hermes or a catalog-only runtime, resolve those exact registered names and read their returned definitions; do not assume repository-relative paths exist. If a definition is missing, report it and pause only dependent planning or reproduction. Independent read-only inspection may continue. Loading a skill does not authorize provider calls, publication, or shared-state changes.

## Plan and test design

Reuse an existing approved plan. For a new multi-step request, use `superpowers-writing-plans`; for one small change, keep its per-task checklist in the working plan instead of creating a document. Respect the requested plan location, scope, checkpoints, and execution choice. Do not restart brainstorming or replace an approved plan merely because TDD was invoked.

Each behavior-changing task must be independently testable and specify:
1. One meaningful test through the public interface, with its exact path and requirement-based assertions.
2. The exact command and the expected behavioral failure.
3. The minimum implementation and its production interface.
4. The same test rerun plus relevant regression checks and the expected pass.
5. A commit for the verified slice when committing is within the requested endpoint.

Self-review the saved plan against the requirements, interfaces, and project constraints. Fix missing, reordered, or vague test steps before implementation. Cover high-risk input classes in their owning tasks. Planning-only requests end with the plan; unchecked steps are intended work, not tests already run.

Tests should describe observable behavior, use independent expected values, and survive internal refactors. Use public seams; avoid private methods, internal mocks, and database side channels. Read [tests.md](tests.md) and [mocking.md](mocking.md) for design examples. Work one behavior slice at a time; do not demand unrelated valid tests fail or build an exhaustive risk matrix before implementation. Name the public seam under test. An explicit seam in an approved plan is already agreed; ask only when the seam is genuinely ambiguous.

## RED, GREEN, and reproduction

For each behavior slice:
- **RED:** Write one minimal test and run it against the unfixed behavior. Confirm it fails for the expected assertion, not a typo, import error, or broken fixture. If it already passes, investigate the missing case; never weaken an assertion or change production code to manufacture failure. Historical CI is context, not RED evidence.
- **GREEN:** Implement only that behavior, rerun the same test, then run relevant regressions. Keep expectations honest; do not rewrite one merely to pass.
- **Refactor:** Keep unrelated cleanup out of the cycle. Follow the current review-stage refactoring policy, use the available `code-review` skill when that stage requires review, and rerun affected checks after an approved refactor.

For a bug or PR blocker, follow [4layer](../4layer/SKILL.md) in order: unit, end-to-end, MCP/HTTP, then browser. Move upward only when the current layer passes; stop at the first conclusive reproduction. Discover the project's runner instead of copying example commands blindly. A missing runner, fixture, credential, or execution capability is `UNSUPPORTED ENVIRONMENT / NO REPRO`, never a pass or permission to skip a layer. Keep provider and user state isolated, respect existing spend/access limits, and treat layer labels as triage hints rather than root-cause proof. Follow the companion's evidence and integration-claim requirements.

## Scope and completion

For a genuinely non-behavioral task, record `TDD: N/A`, why, and a concrete verification command; do not manufacture a failing test. Keep checks proportional to the changed behavior. Do not run an unfiltered local suite when repository policy assigns it to CI or prohibits it. Report each attempted check as passed, failed, unsupported, skipped, or not run; include observed failures, including pre-existing ones. Do not fix unrelated failures. A focused pass proves only its stated claim.

Record the revision, command, working directory, environment, and paths to fresh RED/GREEN evidence. State each attempted reproduction layer and leave unexecuted layers explicitly not run. Packaging, planning, or skipped checks alone do not prove completion or activation.

## Upstream reference

Refreshed against Superpowers v7.0.0 at
`bb92a77741419a4ab5f06e711a283343f1ada0c3`:
[writing-plans](https://github.com/obra/superpowers/blob/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/writing-plans/SKILL.md)
and [test-driven-development](https://github.com/obra/superpowers/blob/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/test-driven-development/SKILL.md).
These links provide provenance and rationale; local companions and explicit user constraints govern execution.
