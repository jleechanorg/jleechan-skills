---
description: "Goal Harness — work on a goal until /es, /er, /code-standards, and Independent Agent Review all pass via adversarial subagents"
type: quality
execution_mode: immediate
aliases: [h]
---

# /goal_harness — Goal-Driven Harness Loop

Define a goal (via builtin `/goal`), then iterate until **4 adversarial gates** all pass —
each dispatched to an isolated subagent that receives only the diff and its standard.

Read `~/.claude/skills/goal_harness/SKILL.md` and execute the full workflow.

## 🚨 CODEX MODEL ROUTING (mandatory for Codex sessions)

Policy: `~/.codex/rules/model-routing-policy.md`.
Subagents for the 4 adversarial gates MUST be cost-routed across the Codex 5.6 spectrum (`luna` → `terra` → `sol` + `spark`):
- **Gate 1 (`/es`)**: `gpt-5.3-codex-spark` (fast format scan)
- **Gate 3 (`/code-standards`)**: `gpt-5.6-luna` (fast 5.6 standards scan)
- **Gate 2 (`/er`)**: `gpt-5.6-terra` (mid 5.6 evidence review synthesis)
- **Gate 4 (`Independent Agent Review`)**: `gpt-5.6-sol` (top 5.6 deep bug & security review)

## ⚠️ DEDUP GATE (run before starting a new harness loop)

Check for active in-flight harness/goal threads using shared helper `~/.codex/hooks/codex-dedup-check.sh "<goal>"`:
```bash
~/.codex/hooks/codex-dedup-check.sh "GOAL_KEYWORDS" 1800
# Equivalent SQL:
# sqlite3 ~/.codex/state_5.sqlite "SELECT COUNT(*) FROM threads WHERE first_user_message LIKE '%GOAL_KEYWORDS%' AND tokens_used=0 AND created_at_ms>(unixepoch('now')-1800)*1000;"
```
If count > 0, **steer the existing thread** instead of launching a fresh harness loop.

## Usage

```
/goal_harness <goal description>
/h <goal description>               # alias
```

## Gate summary

| Gate | Checks | Model (Codex) |
|------|--------|---------------|
| `/es` | Evidence Standards (user-scope + project-scope) | `gpt-5.3-codex-spark` |
| `/code-standards` | ZFC + ZFC-leveling + root-cause-first (3 parallel lanes) | `gpt-5.6-luna` |
| `/er` | Evidence Review (adversarial synthesis) | `gpt-5.6-terra` |
| Independent Agent Review | Full-diff code review — bugs, anti-patterns, missing tests | `gpt-5.6-sol` |

Convergence requires **4/4 PASS** (after normalization). Max 10 iterations; stall detection at 2x same score.

## Related Commands

- `/goal` — builtin Claude Code goal command (sets success criteria)
- `/es` — Evidence Standards (reference/display)
- `/er` — Evidence Review (adversarial synthesis)
- `/code-standards` — Coding standards dispatch (ZFC + ZFC-leveling + root-cause-first)
- `/converge` — Iterative goal achievement loop (formerly `/goalexec`)
- `/converge_define` — Define-only variant (sets goal without execution)
