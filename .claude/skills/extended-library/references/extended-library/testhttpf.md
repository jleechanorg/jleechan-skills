---
description: HTTP Tests (FULL) Command
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

# HTTP Tests (FULL) Command

**Purpose**: Run HTTP request tests with REAL APIs (costs money!)

**Action**: Execute HTTP request tests using requests library with real API calls

**Usage**: `/testhttpf`

**MANDATORY**: When using `/testhttpf` command, follow this exact sequence:

1. **Verify Test Environment**
   ```bash
   vpython -c "import requests" || echo "STOP: requests library not installed"
   ```
   - ✅ Continue only if import succeeds
   - ❌ FULL STOP if not installed

2. **Start Test Server (if needed)**
   ```bash
   TESTING=false PORT=8086 vpython $PROJECT_ROOT/main.py serve &
   sleep 3
   curl -s http://localhost:8086 || echo "Note: Using different port or external server"
   ```
   - ✅ Continue even if local server fails (tests may use different setup)

3. **Run HTTP Test with Real APIs**
   ```bash
   TESTING=false vpython testing_http/test_name.py
   ```
   - ✅ Report actual HTTP responses/errors
   - ❌ NEVER pretend requests succeeded
   - ⚠️ **WARNING**: This costs real money through API calls

**CRITICAL REQUIREMENTS**:
- 🚨 **HTTP requests only** - Must use requests library
- 🚨 **NO browser automation** - This is HTTP testing, not browser testing
- 🚨 **REAL APIs** - Makes actual external API calls (costs money!)
- ✅ **API endpoint testing** - Direct HTTP calls to test endpoints
- ❌ **NEVER use Playwright** - Use requests.get(), requests.post(), etc.
- ⚠️ **COST WARNING** - Uses real API calls that incur charges

**Testing Focus**:
- Real API endpoint responses
- Actual HTTP status codes
- Live authentication flows
- Production data validation
- End-to-end API integration
