---
description: /testerc - End2End Tests (Real Mode + Capture)
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**Run only the installed wrapper from the target repository root.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Workflow

**Action Steps:**
1. Change to the target repository root.
2. Verify that `.claude/scripts/testerc.sh` is executable; otherwise report that
   the repository does not install the `/testerc` wrapper.
3. **Run Capture**: Execute `.claude/scripts/testerc.sh` to collect fresh data.
4. **Review Data**: Examine captured responses in the printed
   `/tmp/test_captures/<timestamp>/` directory.
5. **Update Mocks**: Use captured data to improve `FakeFirestoreClient` and `FakeGeminiResponse`.
6. **Validate Accuracy**: Run `/teste` to ensure mocks match real behavior.
7. **Commit Updates**: Include updated mock data in version control.

### Phase 2: Next Steps After Capture

**Action Steps:**
1. **Review Captures**: Check the printed `/tmp/test_captures/<timestamp>/` directory.
2. **Generate Mocks**: Create scripts to update mock classes from captured data
3. **Run Real Tests**: Execute `/tester` to get baseline real service behavior
4. **Validate Mocks**: Run `/teste` and compare results to `/tester` output to ensure mocks match real behavior
5. **Document Changes**: Record what service behaviors changed
6. **Regular Refresh**: Schedule periodic recaptures to keep mocks current

## 📋 REFERENCE DOCUMENTATION

# /testerc - End2End Tests (Real Mode + Capture)

**Purpose**: Run end-to-end tests using real services AND capture data for mock generation

**Usage**: `/testerc`

**Script**: `.claude/scripts/testerc.sh`

## Description

Runs the full end2end test suite using real services with comprehensive data capture:
- Real Firestore database operations (captured)
- Real Gemini API interactions (captured)
- Full persistence validation
- Generates data for updating mock implementations

## Prerequisites

**Required Environment Variables**:
```bash
export TEST_GEMINI_API_KEY=your_test_api_key
# Optional; the wrapper displays this project or worldarchitect-test by default.
export TEST_FIRESTORE_PROJECT=worldarchitect-test
```

**Capture Directory**: `/tmp/test_captures/<YYYYMMDD_HHMMSS>/`
- The wrapper sets a timestamped path and exports it as `TEST_CAPTURE_DIR`.
- The test runner writes captured service interactions there.
- The exact path is printed after the wrapper starts.

## Environment

- `TEST_MODE=capture`
- `TEST_GEMINI_API_KEY` must already be set in the environment.
- `TEST_FIRESTORE_PROJECT` is optional; the wrapper does not export it.
- `TEST_CAPTURE_DIR=/tmp/test_captures/<YYYYMMDD_HHMMSS>` (set by the wrapper)

## Data Capture

**Captured Data Types**:
- 📡 **Gemini Requests**: All API calls with parameters
- 📡 **Gemini Responses**: Full response objects and metadata
- 📡 **Firestore Operations**: Database reads, writes, queries
- 📡 **Firestore Data**: Document structures and field types
- ⏱️ **Timing Data**: Service response times and patterns
- 🔍 **Error Cases**: Failed requests and error responses

**Output Structure**:
```
/tmp/test_captures/<YYYYMMDD_HHMMSS>/
├── gemini_requests.json
├── gemini_responses.json
├── firestore_operations.json
├── firestore_documents.json
├── timing_data.json
└── test_metadata.json
```

## Use Cases

1. **Mock Generation**: Create accurate mock data from real service responses
2. **Behavior Documentation**: Record actual service behavior patterns
3. **Regression Detection**: Compare new captures with previous baselines
4. **Service Evolution**: Track how external services change over time
5. **Test Data Refresh**: Update test fixtures with fresh real data

## Benefits

- 🎯 **Accurate Mocks**: Ensures test doubles match real service behavior
- 🐛 **Bug Prevention**: Identifies mock/reality gaps that hide bugs
- 📈 **Continuous Improvement**: Regular captures keep mocks current
- 📚 **Documentation**: Captured data serves as service behavior spec
- 🔄 **Automation Ready**: Captured data can drive mock generation scripts

## Safety Features

- ⚠️ Confirmation prompt (costs money + captures sensitive data)
- 🧹 Automatic test data cleanup
- 📁 Organized capture directory structure
- 🔐 Requires `TEST_GEMINI_API_KEY`; exits safely before prompting when it is absent

## Related Commands

- `/teste` - Mock mode validation
- `/tester` - Real mode without capture
