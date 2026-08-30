---
description: /exportcommands - Export Claude Commands to Reference Repository (your-project.com only — the filter list is hardcoded to worldarchitect/$PROJECT_ROOT/jleechanorg patterns; rename to /export-worldai-commands for clarity)
type: llm-orchestration
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/exportcommands.md` completely, then execute it with `$ARGUMENTS`.
