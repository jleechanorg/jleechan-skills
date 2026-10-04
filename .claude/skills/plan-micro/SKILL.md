---
name: plan-micro
description: Create or revise an executable engineering plan by writing one full Ironclad contract for the overall objective, decomposing it into TDD micro-beads, and writing a full Ironclad contract for every bead, then refreshing the hand-off with /nextsteps. Use for /plan-micro, granular planning, or work needing integration-first TDD pairs and independently verifiable evidence. Plan only; do not implement or activate session state.
---

# Plan micro

Turn the current goal into a dependency-ordered bead plan and a durable
`~/roadmap/` handoff. Plan only. Do not implement the code. Use `/e` for execution only when authorized.

## Timeline, parallel lanes, and milestones (mandatory)

Read and apply `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/references/timeline-milestones.md`
on every invocation. Always include a timeline, maximize useful independent
lanes within the measured resource ceiling, and report milestones every
20 minutes with an hourly rollup during active work. Preserve this command's
planning, handoff, and execution authorization boundaries.

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
- Use the repository’s configured Beads owner (`br` where applicable); never edit raw records to bypass it.

## Discover the work

Run discovery in parallel per `/p` (planning only, no execution): enumerate independent items and keep a
single coordinating writer for Bead and roadmap mutations. Prefer cheaper
parallel read-only subagents for independent discovery lanes, code-path
tracing, evidence inventory, and adversarial contract review. Use the locally
available lower-cost route (for example the canonical Luna wrapper)
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
including test, implementation, docs, migration, and evidence beads. The
`/ironclad` "Executor-grade contracts" block set is the only contract shape; the
subsections below add plan-micro obligations and proof-grading checks, never a
second template. If a bead's Goal, Steps, and criteria disagree, the bead is
not finished.

1. Draft the exact bead goal and boundaries.
2. Write the dedicated document where the repository keeps plans (for example
   `docs/superpowers/plans/ironclad/<bead-id>-goal-ironclad-<PST-date>.md` on
   the PR branch) and leave a pointer at
   `~/roadmap/<project-slug>/ironclad/<bead-id>-goal-ironclad-<PST-date>.md`.
   When the repository has no such convention, the roadmap path is canonical.
3. Persist the resulting full contract in that bead's description and link the
   dedicated document. Preserve
   its prior-failure warning and its binary, executable, externally anchored,
   anti-gaming, iterate-until criteria (count per the `/ironclad` count rule).
4. Add the bead-specific proof commands, independent verifier, failure
   condition, LOC budget, owned files, dependency IDs, and the executor blocks
   required by the weak-executor standard below.

A shared parent contract does not satisfy this rule. Each bead carries a full,
bead-specific contract; a one-line acceptance summary is not sufficient. Planning remains document-only and must not start execution.

### Weak-executor standard (mandatory for every bead)

Write every bead as if Haiku 4.5, Gemini 3.8 Flash, or GPT Luna will execute it
with only the bead text and a repo checkout, with no access to this planning
session and no ability to make a judgment call. The planner makes every
decision in the bead text. Each bead body embeds the `/ironclad`
"Executor-grade contracts" block set verbatim and in order (Environment, Goal,
Reuse, Steps, RED, GREEN, Do not, Stop when, Report), follows its rules, and
ends with the criteria table. That section is normative; do not restate it
here. Plan-micro adds only these obligations:

- **Self-contained across beads.** When a value comes from another bead's
  artifact (a runbook table, a branch SHA created later), the bead carries an
  explicit `read <path> § <heading>` step and states what to do if the artifact
  is absent. A bead may not rely on the executor having read the overall
  contract or a sibling bead.
- **Readback before saving.** Hand the bead text alone to a fresh weak-tier
  agent and ask for its command list with GUESS marks. Record the GUESS count in
  the plan document; a bead may not be created while any GUESS remains.
- **No grandfathering.** A bead already in execution when the standard changes
  is brought to the standard before its verify bead runs.
- **Verifier tier.** Name the verifier tier per bead. A weak-tier verifier is
  allowed only when every proof in the bead is self-grading; judge-graded
  criteria name a judge model of a different family from the generator.

