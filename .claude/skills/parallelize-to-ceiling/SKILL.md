---
name: parallelize-to-ceiling
description: Use when designing, debugging, reviewing, or scripting any work that has independent items (rows, files, tests, migrations, jobs, agent lanes, API sweeps, builds). Slash command `/parallel`. Enforces a single rule — the speed ceiling is the workload's real resource bound, not an arbitrary worker count and not "one at a time" — and supplies a decision procedure, a resource-bound table, isolation invariants, and failure modes. Trigger phrases include "parallelize", "scale up", "make this faster", "shard this", "use all the machines", "why is it serial", "it's running one at a time", "speed ceiling", "resource bound", "concurrency ceiling".
---

# Parallelize to Ceiling

**Slash command:** `/parallel` → `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md`

## Core law

For ANY work with independent items, the speed ceiling is the workload's
**real resource bound** — per-item CPU / IO / network, or per-machine
capacity — NOT an arbitrary worker count and NOT "one at a time."

When a full set of N items can run concurrently, run **all N at once**;
**scale to more machines/containers rather than serialize onto fewer.**

Serialize only with a named determinism/corruption constraint. A driver that
only supports serial for parallelizable work is **fixable tooling debt**, not
the answer.

This applies to local CLI work and to remote/distributed compute equally, to
one-off scripts and to production pipelines alike.

## The decision procedure

1. **Enumerate the independent items.** Rows, files, tests, migrations, doc
   sections, instances, jobs, agent lanes. If items share mutable state, they
   are NOT independent — partition or serialize only those.
2. **Classify each item's resource profile.** Light (≤1–2 cores, fast) vs
   heavy (self-saturates a machine: many cores, large memory, or long
   runtime). Measure with a quick probe; don't guess.
3. **Pick the parallelism unit.**
   - **Machine-level sharding is primary** — split the item set into disjoint
     shards across every available machine/container. This is the biggest,
     safest win.
   - **Within a machine, run light items to machine concurrency** (cores /
     per-item cores). Heavy items get their own machine — a high
     `--max-workers` can't make a CPU-saturated item faster and just thrashes.
4. **Scale the fleet to the workload.** If N items are independent and you
   have fewer machines than the ideal, **provision more** so all N run at
   once. Don't serialize a parallelizable set onto the machines you happen
   to have.
5. **Prove the concurrency** by sampling live (process/container counts, load
   average), not by trusting the flag. A passed `--max-workers N` that yields
   1 running worker is a red flag — find the serializer (a lock, a saturated
   resource, or a serial driver).

## Resource-bound table

| Item profile | Per-machine concurrency | Parallelism unit | Why |
|---|---|---|---|
| Light (small tests, quick scripts, transforms) | ~4–6 on an 8-core machine | shard across machines + workers/machine | each uses ~1–2 cores |
| Heavy CPU (big builds, ML training, large test suites) | 1 (self-saturates the cores) | **its own machine** | self-parallelizes; a worker flag can't help |
| IO/network-bound (API sweeps, fetches, downloads) | high (10s) | workers, not machines | CPU idle; bound is latency/rate-limit |
| Memory-bound | until RAM pressure | fewer per machine | watch RSS, not just CPU |

## Worked example (a gold-test preflight across 4 machines)

- **Bug:** a sharded preflight passed `--max-workers 1` → each of 4 machines
  ran its ~8 rows **serially** → 4 concurrent total, ~7 min wall-time.
- **Token fix:** `--max-workers 3` → 6 concurrent.
- **Right fix:** `--max-workers 6` + the heavy/light split → **14 concurrent**.
  Light rows filled to machine concurrency; the few heavy rows still dominated
  one machine each (the real long pole).
- **To go to true all-34-at-once:** needs **more machines** (heavy rows each
  want one), which the shard driver consumes drop-in. The worker count was
  never the real ceiling — per-item CPU and machine count were.

## Failure modes this kills

- **The token worker count.** `--max-workers 3` chosen by feel instead of a
  measured per-item bound. Ask: what does one item actually use?
- **The passed-flag mirage.** `--max-workers 4` passed but 1 worker running
  (a hidden lock / saturated resource / serial driver). Measure live.
- **Serializing onto the machines you have.** "I have 4 machines so I'll run
  4 at a time" when the set could use 12 — provision more.
- **Broad-parallel without isolation.** Parallel writers sharing a mutable
  file/db → the real failure is the shared state, not the parallelism. Give
  each worker a disjoint workspace/output; single-writer for any merged
  artifact; order-deterministic results (sort by id, not completion order).

## Resource admission gate (mandatory — crash 2026-08-30)

Memory is a first-class resource bound. A harness process died silently at
the instant it forked a 20-minute foreground CLI delegate on a host at 92%
swap / memory-pressure WARNING / ~64MB free — the spawn itself was the kill
site, and silent self-exits leave no OS trace.

Before spawning any new lane, subprocess fleet, or CLI delegation:

1. **Probe:** `sysctl vm.swapusage` and
   `sysctl kern.memorystatus_vm_pressure_level` (macOS; on Linux check
   `free`/`vmstat` swap + PSI). Takes one second.
2. **Defer, don't spawn,** when swap >80% used or pressure level ≥2
   (WARNING). Finish or kill existing heavy children first; spawning into
   starvation risks killing the *parent* session, losing all lanes at once.
