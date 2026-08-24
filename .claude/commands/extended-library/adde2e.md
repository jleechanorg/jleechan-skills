---
description: /adde2e - Add or Update End2End Tests for New Features
type: llm-orchestration
execution_mode: immediate
---
# /adde2e [feature description]

Add or update end-to-end tests for a new or changed feature.

Read `~/.claude/skills/end2end-testing/SKILL.md` and execute the full workflow (Phase 0-4: Context Analysis, Discovery, Planning, Implementation, Verification) with the provided feature description. Mock only external APIs (Firestore, Gemini), never internal services; use fake implementations (`FakeFirestoreClient`, `FakeLLMResponse`) instead of `Mock()`; tests go in `$PROJECT_ROOT/tests/test_end2end/`.

## Related Commands

| Command | Purpose |
|---------|---------|
| `/teste` | Run E2E tests (mock mode) |
| `/tester` | Run E2E tests (real mode) |
| `/tdd` | TDD workflow with matrix testing |
| `/4layer` | Four-layer TDD protocol |

## Input

$ARGUMENTS
