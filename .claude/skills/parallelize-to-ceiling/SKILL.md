---
name: parallelize-to-ceiling
description: Use when designing, debugging, reviewing, or scripting any work that has independent items (rows, files, tests, migrations, jobs, agent lanes, API sweeps, builds). Slash command `/parallel`. Enforces a single rule — the speed ceiling is the workload's real resource bound, not an arbitrary worker count and not "one at a time" — and supplies a decision procedure, a resource-bound table, isolation invariants, and failure modes. Trigger phrases include "parallelize", "scale up", "make this faster", "shard this", "use all the machines", "why is it serial", "it's running one at a time", "speed ceiling", "resource bound", "concurrency ceiling".
---

# Parallelize to Ceiling

**Slash command:** `/parallel` → the installed `parallelize-to-ceiling` skill. Resolve it through the current skill catalog or its installed path.

## Runtime capability and permission gate

Use the same skill and timeline reference on Mac, Linux, and hosted runtimes.
Read the live tool schemas and current permissions before selecting a launch
route. A profile, CLI binary, model name, or machine mentioned here is not proof
that it is present, authorized, authenticated, or supported now.

- Prefer available native delegation tools. With `collaboration`, use
  `spawn_agent` for an independent lane, `send_message` for a running lane,
  `followup_task` to resume an idle lane, and `list_agents`/notifications for
  state. Use these names only when exposed by the live runtime; otherwise use
  the equivalent supported API. Do not pretend imported agent files register
  roles, models, or sandbox permissions automatically.
- Native agent capacity is the runtime's declared total slot limit, including
  the parent and other active agents. Admit no more lanes than its remaining
  slots and useful ready work. Local CPU/RAM cannot increase that limit. If
  remote host metrics are not exposed, report that limit and observed lane
  states; do not substitute this computer's metrics as proof of remote capacity.
- Probe CPU, memory, cgroups, and process liveness only for local subprocesses
  or explicitly authorized machines where those metrics are available. The
  local admission gates below do not require shell access for native agents.
- Local CLI/AGY pairs remain available when the user selected that route and
  its installed tools/profiles and current account access are established by
  permitted non-secret checks. Follow live tool, model, sandbox, and user
  constraints. Do not inspect credentials, invoke external providers, log in,
  provision hosts/containers, purchase capacity, start persistent services, or
  create Work/Codex tasks merely to increase parallelism. Missing capacity is
  a named bound: batch ready lanes and report it without expanding access.

## Core law

For ANY work with independent items, the speed ceiling is the workload's
**real resource bound** — per-item CPU / IO / network, or per-machine
capacity — NOT an arbitrary worker count and NOT "one at a time."

When a full set of N useful items fits admitted capacity, run **all N at once**.
Use additional already-authorized capacity when available; provisioning or
paid capacity requires separate authority and is never implied by this skill.

Serialize only with a named dependency, determinism/corruption constraint, or
measured resource, tool, permission, or concurrency bound. A driver that
only supports serial for parallelizable work is **fixable tooling debt**, not
the answer.

This applies to local CLI work and to remote/distributed compute equally, to
one-off scripts and to production pipelines alike.

## Timeline, parallel lanes, and milestones (mandatory)

Read and apply the bundled [timeline and milestones contract](references/timeline-milestones.md), resolved relative to this skill package,
on every invocation. Always include a timeline, maximize useful independent
lanes within the measured resource ceiling, and report milestones every
20 minutes with an hourly rollup during active work. Preserve this command's
planning, handoff, and execution authorization boundaries.

## The decision procedure

1. **Enumerate the independent items.** Rows, files, tests, migrations, doc
   sections, instances, jobs, agent lanes. If items share mutable state, they
   are NOT independent — partition or serialize only those.
2. **Classify each item's resource profile.** Light (≤1–2 cores, fast) vs
   heavy (self-saturates a machine: many cores, large memory, or long
   runtime). Measure with a quick probe; don't guess.
