---
description: /tester - End2End Tests (Real Mode)
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**Run only the installed wrapper from the target repository root.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Change to the target repository root.
2. Verify that `.claude/scripts/tester.sh` is executable; otherwise report that
   the repository does not install the `/tester` wrapper.
3. Run `.claude/scripts/tester.sh`. If an argument is supplied, the wrapper
   reports that pattern filtering is not implemented and still runs the full
   suite.

## 📋 REFERENCE DOCUMENTATION

# /tester - End2End Tests (Real Mode)

**Purpose**: Run end-to-end tests using actual services (Firestore + Gemini)

**Usage**: `/tester`

**Script**: `.claude/scripts/tester.sh`

## Description

Runs the full end2end test suite using real services:
- Real Firestore database writes and reads
- Real Gemini API calls
- Full persistence validation (submit → reload → verify)
- Validates actual system behavior

## Prerequisites

**Required Environment Variables**:
```bash
export GEMINI_API_KEY=your_test_api_key
# Optional; the wrapper displays this project or worldarchitect-test by default.
export TEST_FIRESTORE_PROJECT=worldarchitect-test
```

**Test Firebase Project**:
- `TEST_FIRESTORE_PROJECT` is optional and is only used to identify the test
  project in the wrapper output.
- If it is unset, the wrapper displays `worldarchitect-test`.

## Environment

- `TEST_MODE=real`
- `GEMINI_API_KEY` must already be set in the environment.
- `TEST_FIRESTORE_PROJECT` is optional; the wrapper does not export it.

## Test Coverage

- ✅ API endpoint contracts
- ✅ Response structure validation
- ✅ Real service behavior
- ✅ Database persistence validation
- ✅ Network/timing issues
- ✅ Service integration edge cases

## Safety Features

- ⚠️ Confirmation prompt before running (costs money)
- 🧹 Automatic test data cleanup
- ⏱️ Test duration tracking
- 🔒 Requires `GEMINI_API_KEY`; exits safely before prompting when it is absent

## Benefits

1. **Bug Detection**: Catches issues like Firestore persistence bugs
2. **Real Behavior**: Tests actual service responses and timing
3. **Confidence**: Validates production-like scenarios
4. **Integration**: Tests full service chain

## Costs & Considerations

- 💰 Gemini API calls cost money (small amounts for testing)
- 🐌 Slower than mock mode due to network calls
- 🔧 Requires test environment setup
- 🧹 Creates real data that needs cleanup

## Related Commands

- `/teste` - Mock mode (fast, free)
- `/testerc` - Real mode with data capture

## Output

Shows comprehensive test results including:
- Real service response validation
- Database persistence verification
- Performance timing data
- Service integration status
