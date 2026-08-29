---
name: eloop
description: Run the evolve-loop skill. Canonical instructions live in ~/.claude/skills/evolve-loop/SKILL.md.
type: skill
---

# /eloop

Use the canonical evolve-loop skill at:

- `$HOME/.claude/skills/evolve-loop/SKILL.md`

Execution rule:
- Load that skill and follow it as the source of truth.
- For non-Claude runtimes, prefer the skill file over this wrapper.
- If repo-local automation needs a loop body, read the skill file directly rather than duplicating the command text.
