---
name: evolve_loop
description: Generalized autonomous loop — observe environment, measure health, diagnose friction, fix harness gaps, drive tasks to completion. Repo-agnostic. Use /eloop in any repo. For AO agent-orchestrator-specific patterns, also check the repo-local eloop skill.
type: skill
---

# Evolve Loop — Generalized

**Purpose:** Autonomous self-improving loop that observes the local environment, measures health, diagnoses friction in the harness, drives tasks to completion, and records findings. Repo-agnostic — runs in any working directory.

**Cross-reference:** If working in `agent-orchestrator` specifically, also consult the repo-local `eloop` skill at `.claude/skills/eloop/SKILL.md` for AO-specific PR tracking, worker management, and zero-touch metrics.

## Autonomous Continuation

After completing the loop body, immediately start the next cycle. Do not pause between cycles.

Stop only when:
1. User says `stop` or `pause`
2. Context exceeds 90%
3. System is stable for 3 consecutive cycles
4. Time budget exhausted (if set)

## Loop Body

### Phase 1: Observe

1. **Memory first** — Run `/ms` to pull prior context:
   ```
   /ms "open tasks [current repo]"
   /ms "stuck tasks [current repo]"
   /ms "friction [recent]"
   /ms "bead [open]"
   ```
   This surfaces what was already dispatched, what failed, and what blockers are known.

2. Check the local environment:
   - Active agent/worker sessions (tmux panes, background processes)
   - Open PRs in the current repo
   - Running automation jobs (CI, cron, watchers)
   - Recent file changes that may have broken things

3. Capture live session output (last 20-30 lines of each active pane).

4. Kill zombie sessions — any worker on merged/closed work still burning tokens.

5. Check for stale local artifacts: broken symlinks, out-of-sync worktrees, stale lock files.

### Phase 2: Measure

For each open task/PR:
- Is it actually in progress, or stalled?
- Does it have a live worker, or is it abandoned?
- Does it have CI green, or is it blocked on checks?
- Is the bottleneck technical, or a harness gap?

Calculate a health signal: ratio of active/in-progress items to total open items.

### Phase 3: Diagnose

1. Run `/harness` on each new friction point.
2. For each stuck item, ask: is this a one-off bug, or a harness failure that will recur?
3. Identify the recurring patterns — classify as:
   - **Harness gap** — something the harness should have prevented/caught but didn't
   - **Code bug** — an actual implementation error
   - **External** — outside the system's control (API outages, upstream changes)
4. If a harness gap: fix it in the harness, not just the symptom.

### Phase 4: Plan

1. Run `/nextsteps` or equivalent.
2. Prioritize:
   - P0: Items blocking multiple other items
   - P1: Recurring harness failures
   - P2: Nice-to-have improvements

### Phase 5: Record

1. For each new harness gap: update the relevant CLAUDE.md, AGENTS.md, skill, or hook.
2. Append cycle findings to the local `roadmap/evolve-loop-findings.md` or equivalent log.
3. If the fix was significant, run `/learn` to capture the pattern.

### Phase 6: Fix

1. Drive each actionable item to completion — don't just dispatch and forget.
2. If using `/claw` or equivalent dispatch: babysit the worker. Check back within 2 cycles.
3. If the dispatch fails twice, fix it directly — don't keep dispatching the same failed approach.
4. Verify completion before moving on — don't mark done until the observable outcome exists.

### Phase 7: Recap

Summarize:
```
## Cycle — HH:MM
- Health: X/Y items active
- Friction: N new points, N resolved
- Fixes: N dispatched, N direct
- Harness updates: [files changed]
```

## Invocation

- Start loop: `/loop 10m /eloop`
- One shot: `/eloop`

## Anti-Stall Rules

- If a worker is stuck for 2+ cycles: kill and investigate, don't just keep watching
- If the same failure recurs 3x: it's a harness gap — fix the harness, not the symptom
- If GraphQL/REST is rate-limited: pause before burning more calls
- If context exceeds 80%: compact or stop before it becomes unusable

## Core Principle

**The loop modifies the harness, not just the codebase.** Every cycle that only fixes code without improving the system that produced the bad code has failed. If the same class of problem appears twice, the loop should have fixed the harness to prevent it. If it didn't, the loop failed.
