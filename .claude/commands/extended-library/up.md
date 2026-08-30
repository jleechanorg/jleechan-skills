---
description: Persist a coding-agent rule in the active repo by default; use --global for cross-runtime home policy
argument-hint: "[--repo <path>|--global|--both] <instruction>"
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/up.md` completely, then execute it with `$ARGUMENTS`.
