---
description: /ready command dispatcher
type: skill
execution_mode: immediate
---

# /ready — drive PR(s) to merge-ready

Load and follow `${CLAUDE_HOME:-$HOME/.claude}/skills/ready/SKILL.md` (Skill tool: `ready`).

PRs should satisfy — or be made to satisfy — ALL of: /es, and /er and /advice
where `draft-first-pr` (including repo-defined exemptions) requires them, then /green, with all comments and merge conflicts handled, verified
at the current head with `$ARGUMENTS`.
