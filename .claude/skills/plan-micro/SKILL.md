---
name: plan-micro
description: Create or revise an executable engineering plan by writing one full Ironclad contract for the overall objective, decomposing it into TDD micro-beads, and writing a full Ironclad contract for every bead, then refreshing the hand-off with /nextsteps. Use for /plan-micro, granular planning, or work needing integration-first TDD pairs and independently verifiable evidence. Plan only; do not implement or activate session state.
---

# Plan micro

Turn the current goal into a dependency-ordered bead plan and a durable `${ROADMAP_DIR:-$HOME/roadmap}/` handoff (skip the handoff and say so when that directory is absent). Plan only; do not implement the code. Use `/e` for execution only when authorized. Ironclad rules referenced below live in [ironclad](../ironclad/SKILL.md); this skill adds plan-micro obligations and does not restate them.

## Timeline, parallel lanes, and milestones (mandatory)

Read and apply `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/references/timeline-milestones.md` on every invocation. Always include a timeline, maximize useful independent lanes within the measured resource ceiling, and report milestones every 20 minutes with an hourly rollup during active work. Preserve this command's planning, handoff, and execution authorization boundaries.

## Harden the overall objective first

Before decomposition, run the full `/ironclad` document workflow for the overall objective, save or update its dedicated roadmap document, and use its exit criteria as the plan's parent contract. Mandatory: a short summary in the micro-plan does not substitute for the full overall contract. Do not activate session state or begin execution. Record the overall contract path in the micro-plan and in the parent Bead, if one exists.

## Operating mode

- Do not ask the user questions. Inspect the repo, history, roadmap, PRs, and beads; make the recommended choice and record any scope-affecting assumption.
- Consider two or three viable decompositions internally; write only the smallest design that meets the goal.
- Reuse or revise the newest relevant roadmap plan and open beads before creating artifacts. Do not duplicate active work.
- Use PST dates. Resolve current PR and branch state live before citing it.
- Use the repository’s configured Beads owner (`br` where applicable); never edit raw records to bypass it.

## Discover the work

Run discovery in parallel per `/p` (planning only, no execution), with a single coordinating writer for Bead and roadmap mutations. Prefer cheaper parallel read-only subagents (for example the canonical Luna wrapper, when capable of the bounded task) for discovery, code-path tracing, evidence inventory, and adversarial contract review. Lanes:

1. Repo instructions, the active goal, recent commits, changed files, open PRs.
2. Relevant chat or memory history and the newest `${ROADMAP_DIR:-$HOME/roadmap}/` plans.
3. Open beads, with each candidate's full description and dependencies.
4. The real code path and existing test entry points; prefer an existing integration harness over a new unit-test seam.

Record the chosen architecture, boundaries, and non-goals in a short decision record. When evidence is incomplete, choose the smallest reversible scope and label the assumption; never pause for preference questions.

## Decompose into micro-beads

> **PR mapping:** Treat TEST/IMPL micro-beads as task and commit checkpoints on
> one shared feature branch and PR; never create one PR per micro-bead or a
> TEST-only PR separate from its IMPL. Follow [PR quantity control](../pr-quantity-control/SKILL.md)
> for any coarse stage-PR limits.

Create a bead DAG. Every row includes bead ID, exact goal, owned files or narrowly named area, acceptance criteria, dependencies, proof command, and expected changed-line budget. Invariants:

1. Never mix tests and non-test code in one bead. Every change to non-test code gets a test bead followed by an implementation bead that depends on it.
2. A test bead modifies only tests and test fixtures; an implementation bead only non-test code.
3. 100 changed lines per bead (additions plus deletions across owned files) is a planning target, not a hard cap. A small overrun is acceptable when another split would create an artificial boundary or more coupling; record the estimate and reason. Disclose generated lines separately; generated files do not hide hand-written changes.
4. Split when work is materially beyond 100 lines and a meaningful behavior or dependency boundary exists. Never split arbitrary file chunks to hit the target, and never stop planning or execution solely because a bead exceeds 100 lines.
5. Put refactors, migrations, documentation, and evidence in separate beads when independently reviewable. A refactor or migration bead that changes non-test code still needs a preceding test bead; none may smuggle production changes into a test bead.
6. Assign exclusive write ownership. Parallel beads may read shared files but may not write the same file or mutable state.

