---
name: spec-design-docs
description: Use when writing any spec, design doc, or implementation plan for a non-trivial feature — enforces the three-doc rule (no-code spec, design doc with interfaces, TDD impl plan) with adversarial review gates between stages.
---

# Spec + Design Doc Methodology

Codifies the doc trio from the auto-factory-daemon exemplar (dark-factory,
2026-07-03): `docs/auto-factory-daemon-spec.md`,
`docs/auto-factory-daemon-design-rust.md`,
`docs/superpowers/plans/2026-07-03-auto-factory-daemon-rust-stage1.md`. Read
those three files as the canonical example when in doubt about depth or tone.

## The Three-Doc Rule

Every non-trivial feature gets exactly three documents, produced **in this
order**, each frozen (adversarially reviewed) before the next one starts:

1. **NO-CODE SPEC** — behavior only. States, contracts, safety invariants. No
   implementation language, no code blocks except JSON/text examples of
   wire formats. Carries a **status header** (`Status: Draft r1` /
   `Final r3.1`), an **Adversarial Review Ledger** appendix, and a
   **Resolved Design Choices** appendix. Its **FIRST section must be "Exit
   criteria"** — before goals/requirements. Each criterion must be binary
   (pass/fail), executable (a stated command or observable check), and
   externally anchored (verified at the layer users experience — real
   system-of-record state, not implementer-authored logs/telemetry). Ground
   rules (per `~/projects/dark-factory/docs/cutover-exit-criteria.md`,
   R1–R6 + X1–X10 charter, hardened 2026-07-04 by a 3-reviewer adversarial
   pass): implementer-authored artifacts are corroborating, never
   sufficient; the verifier reproduces rather than inspects;
   satisfied-via-mock/dry-run = FAIL; default verdict is FAIL.
2. **DESIGN DOC** — code and interfaces. Binding names: types, traits/
   interfaces, file layout with a **LOC budget** per file, error taxonomy,
   test strategy, an explicit **YAGNI/deferred** section. States plainly:
   *"if the spec and this doc disagree, the spec wins."*
3. **TDD IMPL PLAN** — superpowers `writing-plans` format. Bite-sized
   checkbox steps, complete code per step, a testing-layer map, and a
   Definition of Done.

**Fast path (explicit entry criteria):** single-file change, no public
API / data-model / safety-invariant impact, no new dependency → a
two-paragraph no-code spec + a test plan replaces the trio. Everything
else gets the full trio. Genuinely trivial (config tweak, one-line fix,
doc typo) skips docs entirely. When unsure, write the spec — two
paragraphs cost less than a wrong implementation.

**Optional Phase-0 spike:** when feasibility is uncertain (unproven
library, unknown API), run a throwaway prototype *before* freezing the
spec and record what it proved in Resolved Design Choices. Spike code is
discarded, never promoted.

## Key principles

- **Contracts frozen before implementation.** Schemas, config shape, and
  telemetry event shape are pinned as their own small sub-sections (or files)
  in the design doc *before* any code is written, so both a bootstrap
  implementation and the final one honor the same shape.
- **Prompt CONTRACTS, never prompt text.** Specs pin LLM-role I/O schemas
  (input fields, output JSON shape, verdict grammar) as an appendix. The
  actual prompt wording is an implementation artifact written at build time
  — inlining it in the spec is a leak, not documentation (ZFC: judgment
  belongs to the model call, not to spec prose that tries to pre-script it).
- **Revision discipline.** Specs move r1 → r2 → r3... **Never silently edit**
  a past revision. Every substantive change is a new revision number with a
  corresponding Adversarial Review Ledger entry explaining why.
- **Adversarial review before coding, not after.** One **full refute-round**
  gates the design doc: an independent reviewer — a *different* model/agent
  than the author (spawn via `/advice`, a fresh adversarial subagent, or a
  cold CLI review; never self-review) — tries to refute it. Verdict
  `pass | warn | fail`; every P0/P1 fixed (or explicitly rejected with
  reasoning) before implementation. The design→plan transition is a
  **lighter conformance checkpoint**, not a second full round: verify the
  plan's names/types match the design doc and the traceability matrix is
  complete. Time-box both — a gate that blocks for days becomes gate
  theater. The spec→design gate must additionally check the spec's Exit
  criteria are **game-proof** (attackable-loophole review: can any
  criterion be satisfied by a mock, dry-run, or implementer-authored
  artifact alone?) before stage 2 proceeds. `/design`'s Phase-0
  batch-review checkpoint (all recommended decisions presented to the
  user at once, reviewed in one pass — never serial questioning) is the
  expected input to this stage-1 gate: the gate reviews the batch-approved
  decisions and exit criteria, not a fresh round of user Q&A.
