---
name: pairv2-llm-driven-philosophy
description: Pairv2 implementation philosophy: LLM-decided outcomes, fail-soft file handling, and evidence-first promotion
type: policy
scope: project
---

# Pairv2 LLM-Driven Philosophy

## Core Rule

Pairv2 should fail only for bounded safety reasons (timeout/max cycles) or verifier
judgment, not because a specific file path was missing.

## Decision Hierarchy

1. Verifier LLM verdict is the primary quality signal.
2. Non-LLM checks provide notes and evidence, not hard overrides.
3. Missing optional inputs (design docs, user-provided contract paths) must degrade
   gracefully to generation or inference.

## Anti-Brittle Rules

- Do not hard-fail solely because a provided path does not exist.
- When provided left/right contract files are missing, fall back to LLM generation.
- When design doc path is missing, continue without design doc context and add a note.
- Prefer reproducible evidence bundles (reports/artifacts/logs) over path heuristics.

## Practical Checklist

When editing pairv2:
1. Ask: "Will this block execution because a file is missing?"
2. If yes, replace with note + fallback path.
3. Ensure verifier still gets enough context to decide PASS/FAIL/NEEDS_HUMAN.
4. Add tests for missing-file fallback and note emission.
