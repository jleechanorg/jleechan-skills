---
description: Red-Green Debug & Fix Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### 🔴 Phase 1: RED - Test-First Error Reproduction

**Action Steps:**
**MANDATORY**: Must use test-first approach to catch and reproduce the error before proceeding

### Phase 2: Step 1: Error Analysis

**Action Steps:**
1. Parse the exact error message from user input
2. Identify the file, line number, and error type
3. Understand the context and conditions that trigger the error

### Phase 3: Step 2: Find Existing Tests

**Action Steps:**
1. Search for existing tests that should catch this error
2. Look for integration tests (with real services), functional tests (with fixtures), and unit tests
3. Use judgment to determine which test type is most appropriate
4. Document which existing tests are relevant

### Phase 4: Step 3: Confirm Tests Reproduce Error

**Action Steps:**
1. Run existing tests to check if they catch the error
2. Verify if tests fail with the expected error message
3. Document whether existing tests successfully reproduce the issue

### Phase 5: Step 4: Update or Create Tests (If Needed)

**Action Steps:**
1. **ONLY IF existing tests don't catch the error**: Update or create new tests
2. Consider test types: integration tests (real services), functional tests (fixtures), unit tests
3. Create minimal test case that reproduces the exact error
4. Use normalized error signatures: `ErrorType | ["key", "tokens"] | file:function`
5. Document why new/updated tests were needed

### Phase 6: Step 5: Confirm Tests Fail

**Action Steps:**
1. Run the tests to confirm they fail with expected error message
2. Verify the error occurs with deterministic error signature (not byte-for-byte stack traces)
3. Ensure test accurately reproduces the issue
4. Document reproduction steps and environment

### 🔧 Phase 2: CODE - Fix Implementation

**Action Steps:**
**Implementation**: Write minimal code change to fix the reproduced error

### Phase 6: Step 1: Root Cause Analysis

**Action Steps:**
1. Identify why the error occurs (scope issues, import problems, etc.)
2. Determine minimal fix approach
3. Consider side effects and compatibility

### Phase 7: Step 2: Code Changes

**Action Steps:**
1. Make targeted fix to resolve the specific error
2. Avoid unnecessary changes or refactoring
3. Maintain existing functionality

### Phase 8: Step 3: Implementation Verification

**Action Steps:**
1. Ensure fix addresses root cause
2. Verify no new errors introduced
3. Test fix in isolation

### 🟢 Phase 3: GREEN - Test-Driven Verification

**Action Steps:**
**Validation**: Confirm tests pass and error is completely resolved

### Phase 10: Step 1: Confirm Tests Pass

**Action Steps:**
1. **PRIMARY VALIDATION**: Run the tests that were failing in Phase 1
2. Verify all tests now pass after the fix
3. Confirm the specific error is no longer occurring
4. Control randomness/time (fixed seed, frozen time) to ensure determinism

### Phase 11: Step 2: Direct Fix Test

**Action Steps:**
1. Run the exact same scenario that caused the original error
2. Verify error no longer occurs
3. Confirm expected behavior works

### Phase 12: Step 3: Regression Testing

**Action Steps:**
1. Run existing tests to ensure no breaks
2. Test related functionality
3. Verify broader system stability
4. Re-run the focused test N times to detect flakiness

### Phase 13: Step 4: Green Confirmation

**Action Steps:**
1. **CONFIRM ALL TESTS PASS**: Primary validation that fix is complete
2. Verify fix resolves the original issue
3. Document test results and success evidence

### Phase 1 (RED):

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 2 (CODE):

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 3 (GREEN):

**Action Steps:**
python3 $PROJECT_ROOT/main.py

### 🔍 Phase 4: CONSENSUS - Flow Validation

**Action Steps:**
**Validation**: Verify the entire red-green debug flow was legitimate and properly executed

### Phase 17: Step 1: Consensus Check

**Action Steps:**
1. Run `/consensus` to validate the debugging approach was sound
2. Ensure all phases were properly executed with evidence
3. Confirm the fix addresses the root issue comprehensively

### Phase 18: Step 3: Flow Legitimacy

**Action Steps:**
1. Verify proper RED-GREEN-REFACTOR flow was followed
2. Confirm all phases completed with evidence

### ✅ RED phase: Actual error reproduced with evidence

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### ✅ CODE phase: Minimal, targeted fix implemented

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### ✅ GREEN phase: Complete resolution verified

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

## 📋 REFERENCE DOCUMENTATION

# Red-Green Debug & Fix Command

**Purpose**: Three-phase debugging workflow: Red (reproduce exact error) → Code (fix implementation) → Green (verify working)

**Action**: Systematic debugging with exact error reproduction and fix validation

**Usage**: `/redgreen` or `/rg`

# Must see this exact error before proceeding:

# UnboundLocalError: cannot access local variable 'X' before it is associated with a value

# ImportError: cannot import name 'Y' from 'Z'

# etc.

```

**CRITICAL RULE**: Phase 2 cannot begin until the exact error is reproduced

# Must see successful execution:

# ✅ Original error scenario now works

# ✅ No new errors introduced

# ✅ Expected functionality confirmed

```

## 🧪 Test Creation Guidelines

**Reference `/tdd` command for test writing style and patterns**

### Test Structure