3. **Pick the parallelism unit.**
   - For local/distributed subprocess work, shard into disjoint units across
     already available, authorized machines/containers when useful. For native
     agents, the parallelism unit is a runtime slot, not a local CPU core.
   - **Within a machine, run light items to machine concurrency** (cores /
     per-item cores). Heavy items get their own machine — a high
     `--max-workers` can't make a CPU-saturated item faster and just thrashes.
4. **Fill admitted capacity.** If N independent items exceed available slots,
   machine resources, quota, or authorization, state the binding limit and
   refill slots as lanes finish. Propose additional capacity only if useful;
   never provision it, spend money, or expand access without authorization.
5. **Prove the concurrency** using live native lane states/notifications or
   permitted local process/container counts and load, not by trusting the flag. A passed `--max-workers N` that yields
   1 running worker is a red flag — find the serializer (a lock, a saturated
   resource, or a serial driver).

## Resource-bound table

These are local subprocess examples; native agents obey runtime slots and
service quotas. Measurements and current workload replace the illustrative
counts below; authorized capacity is an upper bound.

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
- **Leaving admitted capacity idle.** "I have 4 machines so I'll run 4 at a
  time" when measured light-item capacity can fit 12. Fill existing capacity;
  if more machines are actually needed, name that bound rather than provision
  them without authority.
- **Broad-parallel without isolation.** Parallel writers sharing a mutable
  file/db → the real failure is the shared state, not the parallelism. Give
  each worker a disjoint workspace/output; single-writer for any merged
  artifact; order-deterministic results (sort by id, not completion order).

## Resource admission gate (mandatory — crash 2026-08-30)

Memory is a first-class resource bound. A harness process died silently at
the instant it forked a 20-minute foreground CLI delegate on a host at 92%
swap / memory-pressure WARNING / ~64MB free — the spawn itself was the kill
site, and silent self-exits leave no OS trace. That failure is real and this
gate stays mandatory. But **a false stop is also a failure**: refusing to
parallelize on a healthy machine costs real throughput and tempts reporting
a serial run as if the ceiling were zero.

**Do not gate on swap used/total ratio.** macOS sizes the swapfile
dynamically, so `vm.swapusage` used-vs-current-size can read >80% "full" on
a perfectly healthy machine indefinitely — used/total is not a saturation
metric. `kern.memorystatus_vm_pressure_level = 2` is WARNING/amber, not
critical (critical is 4); treating 2 as a hard stop over-triggers. (Observed
2026-09-02: 8.9GB/10.24GB swap + pressure=2 read as "stop" under the old
wording, while real available memory was 12.9GB and the pressure source was
a steady-state 11GB Virtualization.framework VM — a constant that doesn't
change whether you spawn 0 or 3 lanes. That was a false stop.)

Before spawning a new **local subprocess** lane/fleet or CLI delegate, apply
the host-appropriate checks below. Native lanes instead use the runtime slot
and permission gate above; do not probe inaccessible remote hosts:

1. **Probe available memory — the primary signal.**
   - macOS: `vm_stat | awk -v ps=$(sysctl -n hw.pagesize) '/Pages free/{f=$3}
     /Pages inactive/{i=$3} /Pages purgeable/{p=$3} /Pages speculative/{s=$3}
     END{gsub(/\./,"",f);gsub(/\./,"",i);gsub(/\./,"",p);gsub(/\./,"",s);
     printf "%.1f GB available\n",(f+i+p+s)*ps/1073741824}'` — available =
     free + inactive + purgeable + speculative, not free alone.
   - Read `sysctl kern.memorystatus_vm_pressure_level` as a secondary signal
     (1=normal, 2=warning, 3=urgent, 4=critical).
   - Linux: use `/proc/meminfo` `MemAvailable` (or `free -b`) and
     `/proc/pressure/memory` PSI. Resolve the current process's cgroup and
     mount from permitted `/proc/self/cgroup` and `/proc/self/mountinfo`.
     For cgroup v2, account for finite `memory.max` and `memory.high` headroom
     against `memory.current`, plus `memory.events`/`memory.pressure`; for
     v1 use available equivalent memory limit/usage files. Use the tightest
     applicable finite limit, not host RAM, for container admission. CPU
     concurrency is also bounded by affinity/cpuset and effective CPU quota
     (`cpu.max` on v2), not merely host core count. If metrics are unavailable,
     report that gap and keep admission conservative/provisional.
   - These are read-only probes; do not change cgroup or host settings.
