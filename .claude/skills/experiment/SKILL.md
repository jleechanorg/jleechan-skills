---
name: experiment
description: "Design and run controlled comparisons of skills, CLAUDE.md, AGENTS.md, and prompts using matched tasks, verified instruction loading, randomized labels, blind evaluation, and retained results."
---

# Experiment: compare instruction changes

Use this workflow to measure whether an instruction change improves task outcomes.
Compare the old and revised instructions in the same runtime, using the same
tasks and acceptance criteria. Freeze the design, verify what each subject loads,
collect outputs, then have a separate evaluator score them before revealing the
assignments. Report correctness, instruction following, resource use, and uncertainty.

Contents: [comparison](#choose-the-comparison) · [commands](#commands) ·
[design](#1-freeze-the-design) · [setup](#2-prepare-isolated-subjects-and-verify-loading) ·
[execution](#3-assign-and-execute) · [evaluation](#4-evaluate-before-revealing) ·
[results](#5-reveal-and-report) · [retention](#retain-and-deliver) ·
[example](#example-test-an-edited-skill) · [history](#historical-lesson-retain-the-primary-evidence).

## Choose the comparison

| Question | Workflow |
| --- | --- |
| Do revised skills or instruction files improve behavior? | This workflow; old and new bytes in otherwise matched environments. |
| Is a normal CLI better than its clean profile? | [codexa-bench](../codexa-bench/SKILL.md) or [claudea-bench](../claudea-bench/SKILL.md); compare complete environments. |
| What caused a captured model failure? | [ablation](../ablation/SKILL.md); replay the real input with its control-first procedure. |

## Commands

These are instructions for the agent invoking the skill. The skill does not
include an executable runner. Use available runtime tools and record the actual
commands; creating prompts or directories is preparation, not a completed run.

| Invocation | Action |
| --- | --- |
| `/experiment design <name> <hypothesis>` | Prepare the frozen comparison and runnable plan; launch no subject or evaluator runs. |
| `/experiment execute <name>` | Run the prepared subject tasks within their recorded budget. |
| `/experiment evaluate <name>` | Score frozen anonymous outputs with the prepared rubric. |
| `/experiment reveal <name>` | Reveal assignments and write the comparison. |
| `/experiment autorun <name>` | Carry the authorized comparison through design, execution, evaluation, and reporting. |

Reuse the experiment's existing record on resume. Keep each phase's actual
status and next action there. Resolve missing design choices from the request
and available evidence; ask only when an essential choice remains unresolved.

## 1. Freeze the design

Record these before launching either arm:

- The hypothesis and primary outcome, such as completed tasks without unsupported
  claims, rather than a preference for a particular wording.
- Immutable control and treatment revisions or content hashes. Change one
  instruction component; if several files change together, name the bundle as
  the treatment and attribute the result to that bundle.
- Identical task inputs and shared acceptance criteria, with representative
  failures and successful cases. Distinguish captured incidents from constructed
  scenarios. Keep the expected answers and hypothesis out of subject prompts.
- The scoring rubric, task count, independent runs per arm, run order, resource
  budget, timeout, and permitted recovery. Set repetition based on the question
  and authorized budget before seeing results; one run is a pilot.
- The fixed runtime, model, reasoning setting, tools, permissions, and other
  instructions. Record unavoidable differences and which conclusions they affect.

A formatting requirement used to judge compliance must be available to both
arms through their task contract. If adding that requirement is itself the
treatment, measure the resulting behavior as a policy difference; do not label
the control disobedient for lacking the new instruction.

Use neutral tasks that require the behavior under study. For example, ask for
a delivery brief using supplied deployment and test records; do not tell one
arm which evidence trap to find or show either arm the other one's answer.

## 2. Prepare isolated subjects and verify loading

Use separate disposable workspaces initialized from the same task snapshot.
Keep the live installation unchanged. Give each workspace its selected
instruction version through the runtime's supported loading mechanism.

Verify before scoring any task:

1. The actual launcher, profile and inherited environment select the intended
   arm. Inspect configuration identity without exposing credentials.
2. The runtime loads the selected instruction bytes, with their hashes and
   loading evidence retained. A file on disk or a successful launch alone is
   insufficient. Check discovery limits, disabled instruction loading, global
   overlays, symlinks, hooks and resume state where they affect exposure.
3. The effective model, effort and tool access match the design. A clean
   profile belongs only in an experiment that deliberately tests that profile.

Keep hypothesis, assignments, scoring keys and other subjects' outputs outside
subject-readable workspaces. Preserve task authorization in both arms. Use
isolated fixtures for stateful work; do not duplicate external sends, production
writes, deployments or other consequential actions as benchmark repetitions.

## 3. Assign and execute

Draw the assignment of neutral subject IDs to arms using a random source;
retain the actual draw privately. Use neutral paths and labels that do not
reveal old/new or control/treatment. Randomize or counterbalance run order
when practical and record it.

Give subjects identical neutral task prompts and equivalent starting state.
Do not describe the hypothesis or desired winner. Start fresh sessions and
record any unavoidable experimental awareness; label only the blindness
actually achieved. The coordinator knows the mapping.

Capture each run's input identity, effective configuration, start/end time,
exit or timeout status, complete output and tool trace, and available usage
counters. Verify input/workspace integrity afterward. Count subject descendants
and rework separately when permitted; keep their scope within their arm.

Preserve failed and invalid runs with a reason. A contaminated profile, missing
instruction exposure or changed input invalidates the affected comparison.
Repair the setup under the recorded recovery budget and retain superseded
receipts. Never retry merely to obtain a preferred result or erase a quota
failure. When execution cannot continue, record the exact missing capability
and complete independent preparation or analysis.

## 4. Evaluate before revealing

Freeze and hash the subject outputs. Prepare an anonymous evaluation package
containing the shared task contract, relevant source evidence, fixed rubric,
and outputs. Remove arm-revealing paths and metadata from the evaluation copy;
preserve the originals and a record of those transformations.

Use a fresh evaluator session that did not implement the change or run either
arm. Give it no hypothesis, mapping, profile identities, resource totals or
coordinator conclusions. The coordinator must not supply the blind score.
If the evaluator becomes unblinded, record that and qualify the analysis.

Use executable checks for deterministic requirements and a blind evaluator
for semantic judgments. Check the full response and supporting evidence;
paraphrases count. Do not use Markdown phrase-pinning tests as behavioral proof.

| Dimension | Required scoring basis |
| --- | --- |
| Task completion | Completed accepted tasks / assigned tasks; list omissions. |
| Supported claims | Supported and unsupported claims, with evidence references. |
| Instruction following | Compliance with the shared task contract; name each violation. |
| Evidence quality | Whether cited artifacts establish the claimed outcome. |

Define any weights and 0–100 conversion in the frozen rubric. Retain raw
counts alongside scores. An ambiguous key gets a documented adjudication:
keep the original score and show any revised interpretation separately.
Do not rewrite the rubric after seeing which arm wins.

## 5. Reveal and report

Reveal the retained mapping only after scores are saved. Report the primary
outcome as counts and denominators per arm, plus task-level differences,
failures, uncertainty and the scope of any supported advantage.

Separate quality from resource measurements: elapsed time, tool calls, input,
cached input and output tokens. Include invalid-run and recovery overhead;
identify unmeasured controller work. Cached tokens are not a bill. Several
judgments in one response are not independent trials. Use statistical tests
only when their assumptions and sample size fit the recorded design.

The verdict is `treatment better`, `control better`, `tie on measured outcomes`,
or `inconclusive`, naming the dimension and observations that support it.
Do not infer that fewer tokens preserve quality or that a whole-profile result
establishes the effect of one skill edit.

## Retain and deliver

Use the repository's existing experiment/evidence location, or a task-owned
location allowed by the active environment. Keep:

- Private design, arm mapping, configuration identities and execution log.
- Frozen task inputs, rubric, instruction hashes and loading receipts.
- Raw runs, anonymous evaluation copies, evaluator's scored JSON and N per arm.
- Final report with links to those artifacts and reproducible calculations.

Retain the rubric, both anonymous outputs, scored JSON and N before citing
scores outside the results directory. Use authorized storage and protect secrets
and personal data; public repositories receive only permitted sanitized material.
A Git commit is one retention option. PR creation and external publication
follow the task's actual workflow and authorization.

## Example: test an edited skill

```text
/experiment design delivery-brief "The revised delivery skill improves compliance with the shared handoff requirements."
```

Pin the old skill as control and the revised skill as treatment. Keep the same
Codex profile, model and shared delivery requirements in both workspaces.
Freeze tasks, repetitions and scoring, verify the loaded bytes, then use
`/experiment autorun delivery-brief` to execute the prepared comparison and
obtain a blind evaluation. For `CLAUDE.md` or `AGENTS.md`, substitute the two
file versions and verify their runtime loading in the same way.

## Historical lesson: retain the primary evidence

The earlier anti-hallucination experiment's surviving narrative is
`experiments/TRIPLE_BLIND_EXPERIMENT_RESULTS.md` in the repository
`jleechanorg/worldarchitect.ai`. A 2026-11-02 audit recorded in
`rev-experiment-skill-unsourced-delta-3su73l` did not locate its rubric,
anonymous subject outputs or evaluator's scored JSON. Its sample size and
run date were not established. Commit `5530b6e921a6` dated 2025-07-11 records
the narrative's move into that repository, not the experiment's execution.

The narrative favored behavioral warnings over output specifications; treat
that direction as a hypothesis, not a measured effect. Do not cite its
percentages or claimed confidence. Its fixed seed and fixed assignment do not
establish an actual random draw, and its claimed blinding lacks retained proof.
The retention and assignment steps above preserve what that record could not.