Use the comprehensive matrix testing approach from `/tdd`:
- Create failing tests that reproduce the exact error
- Write minimal code to make tests pass
- Ensure test coverage for the specific bug scenario

### Test Categories

1. **Error Reproduction Tests**: Verify the bug can be triggered
2. **Fix Validation Tests**: Confirm the fix resolves the issue
3. **Regression Tests**: Ensure no new problems introduced
- Name tests with a regression prefix and identifier, e.g., `test_regression_<issue-id>_<behavior>()`

## 🚨 Critical Rules

**RULE 1**: Must search for existing tests BEFORE attempting to reproduce error manually
**RULE 2**: Cannot proceed to CODE phase without failing tests that reproduce the error
**RULE 3**: Cannot proceed to GREEN phase without implementing a fix in CODE
**RULE 4**: Must verify exact same error is resolved via passing tests
**RULE 5**: Fix must be minimal and targeted to the specific error
**RULE 6**: Green phase must demonstrate all tests pass, not just absence of error
**RULE 7**: Consider test types: integration tests (real services), functional tests (fixtures), unit tests - use judgment

**RULE 8 — RED PROOF DISCIPLINE (HARD GATE):** A red proof MUST be a fresh, real
failing test that runs locally against the codebase (e.g. `testing_mcp/test_*.py`
or `$PROJECT_ROOT/tests/test_*.py`) and FAILS before the fix is applied.
- **FRESH RUN REQUIRED — observing a bug is not proving RED.** The RED must come
  from a test execution YOU run NOW, in the current session, before any fix is
  applied — with the command, timestamp, git SHA, and failing output captured.
  Pointing at an existing failure (an old test run, an already-red CI job, a
  previously captured stack trace, someone else's repro, or "the bug is clearly
  happening in this transcript") is OBSERVATION, not RED proof. If you did not
  execute the failing run yourself in this session, you do not have RED.
- A past bug report does NOT count as red proof, even if it captures the exact
  original error stack. Past reports are narrative, not test runs.
- A BigQuery / Firestore / production log showing the bug in prod does NOT count
  as red proof on its own. Replay the symptom through a fresh running test.
- A copy-campaign replay script that "shows" the bug via offline LLM replay does
  NOT count as red proof unless it runs a deterministic test that fails pre-fix.
- For LLM-behavior bugs: prefer a unit test that asserts a deterministic contract
  (e.g. prompt contains required rule strings) OR a `testing_mcp/` test that runs
  against a real local server (`./local.sh`) with the DEFAULT AGY CLI provider
  (verify `provider_mode=agy` in captured `agy_request`/`agy_response` payloads)
  and fails for the same reason as prod. Opting out of AGY (direct Gemini API)
  is allowed ONLY for a documented provider-specific claim, and the opt-out must
  be stated in the evidence.
- If you cannot produce a red proof, STOP. Do not write the fix. Do not proceed.
  Ship a bead instead and surface the missing red proof as the blocker.

## Example Workflow

```bash

# User reports: "UnboundLocalError: cannot access local variable 'os'"

# Step 1: Search for existing tests
# Look for tests in $PROJECT_ROOT/tests/ that test main.py functionality

# Step 2: Run existing tests to see if they catch the error
TESTING=true python $PROJECT_ROOT/tests/test_main.py

# Step 3: If tests don't exist or don't catch it, create/update tests
# Consider: integration test (real service), functional test (fixtures), or unit test

# Step 4: Confirm tests fail
TESTING=true python $PROJECT_ROOT/tests/test_main.py
# ✅ Signature: UnboundLocalError | ["cannot access local variable", "os"] | $PROJECT_ROOT/main.py:main

# Step 5: Implement minimal fix for the os import issue

# Step 6: Confirm tests pass
TESTING=true python $PROJECT_ROOT/tests/test_main.py
# ✅ All tests pass
# ✅ Confirmed: Application starts successfully

```

### Step 2: Documentation Review

- Validate that error reproduction was genuine and accurate
- Confirm the fix is minimal and targeted as required
- Verify testing demonstrates complete resolution

# Must confirm legitimate debugging process:

# ✅ CONSENSUS: Flow integrity validated

```

**CRITICAL RULE**: Phase 4 provides final validation that the red-green process was executed with integrity and produces genuine bug fixes, not superficial changes.

## Integration Points

- **Inherits test patterns from `/tdd`**: Use matrix testing and systematic coverage
- **Focuses on specific bugs**: Unlike `/tdd` which is feature-driven, this is error-driven
- **Minimal fix approach**: Targeted fixes rather than comprehensive refactoring
- **Error reproduction requirement**: Must reproduce exact error before fixing
- **Flow validation via `/consensus`**: Ensures debugging integrity and legitimacy

---

**Key Difference from `/tdd`**: While `/tdd` drives development with failing tests for new features, `/redgreen` takes a test-first approach to debugging actual bugs or errors:

1. **Search existing tests first** - Check if tests already catch the error
2. **Run tests to confirm reproduction** - Verify tests fail with the error
3. **Create/update tests only if needed** - Don't duplicate existing test coverage
4. **Confirm tests fail** - Ensure error is reproduced
5. **Fix** - Implement minimal fix
6. **Confirm tests pass** - Primary validation of fix

The workflow emphasizes finding and using existing tests before creating new ones, and uses test types (integration/functional/unit) based on judgment. It concludes with `/consensus` validation of the entire debugging flow.
