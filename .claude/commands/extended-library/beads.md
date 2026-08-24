---
description: Create or update executable br follow-up beads with implementation instructions, signatures, and acceptance criteria
aliases: [bead]
type: skill
execution_mode: immediate
---

# /beads [finding-or-task]

Create or update executable `br` follow-up beads.

Read `~/.claude/skills/bead-followup-templates/SKILL.md` and execute it with the provided finding or task.

Each bead must include source context, current SHA, file/line evidence, exact implementation instructions, live-code API/function signatures, call-site examples, standards constraints, verification commands, acceptance criteria, and a staleness note.

## Hard rules

| Rule | Detail |
|------|--------|
| Worktrees/branches | Use `br --no-auto-flush`; never `bd` |
| Signatures | Read current code first — never invent from memory |
| Multi-bead PRs | Put the PR URL in the body instead of reusing `--external-ref` |
| Production `$PROJECT_ROOT/**` | Include required `/es` evidence class in acceptance criteria |
