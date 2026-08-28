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
