---
description: Switch the main thread to the Fable (latest Claude) model with strict token-economy discipline. Heavily use Haiku/Sonnet subagents; reserve the main model for hardest reasoning only.
type: workflow
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/fable.md` completely, then execute it with `$ARGUMENTS`.
