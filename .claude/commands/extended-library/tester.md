---
description: /tester - End2End Tests (Real Mode)
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# /tester - End2End Tests (Real Mode)

**Purpose**: Run end-to-end tests using actual services (Firestore + Gemini)

**Usage**: `/tester`

**Script**: `./claude_command_scripts/tester.sh`

## Description

Runs the full end2end test suite using real services:
- Real Firestore database writes and reads
- Real Gemini API calls
- Full persistence validation (submit → reload → verify)
- Validates actual system behavior

## Prerequisites

**Required Environment Variables**:
```bash
export REAL_FIREBASE_PROJECT=worldarchitect-test
export REAL_GEMINI_API_KEY=your_test_api_key
```

**Test Firebase Project**:
- Separate from production Firebase project
- Dedicated for testing with cleanup policies
- Same schema as production

## Environment

- `TEST_MODE=real`
- `TESTING=true`
- `FIREBASE_PROJECT_ID=$REAL_FIREBASE_PROJECT`
- `GEMINI_API_KEY=$REAL_GEMINI_API_KEY`

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
- 🔒 Requires explicit environment setup

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