2. **Attribute the pressure before reacting.** On macOS use
   `ps -Ao rss,comm -r | head`; on Linux use
   `ps -eo rss,comm --sort=-rss | head`
   to find the top-RSS consumer. If it's a steady-state VM/daemon
   (Virtualization.framework, colima, docker, qemu, lima), the pressure is
   structural — it won't improve by refusing to spawn, and it barely moves
   whether you spawn 0 or a few lanes.
3. **Apply graduated thresholds, not a binary stop.** The following numbers
   and pressure levels are macOS heuristics, not Linux PSI values. On Linux,
   admit lanes against measured per-lane demand, cgroup headroom, pressure
   trend and OOM events with a safety margin; never compare PSI percentages
   to macOS pressure levels. Recalibrate per host:
   - Available >8GB **and** pressure ≤2 → spawn normally.
   - Available 4-8GB **or** pressure = 3 → reduce lane count / prefer
     cheaper models, rather than deferring entirely.
   - Available <4GB **or** pressure = 4 → defer. Finish or stop only your own
     authorized heavy children first; spawning into genuine starvation risks killing
     the *parent* session, losing all lanes at once.
4. **Swap is a stop signal only when it's actively growing**, not from a
   used/total ratio. On macOS sample twice, seconds apart
   (`sysctl vm.swapusage; sleep 5; sysctl vm.swapusage`), and compare
   `used`. On Linux use permitted swap/pressure metrics and cgroup limits.
   Flat-but-high used/total is not evidence of saturation; `used` climbing
   between samples while available memory is also low is.
5. **Never fork a multi-minute CLI delegation (agy, codex, claude -p) as a
   foreground shell call.** Use the runtime's supported asynchronous process
   API with an explicit timeout and observable completion handle. A local
   `run_in_background` option applies only where documented; do not invent it.
   If asynchronous execution is unavailable, report that limit rather than
   launch a detached/unobservable process.
6. **Cap concurrent pytest lanes** in gRPC-loaded repos (macOS
   fork-unsafety: "multi-threaded process forked" SIGTRAP storms). 2-3
   lanes max per host unless measured safe; prefer sharding across
   machines.
7. **Watch delegate RSS.** A CLI delegate above ~2-3GB RSS is itself a
   heavy item — one per machine, per the resource-bound table.

## Isolation invariants (always, when parallelizing)

- Disjoint per-worker workspaces / output files.
- Single-writer for any shared ledger/manifest.
- Order-deterministic merged results (sort by id, never completion order).
- Instance-scoped container/process names so concurrent workers can't collide.
- Never relax a correctness/validation contract for speed — if a result's
  determinism can't be preserved, THAT is the written justification for serial.

## Coding and verification lane routing

Keep coder and verifier in separate contexts. Prefer the currently supported
native lane tools under the runtime gate. When an explicitly selected local
AGY route is already available and authorized, load its installed coder/verifier
profiles through their resolved paths for launch, logging, isolation, and
signaling details. For that admitted local route, resolve these defaults through
the configured `CLAUDE_HOME` and verify the profiles are present:

- Coder: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`
- Verifier: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`

Do not assume these profiles exist or treat profile text as permission to
override the current runtime. A missing local profile is an unavailable route,
not authorization to install tools, change permissions, or call a provider.

