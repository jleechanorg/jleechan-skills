---
description: Use Agent Orchestrator with strict parameter fidelity, post-spawn verification, and pre-spawn cap cleanup
type: workflow
execution_mode: deferred
scope: user
---
# /ao [args]

Use AO for durable coding work instead of manually creating worktrees or running agent CLIs directly. User-specified AO constraints (`--agent`, `--runtime`, `--project`, `--claim-pr`) are mandatory.

Read `~/.claude/skills/agent-orchestrator/SKILL.md` and execute the full workflow with the provided arguments — including the pre-spawn cap check (Step 0), quota-wall fallback (Step 0.5), parameter fidelity rules, and post-spawn verification.

## Related skills

| Skill | Purpose |
|-------|---------|
| `ao-worker-dispatch` | pre-dispatch checklist (venv, commit discipline, branch drift, CodeRabbit verify) |
| `ao-operator-discipline` | strict parameter fidelity + post-spawn verification |
| `ao-spawn-gate` | pre-spawn safety gate |
| `ao-session-monitor` | proper tmux inspection for live workers |
| `ao-model-override` | override worker model without editing `agent-orchestrator.yaml` |

## Input

$ARGUMENTS
