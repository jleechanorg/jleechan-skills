---
description: Browser Tests Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute UI Tests with Real Services

**Action Steps:**
1. Follow `testing_ui/CLAUDE.md` and use the approved test account and real running application server/services
2. Run the selected test through `/testuif`; do not set mock endpoint or authentication bypass variables
3. Stream test output and track progress with TodoWrite as each test suite completes
4. Collect test artifacts (screenshots, logs) from the test output directory
5. If any test fails, report the failing test name and first error snippet
6. If all tests pass, report the exact real-service validations covered

## 📋 REFERENCE DOCUMENTATION

# Browser Tests Command

**Purpose**: Compatibility alias for `/testuif`, which runs browser tests under the real-service-only contract.

**Action**: Redirect to `/testuif` without mock mode configuration

**Usage**: `/testui`

## 🔄 **Command Redirect**

This command delegates to `/testuif` and follows `testing_ui/CLAUDE.md`:

- **Same testing methodology**: Claude vision analysis, accessibility trees, visual regression
- **Same validation protocols**: Enhanced screenshot validation, progressive baselines
- **Same execution workflow**: `/think` → `/execute` with comprehensive testing
- **Same documentation**: Structured PR comments with visual evidence

## 📋 **Full Documentation**

**See**: `/testuif` command documentation for complete details

Every `testing_ui/` test uses a real application server and real services. Use
non-UI deterministic unit tests outside `testing_ui/` when mocks are needed.
| PR Documentation | Same format | Same format |

**For complete command documentation, usage examples, and enhanced validation protocols, see**: `.claude/commands/testuif.md`
