---
description: /bashrc — safe wrapper and settings editing playbook
type: llm-orchestration
execution_mode: immediate
---

# /bashrc

Safe editing playbook for `~/.bashrc` wrapper functions and Claude CLI model/provider routing.

Read `~/.claude/skills/bashrc/SKILL.md` and execute the full workflow.

## Quick reference

| Step | Action |
|------|--------|
| 1 | `/history` + `/ms` checks for prior unresolved confusion |
| 2 | Safe edit protocol: read current values, decide variable ownership, scoped edits only |
| 3 | Validate with env/declare -f check matrix in a fresh shell |
| 4 | Record files changed + validation results in final summary |

Use this whenever editing `~/.bashrc` or changing any Claude CLI model/provider routing.
