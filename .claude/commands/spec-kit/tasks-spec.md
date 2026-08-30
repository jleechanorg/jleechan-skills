---
description: Generate an actionable, dependency-ordered tasks.md for the feature based on available design artifacts.
type: llm-orchestration
execution_mode: immediate
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json
  sh: scripts/bash/check-prerequisites.sh --json
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/spec-kit/tasks-spec.md` completely, then execute it with `$ARGUMENTS`.
