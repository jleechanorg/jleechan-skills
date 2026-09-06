---
name: ablation
description: Use when diagnosing a bug in LLM/model behavior, or any stochastic system, where the cause is disputed or theorized rather than measured. Slash commands `/ablation` and `/abal`. Enforces the rule that you manipulate the REAL captured input and replay it through the REAL production path, one variable at a time, with a verbatim control arm run first to establish the base rate. Trigger phrases include "ablation", "ablate", "what actually causes", "is X the trigger", "prove the root cause", "A/B the payload", "does removing X fix it", "why does the model do this", "test the hypothesis", "root cause is disputed".
---

# Ablation — measure the cause, don't theorize it

## Core law

For any disputed cause in a model-driven or stochastic system, **manipulate the real
captured input and replay it through the real production path**, one variable per arm,
**with a verbatim control arm run first**.

A plausible mechanism is not evidence of causation. A code reading is a hypothesis.
A single clean run is not a fix. The control's base rate is the measurement that makes
every other arm interpretable — run it first, report it, and never skip it.

Origin: 2026-08-18, worldarchitect.ai campaign time-travel. Three documents, one PR, and
a multi-lane investigation theorized the root cause; a 5-arm ablation refuted the shipped
fix in ~30 minutes and revealed the bug was 80% stochastic, invalidating every N=1 result
in the incident — including the fix PR's own evidence bundle.

## When to reach for this

- Root cause is disputed, or two lanes/docs disagree.
- A fix is about to be written from a code reading rather than a measurement.
- The symptom involves an LLM choosing wrong when the right information was available.
- Someone reports "I removed X and it still happens" or "I removed X and it stopped" at N=1.
- A PR claims a fix but its evidence is a single successful run.

**Do NOT reach for this** when the failure is deterministic and a unit test reproduces it —
just write the test.

## The procedure

### 1. Recover the real input
Not a reconstruction, not a synthetic fixture — **the actual captured payload** from the
failing event. Look in provider/forensics capture mirrors, BigQuery payload tables, and
worktree-local `*_forensics.jsonl` files.

**Confirm it is the right specimen by CONTENT, never by timestamp proximity.** Match
multiple independent fields against the persisted record of the failure (e.g. the stored
output document): byte-identical state updates, verbatim summary text, verbatim narrative
opening, matching headers. State how you confirmed it.

### 2. Identify the real production call path
Read the code to find what production actually invokes, then call **that**. Not a
convenient SDK equivalent, not a CLI wrapper you construct yourself.

If the production path applies its own transformation (prompt wrapping, tool loop,
retries), that is acceptable **only because it is constant across arms**. Say so
explicitly; do not claim you made a bare API call when you didn't.

### 3. Run the CONTROL arm first — this is not optional
Replay the payload **verbatim**, N≥5. Report the failure ratio.

If the control does not reproduce, stop: your specimen or instrument is wrong, and every
downstream arm is void. If it reproduces at less than 100%, **that base rate is the single
most important number you will produce** — it determines what any treatment arm can mean.

### 4. Define arms — one variable each
Each arm changes exactly one thing from the control. Hold constant, and state that you
held constant: model string, system instruction, generation config, safety settings, and
every field except the one under test.

**Read the model string from the captured payload** rather than hardcoding it — that way
it provably cannot drift between arms.

Include a **size-matched / structure-matched control** whenever your treatment removes a
large fraction of the input. Removing 40% of a payload confounds "the content mattered"
with "the volume mattered", and those imply opposite fixes. The matched arm removes an
equivalent mass of *different* content.

Prefer **same-offset replacement over deletion** when isolating a string or block:
deletion shifts every downstream offset and confounds content with position. Swap in a
neutral placeholder of equal length instead.

