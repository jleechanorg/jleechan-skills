---
description: /testerc - End2End Tests (Real Mode + Capture)
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Workflow

**Action Steps:**
1. **Run Capture**: Execute `/testerc` to collect fresh data
2. **Review Data**: Examine captured responses in `./test_data_capture/`
3. **Update Mocks**: Use captured data to improve `FakeFirestoreClient` and `FakeGeminiResponse`
4. **Validate Accuracy**: Run `/teste` to ensure mocks match real behavior
5. **Commit Updates**: Include updated mock data in version control

### Phase 2: Next Steps After Capture

**Action Steps:**
1. **Review Captures**: Check `./test_data_capture/` contents
2. **Generate Mocks**: Create scripts to update mock classes from captured data
3. **Run Real Tests**: Execute `/tester` to get baseline real service behavior
4. **Validate Mocks**: Run `/teste` and compare results to `/tester` output to ensure mocks match real behavior
5. **Document Changes**: Record what service behaviors changed
6. **Regular Refresh**: Schedule periodic recaptures to keep mocks current

## 📋 REFERENCE DOCUMENTATION

# /testerc - End2End Tests (Real Mode + Capture)

**Purpose**: Run end-to-end tests using real services AND capture data for mock generation

**Usage**: `/testerc`

**Script**: `./claude_command_scripts/testerc.sh`

## Description

Runs the full end2end test suite using real services with comprehensive data capture:
- Real Firestore database operations (captured)
- Real Gemini API interactions (captured)
- Full persistence validation
- Generates data for updating mock implementations

## Prerequisites

**Required Environment Variables**:
```bash
export REAL_FIREBASE_PROJECT=worldarchitect-test
export REAL_GEMINI_API_KEY=your_test_api_key
```

**Capture Directory**: `./test_data_capture/`
- Created automatically
- Previous captures cleared on each run
- Contains JSON files with service interactions

## Environment

- `TEST_MODE=capture`
- `TESTING=true`
- `FIREBASE_PROJECT_ID=$REAL_FIREBASE_PROJECT`
- `GEMINI_API_KEY=$REAL_GEMINI_API_KEY`
- `CAPTURE_OUTPUT_DIR=./test_data_capture`

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
./test_data_capture/
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
- 🔐 Capture data excluded from git (add to .gitignore)

## Related Commands

- `/teste` - Mock mode validation
- `/tester` - Real mode without capture
