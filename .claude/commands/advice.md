---
description: Token-efficient second opinion — runs the Codex + Opus CLI primary pair concurrently where available and requires two independent, full-coverage votes, using eligible alternate CLI reviewers when a primary vote is missing. Requires a complete default 1800-second (30-minute) end-to-end budget per reviewer attempt, including setup and cleanup; an explicit user-specified limit governs that attempt, whether shorter or longer; otherwise the 30-minute default applies. A later specific user instruction to await a named reviewer overrides this deadline for that requested attempt, even without a numeric duration; unsupported routes are unavailable. `/research` is nonvoting.
aliases: [smart-advisor]
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/advice/SKILL.md` completely, then execute it with `$ARGUMENTS`.
