---
description: Diagnose why the AO + Hermes automation system is not autonomously driving PRs to green and merge.
type: skill
execution_mode: immediate
---

# /auton [description]

Autonomy diagnostic: figure out why PRs are not completing draft readiness and
`/green` without operator intervention. Run this after a work block; use
`/babysit` for live monitoring.

Read `~/.claude/skills/auton/SKILL.md` and execute the full workflow with the provided context.

## Quick reference

| Phase | What it covers |
|-------|-----------------|
| Read first | Hermes config, AO worker vs CLI config, agent policies |
| Diagnostic questions 0-8 | Active config, lifecycle-worker/orchestrator state, spawns, sessions, readiness gaps, rate limits, stale wiring, stray worktrees |
| Group A + B sweep | Infrastructure/session state + GitHub/rate-limit diagnostics, run in parallel |
| Cross-references | Draft-readiness gaps, stalled PRs, zombie sessions, and canonical zero-touch rate |
| 48h worker review | Per-worker outcome table + root cause taxonomy (RC-1..RC-7) |

## Example

```
/auton
/auton workers keep going idle after CR approval
```
