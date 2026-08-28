---
name: plan-micro
description: Create or revise an executable engineering plan by writing one full Ironclad contract for the overall objective, decomposing it into TDD micro-beads, and writing a full Ironclad contract for every bead. Use for /plan-micro, granular planning, or work needing integration-first TDD pairs and independently verifiable evidence. Plan only; do not implement or activate session state.
---

# Plan micro

Turn the current goal into a dependency-ordered bead plan and a durable
`~/roadmap/` handoff. Plan only. Do not implement the code.

## Harden the overall objective first

Before decomposition, run the full `/ironclad` document workflow for the
overall objective. Save or update its dedicated roadmap document and use its
exit criteria as the parent contract for the plan. This is mandatory: a short
summary in the micro-plan is not a substitute for the full overall contract.

Do not activate session state or begin execution. Record the overall contract
path in the micro-plan and in the parent Bead, if one exists.

## Operating mode

- Do not ask the user questions. Inspect the repo, history, roadmap, PRs, and
  beads. Make the recommended choice and record any assumption that affects
  scope.
- Consider two or three viable decompositions internally. Select the smallest
  design that meets the goal, and write only the recommended choice.
- Reuse or revise the newest relevant roadmap plan and open beads before
  creating artifacts. Do not duplicate active work.
- Use PST dates. Resolve current PR and branch state live before citing it.
- Use `br` for bead operations. If the repository has an owning command such
  as `bd`, follow its local instructions instead.

## Discover the work

Run discovery through `/e` with `/p`: enumerate independent items and keep a
single coordinating writer for Bead and roadmap mutations. Prefer cheaper
parallel read-only subagents for independent discovery lanes, code-path
tracing, evidence inventory, and adversarial contract review. Use the locally
available lower-cost route (for example Luna or the canonical Spark wrapper)
when it is capable of the bounded task. Gather these lanes in parallel:

1. Read repo instructions, the active goal, recent commits, changed files, and
   open PRs.
2. Search relevant chat or memory history and the newest `~/roadmap/` plans.
3. List open beads and inspect each candidate bead's full description and
   dependencies.
4. Trace the real code path and existing test entry points. Prefer an existing
   integration harness over a new unit-test seam.

State the chosen architecture, boundaries, and non-goals in a short decision
record. When evidence is incomplete, choose the smallest reversible scope and
label the assumption. Never pause for preference questions.

## Decompose into micro-beads

Create a bead DAG. Every row must include its bead ID, exact goal, owned files
or narrowly named area, acceptance criteria, dependencies, proof command, and
expected changed-line budget.

Apply these invariants:

1. Never mix tests and non-test code in one bead.
2. For every bead that changes non-test code, create a test bead followed by an
   implementation bead. The implementation bead depends on the test bead.
3. A test bead may modify only tests and test fixtures. Aim for 100 changed test
   lines. A small overrun is acceptable; disclose generated lines separately.
4. An implementation bead may modify only non-test code.
   100 changed non-test lines is a planning target. Count additions plus
   deletions across its owned files. It is not a hard cap.
   A small overrun is acceptable when another split would create an artificial
   boundary or increase coupling. Record the estimate
   and reason. Generated files do not hide hand-written changes.
5. Split work when it is materially beyond 100 lines and a meaningful behavior
   or dependency boundary exists.
   Never stop planning or execution solely because a bead exceeds 100 lines.
   Do not split arbitrary file chunks to hit the target.
6. Put refactors, migrations, documentation, and evidence in separate beads
   when they are independently reviewable. Every refactor or migration bead that changes non-test code still requires a preceding test bead. None may smuggle production changes into a test bead.
7. Assign exclusive write ownership. Parallel beads may read shared files but
   may not write the same file or mutable state.

## Enforce TDD across bead pairs

The test bead owns RED:

- Prefer an integration test that exercises the real boundary and backend.
- Use a unit test only when an integration test cannot expose the behavior at
  reasonable cost. Record the concrete reason in the bead.
- Name the exact command and expected failure caused by missing behavior.
- Close the test bead only after the test fails for that expected reason and
  the failing test is committed without production changes.

The implementation bead owns GREEN:

- Depend on the completed test bead.
- Make the minimum production change, using 100 changed lines as the target.
- Do not edit tests to obtain GREEN. If the test contract is wrong, reopen the
  test bead and correct it there.
- Name the focused passing command and the nearest relevant integration suite.

Create another pair for the next behavior. Do not group several RED/GREEN
cycles into one large bead.

## Ironclad every bead

Define each bead's goal through the full `/ironclad` document workflow,
including test, implementation, docs, migration, and evidence beads.

1. Draft the exact bead goal and boundaries.
2. Write or update a dedicated document at
   `~/roadmap/<project-slug>/ironclad/<bead-id>-goal-ironclad-<PST-date>.md`.
3. Persist the resulting full contract in that bead's description and link the
   dedicated document. Preserve
   its prior-failure warning and 3-7 binary, executable, externally anchored,
   anti-gaming, iterate-until criteria.
4. Add the bead-specific proof commands, independent verifier, failure
   condition, LOC budget, owned files, and dependency IDs.

A shared parent contract does not satisfy this rule. Each bead carries a full,
bead-specific contract with 3-7 criteria; a one-line acceptance summary is not
sufficient. Planning remains document-only and must not start execution.

## Write and sync the plan

Prefer updating the newest relevant plan. Otherwise write
`~/roadmap/YYYY-MM-DD-<scope>-plan-micro.md` with:

1. Goal, recommended decision, assumptions, and non-goals.
2. Current branch, PR, and bead state.
3. Dependency-ordered bead table with test and implementation pairs visible.
4. The overall Ironclad contract link plus every per-bead Ironclad contract
   link and embedded full criteria.
5. RED and GREEN commands, expected outcomes, and integration-test rationale.
6. File ownership and changed-line budgets.
7. Parallel execution waves and the final independent verification gate.

Create or update the beads in the owning store, add dependencies, then re-read every saved description. Verify that each coding pair is test-first, no bead
mixes test and non-test files, each implementation bead states its line target
and explains any overrun, and every bead has a full ironclad contract and
dedicated document. A line-count
overrun alone is never a blocker.

## Completion report

Return the roadmap path and a compact table of bead IDs, TEST or IMPL type,
goal, dependency, files, line budget, and proof command. Report counts for
beads created, beads reused, TDD pairs, integration tests, unit-test exceptions,
and ironclad contracts, distinguishing the one overall contract from the
per-bead contracts. List only true blockers that require human authority.

The three-day baseline that informed these rules is in
[references/history-baseline-2026-08-04-06.md](references/history-baseline-2026-08-04-06.md).

