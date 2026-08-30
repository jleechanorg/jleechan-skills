---
description: Alias for /evidence-review. Runs canonical evidence-review workflow with lifecycle authority in draft-first-pr.
aliases: []
type: orchestration
execution_mode: immediate
---

# /er — Alias for /evidence-review

Runs `/evidence-review` with the same arguments.

**Usage**: `/er [subject or path]`

## Action

Invoke `/evidence-review` with the same `$ARGUMENTS`.

This is a thin alias:
- The canonical evidence review workflow, standards check, and verdict rubric live in `~/.claude/skills/evidence-review/SKILL.md`.
- The canonical PR lifecycle gates, documentation-only exception, SHA-binding rules, and draft/ready progression authority live in `~/.claude/skills/draft-first-pr/SKILL.md`.
