---
name: codexa-bench
description: Compare one task run through the configured `codexa` shell command and the normal `codex` command, then assess whether either arm did better.
---

# Codexa benchmark

Use when asked to compare `codexa` with normal `codex` on the same review, job, or task. The deliverable is a bounded, evidence-based comparison, including an explicit verdict. Do not benchmark this skill against itself or trigger another review workflow just to report the benchmark.

## Set up a fair, bounded comparison

1. Freeze one task statement, input snapshot, acceptance rubric, and budget. Record hashes for available task/input/rubric artifacts. Keep task constraints and safety limits identical in both prompts. Do not share either arm's answer, findings, or intermediate reasoning with the other.
2. Default to **as-used**: invoke the actual shell `codexa` command once and the actual shell `codex` command once, in fresh isolated sessions. Preserve each command's normal configuration and harness; do not disable normal Codex instructions or features to make the arms look alike. Record the effective model, reasoning setting, config/profile identity, loaded instruction/skill context, working directory, executable or shell-function identity, and CLI version for each arm. Do not record secrets or credential values.
3. If the caller explicitly selects a **matched-model** comparison, select and set the same model and reasoning effort for both arms only for this task. Record the overrides and every remaining difference in configuration, instructions, skills, tools, wrappers, and working roots. Do not alter persistent defaults. Never infer that output differences came from cleanliness alone when other factors differ.
4. Use one bounded run per arm by default. Honor the caller's stated budget or the task owner's existing limits; do not invent extra spend or time. No automatic retry loop. If an arm fails or is unavailable, report the comparison as incomplete; the other arm is not the winner by default. A retry requires an explicit, task-relevant reason and must remain within the authorized budget.

For a read-only review, give both arms the same frozen source snapshot and an explicit no-modifications constraint. If their configured execution modes cannot enforce read-only access, use separate disposable copies initialized from that snapshot and record this setup difference. For a mutating task, provide separate equivalent task-owned worktrees or fixtures, initialized from the same pinned state. Never let the arms write to the same checkout, shared production state, or each other's outputs. Do not repeat destructive, spending, credential, external-send, deployment, or other side effects: omit them from both arms or evaluate using safe isolated fixtures. The benchmark grants no authority beyond the original task.

## Run the actual commands

Verify the locally available command shape before using it; shells may define `codexa` as a wrapper or function. Keep its configured behavior intact. With the local Codex `exec` interface, a prompt can be supplied on stdin and the final response written to an arm-specific file:

```sh
codexa exec --ephemeral -C "$WORKDIR_A" -o "$OUTPUT_A" - < "$PROMPT_FILE"
codex exec --ephemeral -C "$WORKDIR_B" -o "$OUTPUT_B" - < "$PROMPT_FILE"
```

Use the same prompt bytes and equivalent inputs; choose workdirs according to the read-only or isolated-mutating setup above. If a local wrapper does not accept this shape, inspect its help/definition and adapt without replacing it with another model, provider, or configuration. Use the caller's/native timeout mechanism. Preserve private raw receipts in the approved scratch location; publish only sanitized material authorized for the task.

## Evaluate and report

Where feasible, freeze both outputs (including hashes), label them A/B, and adjudicate before revealing which command produced which. Independently check each claimed issue against the pinned source and rubric. Deduplicate equivalent findings. Count valid unique findings by arm; record severity, false positives, missed planted or independently verified requirements, and task completion/correctness/safety. Treat unknown recall as unknown, never as zero. More findings, longer answers, or more confident wording do not by themselves win. Correct, safe task completion takes priority over finding count.

Compare elapsed time, tool use, output size, and token/cached-token data only when actually available; cached tokens are not dollars. Separate observed measurements from estimates. State confounds and what the result cannot establish.

End with exactly one verdict: **codexa better**, **normal codex better**, **tie**, or **inconclusive**. Name the supported dimension, each arm's valid-unique finding count, uncertainty, and the smallest next test only if another test is needed to resolve a material uncertainty. A single task supports a result for that task and setup, not a general model-quality claim. Write one durable Markdown report at the location required by the active environment's instructions; keep raw receipts private in approved scratch storage.
