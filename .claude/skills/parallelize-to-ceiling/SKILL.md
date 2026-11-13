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

When N independent items fit within the current host's measured task-specific
capacity, run **all N at once on that host**. Prefer the current host when it is
eligible and has headroom. Add another eligible machine/container only when the
current host cannot safely admit the work under the host-specific rules in
`references/host-load-balancing.md`, or another measured constraint makes it
ineligible; a remote host having more idle CPU by itself is not a reason to
transfer. Use already available, authorized capacity by default; greater demand
does not authorize provisioning or additional spend.

Apply higher-priority shared routing gates before choosing a host. In
particular, below 25% Mac CPU idle, a well-scoped coding task follows the
`~/.codex/AGENTS.md` `/dot` cloud-computer instruction; current-host-first
placement applies to work that remains eligible for local execution, such as
review lanes.

Serialize only with a named determinism/corruption constraint. A driver that
only supports serial for parallelizable work is **fixable tooling debt**, not
the answer.

This applies to local CLI work and to remote/distributed compute equally, to
one-off scripts and to production pipelines alike.

`/parallel` means **maximum parallelism within measured eligible capacity**:
when invoked, schedule every step from its true dependencies, not from list
order, and overlap everything that fits the current host's safe resource bound.
A step waits only on outputs it actually consumes. Read-only verification
(reviews, audits, evidence checks) never blocks a reversible action (push, CI
start, preview deploy); run them side by side and handle a finding with a
follow-up commit. Start the longest pole (CI, real-LLM runs, slow builds) as
early as its inputs allow. Hand idle-capable work to available lanes up to that
bound; use another host only under the selection rules above. Merges,
force-pushes, and destructive actions keep their own gates and are never
"overlapped" past them.

Every subagent or lane launched under `/parallel` drives its unit to done:
implement, verify, and push or produce the artifact. It does not return a
plan or analysis for the parent to execute, unless the lane is explicitly a
read-only review lane. Say so in the lane's prompt. **Single integration PR rule (`pr-quantity-control`)**: When parallel coding lanes implement parts of a single feature, their worktrees/branches must merge into **one shared integration branch/PR** (or at most `≤ 3` coarse stage PRs per `${CLAUDE_HOME:-$HOME/.claude}/skills/pr-quantity-control/SKILL.md`), never N separate GitHub PRs.

## Timeline, parallel lanes, and milestones (mandatory)

Read and apply `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/references/timeline-milestones.md`
on every invocation. Always include a timeline, maximize useful independent
lanes within the measured resource ceiling, and report milestones every
20 minutes with an hourly rollup during active work. Preserve this command's
planning, handoff, and execution authorization boundaries.

## The decision procedure

For cross-host CPU, RAM, disk, and I/O measurements and safe routing, follow
[`references/host-load-balancing.md`](references/host-load-balancing.md).
For Linux transfer, follow
`${CLAUDE_HOME:-$HOME/.claude}/skills/lm/SKILL.md`;
for existing cmux Cloud capacity, follow
`${CLAUDE_HOME:-$HOME/.claude}/skills/cc/SKILL.md`.

1. **Enumerate the independent items.** Rows, files, tests, migrations, doc
   sections, instances, jobs, agent lanes. If items share mutable state, they
   are NOT independent — partition or serialize only those.
2. **Classify each item's resource profile.** Light (≤1–2 cores, fast) vs
   heavy (self-saturates a machine: many cores, large memory, or long
   runtime). Measure with a quick probe; don't guess.
3. **Pick the parallelism unit.**
   - **Current-host-first for host selection.** Keep work on the current host
     when it is eligible and has task-specific headroom. Do not move work just
     because another host has more idle CPU. Within the current host, run light
     items to measured machine concurrency (cores / per-item cores); heavy
     items get a machine where they will not contend with another self-saturating
     workload.
   - **Shard across hosts when needed.** Split independent items across other
     suitable, already available and authorized hosts only when the current
     host's measured workload-specific admission rule refuses the next lane,
     or another measured constraint makes the current host ineligible. A
     comparative idle-CPU ranking alone is not a reason to transfer.
4. **Scale across eligible capacity.** Use current-host headroom first, then
   eligible remote capacity when the current host cannot safely admit the work.
   If the ideal needs more capacity than is available, report that gap; do not
   provision machines or incur new spend without separate authorization.
