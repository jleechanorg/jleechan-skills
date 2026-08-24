---
description: /command-research - Measure true slash command & skill invocations across Hermes, Claude Code, and Codex without noise
type: analysis
execution_mode: immediate
---

# /command-research [--days N] [--top N] [--human-only] [--agent-only]

Empirically audit and rank slash command usage across all primary session stores (Hermes SQLite, Claude Code JSONL, Codex SQLite) with strict system-reminder noise filtering and human vs. agentic separation.

Read `~/.claude/skills/command-research/SKILL.md` and execute the multi-store scanner against `$ARGUMENTS`.

## Common Invocations

```text
# Full all-time audit
/command-research

# Last 30 days top 20
/command-research --days 30 --top 20

# Human-typed commands only
/command-research --human-only --top 15

# Export structured JSON
/command-research --json
```

## References
- Skill implementation: `~/.claude/skills/command-research/SKILL.md`
- Scanner script: `~/.claude/skills/command-research/scripts/count_command_usage_unified.py`
