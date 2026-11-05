---
description: /ready command dispatcher
type: skill
execution_mode: immediate
---

# /ready — drive PR(s) to merge-ready

Load and follow `${CLAUDE_HOME:-$HOME/.claude}/skills/ready/SKILL.md` (Skill tool: `ready`).

Use `draft-first-pr` for applicability, draft-to-ready sequencing, final review
closure, and review receipts. Apply `$ARGUMENTS`; never equate undrafting with
completed readiness or merge authorization.
