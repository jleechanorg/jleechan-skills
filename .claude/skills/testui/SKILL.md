---
name: testui
description: Compatibility alias for real-service browser acceptance tests through /testuif.
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute the real-service UI workflow

**Action Steps:**
1. Follow `testing_ui/CLAUDE.md` and the `/testuif` command for the selected real application, services, account, and runner
2. Do not set mock endpoints or authentication-bypass variables for acceptance
3. Stream test output and track progress with TodoWrite as each selected test completes
4. Collect the artifacts required by the UI evidence owner
5. Report failures with their actual test name and first error excerpt
6. Report only the real-service validations that the run completed

## 📋 REFERENCE DOCUMENTATION

# Browser Tests Command

**Purpose**: Compatibility alias for `/testuif`, which runs the repository's real-service UI acceptance workflow.

**Action**: Redirect to `/testuif` without changing service or authentication configuration

**Usage**: `/testui`

## 🔄 **Command Redirect**

This command delegates to `/testuif` and follows `testing_ui/CLAUDE.md`:

- **Same testing methodology**: Claude vision analysis, accessibility trees, visual regression
- **Same validation protocols**: Enhanced screenshot validation, progressive baselines
- **Same execution workflow**: `/think` → `/execute` with comprehensive testing
- **Same documentation**: Structured PR comments with visual evidence

## 📋 **Full Documentation**

**See**: `/testuif` command documentation for complete details

Deterministic unit tests with mocks remain useful outside `testing_ui/`, but do
not establish UI acceptance against the real application and services.

**For complete command documentation and validation protocols, see**:
`~/.claude/commands/extended-library/testuif.md` and `testing_ui/CLAUDE.md`.
