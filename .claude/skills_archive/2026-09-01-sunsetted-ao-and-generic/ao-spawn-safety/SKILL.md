---
name: ao-spawn-safety
description: "Use BEFORE bulk or iterative AO spawns over 3 workers. Respect the channel max_spawn setting, enforce the absolute 30-worker cap, spawn at most 15 per batch, and never use load average as the gate."
---

# AO spawn safety — resource check before bulk spawning

> **This file is the single source of truth for the AO spawn cap.** Other surfaces (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) must link here and must NOT restate the numbers — restating them is what produced the 20-vs-30 contradiction resolved on 2026-07-25.

**Scope: AO worker spawning only.** Do NOT apply these checks to Hermes's own incoming message handling — that blocks Hermes from responding when AO workers are running.

Before issuing any bulk or iterative AO spawn sequence (more than 3 spawns in a loop or in response to an open-ended instruction like "do all" / "take it all the way"):

1. **Honor the channel admission limit.** If active AO sessions on the target channel exceed its `kanban.max_spawn` setting (default 8), pause and ask the operator before spawning more.
2. **Hard cap at 30 AO workers.** If `ao session ls` shows 30 or more active sessions total, decline to spawn and report the count. This cap is on **AO worker count**, not system load average — do NOT use `sysctl vm.loadavg` as the spawn gate.
3. **Batch at most 15 workers.** Spawn no more than 15 workers in one batch, then wait for completions or explicit progress signals before starting another batch.

**Why**: A 2026-05-15 spawn storm created 517 sessions, starved the host, and interrupted the gateway. The policy uses three independent controls: channel admission, an absolute worker cap, and bounded batches.

**Cap history** — 20-cap / 5-batch was the policy through 2026-07-02. Raised to **30-cap / 15-batch by explicit user directive on 2026-07-03**, aligning with auto-factory-daemon spec §4.2.8, and re-confirmed by the user on 2026-07-25 when a three-way contradiction between this file, `CLAUDE.md`, and `AGENTS.md` was found and resolved in favour of 30/15. A prior revision of this file claimed the "15" was a superseded batch-size value that had never been a real gate; **that claim was wrong and has been removed.**

**These are policy caps, not software-enforced ones.** As of 2026-07-25 there is no `MAX_CONCURRENT_SESSIONS` constant anywhere in `~/projects/agent-orchestrator` (the `packages/core/` tree that older docs cite no longer exists), and `~/.hermes/agent-orchestrator.yaml` defines no concurrency limit. Nothing will reject a 25th spawn for you — the agent is the enforcement layer. Verify the count yourself with `ao session ls` before each batch.

## backfillAllPRs — separate per-project cap

`backfillAllPRs: true` spawns via `backfillUncoveredPRs` each health-cron cycle (every 3600s by default). Its project cap is `project.spawnQueue.maxActiveSessions` — currently default **20** in the TypeScript implementation. Keep it explicitly lower for backfill workloads.

**Always set this companion when enabling backfill:**
```yaml
backfillAllPRs: true
spawnQueue:
  enabled: true
  maxActiveSessions: 5  # prevents zombie accumulation from dead-tmux sessions
```

`maxConcurrentSessions` is NOT a valid config field and is silently ignored by Zod. Using it instead of `spawnQueue.maxActiveSessions` has no effect.

**Why 9 zombies accumulated (2026-06-18)**: Dead tmux sessions → `hasSession()=false` → PR marked "uncovered" → new worker spawned each cycle. Without a deliberately low per-project cap (or with a silently ignored field), accumulation continued unchecked.
