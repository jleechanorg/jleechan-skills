---
description: Autonomous evolution loop — observe AO ecosystem, measure zero-touch rate, diagnose friction, dispatch fixes. Adaptive — skips phases when system is healthy.
aliases: [eloop]
type: skill
execution_mode: immediate
---

# /evolve_loop

Generic autonomous improvement loop — observe, measure, diagnose, fix, repeat. System-agnostic framework; default profile targets AO + Antigravity.

Read `~/.claude/skills/evolve-loop/SKILL.md` and execute the full workflow.

## Adaptive behavior

Not every phase runs every cycle:
- All workers alive and PRs progressing → just report status and wait
- Zero-touch rate unchanged and no new friction → skip diagnose/fix phases
- Only run /harness, /nextsteps, /claw when there's a NEW problem to solve
- Always measure (Phase 2) and always recap (Phase 7)

## Usage

| Mode | Command |
|------|---------|
| Start recurring loop | `/loop 10m /eloop` (every 10min, max 12h) |
| Single cycle | `/eloop` |