5. **Prove the concurrency** by sampling live CPU idle and process/container
   counts, not by trusting the flag or load average. A passed `--max-workers N`
   that yields
   1 running worker is a red flag — find the serializer (a lock, a saturated
   resource, or a serial driver).

## Resource-bound table

| Item profile | Per-machine concurrency | Parallelism unit | Why |
|---|---|---|---|
| Light (small tests, quick scripts, transforms) | ~4–6 on an 8-core machine | workers on current host first; add hosts only when its safe capacity is full | each uses ~1–2 cores |
| Heavy CPU (big builds, ML training, large test suites) | 1 (self-saturates the cores) | **its own machine** | self-parallelizes; a worker flag can't help |
| IO/network-bound (API sweeps, fetches, downloads) | high (10s) | workers, not machines | CPU idle; bound is latency/rate-limit |
| Memory-bound | per host's RAM admission tier | fewer per machine | measure available RAM and current RSS |

## Worked example

A sharded gold-test preflight passed `--max-workers 1` and ran only 4 rows at
once across 4 machines; the real ceiling was per-item CPU and machine count,
never the worker flag. Full numbers and the heavy/light split:
[`references/worked-examples-and-incidents.md`](references/worked-examples-and-incidents.md#gold-test-preflight-across-4-machines).

## Failure modes this kills

- **The token worker count.** `--max-workers 3` chosen by feel instead of a
  measured per-item bound. Ask: what does one item actually use?
- **The passed-flag mirage.** `--max-workers 4` passed but 1 worker running
  (a hidden lock / saturated resource / serial driver). Measure live.
- **Ignoring eligible capacity.** Underfilling the current host when independent
  work fits more workers there — measure the bound and use its safe capacity
  first; add remote capacity only when that bound is full or another measured
  constraint excludes the current host.
- **Broad-parallel without isolation.** Parallel writers sharing a mutable
  file/db → the real failure is the shared state, not the parallelism. Give
  each worker a disjoint workspace/output; single-writer for any merged
  artifact; order-deterministic results (sort by id, not completion order).

## Resource admission gate (mandatory — crash 2026-08-30; command source of truth)

Memory is a first-class resource bound. A harness process died silently at
the instant it forked a 20-minute foreground CLI delegate on a host at 92%
swap / memory-pressure WARNING / ~64MB free — the spawn itself was the kill
site. That gate stays mandatory. But **a false stop is also a failure**:
refusing to parallelize on a healthy machine costs real throughput and tempts
reporting a serial run as if the ceiling were zero. Incident detail and the
2026-09-02 false-stop observation:
[`references/worked-examples-and-incidents.md`](references/worked-examples-and-incidents.md#resource-admission-incidents).

**Do not gate on swap used/total ratio.** macOS sizes the swapfile
dynamically, so `vm.swapusage` used-vs-current-size can read >80% "full" on
a perfectly healthy machine indefinitely — used/total is not a saturation
metric. Under the current shared action policy, pressure 2 is informational
and not the defer tier; treating it as a hard stop over-triggers when
available memory is ample.

Before spawning any new lane, subprocess fleet, or CLI delegation, **and any time
diagnosing whether this Mac is under memory pressure** (exact probe
commands: [`references/specialist-commands.md`](references/specialist-commands.md#memory-admission-probes)):

1. **Probe available memory — the primary signal.**
   - macOS: available = free + inactive + purgeable + speculative (times page
     size) from `vm_stat`, not free alone.
   - Read `sysctl kern.memorystatus_vm_pressure_level` as a secondary signal
     use the current shared numeric action policy: pressure 3 reduces
     concurrency; pressure 4 is a defer condition by itself.
   - Linux: `free -g` available column; do not map macOS pressure numbers
     onto Linux.
   - Takes one second.
2. **Attribute the pressure before reacting.** Find the top-RSS consumer (command in the reference). If it's a steady-state VM/daemon
   (Virtualization.framework, colima, docker, qemu, lima), the pressure is
   structural — it won't improve by refusing to spawn, and it barely moves
   whether you spawn 0 or a few lanes.
3. **Apply graduated thresholds, not a binary stop** (heuristics, not
   physics — recalibrate per host):
   - Available <4GB **or** macOS pressure =4 → **defer new heavy
     work**. Inspect active children and stop only task-owned work under its
     existing authorization; do not kill unrelated processes.
   - Available 4–8GB **or** macOS pressure =3 (with at least 4GB available) →
     **reduce lane count**, rather than deferring entirely.
   - Available >8GB **and** macOS pressure ≤2 → **spawn normally**.
4. **Swap is evidence, not a separate defer tier.** Never defer from a static
   used/total ratio. If available memory is low, sample twice, seconds apart
   (command in the reference), and compare
   `used`. Flat-but-high used/total is not evidence of saturation; actively
   growing swap plus low available memory informs the measured tier above.
5. **Never fork a multi-minute CLI delegation (agy, codex, claude -p) as a
   foreground Bash call.** Always `run_in_background` + explicit timeout —
   a foreground fork pins the parent at the worst possible moment. Read the
   output file on the task notification. In Claude Code, background commands
   owned by a foreground subagent end with that subagent's run; do not hand
   off a long-lived job that way. Subagents run bounded foreground steps
   that finish inside their own turn; the top-level session owns longer jobs.
6. **Cap concurrent pytest lanes** in gRPC-loaded repos (macOS
   fork-unsafety: "multi-threaded process forked" SIGTRAP storms). 2-3
   lanes max per host unless measured safe; fill the current host's safe
   capacity first, then shard across machines only when that bound is full or
   another measured constraint makes the current host ineligible.
7. **Watch delegate RSS.** A CLI delegate above ~2-3GB RSS is itself a
   heavy item — one per machine, per the resource-bound table.

### /prw endpoint lanes

For Claude Code, start each `/prw` endpoint lane as a top-level session so it
can hold the session goal and receive its own background-job results (waiting
rules: [pr-workflow-manager](../pr-workflow-manager/SKILL.md#terminal-goal-and-entry-contract)).
Its first prompt must be the coordinator's complete, authoritative task brief,
including the intended `/prw <PR URL>` endpoint; a bare PR URL or command is
not a sufficient handoff. The brief must preserve the requested endpoint and
task scope, any stop point or no-merge hold, the pinned source/revision, the
original authority and approval constraints, and the remaining deadline. Before
starting `/prw` or taking other action, the lane must confirm that it accepts
the scope and restate those constraints. If the brief is missing or conflicts
with the coordinator's instructions, it must stop and return the discrepancy
for resolution. The lane runs under the operator's existing permission
settings. For another runtime, use its supported independent-session interface
and provide the same complete brief and scope confirmation; if none is
available, keep endpoint ownership in the coordinator and delegate only bounded
steps.

## Isolation invariants (always, when parallelizing)

- Disjoint per-worker workspaces / output files: resolve disposable build output, test scratch, and evidence bundles dynamically via canonical [`${CLAUDE_HOME:-$HOME/.claude}/skills/scratch-space/SKILL.md`](../scratch-space/SKILL.md) using `diskm scratch-new <repo-path> <purpose> --kind build|evidence` or `${CLAUDE_HOME:-$HOME/.claude}/skills/scratch-space/scripts/scratch-dir.sh [subpath]`; allocate git worktrees under `~/.worktrees/<repo>/<name>` via `diskm worktree-new <repo-path> <branch>`.
- Single-writer for any shared ledger/manifest.
- Order-deterministic merged results (sort by id, never completion order).
- Instance-scoped container/process names so concurrent workers can't collide.
- Lanes clean up their own `mktemp` scratch without a permission prompt: delete
  it inside the script that created it (`trap`/`finally`), or `mv` it under
  the active Scratch volume resolved via `${CLAUDE_HOME:-$HOME/.claude}/skills/scratch-space/scripts/scratch-dir.sh` (or `/tmp`). Never `rm -rf "$(...)"` or `rm -rf "$VAR"`; the harness cannot resolve
  those targets and stops the lane to ask.
- Never relax a correctness/validation contract for speed — if a result's
  determinism can't be preserved, THAT is the written justification for serial.

## Coding and verification lane routing

For automatic review of a Codex-origin PR, the PR driver's shared review-dispatch
budget governs independent verifier and reviewer lanes, including delegated
runtimes and fallback attempts. Start only assignments reserved by the driver;
if the budget or authority is unclear, stop automatic reviewer dispatch and ask
the driver. Ordinary coder result inspection and tests are not review seats.
Direct user requests for a specific review, required external gates and non-PR
work retain their applicable rules.

**Precedence, in order (resolve the "AGY pair" and "cheapest tier" sections
below by this order, don't pick whichever is more convenient):**

1. **An explicitly requested method wins.** If the user or task named a
   specific tool, model, or workflow, use it — this section doesn't override
   that.
2. **Work finishable in a handful of tool calls stays in the root session.**
   Don't bootstrap an AGY pair, a subagent, or any delegated lane for a
   change you can just make. Delegating it costs more than it saves and is
   the single most common way this skill's own guidance gets misapplied
   (session incident 2026-09-25: repeated AGY relaunches and drafting cycles
   dominated the critical path on changes that were a few lines each).
3. **Bounded mechanical work that's too large for a handful of calls, but
   doesn't need adversarial review,** goes to the cheapest capable tier
   (Codex: a `gpt-6-luna` subagent; Claude: haiku, or sonnet when the lane
   needs judgment) per Model-tier routing
   below — not the AGY pair. For simple independent tasks, the Luna lane may
   also drive the task through its focused checks and deliver the result; keep
   the root session responsible for scope and integration.
4. **Only once scope actually justifies a dedicated coder + independent
   verifier** (a track large enough to earn its own context, where a second
   independent pass adds real value) do you reach for the AGY pair described
   next.
5. **Parallel coding lanes for one feature merge into one shared integration branch/PR** — the single integration PR rule in Core law (≤ 3 coarse stage PRs per `${CLAUDE_HOME:-$HOME/.claude}/skills/pr-quantity-control/SKILL.md`), never N separate PRs.

For implementation and review lanes that clear step 4 above, prefer the
installed AGY CLI pair. Use the canonical profiles for the complete launch,
logging, isolation, and signaling contracts:

- Coder: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md`
- Verifier: `${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md`

**Before writing the handoff**, resolve three things — skipping this is how a
narrow evidence gap grows into an unrequested replacement framework (incident:
[`references/worked-examples-and-incidents.md`](references/worked-examples-and-incidents.md#narrow-gap-became-a-replacement-framework-2026-09-26)):

1. **State hard constraints vs. preferences** in the task line — the coder
   can't tell which parts of your framing are mandatory and which are just
   how you'd phrase it, and will otherwise satisfy the letter over the intent.
2. **Enumerate direct consumers of the change** before coding starts — tests,
   configs, or budgets that read the touched code path. Discovering these
   mid-implementation is what turns one edit into a serial fixup chain.
3. **Name the existing evidence driver to reuse**, and the minimal override it
   needs. A narrow gap gets a thin override on that driver — never a new
   framework. If the existing driver can't be thinly overridden, that's a
   finding to report, not license to build a replacement.

### Two-agent pair template

The copy-paste `PAIR TASK` handoff block is in
[`references/specialist-commands.md`](references/specialist-commands.md#two-agent-pair-handoff-template). It must carry the
exact committed `Revision` and absolute `Worktree` of the coder's hand-off, and
its fallback is governed by the Fallback precedence section below.

## Fallback precedence

The pair template's `FALLBACK` line ([`references/specialist-commands.md`](references/specialist-commands.md#two-agent-pair-handoff-template)) is governed by this order:

1. Start with the AGY pair as the primary implementation and verification lanes.
2. After a concrete AGY lane failure, retry the same bounded lane with a Codex
   subagent using `gpt-6-luna`. If Luna is unavailable or concretely fails, or
   the task requires more capability, retry it with a Codex subagent using
   `gpt-6.1-terra`. Only if Terra is unavailable, concretely fails, or lacks
   required capability, use a Codex subagent with `gpt-6.1-sol` as the final
   fallback. Advance only after a concrete failure, unavailability, or
   demonstrated capability gap at the preceding tier; preserve the same
   bounded scope and verification requirements. Never use 5.6 models.
3. Use `claudem` or an own cheap agent only when the ordered Codex route is
   unavailable; preserve the same bounded scope and verification requirements.

## Isolation contract

Coder and verifier remain distinct lanes and contexts. The orchestrating caller
decides whether each lane and retry operates in an allocated worktree on a fresh
branch or directly within the caller's workspace. Every attempt, including
initial execution and each retry, uses a fresh workspace (either an allocated
worktree on a fresh branch or caller-provided clean workspace) and unique
output/log paths disjoint from both coder and verifier lanes and from all
previous attempts.
Attempts must not read or reuse partial files, logs, or outputs from another
attempt, and the verifier must independently rerun focused checks before signaling completion.
When worktree isolation is used, every retry uses a fresh worktree on its own
branch and unique output/log paths. Start a fresh `agy --new-project` invocation
for every attempt; never pass a conversation-resume option or use an equivalent
conversation-reuse mechanism.
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

For Codex parallel lanes, use this default progression unless the caller
explicitly requests a different model:

`gpt-6-luna` → `gpt-6.1-terra` → `gpt-6.1-sol`

Start with Luna for bounded work. Escalate to Terra when Luna is unavailable,
concretely fails, or the task requires more intelligence or capability. Use Sol
only as the final fallback after Terra is unavailable, concretely fails, or
lacks required capability. Record the specific reason for each escalation and
retry the same bounded lane with the next explicit model. Explicit model
requests remain authoritative; this routing rule does not grant review,
approval, or merge authority. Never use 5.6 models.

## One-line form (for config files)

> Parallelize independent work up to the current host's measured safe resource bound first; add suitable, already available and authorized hosts only when that bound is full or another measured constraint excludes the current host; do not transfer solely for comparative idle CPU. Provisioning or new spend requires separate authorization.

## Quick diagnostic — "why is it slow?"

Run this in order; stop at the first that explains it:

1. **Are items independent?** If they share mutable state, fix isolation first.
2. **Is the driver even using more than one worker?** `ps` / `docker ps` /
   `kubectl get pods`. A passed `--max-workers N` is not proof — find the
   serializer.
3. **Is the machine CPU- or memory-bound?** Measure CPU idle using the
   platform commands in [`references/host-load-balancing.md`](references/host-load-balancing.md)
   and inspect live RSS. Load average alone is not a saturation verdict.
4. **Is the per-item bound actually IO/network?** Workers/machine can go high
   (10s); the ceiling is rate limits, not cores.
5. **Are you using eligible capacity?** Fill the current host's safe measured
   capacity first. Route remaining independent work to another suitable,
   already available and authorized host only when that bound is full or
   another measured constraint excludes the current host; do not transfer just
   because another host has more idle CPU. Additional provisioning or spend
   needs separate authorization.

## Model-tier routing and delegation defaults — source of truth

Origin: `${CLAUDE_HOME:-$HOME/.claude}/CLAUDE.md` § Parallel subagents and model routing (compressed
there to a pointer 2026-09-06; this section is the full policy).

- Route every independent unit to the **cheapest capable tier** — never
  silently inherit an expensive session model for delegated work. Prefer fast,
  low-cost subagents for bounded tasks; escalate when capability or a required
  independent review justifies it.
- For every lane, name the model explicitly and verify the model that actually
  ran from launch or runtime metadata before relying on its result. If the
  cheapest capable tier cannot do the bounded task, state the concrete failure
  or capability gap that justifies escalation. Honor an explicit user model
  choice under the precedence above.
- Small/mechanical bounded coding:
  - AGY CLI (`agy`) and Antigravity native subagents (`invoke_subagent`): use
    Gemini 3.8 Flash tiers per the Gemini Model Invariant below; exact flag and
    `Model:` values are in [`references/specialist-commands.md`](references/specialist-commands.md#gemini-flash-lane-flags).
  - Codex: spawn a `gpt-6-luna` subagent when available; escalation and
    fallback follow the Codex model routing section above (it is the single
    owner of that order). Never use 5.6 models.
  - Claude: `haiku` subagent.
- Simple task-driving, polling, and mechanical sweeps: the available Gemini 3.8 Flash (`Model: "flash"` / `--model gemini-3.8-flash-medium`), Luna, or
  haiku/mini tier.
- Judgment-bearing bounded lanes (driving a PR through `/prw`, capturing and
  adjudicating evidence, non-trivial fixes, first-pass code review): Claude
  `sonnet` subagent; Codex `gpt-6.1-terra`; AGY `gemini-3.8-flash-high`. Use
  haiku only when the lane is mechanical, and escalate past sonnet only under
  the top-tier rule below.
- Apply the same handoff discipline to bounded independent investigation,
  tests, monitoring, and mechanical follow-through when it costs less than
  keeping that work in the parent session. Give each lane an explicit output
  and completion condition, and let it run asynchronously when supported.
  For finite operations, retain the yielded session handle and resume that
  same operation through its exit receipt. For a service meant to stay running,
  verify readiness and explicitly retain or transfer ownership instead. Empty
  or partial output is not permission to launch a second copy.
- **Child task contract.** Every work dispatch carries, by pointer where
  possible: the exact workspace and source snapshot (path, SHA or hash);
  allowed actions and prohibited reads and actions (a snapshot-only task gets
  no Git, history, checkout or directory setup); the repository rules that
  bear on the unit; acceptance criteria; and, when code changed, a boundary
  brief of likely edges as examples, not required work (missing or null data,
  limits, provenance, roles and timestamps, symlinks, failures, concurrency).
  Pass user restrictions verbatim. The child returns compact findings, exact
  paths and acceptance proof, never transcript copies; its receipt records the
  model and scope that ran. Review seats are not work dispatches: source and
  advice seats take input only from [static-review](../static-review/SKILL.md)
  and `/er` seats from [evidence-review](../evidence-review/SKILL.md), never
  this brief.
- Before waiting on a lane, confirm it started (a live handle, process or
  session); assignment is not progress.
- A worker owns its assigned checks through completion and reports when done,
  blocked, or awaiting a material decision. The parent should not duplicate
  the worker's execution or repeatedly poll while it is progressing; use
  asynchronous completion notifications, continue independent parent work,
  and inspect the supporting artifact on delivery.
  After an empty wait, do available independent work; if none remains, wait on
  the existing completion handle until a meaningful deadline instead of chaining
  short empty waits. Report progress at the runtime cadence. Never call a wait
  on a finished handle; inspect its delivered result or transcript first.
- **Gemini Model Invariant**: Never use Gemini 3.1 Pro (or older Gemini Pro models), and never leave `Model: "inherit"` or `"pro"` on any subagent lane, bounded or not (AGY CLI `agy` and Antigravity native `invoke_subagent` alike). Always use Gemini 3.8 Flash or later (exact `agy --model` and `invoke_subagent` `Model:` values: [`references/specialist-commands.md`](references/specialist-commands.md#gemini-flash-lane-flags)).
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
- Delegate coding (edits, new files, generated code) to `/s` (sidekick) or a
  subagent when the track is independent and large enough to earn its own
  context. Work you can finish in a handful of tool calls, do in the root
  session — delegating it costs more than it saves. This exception applies to
  checks and follow-through too when the handoff costs more than the work.

Teammate/subagent stall detection (transcript-proof liveness) is owned by
`${CLAUDE_HOME:-$HOME/.claude}/skills/sidekick/SKILL.md` § Transcript-proof liveness — do not
duplicate that procedure here.

## Collecting results — check every channel before redoing the work

A finished lane is not a delivered lane. Direct result delivery to the parent
can fail silently: `ListAgents` shows `idle` (its turn ended) and no report
ever arrives. **`idle` means "finished", not "reported".**

Before dispatching a fan-out, resolve each intended recipient and confirm its
task prompt and required inputs are present. A successful dispatch call with no
valid targets or missing task inputs launches no useful work; correct that
before scaling the fan-out.

The inverse trap is just as real: `running` means "active", not "progressing".
A lane producing frequent transcript updates, tool calls, or status pings is
not evidence of progress by itself — only a promised artifact, test result,
or completed acceptance criterion is (incident: [`references/worked-examples-and-incidents.md`](references/worked-examples-and-incidents.md#active-is-not-progressing-2026-09-25)). If a lane has been running for a while with
activity but no artifact, reassess and re-scope or switch it to a cheaper
path per the routing precedence above — don't wait longer just because it's
still "running", and don't restart an equivalent job automatically without
changing what it's being asked to do.

Before re-doing any lane's work yourself:

1. **Check the lane's state and use the current runtime's supported controls.**
   First inspect the lane and any existing artifact. A message to a running
   lane can steer it; a message to an idle lane may only queue or deliver text
   and may not start a new turn. When the lane is idle and the result is still
   needed, use that runtime's documented start, resume, or follow-up operation
   to trigger work. Do not assume a message call starts execution. Distinguish
   a queued or delivered prompt, an acknowledged or started turn, and a
   completed artifact; tool-call success alone proves only the call succeeded.
2. **Check the side channels it was told to write.** If lanes were instructed to
   post to beads (`br comments add`), write files, or comment on a PR, read
   those. A lane whose direct message vanished has usually still written its
   artifact.
3. **Only then re-run it** — and if you do, say so in the final report, because
   the duplicated cost is real.

Failure mode this kills: a fan-out whose direct delivery silently dropped every
report while the bead-comment channel worked the whole time, so the orchestrator
paid twice for the same review work (detail:
[`references/worked-examples-and-incidents.md`](references/worked-examples-and-incidents.md#collecting-results-failure-2026-09-07)).

Corollary: **verify the delivery path on the first lane before scaling to N.**
Spawn one, confirm its result actually reaches you, then fan out. A broken
channel discovered at N=1 costs one lane; at N=15 it costs fifteen.
