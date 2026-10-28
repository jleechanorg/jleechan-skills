# Host load balancing

Use this reference when independent work is heavy enough that CPU, RAM, disk capacity, or I/O may limit progress. Choose among hosts already available to the task; this guidance does not authorize new spending, VM provisioning, credential movement, cleanup, or data exposure.

## Measure the constraint

- CPU: measure idle on each candidate and inspect the task's CPU use or a comparable run. On macOS use `top -l 2 -n 0 -s 2 | grep 'CPU usage' | tail -1`; on Linux use `top -bn2 -d1 | grep '%Cpu' | tail -1`. Do not use load average alone as a saturation verdict.
- Mac heavy-lane cap: below 25% CPU idle, run at most two heavy lanes and never two test suites concurrently; below 10% idle, start no new heavy lane. Re-measure before each new batch. Apply Linux CPU decisions from measured host capacity and workload; do not transfer these Mac-only thresholds.
- RAM: macOS available memory is `(free + inactive + purgeable + speculative) × page_size`; Linux available memory is the `free -g` available column. Defer new heavy work only below 4 GB available or at macOS pressure level 4. Reduce lane count at 4–8 GB available or macOS pressure level 3 (with at least 4 GB available). Normal admission requires above 8 GB; on macOS also require pressure at most 2. Use the current numeric action tiers; do not assume operating-system labels or map macOS pressure numbers onto Linux. Attribute the top RSS consumer before reacting; ignore a static swap-used/total ratio.
- Disk: run `df -h` on the filesystem holding the checkout, temporary files, and outputs. Estimate growth from a comparable task or known artifact sizes, then compare with free space. If growth is unknown, say so and recheck before starting large-output work. Never delete files to make room.
- I/O: inspect active processes and available host I/O indicators where supported. Prefer the candidate with less contention for a disk- or I/O-bound task; report when the capacity signal is unavailable.

## Select an eligible host

Choose the suitable host with the most headroom in the resource that bounds the task, while accounting for transfer time, toolchain, hardware, signing, authorization, data access, and review constraints. Keep Mac-only hardware or toolchain work on a Mac and Linux-only work on Linux. Use `/linux-mirror` or `/mac-mirror` for the established SSH/session handoff. Use the installed cmux Cloud workflow only after `cmux cloud ls --json` confirms an already-running machine; pin its exact ID and measure capacity with short, read-only probes against that ID. Do not use routing or a probe to provision or resume a VM: opening or executing against a paused paid VM can restart billing. If no eligible host fits, defer only that heavy run and continue independent safe work.

## Preserve task ownership across transfer

Prepare a task-isolated worktree/branch containing only changes owned by this task, using the approved worktree-creation path. Stage and commit explicit task-owned paths; leave unrelated dirty files in their original checkout, untouched. Never reset, clean, stash, overwrite, or delete unrelated work to satisfy a mirror preflight. If the task changes cannot be separated safely, continue safe independent work and report the concrete blocker.

Before transfer, record source, destination, branch, and exact task commit SHA. Verify the destination uses that SHA and has the required toolchain and authorized credential path; never copy secrets into prompts, logs, or repository config. Confirm remote work actually started and produced attributable output; a session-ready marker proves transport only. Stop source-side writes to the same task/branch after handoff. Resume local writes only after the remote lane stops and its final SHA/state are checked. Sample live worker/process counts to prove intended concurrency.

## Contract

- **Normative outcome:** Route a resource-bound task only to a measured, suitable, authorized host with sufficient headroom, preserving one writer and unrelated work.
- **Non-goals:** No new paid capacity, automatic VM wake, deletion/cleanup, credential changes, or relaxation of toolchain, authorization, merge, or destructive-action rules.
- **Acceptance:** Fresh measurements support host selection; the task SHA is verified remotely; remote activity is attributable; there is one writer for the task; unrelated source dirt remains unchanged.
- **User story:** When one host lacks task-specific headroom, the agent moves the isolated work to a suitable available host without disturbing unrelated changes.
- **Proof:** Check the CPU/RAM rules, disk estimate, cloud pinning, mirror links, and ownership/response-proof steps. Before and after edits, verify by canary that a clearly implied next step proceeds without asking and that any status claim cites fresh source evidence.
- **Mock exemption:** No application runtime changes; application tests and mock tests are inapplicable. The agent-behavior canaries still apply because this file changes instructions.
- **Risk:** Measurements age quickly and remote environments may differ. Re-measure before each heavy batch and disclose any unverified capacity or auth constraint.
