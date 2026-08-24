---
description: Zero-Framework Cognition review — check current work for ZFC violations and apply ZFC principles
type: quality
execution_mode: immediate
---

# /zfc

## Purpose

Apply Zero-Framework Cognition principles to the current task or file under review. Models decide; server executes.

## Skill Reference

Full principle set: `.claude/skills/zero-framework-cognition/SKILL.md`
Backend guard proof standard: `.claude/skills/root-cause-first/SKILL.md`

## Execution Steps

1. **Load skills** — read `.claude/skills/zero-framework-cognition/SKILL.md` and `.claude/skills/root-cause-first/SKILL.md` in full
2. **Identify scope** — if an argument is given (`/zfc <file or description>`), focus there; otherwise review the current diff or most recently discussed code
3. **Run banned-pattern scan** — check for:
   - Keyword/substring routing for user intent (`if text.contains(...)`)
   - New regex-based semantic classification or intent detection
   - Hardcoded phrase-to-action maps
   - Hand-tuned keyword scores
   - Redundant model output fields (multiple fields expressing the same semantic decision)
   - Backend recomputation of decisions that belong to the model
   - Backend guards added before capturing raw model request/response
4. **Check field ownership** — for each model output field: is it the minimal semantic decision, or a display derivative that should be derived deterministically? For each control/state flag: does it have one canonical location, or is it duplicated to a second place and reconciled with read-time precedence/fallback? Single-home each flag and canonicalize once at the load/persist boundary.
5. **Classify every non-prompt behavior** — for each backend guard, fallback, scrubber, sanitizer, clamp, suppression, server-injected choice, routing rule, persistence rule, or schema normalizer, identify whether it is:
   - Server-owned invariant
   - Prompt/schema-insufficient, proven by raw real-path request/response
   - Backend-transformation bug
   - Unproven fallback
   - ZFC violation candidate
6. **Recommend fixes** — for each violation found:
   - Name the banned pattern
   - Quote the offending code
   - Provide a ZFC-compliant replacement (delegate to model or derive deterministically)
7. **Report** — output a concise verdict: PASS (no violations), WARN (borderline), or FAIL (clear violations) with line-level evidence

## Required Report Table

Whenever `/zfc` reviews non-prompt logic, include this table:

| Component | Non-prompt behavior | Proof state | Evidence | Verdict |
|---|---|---|---|---|

Use `Keep`, `Narrow`, `Move upstream`, or `Delete or prove` as the verdict.
Do not describe a backend behavior as "needed" unless it is a server-owned
invariant or has raw real-path evidence that prompt/schema correction was
insufficient.
