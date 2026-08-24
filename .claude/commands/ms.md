---
description: Alias for /memory-search — search across configured memory systems.
type: llm-orchestration
execution_mode: immediate
---

# /ms — Alias for /memory-search

Invokes `/memory-search` with the provided arguments.

**Usage**: `/ms <query> [--flags]`

## Action

Read `~/.claude/skills/memory-search/SKILL.md` and execute it with `$ARGUMENTS`.

## Common shortcuts

```text
# Quick lookup (no flags)
/ms slack misroute failure 5

# Last 7 days only
/ms hermes deploy --recent 7

# Single source, capped
/ms $USER-owka --source beads --limit 5
```
