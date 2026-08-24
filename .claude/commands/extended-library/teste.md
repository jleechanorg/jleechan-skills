---
description: /teste - End2End Tests (Mock Mode)
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute End-to-End Tests

**Action Steps:**
1. From the workspace root, run `./claude_command_scripts/teste.sh` (mock mode) to execute the end-to-end suite
2. Stream stdout/stderr and log progress and results in TodoWrite as each suite completes
3. If any test fails, stop further steps, include the failing suite name plus the first error snippet in the command response, and request follow-up
4. If all tests pass, report "All mock E2E tests passed" and list key validations covered (API contracts, response structure, mock behavior)

## 📋 REFERENCE DOCUMENTATION

# /teste - End2End Tests (Mock Mode)

**Purpose**: Run end-to-end tests using mocked services (current behavior)

**Usage**: `/teste`

**Script**: `./claude_command_scripts/teste.sh`

## Description

Runs the full end2end test suite using fake/mocked services:
- `FakeFirestoreClient` instead of real Firestore
- `MockGeminiClient` instead of real Gemini API
- Fast execution, no external dependencies
- Tests API contracts and basic flow

## Environment

- `TEST_MODE=mock`
- `TESTING=true`
- Uses existing mock implementations

## Test Coverage

- ✅ API endpoint contracts
- ✅ Response structure validation
- ✅ Basic error handling
- ❌ Real service behavior
- ❌ Database persistence validation
- ❌ Network/timing issues

## Related Commands

- `/tester` - Real mode (actual services)
- `/testerc` - Real mode with data capture

## Output

Shows test results with focus on:
- Pass/fail status for each test
- API contract validation
- Mock behavior verification

**Note**: This mode may miss bugs that only occur with real services (like the Firestore persistence bug we just fixed).
