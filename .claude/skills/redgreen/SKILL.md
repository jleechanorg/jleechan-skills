---
name: redgreen
description: "Strict test-first debugging protocol for fixing a specific reported error (not general feature TDD — see /tdd for that). Enforces RED (reproduce the exact error via a fresh, real failing test run in this session) → CODE (minimal, targeted fix) → GREEN (confirm the same tests now pass, plus regression checks) → CONSENSUS (validate the debugging flow was legitimate). Includes 8 numbered Critical Rules and a hard RED Proof Discipline gate: an observed/historical bug, an old CI failure, or a past stack trace is NOT red proof — only a failing test you execute yourself, right now, counts. Also defines the `test_regression_<issue-id>_<behavior>()` naming convention. Use for /redgreen or /rg."
---

# Red-green debug and fix

**Usage:** `/redgreen` or `/rg`. When invoked, execute the phases below now; this is not background reading. Track the phases with a todo list.

Unlike `/tdd`, which drives new features with failing tests, `/redgreen` is error-driven: it fixes one reported bug. Take test-writing style and matrix patterns from `/tdd`.

## Phase 1: RED — reproduce the error with a test

Phase 2 cannot begin until the exact error is reproduced.

1. **Analyze the error.** Parse the exact error message from the user's input, identify the file, line number and error type, and understand the conditions that trigger it.
2. **Find existing tests.** Search for tests that should catch this error: integration tests (real services), functional tests (fixtures) and unit tests. Use judgment to pick the most appropriate type, and record which existing tests are relevant.
3. **Run them.** Check whether they fail with the expected error message, and record whether they reproduce the issue.
4. **Only if no existing test catches the error, update or create one.** Make it the minimal case that reproduces the exact error, and record why a new or updated test was needed.
5. **Confirm the test fails** with a deterministic, normalized error signature, not a byte-for-byte stack trace: `ErrorType | ["key", "tokens"] | file:function`. Record the reproduction steps and environment.

## Phase 2: CODE — minimal fix

1. **Root cause.** Identify why the error occurs (scope issues, import problems, etc.), choose the minimal fix, and consider side effects and compatibility.
2. **Change.** Make a targeted fix for this specific error. Avoid unrelated changes or refactoring, and keep existing behavior.
3. **Check.** Make sure the fix addresses the root cause, introduces no new errors, and works in isolation.

## Phase 3: GREEN — verify with tests

1. **Primary validation:** run the tests that failed in Phase 1 and confirm they all pass and the specific error no longer occurs. Control randomness and time (fixed seed, frozen time) so the result is deterministic.
2. **Direct fix test:** run the exact scenario that caused the original error (for example `python3 $PROJECT_ROOT/main.py`) and confirm the expected behavior.
3. **Regression:** run the existing tests and related functionality to confirm nothing else broke. Re-run the focused test N times to detect flakiness.
4. **Confirm and record:** all tests pass and the original issue is resolved. Record the test results as evidence.

## Phase 4: CONSENSUS — validate the flow

1. Run `/consensus` to validate that the debugging approach was sound.
2. Confirm that RED, CODE and GREEN each ran in order and produced evidence: the reproduction was genuine, the fix is minimal and targeted, and the tests show complete resolution.
3. Confirm the fix addresses the root issue, not a superficial symptom.

## Test guidelines

- Test categories: **error reproduction** (the bug can be triggered), **fix validation** (the fix resolves it) and **regression** (nothing new broke).
- Name regression tests with a prefix and identifier: `test_regression_<issue-id>_<behavior>()`.
- Do not duplicate coverage an existing test already provides.

## Critical rules

1. Search for existing tests BEFORE attempting to reproduce the error manually.
2. Do not start CODE without failing tests that reproduce the error.
3. Do not start GREEN without a fix implemented in CODE.
4. Verify that the exact same error is resolved, via passing tests.
5. Keep the fix minimal and targeted to the specific error.
6. GREEN must show that all tests pass, not just that the error is absent.
7. Choose the test type (integration with real services, functional with fixtures, unit) by judgment.
8. **RED proof discipline (hard gate).** A red proof MUST be a fresh, real failing test that runs locally against the codebase (e.g. `testing_mcp/test_*.py` or `$PROJECT_ROOT/tests/test_*.py`) and FAILS before the fix is applied.
   - **A fresh run is required; observing a bug is not proving RED.** The RED must come from a test execution YOU run NOW, in the current session, before any fix, with the command, timestamp, git SHA and failing output captured. Pointing at an existing failure (an old test run, an already-red CI job, a previously captured stack trace, someone else's repro, or "the bug is clearly happening in this transcript") is OBSERVATION, not RED proof. If you did not execute the failing run yourself in this session, you do not have RED.
   - A past bug report does NOT count, even if it captures the exact original stack. Past reports are narrative, not test runs.
   - A BigQuery / Firestore / production log showing the bug in prod does NOT count on its own. Replay the symptom through a fresh running test.
   - A copy-campaign replay script that "shows" the bug via offline LLM replay does NOT count unless it runs a deterministic test that fails pre-fix.
   - For LLM-behavior bugs, prefer a unit test that asserts a deterministic contract (e.g. the prompt contains required rule strings), OR a `testing_mcp/` test that runs against a real local server (`./local.sh`) with the DEFAULT AGY CLI provider (verify `provider_mode=agy` in the captured `agy_request`/`agy_response` payloads) and fails for the same reason as prod. Opting out of AGY (direct Gemini API) is allowed ONLY for a documented provider-specific claim, and the opt-out must be stated in the evidence.
   - If you cannot produce a red proof, STOP. Do not write the fix. Ship a bead instead and surface the missing red proof as the blocker.

## Example

```bash
# User reports: "UnboundLocalError: cannot access local variable 'os'"

# RED 2-3: find and run existing tests for main.py
TESTING=true python $PROJECT_ROOT/tests/test_main.py

# RED 4-5: if none catch it, add one, then confirm it fails
TESTING=true python $PROJECT_ROOT/tests/test_main.py
# Signature: UnboundLocalError | ["cannot access local variable", "os"] | $PROJECT_ROOT/main.py:main

# CODE: minimal fix for the os import

# GREEN: same tests pass, and the app starts
TESTING=true python $PROJECT_ROOT/tests/test_main.py
python3 $PROJECT_ROOT/main.py
```
