---
name: parallelize-to-ceiling
description: Apply to all work with independent units. Explain the parallel lanes briefly, then run useful independent work up to measured resource and authorized tool limits while preserving isolation, safety and evidence.
---

# Parallelize to ceiling — portable runtime edition

Apply this workflow by default to all work. Give a brief FYI explaining the independent lanes, owners, shared-write boundary and current ceiling; do not wait for approval to perform already-authorized work. For a short dependent task, say why a single lane is appropriate rather than inventing extra work.

Read [timeline and milestones](references/timeline-milestones.md) on every invocation. These are progress reports during active work, not a background schedule.

## Plan the lanes

1. Enumerate independent items and the outputs each owns. Dependencies and shared mutable state require ordering; unrelated reads can run together.
2. Measure the relevant constraint: available RAM, per-item CPU/RSS, I/O, tool slots, rate limits, or authorized host availability. An installed executable is not proof of authentication or worker capacity.
3. State independent lane count, measured runnable ceiling, planned simultaneous count and binding limit. Keep ready useful lanes running and refill free slots. Use current supported internal delegation tools and authorized connected hosts. Do not bypass native slot limits or launch outside-provider recipients without authority.
4. Work that finishes in a handful of tool calls stays in the root session. Delegate a bounded track when it earns its own context. Use a separate verifier for another agent's substantial implementation when warranted; do not spawn redundant review of your own completed checks.
5. Prefer the cheapest capable supported tier when routing is available and permitted. Honor the user's explicit tool/model choice and the runtime's supported models. Historic model aliases are not a reason to probe credentials or launch an unavailable CLI.
6. Existing authority bounds all lanes. Do not provision paid resources, purchase capacity, create credentials, relax permissions, kill unrelated processes or start new scheduling merely to increase concurrency.

## Resource admission

Before launching local subprocess fleets, inspect available RAM and pressure, and attribute the largest RSS consumers.

- macOS: available estimate is `(free + inactive + purgeable + speculative) * page_size` from vm_stat; use `kern.memorystatus_vm_pressure_level` secondarily. Level2 is warning, not critical;4 is critical. Sort process RSS numerically when finding the largest consumers.
- Linux: use the available-memory column and memory PSI if exposed.
- Heuristics: above8GiB and pressure<=2 normally admits light lanes;4–8GiB or pressure3 calls for reduced concurrency;below4GiB or pressure4 defers new heavy local lanes. Recalibrate to measured per-worker use.
- Swap used/allocated ratio alone is not a stop condition on macOS. Rising swap plus low available RAM is more meaningful. A steady-state VM may explain pressure without proving every additional light lane is unsafe.
- Heavy jobs that already saturate a host receive their own authorized capacity; light or I/O-bound jobs share measured headroom. Cap fork-sensitive test fleets according to real failures and project constraints.
- Use asynchronous supported execution with a timeout for long CLI jobs; keep the parent responsive. Do not infer permission to launch a CLI from this timing rule.

## Isolation and proof

- Give workers disjoint workspaces/output paths and exact bounded scope.
- Assign one writer to shared files, ledgers and merged artifacts.
- Merge results in stable item order, not completion order.
- For coder/verifier handoff, pin exact revision, owned paths, relevant checks and evidence. A verifier must inspect the handed-off revision independently.
- Report observed live worker count or tool status separately from requested concurrency. A flag or advertised slot count is not proof of active work.
- Before relying on a result, read the artifact that supports the particular claim and check revision/provenance. Running is not progressing; idle is not proof that results reached the parent.
- A lost callback or disconnected reporting channel leaves delivery unconfirmed. Ask the lane and inspect its designated outputs and relevant authorized remote state before declaring execution paused or failed, or repeating a write. If the outcome remains unknown, keep it unconfirmed rather than blindly repeating writes. Scope any blocker to the affected action and target; continue independent ready work. Verify one result-delivery path before scaling a new route widely.
- Retry only failed bounded work with an explicit reason and preserved scope; do not repeat an equivalent stalled launch without changing its cause.

## Completion

Report observed timeline, completed lane outputs, validation, active or blocked lanes and remaining limits. Do not claim a skill is in the runtime catalog or visual picker merely because its files exist.

## Portability provenance

Adapted from the canonical parallelize-to-ceiling package. The distribution manifest records the accepted source-bundle hashes and exported file hashes; private usage receipts are not included. The mandatory timeline reference is bundled. Host-specific AGY profiles, permission-skipping flags, credential probes, hard-coded model fallbacks and sidekick's wider workflow are not dependencies of this portable edition. The canonical home source remains unchanged.
