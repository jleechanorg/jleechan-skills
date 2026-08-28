---
name: nextsteps
description: Situational assessment, beads + roadmap sync after a work block; optional brief from user.
---

# /nextsteps — Situational Assessment & Roadmap Update

## When invoked

1. **Gather context in parallel**
   - `git log --oneline -10`
   - `br list --status open` (or `bd` if project uses bd)
   - `ls roadmap/` (or list `roadmap/README.md` recent section)
   - Use any user-provided line after `/nextsteps` as extra context.

2. **Assess**
   - Match recent commits to open beads; close or update status.
   - Note gaps → new `br create` issues.
   - Update `roadmap/README.md` **Recent activity (rolling)** with date + bullets.

3. **Execute**
   - Prefer parallel tasks (subagents) for: beads updates, new issues, roadmap edits.

4. **Report**
   - IDs, paths changed, recommended next actions.

## If `~/.claude/skills/nextsteps.md` is missing

This file is the protocol; keep it in user scope so `/nextsteps` is reproducible across repos.
reate (parallel subagents)
For each identified update, dispatch in parallel:

**Beads updates** (for each relevant open issue):
```bash
br update <id> --status <new_status>
br show <id>  # verify before updating
```

**New beads issues** (for gaps not tracked):
```bash
br create "<title>" --type <task|bug|feature|chore> --priority <0-4> --description "<details>"
```

**Roadmap doc updates** (edit existing `roadmap/*.md`):
- Add new decisions, findings, or status to relevant docs
- Keep updates concise — append, don't rewrite

**New roadmap docs** (for new initiatives):
- Create `roadmap/<TOPIC>.md` following existing doc style
- Include: Background, Current Status, Next Steps, Open Questions

### Phase 3 — Report
Summarize:
- Issues updated/created (with IDs)
- Docs updated/created (with paths)
- Recommended next actions
