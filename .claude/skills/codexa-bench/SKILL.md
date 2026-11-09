---
name: codexa-bench
description: Compare same-task or split-work runs through the configured `codexa` shell command and normal `codex`, then assess their results.
---

# Codexa benchmark

Use when asked to compare `codexa` with normal `codex` on the same review, job, or task. The deliverable is a bounded, evidence-based comparison, including an explicit verdict. Do not benchmark this skill against itself or trigger another review workflow just to report the benchmark.

## Set up a fair, bounded comparison

1. Select a comparison mode before execution. The default is **same-task**: freeze one task statement, input snapshot, acceptance rubric, and budget for both arms. If the caller requests **split-work**, freeze a bounded work set and its shared acceptance rubric, then partition the work before either arm starts. Balance the assigned halves as closely as practical by task type, estimated complexity, acceptance evidence, and input size; record the units, estimates, assignment, and any unavoidable imbalance. Keep constraints, safety limits, and per-arm budgets equivalent. Keep the planned partition and original scoring fixed. If delivery recovery requires reassignment or another runtime after an arm fails, record that work separately and exclude it from the original CLI arm's score. Do not share either arm's answers, findings, or intermediate reasoning. Record hashes for available task, input, rubric, and partition artifacts.
2. For same-task mode, default to **as-used**: invoke the actual shell `codexa` command once and the actual shell `codex` command once, in fresh isolated sessions. Preserve each command's normal configuration and harness; do not disable normal Codex instructions or features to make the arms look alike. Record the effective model, reasoning setting, config/profile identity, loaded instruction/skill context, working directory, executable or shell-function identity, and CLI version for each arm. Do not record secrets or credential values.
3. If the caller explicitly selects a **matched-model** comparison, select and set the same model and reasoning effort for both arms only for this task. Record the overrides and every remaining difference in configuration, instructions, skills, tools, wrappers, and working roots. Do not alter persistent defaults. Never infer that output differences came from cleanliness alone when other factors differ.
   Split-work is a matched-model comparison: use the same caller-selected task-scoped model and reasoning effort in both arms, and record any overrides. If either arm delegates to subagents because the caller requested it, keep each subagent within that arm's assigned work and isolated workspace; record its model, effort, and assignment. Never share workspaces or subagent outputs across arms. Record pre-existing unequal inputs or audits, and extra audits done during execution, separately from the planned split; do not count them as matched work or credit them to the assigned half.
4. Use one bounded run per arm by default. Honor the caller's stated budget or the task owner's existing limits; do not invent extra spend or time. No automatic retry loop. If an arm fails or is unavailable, report the comparison as incomplete; the other arm is not the winner by default. If an arm reports an explicit usage limit, record that result and do not invoke the CLI again just to retest quota. Report any later work completed through another native route separately, identifying its runtime and excluding it from the original CLI arm's result. A retry requires an explicit, task-relevant reason and must remain within the authorized budget.

For a read-only review, give both arms the same frozen source snapshot and an explicit no-modifications constraint. If their configured execution modes cannot enforce read-only access, use separate disposable copies initialized from that snapshot and record this setup difference. For a mutating task, provide separate equivalent task-owned worktrees or fixtures, initialized from the same pinned state. Never let the arms write to the same checkout, shared production state, or each other's outputs. Do not repeat destructive, spending, credential, external-send, deployment, or other side effects: omit them from both arms or evaluate using safe isolated fixtures. The benchmark grants no authority beyond the original task.

## Run the actual commands

Verify the locally available command shape before using it; shells may define `codexa` as a wrapper or function. Keep its configured behavior intact. With the local Codex `exec` interface, a prompt can be supplied on stdin and the final response written to an arm-specific file:

```sh
codexa exec --ephemeral -C "$WORKDIR_A" -o "$OUTPUT_A" - < "$PROMPT_FILE"
codex exec --ephemeral -C "$WORKDIR_B" -o "$OUTPUT_B" - < "$PROMPT_FILE"
```

For same-task mode, use the same prompt bytes and equivalent inputs. For split-work, keep the shared instructions and rubric identical, include only each arm's assigned units and inputs, and record their hashes and sizes. Choose workdirs according to the read-only or isolated-mutating setup above. If a local wrapper does not accept this shape, inspect its help/definition and adapt without replacing it with another model, provider, or configuration. Use the caller's/native timeout mechanism. Preserve private raw receipts in the approved scratch location; publish only sanitized material authorized for the task.

## Evaluate and report

Where feasible, freeze both outputs (including hashes), label them A/B, and adjudicate before revealing which command produced which. Independently check each claimed issue against the pinned source and rubric. Deduplicate equivalent findings. Count valid unique findings by arm; record severity, false positives, missed planted or independently verified requirements, and task completion/correctness/safety. For split-work, report completion and correctness per assigned unit as well as per arm, and compare resource use only when measured on equivalent scopes. Treat task mix, input-size, audit, tool, and configuration differences as confounds; describe the observed outcomes without attributing them to a causal advantage from cleanliness or partitioning. Treat unknown recall as unknown, never as zero. More findings, longer answers, or more confident wording do not by themselves win. Correct, safe task completion takes priority over finding count.

Compare elapsed time, tool use, output size, and token/cached-token data only when actually available; cached tokens are not dollars. Separate observed measurements from estimates. State confounds and what the result cannot establish.

End with exactly one verdict: **codexa better**, **normal codex better**, **tie**, or **inconclusive**. Name the supported dimension, each arm's valid-unique finding count, uncertainty, and the smallest next test only if another test is needed to resolve a material uncertainty. A single task supports a result for that task and setup, not a general model-quality claim. Write one durable Markdown report at the location required by the active environment's instructions; keep raw receipts private in approved scratch storage.
