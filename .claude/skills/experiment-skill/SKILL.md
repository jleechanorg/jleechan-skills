---
name: experiment-skill
description: "Evaluate skills, CLAUDE.md, AGENTS.md, and other agent instructions by replaying a captured incident at its pre-intervention repository state, reproducing the baseline failure, then testing a narrowly changed treatment."
---

# Experiment skill changes against a reproduced incident

Use this workflow when a complaint or failed agent task motivates an instruction
change. First reconstruct what the agent received and reproduce the same failure.
Run the treatment only after the baseline reproduces. The shared
[experiment workflow](../experiment/SKILL.md) owns design, isolation, scoring,
blind evaluation, retention and reporting; this skill adds incident selection
and instruction-loading requirements.

## Usage

Use `/experiment-skill design <name> <incident reference>` to prepare the replay,
or `/experiment-skill autorun <name> <incident reference>` to carry the authorized
comparison through reporting. `execute`, `evaluate` and `reveal` resume the
corresponding phases of the shared workflow. These are agent workflow commands;
they do not identify a bundled executable runner.

## Recover the specimen

Read the incident, issue or complaint and the relevant authorized conversation
records. Select by matching the actual request, observed failure and affected
artifacts, not merely by a nearby timestamp. Preserve:

- The original user request and the context available before the failed action.
- The repository identity and commit the agent actually used, plus any dirty
  patch, untracked task inputs, dependencies and external-state fixtures needed
  to replay it. Keep task data in authorized storage.
- The effective instruction layers: global and repository policy, loaded skills
  and references, tool descriptions, runtime/model settings and wrappers.
- The observed failure and an acceptance check grounded in the user's request
  or existing task contract. Keep the later complaint and proposed fix in the
  coordinator's private design. Give evaluators neutral acceptance criteria,
  relevant source evidence and expected answers; keep expected answers out of
  subject context while preserving the shared task requirements in both arms.

Choose the last evidenced state before the failed action or intervention. A Git
commit preceding the complaint is a candidate, not proof of that state. A commit
before the defect existed may be incapable of reproducing it. Record missing
inputs explicitly; a reconstruction is not a verbatim replay.

## Freeze the repository without future leakage

Create task-owned snapshots at the selected commit. Use a source export when
the task does not require Git history; otherwise expose only the history needed
for the task in an isolated checkout. Exclude later fixes, issue resolutions,
treatment files and neighboring experiment outputs from subject access.

Preserve authorized dirty changes and required task fixtures separately, hash
them, and apply identical copies to both arms. Do not reset, truncate history,
delete branches or overwrite the user's working checkout to create a baseline.
Hold the repository snapshot fixed for an instruction-only treatment; changing
code and instructions together tests a bundle and must be reported as such.

## Verify instruction exposure

Freeze the original instructions as control and the edited instructions as
treatment. Keep the same runtime profile, model, reasoning effort, tools,
permissions and task inputs except for the declared instruction delta.

Use runtime-supported isolated loading; preserve live user configuration. Check
inherited profile variables, global overlays, discovery/token limits, symlink
targets, disabled skill loading, hooks and resume state. Record selected file
hashes and evidence that the process actually consumed them. A catalog entry or
file on disk alone does not prove loading. If exposure cannot be established,
report the comparison as unverified and correct the setup before scoring it.

A clean CLI that drops all global policy is a different experiment from changing
one skill. An instruction supplied only to treatment can be measured as an added
policy's behavioral effect; the control cannot fail compliance with a requirement
it never received. Keep shared user acceptance criteria identical.

## Reproduce before testing the change

Freeze the detector, run count and budget before execution. For stochastic
model failures, use [ablation](../ablation/SKILL.md)'s control-first procedure:
replay the captured input through the actual agent path, with at least five
baseline trials, retaining every output and the observed failure ratio. If the
authorized budget cannot support that design, record an incomplete pilot and
do not claim the reproduction gate passed.

The detector must recognize the reported semantic failure across the full output
and tool trace. It must distinguish wrong behavior from missing dependencies,
invalid credentials, quota refusal, an unavailable model or an unrelated error.
Deterministic failures use the relevant executable reproduction instead of
manufacturing stochastic repetitions.

If the baseline does not reproduce, stop treatment execution. Report
`NOT REPRODUCED` with completed trials, observed outcomes and missing context.
Investigate the snapshot, inputs and detector; preserve any superseded attempt.
Changing the detector or specimen creates a new frozen attempt, not a retroactive
pass. Never weaken the detector because treatment already looks promising.

After reproduction, run the treatment with the frozen tasks and planned budget.
Use identical fixtures, preserve all failures, and include neighboring accepted
cases to catch regressions. Randomize anonymous labels and use a separate blind
evaluator for semantic outcomes, as the general workflow requires. Record the
baseline-first ordering; later paired or interleaved runs can measure time drift.

## Measure and deliver

Report baseline and treatment failures as X/N, task completion, violations of
shared requirements, supported claims, and regressions. Keep elapsed time, tool
calls, token counters and recovery overhead separate from quality. Retain actual
model/profile identities and include descendants when they participated.

Reuse existing usage collectors and content-hash receipts when available. Bind
their session IDs to the experiment's arm manifest; a time-window aggregate can
include unrelated work. Keep active-time estimates distinct from measured wall
time, and retain raw traces separately from privacy-preserving usage summaries.

State whether the treatment prevented the reproduced failure in the observed
runs. A clean treatment run does not establish reliability; match conclusions to
the number and independence of trials. Publish the source/input/instruction
identities, loading receipts, detector/rubric, anonymous outputs, evaluator scores
and retained mapping through the authorized evidence path.

For a new instruction without a captured failure, use the general `/experiment`
workflow with explicit acceptance tasks and label the cases as constructed.

## Example

```text
/experiment-skill design delivery-brief <captured request and failed reply>
```

Select the repository and instruction versions used before that reply, recover
its inputs, and define the user's required delivery outcome. Reproduce the old
behavior before comparing the edited skill. The same process applies to changes
in `CLAUDE.md`, `AGENTS.md`, skill descriptions and referenced instructions.
