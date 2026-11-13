---
description: /testmcp - MCP Test Suite Execution Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Step 1: Test Specification Resolution

**Action Steps:**
Based on the command arguments, resolve to appropriate test specification:

**Test Type Mapping**:
1. `integration` → `testing_mcp/test_create_continue_mcp.md` (comprehensive integration test)
2. `performance` → Run `testing_mcp/run_mcp_tests.sh performance` via `/testllm`
3. `unit` → Run `testing_mcp/run_mcp_tests.sh unit` via `/testllm`
4. `mock` → Do not run a mocked `testing_mcp` test. Every test in `testing_mcp/` uses a real running application server and real services; use only an explicitly allow-listed direct-provider schema probe when applicable.
5. `all` or no args → Use focused local coverage for the requested behavior; CI owns the unfiltered full suite. Never run an unfiltered full suite locally.
6. Specific `.md` file → Direct execution of test specification via `/testllm`

### Phase 2: Step 2: /testllm Delegation

**Action Steps:**
Execute the resolved test specification using `/testllm` with appropriate mode:

**Single-Agent Mode** (default):
```
/testllm [resolved_test_spec] [additional_args]
```

**Dual-Agent Mode** (when `verified` keyword present):
```
/testllm verified [resolved_test_spec] [additional_args]
```

### Phase 1: Argument Analysis

**Action Steps:**
1. **Parse command arguments** to determine test type and mode
2. **Validate test specifications** exist in `testing_mcp/` directory
3. **Check for `verified` keyword** to determine single vs dual-agent mode
4. **Resolve target test specification** based on test type

### Phase 2: Environment Validation

**Action Steps:**
1. **Check MCP server availability** (production mode required)
2. **Verify test dependencies** (pytest, browser automation tools)
3. **Validate authentication configuration** for real API testing
4. **Confirm network connectivity** for Firebase/Gemini integration

### Phase 3: /testllm Execution

**Action Steps:**
1. **Delegate to `/testllm`** with resolved test specification
2. **Apply systematic validation protocol** from `/testllm` framework
3. **Execute with TodoWrite tracking** for comprehensive requirement validation
4. **Capture evidence** (screenshots, logs, API responses) in a unique `/tmp/<run-id>/` directory

### Phase 4: Results Analysis

**Action Steps:**
1. **Process test results** using `/testllm` analysis framework
2. **Generate evidence-backed conclusions** with specific file references
3. **Classify findings** as CRITICAL/HIGH/MEDIUM per MCP test specifications
4. **Provide actionable recommendations** for MCP architecture improvements

### Phase 7: Specific Test File Execution

**Action Steps:**
```bash
/testmcp test_create_continue_mcp.md
```
**Result**: Direct execution of specified test specification with systematic validation

## 📋 REFERENCE DOCUMENTATION

# /testmcp - MCP Test Suite Execution Command

## Purpose

Execute MCP (Model Context Protocol) test specifications using the comprehensive `/testllm` framework for systematic test validation with real authentication and integration testing.

## Usage Patterns

```bash

# Run all MCP tests

/testmcp

# Run specific test type

/testmcp integration
/testmcp performance
/testmcp unit

# Run with verification (dual-agent mode)

/testmcp verified
/testmcp verified integration

# Run specific test file

/testmcp test_create_continue_mcp.md
/testmcp verified test_create_continue_mcp.md
```

## Core Principles

- **LLM-Native Execution**: Uses `/testllm` framework for intelligent test execution
- **Real Integration Testing**: Tests actual MCP server functionality with real Firebase/Gemini APIs
- **Comprehensive Coverage**: Unit, integration, and performance testing for MCP architecture
- **Systematic Validation**: Evidence-based testing with TodoWrite tracking and screenshot documentation

## Implementation Method

This command delegates to `/testllm` for intelligent test orchestration of MCP test specifications in the `test_mcp/` directory (override with `$MCP_TEST_DIR`, default: `test_mcp/`).

**Execution Flow**:
```
/testmcp [args] → /testllm [testing_mcp/test_spec] [args]
```

## Test Specifications Available

### Integration Test Specification

**File**: `testing_mcp/test_mcp/test_create_continue_mcp.md`
- **Objective**: Complete MCP workflow validation from campaign creation through story progression
- **Coverage**: Real Firebase integration, Gemini AI integration, character creation, story continuation
- **Duration**: 5-10 minutes
- **Authentication**: Real user authentication required
- **Validation**: Full game state persistence and AI-generated content verification

