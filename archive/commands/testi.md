---
description: Integration Test Command
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

# Integration Test Command

**Purpose**: Run HTTP integration tests with real APIs

**Action**: Execute integration test suite using `testi.sh` script

**Usage**: `/testi`

**Implementation**:
- Run: `./testi.sh` (preferred) or fallback to manual execution
- Script location: `./testi.sh` in project root
- Alternative: `source venv/bin/activate && TESTING=true python3 $PROJECT_ROOT/test_integration/test_integration.py`
- Execute from project root with virtual environment activated
- Use TESTING=true environment variable for real API testing
- Analyze integration test results
- Fix any integration failures

**Script Benefits**:
- ✅ Handles virtual environment activation automatically
- ✅ Sets proper TESTING environment variables
- ✅ Provides consistent execution across environments
- ✅ Includes error handling and logging
