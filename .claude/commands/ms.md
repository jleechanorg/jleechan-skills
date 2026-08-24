---
description: Alias for /extended-library:memory_search — search across all memory systems
type: llm-orchestration
execution_mode: immediate
---

# /ms — Alias for /extended-library:memory_search

Invokes `/extended-library:memory_search` with the provided arguments. See `~/.claude/commands/extended-library/memory_search.md` for the full workflow, sources, flags, and cache semantics.

**Usage**: `/ms <query> [--flags]`

## Action

Read `~/.claude/skills/memory-search/SKILL.md` and execute `/extended-library:memory_search $ARGUMENTS` end-to-end.

## Common shortcuts

```text
# Quick lookup (no flags)
/ms slack misroute failure 5

# Last 7 days only
/ms hermes deploy --recent 7

# Single source, capped
/ms $USER-owka --source beads --limit 5
```

## Why this command exists

Prior to 2026-06-25, this was a 109 B stub that dispatched `memory-search $ARGUMENTS` to a shell command that did not exist. Sessions calling `/ms` would see `memory-search: command not found` and conclude "skill not found", then spend ~5 minutes scanning `~/.openclaw/` (the dead OpenClaw path) for what should have been a one-line dispatch. The augmentation makes the underlying skill (`memory-search`) and its memory sources explicit so a future session does not re-discover the workaround by hand.
