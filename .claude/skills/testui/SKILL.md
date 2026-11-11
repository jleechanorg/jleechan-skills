---
name: testui
description: Run real-service browser acceptance tests under the testing_ui/CLAUDE.md contract.
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute the real-service UI workflow

**Action Steps:**
1. Follow `testing_ui/CLAUDE.md` for the selected real application, services, account, and runner
2. Do not set mock endpoints or authentication-bypass variables for acceptance
3. Stream test output and track progress with TodoWrite as each selected test completes
4. Collect the artifacts required by the UI evidence owner
5. Report failures with their actual test name and first error excerpt
6. Report only the real-service validations that the run completed

## 📋 REFERENCE DOCUMENTATION

# Browser Tests Command

**Purpose**: Run the repository's real-service UI acceptance workflow.

**Action**: Run the selected browser tests without changing service or authentication configuration

**Usage**: `/testui`

## 🔄 **Method**

Follow `testing_ui/CLAUDE.md`:

- **Testing methodology**: Claude vision analysis, accessibility trees, visual regression
- **Validation protocols**: Screenshot validation, progressive baselines
- **Execution workflow**: plan the checks, then `/execute` with comprehensive testing
- **Documentation**: Structured PR comments with visual evidence

Deterministic unit tests with mocks remain useful outside `testing_ui/`, but do
not establish UI acceptance against the real application and services.

**For the validation protocol, see**: `testing_ui/CLAUDE.md`.
