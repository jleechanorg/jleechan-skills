---
description: /swarm — orchestrate multi-agent swarms (ultracode workflows + agent-team lanes) with adversarial verification
type: llm-orchestration
execution_mode: immediate
---

# /swarm <goal> [--engine workflow|team] [--shape retro|review|solutions|innov|triage] [--sidekick [model]]

Run the goal as a multi-agent swarm with adversarial verification, cost-routed subagents, and artifacts committed to a PR. The sidekick wrap is mandatory regardless of `--engine`.

**Parallel ceiling:** Before sizing fan-outs, load `/parallel` → `~/.claude/skills/parallelize-to-ceiling/SKILL.md`.

Read `~/.claude/skills/swarm/SKILL.md` and execute the full playbook with the provided goal — including the instant-start sequence (STATE.md, in-session Agent Teams lanes, in-session sidekick teammate per the team-only sidekick skill — tmux/codex/`-p` sidekicks are banned), engine selection, canonical phase shapes, hard rules, and execution recipe.

## 🚨 CODEX MODEL ROUTING (mandatory for Codex sessions)

Policy: `~/.codex/rules/model-routing-policy.md`.
For Codex subagent spawns and any Codex threads this swarm launches:
- **Default: `gpt-5.3-codex-spark`** — all research, history reads, file scans, mechanical edits
- **`gpt-5.6-sol` ONLY when**: cross-context synthesis or hard architectural reasoning where Spark has demonstrably failed.

## ⚠️ DEDUP GATE (run before spawning any new Codex thread)

Check for active in-flight threads using shared helper `~/.codex/hooks/codex-dedup-check.sh "<goal>"`:
```bash
~/.codex/hooks/codex-dedup-check.sh "GOAL_KEYWORDS" 1800
# Equivalent SQL:
# sqlite3 ~/.codex/state_5.sqlite "SELECT COUNT(*) FROM threads WHERE first_user_message LIKE '%GOAL_KEYWORDS%' AND tokens_used=0 AND created_at_ms>(unixepoch('now')-1800)*1000;"
```
If count > 0, **steer the existing thread** instead of spawning fresh.

## Input

$ARGUMENTS