### Shell Script Test Suite

**File**: `testing_mcp/run_mcp_tests.sh`
- **Test Types**: unit, integration, performance, all, docker (use only modes that honor the real-service contract)
- **Features**: Real-service testing and comprehensive reporting
- **Timeout**: Configurable (default 300 seconds)
- **Output**: JUnit XML results, HTML reports, detailed logging

## Command Implementation

When `/testmcp` is executed, it follows this systematic protocol:

## Test Environment Requirements

### Production Mode Testing

- **MCP Server**: Must be running in production mode (`PRODUCTION_MODE=true`)
- **Authentication**: Real Google OAuth for authentic user flows
- **APIs**: Real Firebase Firestore and Gemini API integration
- **Browser**: Playwright MCP for headless browser automation

Do not run `testing_mcp/` in mock mode. Every test in that directory must use
a real running application server and real services, except explicitly
allow-listed direct-provider schema probes.

## Success Criteria

### Integration Test Success

- ✅ Campaign creation with real Firebase document ID
- ✅ Character creation flow completion without errors
- ✅ Story progression with genuine AI-generated content
- ✅ Game state persistence across multiple interactions
- ✅ All MCP tool calls successful with proper validation

### Shell Script Test Success

- ✅ All pytest test cases pass (unit, integration, performance)
- ✅ Mock services start and respond correctly
- ✅ Test reports generated with detailed metrics
- ✅ No timeout or connection failures
- ✅ Cleanup procedures execute successfully

## Error Handling

### Common Test Failures

- **MCP Server Connection**: Verify server is running and accessible
- **Authentication Failures**: Ensure real Google OAuth credentials configured
- **API Rate Limits**: Implement backoff strategies for Gemini API calls
- **Test Environment**: Check Python virtual environment and dependencies
- **Browser Automation**: Verify Playwright MCP is available and functional

### Recovery Protocols

1. **Environment Reset**: Clean test databases and restart services
2. **Dependency Check**: Validate all required packages and tools installed
3. **Configuration Audit**: Verify environment variables and API keys
4. **Network Validation**: Test connectivity to external services
5. **Log Analysis**: Review detailed test logs for specific failure points

## Integration with /testllm Framework

This command leverages the complete `/testllm` infrastructure:

### Systematic Validation Protocol

- **Requirements Analysis**: Extract ALL test requirements to TodoWrite checklist
- **Evidence Collection**: Screenshots, logs, console output for each requirement
- **Success Declaration**: Only with complete evidence portfolio
- **Failure Analysis**: Specific error categorization and recommendations

### Dual-Agent Architecture (Optional)

- **TestExecutor Agent**: Pure execution and evidence collection
- **TestValidator Agent**: Independent validation with fresh context
- **Cross-Verification**: Both agents must agree for final success declaration
- **Bias Elimination**: Separate validation removes execution investment bias

## Command Examples

### Basic MCP Integration Test

```bash
/testmcp integration
```
**Result**: Executes comprehensive campaign creation and story progression test with real APIs

### Verified Performance Testing

```bash
/testmcp verified performance
```
**Result**: Dual-agent performance benchmark execution with independent validation

## Anti-Patterns to Avoid

- ❌ **Bypassing /testllm**: Never implement test execution logic directly
- ❌ **Mocked `testing_mcp/` runs**: Use deterministic unit tests outside `testing_mcp/` when mocks are needed
- ❌ **Incomplete Evidence**: Must capture screenshots and logs for all test steps
- ❌ **Manual Assumptions**: All test results require specific evidence backing
- ❌ **Single-Pass Testing**: Must test both success and failure scenarios

## Quality Assurance Integration

### Evidence Requirements

- **Screenshots**: Saved to `/tmp/<run-id>/` with descriptive names for each test phase
- **Test Logs**: Detailed execution logs with timestamps and status codes
- **API Responses**: Captured request/response data for integration validation
- **Error Documentation**: Specific error messages and stack traces when failures occur

### Reporting Standards

- **TodoWrite Tracking**: Complete requirement-by-requirement validation status
- **Priority Classification**: CRITICAL/HIGH/MEDIUM/LOW issue categorization
- **Actionable Feedback**: Specific recommendations with code references
- **Evidence Portfolio**: Complete documentation package for each test execution

This command provides comprehensive MCP architecture testing through intelligent delegation to the proven `/testllm` framework, ensuring systematic validation and evidence-based conclusions for production readiness assessment.
