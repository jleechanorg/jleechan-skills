---
name: optimization-baseline-fidelity
description: "Use BEFORE any cost/latency optimization. A/B control MUST be deployed prod config; gate code-start on stated $X/mo savings; reject forced-OFF controls."
---

# Optimization Baseline Fidelity

## Purpose

Prevent the recurring failure mode where a mechanism is built, demonstrated to "work" in a controlled A/B, and shipped — but produces no real production savings because the A/B control was a configuration that does not exist in stable prod.

## When to invoke

Invoke this skill whenever the work involves:

- Adding or changing a cache (per-user, per-campaign, shared, system-prompt, etc.)
- Batching, request coalescing, or N+1 reduction
- Model swap, downgrading tier, or routing change
- Prompt slimming or context trimming
- Dedup or idempotency layer
- Any "fall-through" or "opportunistic" mechanism that lives behind an existing primary

## Required workflow

Before writing the first line of code:

1. **Quantify the addressable slice first.** State the target as a percentage of the *measured* bill/metric, using real data already on hand (census, billing export, traces, telemetry). If the slice the optimization can actually touch is small after accounting for what's already deployed, STOP — do not build.

2. **The A/B control arm MUST be the currently-deployed production config**, never "off" / "do nothing" / "uncached" / a hand-picked config that maximizes apparent benefit. If another optimization already wins the same traffic in prod (e.g. an existing cache, implicit caching), the control must include it.

3. **A measurement run in a config that does not exist in prod is NOT evidence.** Forcing a competing feature OFF to make yours look effective produces a preview-path number, not a prod-savings number. Label it as such or discard it.

4. **Gate code-start on a stated incremental-savings-over-baseline target.** Write "this saves $X/mo vs the deployed config" as the success criterion *before* the first commit. If you cannot state it, the premise is unvalidated — STOP.

5. **For a fall-through / opportunistic mechanism**, compute when it actually fires in prod *before* building. A fall-through behind an already-warm primary is structurally dead.

## Why this rule exists

A shared `system/tools` Gemini cache was built and driven to a near-merged PR whose only savings land when the per-campaign cache is cold (a sliver of prod). The feature was "proved" with a 74.6% reduction measured with the per-campaign cache forced OFF — an isolated control that does not exist in stable prod. 43 tasks of mechanism-correctness, 0 tasks of marginal-$-vs-baseline. The feature also excluded the 89% test/CI cost center by design, so it was aimed away from the money.

The failure was confusing "the mechanism works" with "the bill drops." The deployed-config control is the fix.

## Red flags

- "The mechanism is correct, the savings will follow" (without a stated $X/mo)
- A/B comparison against "no cache" when a cache is already deployed
- "Falls through when the primary is cold" without showing what fraction of prod traffic sees a cold primary
- Targeting a 1% slice of the cost center when 89% is elsewhere

## Output expectation

State the success criterion ("this saves $X/mo vs the deployed config") before code, and produce measurement artifacts that compare against the deployed config — not a forced-OFF control.
