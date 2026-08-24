---
description: Browser Tests (Mock) Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute UI Tests in Mock Mode

**Action Steps:**
1. Export or set mock environment variables required by the tests (TESTING=true, mock API endpoints)
2. Run the UI test script with the mock flag: `./run_ui_tests.sh mock`
3. Stream test output and track progress with TodoWrite as each test suite completes
4. Collect test artifacts (screenshots, logs) from the test output directory
5. If any test fails, report the failing test name and first error snippet
6. If all tests pass, report "All mock UI tests passed" with summary of validations covered

## 📋 REFERENCE DOCUMENTATION

# Browser Tests (Mock) Command

**Purpose**: Mock version of `/testuif` - identical functionality but runs with FAKE/MOCK APIs instead of real APIs

**Action**: Redirect to `/testuif` command with mock mode configuration

**Usage**: `/testui`

## 🔄 **Command Redirect**

This command is **exactly the same** as `/testuif` but runs in **mock mode**:

- **Same testing methodology**: Claude vision analysis, accessibility trees, visual regression
- **Same validation protocols**: Enhanced screenshot validation, progressive baselines
- **Same execution workflow**: `/think` → `/execute` with comprehensive testing
- **Same documentation**: Structured PR comments with visual evidence

**ONLY DIFFERENCE**: Uses mock APIs instead of real APIs

## 📋 **Full Documentation**

**See**: `/testuif` command documentation for complete details

**Mock Mode Configuration**:
```bash

# Environment variables for mock mode

export USE_MOCK_FIREBASE=true
export USE_MOCK_GEMINI=true
export API_COST_MODE=free

# Same execution as testuif but with mocks

./run_ui_tests.sh mock --playwright --enhanced-validation
```

## 🚨 **API Mode Differences**

| Feature | `/testui` (Mock) | `/testuif` (Real) |
|---------|------------------|-------------------|
| Firebase | Mock responses | Real Firestore API |
| Gemini | Mock responses | Real API calls ($) |
| Cost | Free | Costs money |
| Validation | Same methodology | Same methodology |
| Screenshots | Same approach | Same approach |
| PR Documentation | Same format | Same format |

**For complete command documentation, usage examples, and enhanced validation protocols, see**: `.claude/commands/testuif.md`