### Definition-of-done is a literal, not a sentence

Apply the `/ironclad` "Derived, not asserted" rules to every bead. A bead's
proof is a **self-grading command** at a named SHA whose last line is
`PASS <id>` or `FAIL <id>`, never prose the implementer can satisfy by writing
it and never a literal the verifier must compare by eye.

```
BAD   "Add contract tests for the three spell-slot shapes and report results."
BAD   proof: python3 -m pytest tests/test_feature.py -q ; expect `24 passed`
GOOD  proof: N=$(python3 -m pytest tests/test_feature.py -q -p no:randomly | grep -oE '^[0-9]+ passed' | cut -d' ' -f1); [ "${N:-0}" -ge 24 ] && echo PASS T1 || echo FAIL T1 n=$N
      at:     the bead's final committed SHA, re-executed by the verifier
      fail:   last line is not `PASS T1`, or output pasted rather than re-run
```

Rules the bead table must satisfy:

1. **One self-grading proof command per criterion.** "Tests pass" is not a
   proof; a command whose last line is `PASS T1` is. "CI green" is not a proof;
   the `statusCheckRollup` filter that prints `PASS` only when 0 non-SUCCESS is.
2. **The verifier re-executes** (ironclad Anti-gaming). The plan names who
   re-runs each proof, and it is never the implementer and never the plan
   author. The orchestrator that wrote the plan is an author for this purpose
   and may not close its own beads; use a cross-model reviewer or CI.
3. **Atomize in the script, not in the bead count.** Do not create one bead per
   falsifiable number — past roughly 10–20 beads, implementers stop reading
   contracts and the gate loses force. Keep one bead per reviewable deliverable
   (each deliverable still carries its own TEST bead and IMPL bead per the pair
   rule above) and put the individual assertions inside its proof script or
   test file, so the agent-facing contract stays one command with one exit
   code while the atoms live in code.
4. **Bind outputs to SHAs.** Every proof references the SHA it was run at;
   when HEAD moves, staleness follows ironclad's Materiality rule.
5. **Name the tool traps in the bead when they apply**: `gh pr checks` summary
   hides SKIPPED/NEUTRAL; empty git output renders as `ok` in the Claude Code
   harness (other harnesses differ; use the canonical self-grading forms); a
   published artifact drifts from its source after copy. A bead that reports CI
   state, tree state, or publishes an artifact must state which trap it guards
   against and how.

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
7. Parallel execution waves, lane ownership and capacity limits, an estimated
   timeline with 20-minute milestones and hourly rollups, and the final
   independent verification gate.

Create or update the beads in the owning store, add dependencies, then re-read every saved description. Verify that each coding pair is test-first, no bead
mixes test and non-test files, each implementation bead states its line target
and explains any overrun, and every bead has a full ironclad contract and
dedicated document. A line-count
overrun alone is never a blocker.

## Run /nextsteps before reporting

After the beads and plan are written and re-read, run `/nextsteps` (default
mode) so the hand-off state is refreshed in the same pass: update the newest
relevant nextsteps doc rather than creating one, point its work queue at the
new bead DAG and plan path, add the roadmap activity entry and README date
link, and append a learnings entry only if the planning surfaced a new lesson.
Planning is not complete until the nextsteps artifacts name the plan path and
the first bead a coder should pick up. This step is document-only; it must not
start execution.

## Completion report

Return the roadmap path and a compact table of bead IDs, TEST or IMPL type,
goal, dependency, files, line budget, and proof command. Report counts for
beads created, beads reused, TDD pairs, integration tests, unit-test exceptions,
ironclad contracts, distinguishing the one overall contract from the
per-bead contracts, and weak-executor readiness as `N/N beads at zero GUESS
on readback`, naming the executor tier and the verifier tier per bead. Name the nextsteps doc that was updated. List only true
blockers that require human authority.

The three-day baseline that informed these rules is in
[references/history-baseline-2026-08-04-06.md](references/history-baseline-2026-08-04-06.md).
