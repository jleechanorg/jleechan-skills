---
description: Execute the implementation planning workflow using the plan template to generate design artifacts.
type: llm-orchestration
execution_mode: immediate
scripts: {ps: scripts/powershell/setup-plan.ps1 -Json, sh: scripts/bash/setup-plan.sh --json}
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/spec-kit/plan-spec.md` completely, then execute it with `$ARGUMENTS`.