## Enforce TDD across bead pairs

The test bead owns RED:

- Prefer an integration test that exercises the real boundary and backend; use a unit test only when integration cannot expose the behavior at reasonable cost, recording the concrete reason in the bead.
- Name the exact command and the expected failure caused by missing behavior.
- Close the test bead only after the test fails for that reason and is committed without production changes.

The implementation bead owns GREEN:

- Depend on the completed test bead; make the minimum production change.
- Do not edit tests to obtain GREEN. If the test contract is wrong, reopen and correct the test bead.
- Name the focused passing command and the nearest relevant integration suite.

Create another pair for the next behavior; never group several RED/GREEN cycles into one large bead.

## Ironclad every bead

Define every bead's goal (test, implementation, docs, migration, evidence) through the full `/ironclad` document workflow. The ironclad [Executor-grade contracts](../ironclad/SKILL.md#executor-grade-contracts-when-a-weaker-model-will-execute) block set is the only contract shape; the subsections below add obligations, never a second template. If a bead's Goal, Steps, and criteria disagree, the bead is not finished.

1. Draft the exact bead goal and boundaries.
2. Write the dedicated document where the repository keeps plans (for example `docs/superpowers/plans/ironclad/<bead-id>-goal-ironclad-<PST-date>.md` on the PR branch) and leave a pointer at `${ROADMAP_DIR:-$HOME/roadmap}/<project-slug>/ironclad/<bead-id>-goal-ironclad-<PST-date>.md`. With no repository convention, the roadmap path is canonical.
3. Persist the full contract in the bead description and link the dedicated document. Preserve its prior-failure warning and criteria meeting all six [ironclad requirements](../ironclad/SKILL.md#what-ironclad-means-all-six-required-per-criterion) (count per the `/ironclad` count rule).
4. Add the bead-specific proof commands, independent verifier, failure condition, LOC budget, owned files, dependency IDs, and the executor blocks.

A shared parent contract or one-line acceptance summary does not satisfy this rule; each bead carries a full, bead-specific contract. Planning remains document-only and must not start execution.

### Weak-executor standard (mandatory for every bead)

Write every bead as if Haiku 4.5, Gemini 3.8 Flash, or GPT Luna will execute it with only the bead text and a repo checkout, no access to this planning session, and no ability to make a judgment call; the planner makes every decision in the text. Each bead body embeds the executor-grade block set verbatim and in order (Environment, Goal, Reuse, Steps, RED, GREEN, Do not, Stop when, Report), follows its rules, and ends with the criteria table. Plan-micro adds:

- **Self-contained across beads.** When a value comes from another bead's artifact (a runbook table, a branch SHA created later), the bead carries an explicit `read <path> § <heading>` step and states what to do if the artifact is absent.
- **Readback before saving.** Run ironclad's GUESS-mark self-check on each bead and record the GUESS count in the plan document; a bead may not be created while any GUESS remains.
- **No grandfathering.** A bead already in execution when the standard changes is brought to the standard before its verify bead runs.
- **Verifier tier.** Name the verifier tier per bead. A weak-tier verifier is allowed only when every proof in the bead is self-grading.

### Definition-of-done is a literal, not a sentence

Apply ironclad's [Derived, not asserted](../ironclad/SKILL.md#derived-not-asserted-binds-every-agent-including-the-orchestrator) rules and canonical self-grading forms to every bead: its proof is a self-grading command at a named SHA whose last line is `PASS <id>` or `FAIL <id>`, never prose the implementer can satisfy by writing it.

```
BAD   "Add contract tests for the three spell-slot shapes and report results."
BAD   proof: python3 -m pytest tests/test_feature.py -q ; expect `24 passed`
GOOD  proof: N=$(python3 -m pytest tests/test_feature.py -q -p no:randomly | grep -oE '^[0-9]+ passed' | cut -d' ' -f1); [ "${N:-0}" -ge 24 ] && echo PASS T1 || { echo FAIL T1 n=$N; exit 1; }
      at:     the bead's final committed SHA, re-executed by the verifier
      fail:   last line is not `PASS T1`, or output pasted rather than re-run
```

Rules the bead table must satisfy:

1. **One self-grading proof command per criterion** ("tests pass" and "CI green" are not proofs; the `statusCheckRollup` filter is).
2. **Name who re-executes each proof**: never the implementer and never the plan author. The orchestrator that wrote the plan is an author and may not close its own beads; use a cross-model reviewer or CI.
3. **Atomize in the script, not in the bead count.** Do not create one bead per falsifiable number: past roughly 10–20 beads, implementers stop reading contracts and the gate loses force. Keep one bead per reviewable deliverable (each still with its own TEST and IMPL bead) and put the individual assertions in its proof script or test file: one command, one exit code, atoms in code.
4. **Bind outputs to SHAs.** Every proof names the SHA it ran at; when HEAD moves, staleness follows ironclad's Materiality rule.
5. **Name the applicable tool traps in the bead** (`gh pr checks` hides SKIPPED/NEUTRAL; empty git output renders as `ok` in the Claude Code harness, other harnesses differ, so use the canonical self-grading forms; a published artifact drifts from its source). A bead that reports CI state or tree state, or publishes an artifact, states which trap it guards against and how.

## Write and sync the plan

Prefer updating the newest relevant plan. Otherwise write `${ROADMAP_DIR:-$HOME/roadmap}/YYYY-MM-DD-<scope>-plan-micro.md` with:

1. Goal, recommended decision, assumptions, and non-goals.
2. Current branch, PR, and bead state.
3. Dependency-ordered bead table with test and implementation pairs visible.
4. The overall Ironclad contract link plus every per-bead Ironclad contract link and embedded full criteria.
5. RED and GREEN commands, expected outcomes, and integration-test rationale.
6. File ownership and changed-line budgets.
7. Parallel execution waves, lane ownership and capacity limits, an estimated timeline with 20-minute milestones and hourly rollups, and the final independent verification gate.

Create or update the beads in the owning store, add dependencies, then re-read every saved description to verify the invariants above: each coding pair is test-first, no bead mixes test and non-test files, each implementation bead states its line target and explains any overrun, and every bead has a full ironclad contract and dedicated document. A line-count overrun alone is never a blocker.

## Run /nextsteps before reporting

After the beads and plan are written and re-read, run `/nextsteps` (default mode) in the same pass: update the newest relevant nextsteps doc rather than creating one, point its work queue at the new bead DAG and plan path, add the roadmap activity entry and README date link, and append a learnings entry only if planning surfaced a new lesson. Planning is not complete until the nextsteps artifacts name the plan path and the first bead a coder should pick up. This step is document-only and must not start execution.

## Completion report

Return the roadmap path and a compact table of bead IDs, TEST or IMPL type, goal, dependency, files, line budget, and proof command. Report counts of beads created, beads reused, TDD pairs, integration tests, unit-test exceptions, and ironclad contracts (the one overall contract separate from per-bead contracts), plus weak-executor readiness as `N/N beads at zero GUESS on readback`, naming the executor and verifier tier per bead. Name the nextsteps doc updated. List only true blockers that require human authority.

These rules came from a three-day baseline of one roadmap: about half (48%) of the Markdown additions were executable planning artifacts, while 15 of 16 sampled formal plans met the six-field granularity rubric.
