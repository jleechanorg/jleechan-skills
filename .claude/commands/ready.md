---
description: /ready command dispatcher
type: skill
execution_mode: immediate
---

# /ready — drive PR(s) to merge-ready

Load and follow `${CLAUDE_HOME:-$HOME/.claude}/skills/ready/SKILL.md` (Skill tool: `ready`).

PRs should satisfy — or be made to satisfy — ALL of: /es, /er, /advice
approved, then /green, with all comments and merge conflicts handled, verified
at the current head with `$ARGUMENTS`.