### 5. Verify each manipulation BEFORE firing
Programmatically assert what you removed or changed — indices, byte/char deltas, and a
positive assertion that the target is (or isn't) present. Print it.

This is where ablations silently die. A filter that matches nothing produces a
"treatment" arm identical to the control, and it will look like a null result.

### 6. Score mechanically, on the full raw output
Write a scoring function; do not eyeball. Search the **entire raw response**, not one
field — field names drift between runs and a field-scoped check under-counts.

Count **semantic** recurrences, not just literal ones. If you removed a string and the
model paraphrases it, that is still a failure — and the fact that it paraphrased is itself
a finding.

### 7. Report ratios against the control, with the null
Always `X/N vs control's Y/N`. Give P under the null (that the treatment did nothing) and
say what N can and cannot support.

## Statistical floor

| Control base rate | Result | P under null | Reading |
|---|---|---|---|
| 80% | 0/5 | 0.2^5 ≈ 0.03% | Real signal |
| 80% | ≤2/5 | ≈ 5.8% | Borderline, not confirmatory |
| 80% | 3/3 fail | 0.8^3 ≈ 51% | Refutes SUFFICIENCY; proves nothing about zero-effect |
| 80% | any 1 run | 20% clean by chance | Worthless |

Rules of thumb:
- **N=1 is never evidence** when the control is stochastic.
- Refuting *sufficiency* needs only counterexamples and no p-value. Claiming *zero causal
  contribution* needs power you probably don't have — say "refuted as a sufficient fix,
  not proven to have zero effect."
- Candidate fixes need **N in the high teens per arm** before a low-failure result is
  trustworthy.
- Binomial math assumes i.i.d. trials. Shared caching, seeds, or upstream state shrink
  effective N — note it.

## Failure modes this kills

- **Theorizing from a code read.** A mechanism that explains the symptom is a hypothesis.
- **The N=1 fix.** A single clean run at an 80% base rate happens 1 time in 5.
- **The silent no-op arm.** Your filter matched nothing (wrong field, wrong shape) and you
  reported a null result. Verify the diff before firing.
- **The volume confound.** You removed the suspect content *and* 40% of the payload.
- **The deletion confound.** Removing a string shifts all downstream offsets.
- **Field-scoped scoring.** Checking one field misses the failure when the model renames it.
- **Literal-only scoring.** The model paraphrased and you scored it clean.
- **Unit contamination.** Comparing pretty-printed against compact serialization inflates
  a delta with whitespace. Compare like against like.
- **Silent denominator swap.** Quoting a percentage computed against one base next to a
  figure on another base. Always print `X/Y = Z%` with Y named. A real instance: "85.4% of
  the compact delta" got reported as "96.9%" because the text-only sum was the actual
  denominator.
- **Arguing volume from arm-vs-arm instead of arm-vs-baseline.** "Treatment removed more
  and passed; control-removal removed less and failed" is *also* consistent with a
  monotonic size effect. Volume is only refuted by **non-monotonicity against the
  untouched baseline** — e.g. an arm with a *smaller* payload than baseline failing *more*
  than baseline. Anchor on the baseline, not on the other arm.
- **The matched control that changes two things.** Removing "an equivalent mass elsewhere"
  may also destroy the material nearest the query. Then a null result has two explanations
  — your hypothesis, and information starvation. Say which your design can distinguish.
- **Claiming a negative you never tested.** If every arm was verbatim-or-removal, you have
  said nothing about *relocation*. "Reordering doesn't help" is an untested gap, not a
  finding. Name it as the next experiment instead of banking it as a result.
- **Instrument drift.** Different provider/model/config between arms.

## Artifact requirements

Each run row must record: arm label, run index, ok/error, duration, **resolved model
string**, **provider type**, the full raw response, and the parsed scoring fields. Model
and provider per row are routinely omitted and routinely wanted later — stamp them.

Keep superseded runs on disk for audit, and mark them **do not cite**. A corrected rerun
that silently overwrites a buggy one destroys the trail that proves you caught the bug.

Write the methodology up separately from the results, and include a **known weaknesses**
section. If you did not isolate which element of a removed block was responsible, say so —
that is the next experiment, and the fix spec depends on it.

## Reporting template

```
## Ablation summary
- Specimen: <path, size, how confirmed by content>
- Instrument: <production call path; transformations constant across arms>
- Control (Arm A): <X/N> failed  -> base rate <R>%
- Arm <n>: <one-variable change> -> <X/N>, P(null) = <p>
- Verdict: <hypothesis> CONFIRMED | REFUTED-AS-SUFFICIENT | INCONCLUSIVE
- Not established: <what this cannot show>
- Next experiment: <the discriminating test still unrun>
```

## Worked example

Campaign regressed to its opening scene at Turn 131. Five arms, N=5, real payload, real
provider:

| Arm | Manipulation | Failed |
|---|---|---|
| A | verbatim (control) | 4/5 — base rate 80%, NOT deterministic |
| B | remove the 6 occurrences of the suspected trigger string | 3/3 — refutes sufficiency |
| C | strip one word from 3 fields | inconclusive **by design** — word persisted elsewhere; reported, not counted |
| D | remove history entries 0-6 wholesale | **0/5**, P ≈ 0.03% |
| E | keep 0-6, remove an equivalent mass of *other* entries | **5/5** — volume refuted |

D vs E is what made it a cause rather than a correlation. It also exposed that the shipped
fix removed only 3% of what worked — it kept the single largest entry, which matched
neither of its filter markers.