### Two-agent pair template

```text
PAIR TASK: <bounded task and explicit file scope>
CODER: use the admitted lane tool; implement and signal IMPLEMENTATION_READY with Revision: <exact git SHA> and Worktree: <absolute path>.
VERIFIER: use a distinct admitted lane/context; independently verify that exact revision and signal VERIFICATION_COMPLETE or VERIFICATION_FAILED.
FALLBACK: after a concrete lane failure, retry only that bounded lane through another available, authorized route with a fresh workspace/context and unchanged evidence contracts.
```

## Fallback precedence

1. Use supported native lanes unless the user's selected environment/route
   requires an already admitted local CLI pair.
2. Record the concrete per-lane failure. Prefer another supported native lane
   or a currently available capable model allowed by live model-selection
   rules. A model rejection is not permission to name an obsolete model or
   reach another provider. Retry transient capacity failures only as allowed
   by the live tool; otherwise wait for a slot or report the blocker.
3. Use an external CLI route only within existing explicit authorization and
   established capability. If no admitted route works, stop that lane and
   report its blocker while independent work continues.

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
unique output/log paths. Start a fresh native agent context or, only on an
admitted AGY route, a fresh `agy --new-project` invocation for each attempt;
never reuse a prior attempt's conversation. If the runtime cannot allocate
the required isolated workspace or exact revision, report the lane blocked
rather than silently weakening this contract.
Each coder retry must carry the exact prior `Revision`, pin its workspace to
that revision before making changes, rerun focused checks, and finish with an
explicit scoped commit plus an empty status before sending the next handoff.
Verifier retries must carry the exact handed-off `Revision`, pin their workspace
to that revision, rerun focused checks read-only, and never modify files or create a commit.
When worktree isolation is allocated, coder and verifier attempts enter fresh,
per-lane worktrees and unique per-attempt output paths before invoking the admitted lane tool;
each worktree and output path must be disjoint from the other lane and all
previous attempts. `Revision` is the committed clean implementation revision:
the coder must make a final scoped commit and confirm its worktree is clean
before sending IMPLEMENTATION_READY. The verifier must reject dirty inherited
state and verify against `Revision`.

## Current model routing

Resolve model choices from the live runtime catalog and current user/runtime
selection rules. Prefer the cheapest capable allowed tier when explicit
selection is supported; inherit the required runtime default otherwise.
Record per-lane failures and preserve task scope, fresh context, isolation,
and independent verification on retry. Historical wrapper names or model IDs
are not an active fallback ladder or permission to call another provider.

## One-line form (for config files)

> Parallelize any task to its real ceiling — any independent-item work runs to
> its real resource bound, not an arbitrary worker count or one-at-a-time;
> fill all useful, admitted capacity; batch when constrained by measured
> resources, runtime slots, permissions, or dependencies.

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
   and you have 4, use already-authorized spare capacity or state the limit;
   additional provisioning needs its own authority.

## Resource admission gate (macOS) — source of truth

Origin: session crash 2026-08-30 (a foreground multi-minute CLI fork under
apparent swap starvation killed the parent session and every lane); thresholds
corrected 2026-09-02 after the swap-ratio model proved wrong.

On macOS only, run this before local subprocess lanes/fleets or CLI
delegations, or when diagnosing that Mac's memory pressure. Native agents use
their runtime slot gate; Linux subprocesses use the Linux/cgroup gate above:

1. **Available RAM** from `vm_stat`:
   `(free + inactive + purgeable + speculative) × page_size`.
2. **Top RSS consumer**: `ps -Ao rss,comm -r | head`.
3. **Pressure**: `sysctl kern.memorystatus_vm_pressure_level` — 2 is
   amber/informational, not a stop condition; only 4 is critical.

**Never gate on `vm.swapusage` used/total.** macOS sizes the swapfile
dynamically, so an "89% full" swapfile can coexist with 12+ GB available.

