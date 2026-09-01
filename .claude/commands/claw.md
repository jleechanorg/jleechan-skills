---
description: /claw - Route tasks through Hermes gateway inference
type: orchestration
execution_mode: immediate
---
# /claw - Hermes Gateway Inference

**Usage**: `/claw <task description>`

**PR shorthand**: `/claw <PR-number>` (e.g. `/claw 6976`, `/claw PR 6976`, `/claw #6976`) expands to "complete draft-first readiness, then bring that PR to `/green`" with repo auto-detection from the current git remote.

`/claw` is a thin wrapper. The operational behavior lives in:

- `~/.claude/skills/claw-dispatch/SKILL.md`

## Rules

- Dispatch policy: route tasks through the configured Hermes gateway inference workflow.
- Keep this command file thin; update the skill for behavioral changes.

## Execution

When invoked with `$ARGUMENTS`, read `~/.claude/skills/claw-dispatch/SKILL.md` and execute that workflow with the provided task description.