3. **Never fork a multi-minute CLI delegation (agy, codex, claude -p) as a
   foreground Bash call.** Always `run_in_background` + explicit timeout —
   a foreground fork pins the parent at the worst possible moment.
4. **Cap concurrent pytest lanes** in gRPC-loaded repos (macOS
   fork-unsafety: "multi-threaded process forked" SIGTRAP storms). 2-3
   lanes max per host unless measured safe; prefer sharding across
   machines.
5. **Watch delegate RSS.** A CLI delegate above ~2-3GB RSS is itself a
   heavy item — one per machine, per the resource-bound table.

## Isolation invariants (always, when parallelizing)

- Disjoint per-worker workspaces / output files.
- Single-writer for any shared ledger/manifest.
- Order-deterministic merged results (sort by id, never completion order).
- Instance-scoped container/process names so concurrent workers can't collide.
- Never relax a correctness/validation contract for speed — if a result's
  determinism can't be preserved, THAT is the written justification for serial.

## Coding and verification lane routing

For implementation and review lanes, prefer the installed AGY CLI pair. Use
the canonical profiles for the complete launch, logging, isolation, and
signaling contracts:

- Coder: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`
- Verifier: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`

### Two-agent pair template

```text
PAIR TASK: <bounded task and explicit file scope>
CODER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`; implement and signal IMPLEMENTATION_READY with `Revision: <exact git SHA>` and `Worktree: <absolute path>`.
VERIFIER: follow `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`; independently verify the handed-off revision and signal VERIFICATION_COMPLETE or VERIFICATION_FAILED.
FALLBACK: if an AGY lane concretely fails, retry that lane with codexs, claudem, or an own cheap agent while preserving isolation and independent verification.
```

## Fallback precedence

The `FALLBACK` template above is governed by this order:

1. Start with the AGY pair as the primary implementation and verification lanes.
2. After a concrete AGY lane failure, retry the same bounded lane with `codexs`
   as the Spark fallback; codexs is not a multi-model router. If that lane
   also fails, invoke the Codex CLI explicitly with `-m gpt-5.6-luna`, then
   `-m gpt-5.6-terra`, then `-m gpt-5.6-sol`, advancing only after a concrete
   failure in that lane.
3. Use `claudem` or an own cheap agent only when the ordered Codex route is
   unavailable; preserve the same bounded scope and verification requirements.

## Isolation contract

Coder and verifier remain distinct lanes and contexts. The orchestrating caller
decides whether each lane and retry operates in an allocated detached worktree
or directly within the caller's workspace. Every attempt, including initial
execution and each retry, uses a fresh workspace (either an allocated detached
worktree or caller-provided clean workspace) and unique output/log paths disjoint
from both coder and verifier lanes and from all previous attempts.
Attempts must not read or reuse partial files, logs, or outputs from another
attempt, and the verifier must independently rerun focused checks before signaling completion.
When worktree isolation is used, every retry uses a fresh detached worktree and
unique output/log paths. Start a fresh `agy --new-project` invocation for every
attempt; never pass a conversation-resume option or use an equivalent conversation-reuse mechanism.
Each coder retry must carry the exact prior `Revision`, pin its workspace to
that revision before making changes, rerun focused checks, and finish with an
explicit scoped commit plus an empty status before sending the next handoff.
Verifier retries must carry the exact handed-off `Revision`, pin their workspace
to that revision, rerun focused checks read-only, and never modify files or create a commit.
When worktree isolation is allocated, coder and verifier attempts enter fresh,
per-lane worktrees and unique per-attempt output paths before invoking AGY;
each worktree and output path must be disjoint from the other lane and all
previous attempts. `Revision` is the committed clean implementation revision:
the coder must make a final scoped commit and confirm its worktree is clean
before sending IMPLEMENTATION_READY. The verifier must reject dirty inherited
state and verify against `Revision`.

## Codex model routing

For Codex parallel lanes, use this ordered fallback and advance only after a
concrete per-lane failure. Invoke `codexs` as the Spark fallback; codexs is
not a multi-model router:

`gpt-5.3-codex-spark` → `gpt-5.6-luna` → `gpt-5.6-terra` → `gpt-5.6-sol`

Record the rejection and retry the same bounded lane with the next explicit
model. Never skip directly from Spark to Sol.

## One-line form (for config files)

> Parallelize any task to its real ceiling — any independent-item work runs to
> its real resource bound, not an arbitrary worker count or one-at-a-time;
> shard across ALL available capacity and scale to more machines rather than
> serialize.

## Quick diagnostic — "why is it slow?"

Run this in order; stop at the first that explains it:

1. **Are items independent?** If they share mutable state, fix isolation first.
2. **Is the driver even using more than one worker?** `ps` / `docker ps` /
   `kubectl get pods`. A passed `--max-workers N` is not proof — find the
   serializer.
3. **Is the machine saturated?** Load average > cores, or RSS climbing —
   each item is heavy; shard across machines, not workers.
4. **Is the per-item bound actually IO/network?** Workers/machine can go high
   (10s); the ceiling is rate limits, not cores.
5. **Are you on the right number of machines?** If N items want N machines
   and you have 4, add machines — don't serialize.
