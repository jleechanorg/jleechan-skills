---
name: zfc-adjuster
description: Use when designing or reviewing backend adjusters, corrections, defaults, suppressions, clamps, guardrails, compatibility aliases, or fallback logic that may override or reshape model-owned output.
---

# ZFC Adjuster Proof Standard

## Purpose

Backend adjusters are exceptional. The default design is still ZFC: the LLM
decides, and the backend executes deterministic state changes, persistence,
formatting, and tool calls.

Use this skill before accepting code that adjusts, corrects, defaults,
suppresses, clamps, retries, rolls back, composes, or otherwise reshapes
model-owned output after the model responds.

For WorldArchitect changes, read the repository overlay
`.claude/skills/worldai-zfc/SKILL.md` alongside the portable ZFC contract.
Repository-local field ownership, registered adjustment contracts, and the
backend-justification gate determine whether any adjustment is allowed.

## Default Position

Assume backend adjustment is not allowed until proven necessary.

Allowed deterministic backend work:

- Preserve server-owned state, locks, request IDs, persistence, and tool
  execution results.
- Validate syntax, schema structure, enum membership, and required fields.
- Derive display aliases, compatibility fields, timestamps, IDs, and UI payload
  shape from accepted authoritative fields.

Potential adjuster work requires proof:

- Changing a model-owned semantic decision.
- Suppressing an explicit model payload.
- Filling a missing semantic field with a default.
- Correcting contradictions between model fields.
- Rolling back, composing, or rewriting model-produced state transitions.
- Adding fallback behavior when the model path fails.

## Required Proof Before Backend Adjustment

Every backend adjuster must include immutable or redacted proof for all of the
following:

1. **Raw-path evidence**
   - selected agent
   - system prompt or prompt provenance
   - user/input context
   - raw model request
   - raw model response
   - state before and after the turn
   - tool results, if tools affected the model decision
2. **Root-cause classification**
   - missing instruction
   - contradictory instruction
   - instruction ignored
   - wrong selected agent or wrong prompt loaded
   - schema too weak or redundant
   - backend transformed a valid model response incorrectly
   - invariant belongs to server-owned state, not model judgment
3. **Prompt/schema-first attempt**
   - prompt, selected-agent instruction, schema, or tool-feedback correction
     attempted first
   - proof that the real failing path received that correction
   - evidence showing whether the correction solved the issue
4. **Proven need**
   - explanation of why prompt/schema correction alone cannot handle the case,
     or why safety/data integrity requires a minimal server invariant
   - concrete example payload that still needs backend correction
5. **State-aware scope**
   - exact state fields the backend owns
   - exact model-owned fields the adjuster must not reinterpret
   - modal/session/turn boundaries where the adjuster can fire
   - stale-state and replay behavior
6. **Conflict, rollback, and composition**
   - what happens if multiple adjusters apply
   - ordering and precedence rules
   - rollback behavior when downstream persistence/tool execution fails
   - idempotency on retries and duplicate requests
   - logging that makes fired adjusters auditable

## Evidence Rules

Proof must be human-verifiable and durable:

- Prefer immutable evidence bundles, raw logs, checksums, commit SHA, and exact
  command lines.
- Redact secrets and private user content while preserving structure, field
  names, selected agent, prompt provenance, and relevant state transitions.
- Do not rely on screenshots, PR prose, summaries, or agent claims alone.
- Do not accept synthetic evidence for a real runtime path unless the change is
  explicitly test-only.

## Minimal Adjuster Design

If backend adjustment remains necessary:

- Register it in `$PROJECT_ROOT/backend_adjustment_specs.py` with `category=CORRECTION`,
  populated `root_cause_status`, `evidence_refs`, `allowed_when`, and
  `log_reason_code`. Any `server_generated=True` planning_block not covered by a
  registered, active spec is a bug. Registry-listing does not waive the
  long-term goal of removing the synthesis through prompt-first fixes.
- Keep it correction-only and as narrow as possible.
- Log every firing with request ID, selected agent, state scope, reason code,
  and before/after field names.
- Preserve the raw model response for audit.
- Avoid semantic keyword/regex routing.
- Avoid creating a second source of truth for intent, eligibility, target
  state, narrative meaning, or player-facing decisions.
- Prefer deleting redundant model fields or tightening schema over reconciling
  contradictions after the fact.

## Review Checklist

Fail the review if any answer is missing:

- What exact model path produced the bad payload?
- Did the selected agent receive the intended prompt/schema?
- Was prompt/schema/agent correction attempted first on the real path?
- What immutable or redacted artifact proves the failure and the fix attempt?
- Which state fields are server-owned versus model-owned?
- Why is the adjuster necessary after prompt/schema correction?
- What prevents broad suppression, silent defaults, or semantic recomputation?
- How do multiple adjusters compose?
- What is the rollback/retry/idempotency behavior?
- Where is the correction logged and how can a reviewer audit it?

## Relationship To ZFC And Root Cause First

This skill extends:

- `.claude/skills/zero-framework-cognition/SKILL.md`
- `.claude/skills/root-cause-first/SKILL.md`

Run this skill whenever `/zfc` review encounters backend adjustment code or a
proposal to add backend correction, suppression, defaulting, fallback, clamp,
retry, rollback, or guard logic around model-owned output.