| Available RAM | Pressure | Action |
|---|---|---|
| > 8 GB | ≤ 2 | spawn normally |
| 4–8 GB | 3 | reduce lane count |
| < 4 GB | 4 | defer spawns |

Even when deferring, attribute the pressure to its real top-RSS source first —
it is often a steady-state VM or daemon, not the agent fleet.

Never fork a multi-minute CLI delegation (`agy`, `codex`, `claude -p`) as a
foreground shell call: use a supported asynchronous API with an explicit
timeout, then read its output artifact on completion notification.

## Model-tier routing and delegation defaults

Origin: `${CLAUDE_HOME:-$HOME/.claude}/CLAUDE.md` § Parallel subagents and model routing (compressed
there to a pointer 2026-09-06). Apply these preferences only within the live
runtime's model-selection, delegation, and permission rules.

- Prefer the **cheapest capable available tier** when the runtime permits
  explicit selection; otherwise retain its default/inherited model.
- For small/mechanical coding and polling, use a capable lower-cost current
  model if allowed. Do not assume local wrappers, imported roles, or retired
  model identifiers are available.
- Top tier (the session's own model): reserve for adversarial judgment, or
  only after a cheaper tier has already failed on that unit.
- Before you repeat a delegated claim **or act on it**, read the artifact it
  rests on — and read the part that substantiates the specific claim, not just
  that an artifact exists. Check its provenance too: a log from the wrong SHA, a
  run that predates the change, or an empty result file all pass a presence
  check and prove nothing. A lane's own "done" is a claim, not the evidence for
  it, and neither is its summary of its own work. Acting on it counts: closing a
  bead, marking a task complete, or building on a lane's "fixed" all carry the
  claim forward as if it were checked. This is artifact-checking on results you
  carry forward, not a standing verification pass over every lane.
- Do not spawn a subagent to check work **you** did yourself — that is
  self-verification you already perform. This does not touch the coder/verifier
  pair above: a verifier reviewing a *different* agent's revision is an
  independent lane, not a re-check of your own output, and stays required
  wherever the pair template is used.
- Delegate coding (edits, new files, generated code) through available native
  tools or an already admitted local sidekick route when the track is independent
  and large enough to earn its own
  context. Work you can finish in a handful of tool calls, do in the root
  session — delegating it costs more than it saves.

Use the live runtime's lane-status/read/notification tools for liveness.
If an admitted local sidekick route provides transcript-proof liveness, load
its installed skill and use only permitted transcript paths. Never inspect
restricted session roots or infer completion solely from an idle state.

## Collecting results — check every channel before redoing the work

A finished lane is not a delivered lane. Direct result delivery to the parent
can fail silently: a supported lane-status tool shows `idle` (its turn ended) and no report
ever arrives. **`idle` means "finished", not "reported".**

Before re-doing any lane's work yourself:

1. **Ask the lane.** Use its supported message API; if it is idle, use the
   documented resume/follow-up action so it can resend. Do not assume a plain
   message starts a new turn or that another runtime's `SendMessage` exists.
2. **Check the side channels it was told to write.** If lanes were instructed to
   post to beads (`br comments add`), write files, or comment on a PR, read
   those. A lane whose direct message vanished has usually still written its
   artifact.
3. **Only then re-run it** — and if you do, say so in the final report, because
   the duplicated cost is real.

Failure mode this kills (observed 2026-09-07): 15 lanes all completed, direct
delivery silently dropped every report, the orchestrator re-did the analysis
itself, and the original 15 reports arrived afterwards — while the bead-comment
channel had been working the entire time and was never checked. Roughly half a
session's review work paid for twice.

Corollary: **verify the delivery path on the first lane before scaling to N.**
Spawn one, confirm its result actually reaches you, then fan out. A broken
channel discovered at N=1 costs one lane; at N=15 it costs fifteen.
