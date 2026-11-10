---
description: Search requested memory stores or connected conversations with bounded source selection
type: skill
execution_mode: immediate
aliases: [ms]
---

Load `memory-search` from the current skill catalog, or read its resolved installed `SKILL.md` (local default: `${CLAUDE_HOME:-$HOME/.claude}/skills/memory-search/SKILL.md`). Follow the canonical workflow with `$ARGUMENTS` as data and current source permissions. If unavailable, report the missing dependency; do not invent a substitute.
