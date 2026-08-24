---
description: ZFC adjuster proof review — verify backend adjustments have root-cause-first proof and minimal state-aware scope
type: quality
execution_mode: immediate
---

# /zfc-adjuster

## Purpose

Review backend adjusters, corrections, defaults, suppressions, clamps,
guardrails, compatibility aliases, retries, rollbacks, and fallback logic
against the ZFC adjuster proof standard.

## Skill Reference

Full proof standard: `.claude/skills/zfc-adjuster/SKILL.md`

Related skills:

- `.claude/skills/zero-framework-cognition/SKILL.md`
- `.claude/skills/root-cause-first/SKILL.md`

## Execution Steps

1. **Load skills** — read `.claude/skills/zfc-adjuster/SKILL.md`,
   `.claude/skills/zero-framework-cognition/SKILL.md`, and
   `.claude/skills/root-cause-first/SKILL.md`.
2. **Identify scope** — if an argument is given
   (`/zfc-adjuster <file or description>`), focus there; otherwise review the
   current diff or most recently discussed backend adjustment code.
3. **Find adjustment surfaces** — check for backend code that:
   - changes, suppresses, defaults, clamps, retries, rolls back, composes, or
     rewrites model-owned output
   - reconciles contradictory model fields
   - fills missing semantic fields
   - adds fallback behavior after a model/schema/path failure
   - derives semantic decisions outside the model
4. **Verify proof** — require immutable or redacted evidence for:
   - selected agent, prompt provenance, raw request, raw response, and state
     before/after
   - root-cause classification
   - prompt/schema/agent correction attempted first on the real path
   - proven need that prompt/schema alone cannot handle
   - state-owned versus model-owned field boundaries
   - conflict, rollback, composition, retry, idempotency, and logging behavior
5. **Classify findings**:
   - `PASS` — no backend adjustment code, or adjuster proof is complete and
     the implementation is narrow, logged, and state-aware
   - `WARN` — adjustment may be deterministic or low-risk, but proof or
     documentation is incomplete
   - `FAIL` — backend adjustment changes model-owned meaning without the
     required proof, bypasses prompt/schema-first repair, or creates a second
     semantic source of truth
6. **Report** — provide line-level evidence, missing proof artifacts, and the
   smallest correction needed before the work can proceed.