- **Cross-doc traceability.** The impl plan ends with a small matrix mapping
  every spec contract/invariant → the design section that shapes it → the
  task that builds it (`spec §X → design §Y → Task N`). A spec row with no
  task is unbuilt behavior; a task with no spec row is scope creep. The
  testing-layer map covers *tests*; this matrix covers *coverage of the
  spec itself*.
- **AAR triage for external feedback.** Any feedback that didn't originate
  from your own adversarial round (external variant, another agent's spec,
  a reviewer's alternate proposal) gets triaged **Accept / Adapt / Reject**
  with a one-line reason each, logged in the ledger. Never merge external
  feedback wholesale and never discard it silently.
- **LOC budgets as a guideline, not a quota.** Every file in the design
  doc's layout table gets a target line count (e.g. `verifier.rs ~220`) as
  a minimal-glue signal: blowing the budget usually means reimplementing
  something a wrapped tool already does. Exceeding a budget by >30% needs a
  one-line written justification in the design doc — not a rewrite to game
  the number (line-count golf is the failure mode, not the fix).
- **Documenting a decision ≠ deferring a decision.** A choice you already
  made (even a small one, like "spec dir defaults to `.factory/specs/`")
  goes in **Resolved Design Choices** so nobody re-litigates it. A choice
  you have *not* made goes in **Open Questions**, explicitly unresolved.
  Conflating the two is the single most common spec-quality failure.

## Doc skeletons

### 1. No-code spec (`docs/<feature>-spec.md`)

```markdown
# <Feature> — Architectural Specification (No-Code)
**Status:** Draft r1
**Code status:** Declarative blueprint only — zero implementation code

## Exit Criteria  (FIRST section — binary, executable, externally anchored)

## Executive Summary
Key tenets (3-5 bullets)

## Table of Contents
## System Topologies & Diagrams  (data flow, state machine)
## Detailed Specifications
  - States / lifecycle
  - Contracts (wire shapes, not code types)
  - Safety envelope / invariants
## Appendix A — Adversarial Review Ledger
## Appendix B — Resolved Design Choices
## Appendix C — Declarative Prompt Contracts (JSON-schema-shaped I/O, machine-checkable)
## Appendix D — Open Questions (if any remain)
```

### 2. Design doc (`docs/<feature>-design-<lang>.md`)

```markdown
# <Feature> — <Lang> Design Doc (interfaces + code)
**Status:** Draft r1 — companion to [`<feature>-spec.md`] (Final rN)
**Split of concerns:** spec owns behavior, this owns shape. Spec wins on conflict.

## 1. Design tenets (minimal glue)
## 2. Layout & LOC budget (table: file → ~LOC → purpose)
## 3. Core types
## 4. Tool/service boundary (interfaces/traits — the ONLY abstraction seam)
## 5. Component signatures
## 6. Error taxonomy
## 7. Test strategy (binds the TDD plan)
## 8. Deferred (YAGNI until the spec says otherwise)
```

### 3. TDD impl plan (`docs/superpowers/plans/YYYY-MM-DD-<feature>.md`)

```markdown
# <Feature> Implementation Plan
> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal / Architecture / Tech stack** (2-4 lines each, cites the design doc)

### Task 0: Prerequisites
### Task N: <component> (`file.ext`) — Layer <1|2|3>
- [ ] Step 1: failing test(s)
- [ ] Step 2: implementation
- [ ] Step 3: run + commit

## Testing-layer map (table: test → layer → why sufficient)
## Traceability matrix (spec §X → design §Y → Task N)
## Definition of done
```

## Where files go

- No-code spec + design doc: this repo's `docs/` — or `.factory/specs/` where
  that per-repo convention is already established (check for a
  `.factory.toml` `spec_path` override before defaulting).
- TDD impl plan: `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
- Never put any of the three under `roadmap/` — roadmap is session/status
  history, not a versioned spec artifact.

## When invoked as `/design`

Produce the three docs **in order**: no-code spec → adversarial refute-round
(independent reviewer, fix P0/P1) → design doc → adversarial refute-round →
TDD impl plan → conformance checkpoint (names/types match design; spec→
design→task traceability matrix complete). Do not start a later doc until
the earlier one has its verdict recorded in the ledger. Fast-path features
(see entry criteria above) skip to: two-paragraph spec + test plan → one
review → code.
