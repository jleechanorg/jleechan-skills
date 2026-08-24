---
description: Alias for /evidence-review.
aliases: []
type: orchestration
execution_mode: immediate
---

# /er — Alias for /evidence-review

Runs `/evidence-review` with the same arguments.

**Usage**: `/er [subject or path]`

## Action

Invoke `/evidence-review` with the same `$ARGUMENTS`.

This is a thin alias; the workflow lives in the `evidence-review` skill.

**Hard rule — Unit-only evidence is NOT ALLOWED.** If the only proof for a claim is unit tests (Layer 1, mocked/isolated), the verdict must be INSUFFICIENT and the user must be explicitly warned. Minimum: Layer 2 end-to-end integration tests (real callstack, mocks only at external API boundaries). LLM/external-service behavior claims require real-service evidence. **Exception:** unit-only proof IS acceptable for non-production changes (docs, tests, tooling/scripts) or for production changes under 100 delta lines of non-test code.

## Two-Tier Verdicts (added 2026-07-02)

`/er` now returns verdicts keyed to the PR's green-tier classification:

| PR tier | Required `/er` verdict for `/green` |
|---------|-------------------------------------|
| PRODUCTION ($PROJECT_ROOT/**, prompts, CI, schema) | **PASS** |
| NON_PRODUCTION (docs, tests, tooling, roadmap) | **PARTIAL** or better |

See `~/.claude/commands/green.md` Step 2 for the tier classifier and `~/.claude/skills/evidence-review/SKILL.md` for the verdict rubric. When `/er` is invoked via `gh pr comment N --body "/er"`, the response is one of: `PASS` / `PARTIAL` / `FAIL` / `INCONCLUSIVE` — parseable by `/green` directly.
