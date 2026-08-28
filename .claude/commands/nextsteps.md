---
description: Situational assessment, beads + roadmap sync after a work block; writes a self-contained nextsteps markdown doc (TOC, executive summary, full detail, bead links), updates learnings + README, Claude auto-memory, mem0, and beads. Prefers editing existing roadmap docs over creating new files.
type: skill
execution_mode: immediate
---

# /nextsteps [optional: brief description of what just happened]

Situational assessment and roadmap sync after a work block.

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/nextsteps/SKILL.md` and execute the
full workflow with the provided context.

## Quick summary

- Gather context in parallel: `git log --oneline -10`, `br list --status open`, `ls roadmap/`, plus any text after `/nextsteps`.
- Assess which beads issues and roadmap docs need updating based on recent activity; plan new issues/docs for untracked work.
- Dispatch subagents in parallel: update/close beads matching recent commits, create new beads for untracked gaps, update relevant roadmap docs, create new roadmap docs for new initiatives.
- Report everything updated/created with IDs, paths, and recommended next actions.
