---
description: Execute the implementation plan by processing and executing all tasks defined in tasks.md
type: llm-orchestration
execution_mode: immediate
scripts:
  ps: "scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks"
  sh: "scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks"
script_selection:
  default: "sh"
  windows: "ps"
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/spec-kit/implement-spec.md` completely, then execute it with `$ARGUMENTS`.
