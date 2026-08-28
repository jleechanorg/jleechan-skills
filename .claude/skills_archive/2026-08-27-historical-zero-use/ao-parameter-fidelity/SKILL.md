---
name: ao-parameter-fidelity
description: "Use whenever running an AO spawn. Honors exact --agent/--runtime/--project/--claim-pr; verifies session metadata; never silently substitutes a different worker."
---

# Agent Orchestrator parameter fidelity


**Skill**: `~/.claude/skills/ao-operator-discipline/SKILL.md`
**Command**: `~/.claude/commands/ao.md` (invoke with `/ao`)

When the user specifies AO parameters or constraints, they are requirements, not suggestions.

- Respect explicit AO parameters exactly: `--agent`, `--runtime`, `--project`, `--claim-pr`, target PR, branch, and evidence requirements.
- Never silently substitute a different AO agent/runtime because a default exists or another option seems faster.
- After every `ao spawn`, verify the launched session metadata before trusting the worker:
  - session file under `~/.agent-orchestrator/.../sessions/<session>`
  - `agent=<expected>`
  - `runtimeHandle.data.launchCommand` contains the expected CLI
- If the user asked for Codex workers, pass `--agent codex` and verify the launched command is `codex`, not `claude`, `gemini`, or another fallback.
- If AO cannot satisfy the requested parameters, stop and report the exact mismatch instead of continuing with the wrong worker.
