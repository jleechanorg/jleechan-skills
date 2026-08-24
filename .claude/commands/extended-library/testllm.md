---
description: /testllm - LLM-Driven Test Execution Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Mandatory First Step

**Action Steps:**
1. **Read the Entire Suite First**: Before planning, checklist creation, or any execution, explicitly read every test specification in the `testing_llm/` directory to internalize scope, dependencies, and evidence requirements.

### Phase 2: Report Integrity Checklist (MANDATORY)

**Action Steps:**
Before submitting final report, verify:

1. [ ] Every claimed evidence file verified with `ls -la` command
2. [ ] No references to non-existent files or screenshots
3. [ ] Exit status tracked for all commands
4. [ ] Final SUCCESS/FAILURE aligned with actual exit codes
5. [ ] No contradictions between claims and evidence
6. [ ] All TodoWrite items have corresponding verified evidence

### Phase 3: Pre-Execution Requirements

**Action Steps:**
**CRITICAL**: Before starting ANY test specification, ALWAYS follow this systematic protocol:

1. **Read Specification Twice**: Complete understanding before execution
2. **Extract ALL Requirements**: Convert every requirement to TodoWrite checklist
3. **Identify Evidence Needs**: Document what proof is needed for each requirement
4. **Create Validation Plan**: Map each requirement to specific validation method
5. **Execute Systematically**: Complete each requirement with evidence collection
6. **Success Declaration**: Only declare success with complete evidence portfolio

### Phase 4: Step 1: Complete Directory Analysis (MANDATORY GATE)

**Action Steps:**
1. **Read ALL test files** in the specified directory before any execution
2. **Catalog ALL test cases** across all files in TodoWrite checklist
3. **Identify test dependencies** and execution order requirements
4. **Verify test coverage** spans all requested functionality
5. **Document test matrix** showing all scenarios to be validated
6. **🚨 INTEGRATION TEST DISCOVERY**: Search for integration tests in:
   - `$PROJECT_ROOT/tests/integration/`
   - Files matching `**/test_*integration*.py`
   - Files matching `**/integration_test*.py`
   - Backend integration test directories
7. **🚨 INTEGRATION TEST VALIDATION**: For each discovered integration test:
   - Check if it has skip decorators or skip conditions
   - Document skip reasons (e.g., "requires Firestore emulator")
   - If skipped locally, mark as REQUIRES DEPLOYED ENVIRONMENT VALIDATION
8. **⚠️ GATE: Cannot proceed without complete test inventory from ALL files INCLUDING integration tests**

### Phase 5: Step 2: Comprehensive Test Planning

**Action Steps:**
1. **Extract requirements from EACH test file** into unified checklist
2. **Map test interdependencies** (authentication → campaign creation, etc.)
3. **Plan execution sequence** respecting prerequisites
4. **Estimate total test duration** for all cases combined
5. **Document evidence collection** needs for complete matrix
6. **⚠️ GATE: Cannot start testing without unified execution plan**

### Phase 6: Step 3: Sequential Test Execution

**Action Steps:**
1. **Execute ALL test files** in logical dependency order
2. **Complete each test matrix** before moving to next file
3. **Collect evidence for EVERY test case** across all files
4. **🚨 EXIT CODE TRACKING**: Track exit codes for EACH test file execution:
   - Store exit code for each test file (0 = pass, 1 = fail, 124 = timeout)
   - Document which specific test file produced each exit code
   - Aggregate overall exit code (ANY failure = overall failure)
5. **🚨 TIMEOUT DETECTION**: Implement 5-minute timeout per test file:
   - If test hangs beyond timeout, kill process and record exit code 124
   - **Cross-platform note**: Exit code 124 is from GNU `timeout` command (Linux). On macOS, use `gtimeout` (install via `brew install coreutils`). For Python/Node.js, use language-specific timeout (e.g., `subprocess.run(..., timeout=300)`) and document the timeout behavior
   - Document timeout event in evidence
   - Mark test as FAILED due to timeout
6. **🚨 PARTIAL SUCCESS PREVENTION**: Track executed vs total test count:
   - Increment executed_count for each test file run
   - Compare executed_count vs total_count at end
   - If executed_count < total_count, report PARTIAL EXECUTION (not SUCCESS)
7. **Track completion status** for entire directory scope
8. **Validate success criteria** for combined test suite
9. **⚠️ GATE: Cannot declare success without ALL files tested AND all exit codes = 0**

### Phase 7: Step 1: Systematic Requirement Analysis

**Action Steps:**
1. Read test specification completely (minimum twice)
2. Extract ALL requirements into explicit TodoWrite checklist items
3. Identify success criteria AND failure conditions for each requirement
4. Document evidence collection plan for each requirement
5. Create systematic validation approach before any execution

### Phase 8: Step 2: Test Environment Setup

**Action Steps:**
1. Review `run_local_server.sh` to understand how the local environment should be launched
2. Detect whether the local server stack started by `run_local_server.sh` is already running
3. If servers are not running, execute `run_local_server.sh` and wait for successful startup
4. Ensure real authentication is configured (no test mode)
5. Validate Playwright MCP availability for browser automation
6. Confirm network connectivity for real API calls
7. Determine the current repository name (`git rev-parse --show-toplevel | xargs basename`) and active branch (`git rev-parse --abbrev-ref HEAD`) to construct result paths under `/tmp/<repo_name>/<branch_name>/`

### Phase 9: Step 2.5: Result Output Directory Standard

**Action Steps:**
1. Create (if necessary) the directory `/tmp/<repo_name>/<branch_name>/`
2. Store **all** test outputs, logs, screenshots, and evidence artifacts inside this directory or its subdirectories
3. After execution, enumerate every created file and subdirectory so the user receives a complete inventory
4. Explicitly communicate the absolute path to the `/tmp/<repo_name>/<branch_name>/` directory and its contents in the final summary

### Phase 10: Step 3: Test Execution

**Action Steps:**
1. Follow test instructions step-by-step with LLM reasoning
2. Use Playwright MCP for browser automation (headless mode)
3. Make real API calls to actual backend
4. Capture screenshots for evidence using proper file paths
5. Monitor console errors and network requests
6. Document findings with exact evidence references

### Phase 11: Step 4: Results Analysis

**Action Steps:**
1. Assess findings against test success criteria
2. Classify issues as CRITICAL/HIGH/MEDIUM per test specification
3. Provide actionable recommendations
4. Generate evidence-backed conclusions

### Phase 12: Execution Flow with Validation Gates

**Action Steps:**
```
1. Systematic Requirement Analysis (MANDATORY GATE)
   ├── Read test specification twice completely
   ├── Extract ALL requirements to TodoWrite checklist
   ├── Identify success criteria AND failure conditions
   ├── Document evidence needs for each requirement
   ├── Create systematic validation plan
   └── ⚠️ GATE: Cannot proceed without complete requirements checklist

2. Environment Validation
   ├── Inspect `run_local_server.sh` for the expected services and health checks
   ├── Determine if the local server stack is already running; start it with `run_local_server.sh` if needed
   ├── Verify authentication configuration
   ├── Confirm Playwright MCP availability
   ├── Validate network connectivity
   ├── 🚨 INTEGRATION TEST DEPENDENCY CHECK:
   │   ├── Check if Firestore emulator is configured/running
   │   ├── Check if other integration test dependencies available
   │   └── If dependencies missing, flag REQUIRES DEPLOYED ENVIRONMENT VALIDATION
   └── ⚠️ GATE: Cannot proceed without environment validation

3. Systematic Test Execution
   ├── Execute EACH TodoWrite requirement individually
   ├── Capture evidence for EACH requirement (screenshots, logs)
   ├── 🚨 TRACK EXIT CODES: Record exit code for each test execution
   ├── 🚨 TIMEOUT ENFORCEMENT: 5-minute timeout per test, kill if exceeded
   ├── Test positive cases AND negative/failure cases
   ├── Update TodoWrite status: pending → in_progress → completed
   ├── Validate evidence quality before marking complete
   └── ⚠️ GATE: Cannot proceed to next requirement without evidence

4. Comprehensive Results Validation
   ├── Verify ALL TodoWrite items marked completed with evidence
   ├── Cross-check findings against original specification
   ├── Validate that failure conditions were tested (not just success)
   ├── 🚨 MANDATORY: Run `ls -la /tmp/<repo_name>/<branch_name>/` to verify all claimed evidence files
   ├── 🚨 MANDATORY: Compare claimed evidence files against actual directory listing
   ├── 🚨 MANDATORY: Remove any phantom file references from report
   ├── 🚨 MANDATORY: Check executed vs total test count
   ├── 🚨 MANDATORY: If executed < total, report PARTIAL EXECUTION
   ├── 🚨 MANDATORY: If integration tests skipped locally, verify deployed environment testing
   ├── 🚨 MANDATORY: Generate Anti-False-Positive Checklist (see Phase 13)
   ├── Generate evidence-backed report with ONLY verified file references
   ├── Apply priority classification with specific evidence
   ├── 🚨 MANDATORY: Check exit status of all executed commands
   ├── 🚨 MANDATORY: Aggregate all exit codes (ANY failure = overall FAILURE)
   ├── 🚨 MANDATORY: Align final SUCCESS/FAILURE with actual exit codes
   └── ⚠️ FINAL GATE: Success only declared with ALL of:
       ├── Exit code 0 for ALL tests
       ├── All tests executed locally (executed_count == total_count), OR all skipped tests validated in deployed environment
       ├── Complete verified evidence portfolio
       ├── Integration tests passed OR deployed environment validated
       └── Anti-False-Positive Checklist: all items checked OR marked N/A with explicit justification
```

### Phase 13: Anti-False-Positive Checklist (MANDATORY OUTPUT)

**Action Steps:**
Generate this checklist in EVERY test execution report:

```markdown
## Anti-False-Positive Validation Checklist

**Test Discovery & Coverage:**
- [ ] All test files discovered and accounted for ({executed}/{total})
- [ ] Integration tests identified (count: {integration_count})
- [ ] Unit tests identified (count: {unit_count})

**Execution Verification:**
- [ ] Exit code 0 for all executed tests
- [ ] Exit code tracking: [list each test file with its exit code]
- [ ] No tests timed out (5-minute limit per test)
- [ ] Executed count == Total count (100% execution)

**Evidence Verification:**
- [ ] Evidence files verified to exist (ls -la output included)
- [ ] File sizes and timestamps recorded
- [ ] No phantom file references
- [ ] Screenshots saved to /tmp/<repo>/<branch>/ directory

**Integration Test Validation:**
- [ ] Integration tests either:
  - [ ] Passed locally (exit code 0), OR
  - [ ] Skipped locally with documented reason AND validated against deployed environment
- [ ] N/A if no integration tests in scope (with justification)

**Quality Assurance:**
- [ ] No "documented but not fixed" issues
- [ ] Test output matches claimed results
- [ ] No partial success declarations
- [ ] Final status aligned with exit codes

**Overall Status:**
- Tests executed: {executed}/{total} (100% required for SUCCESS)
- Tests passed: {passed}/{total}
- Tests failed: {failed}/{total} (0 required for SUCCESS)
- Tests skipped: {skipped}/{total} (must be 0 for SUCCESS, unless each has documented reason + deployed validation)
- Integration tests: {integration_status} (PASSED / DEPLOYED_VALIDATED / FAILED / N/A)
- Overall exit code: {exit_code} (0 required for SUCCESS, any non-zero including 1 or 124 indicates FAILURE)

**Final Verdict:** ✅ SUCCESS / ❌ FAILURE / ⚠️ PARTIAL EXECUTION
```

### Phase 14: Command Execution Modes

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 15: Execution Flow Selection Logic

**Action Steps:**
```
if not command_args:
    execute_directory_suite("testing_llm", mode="single_agent")
elif command_args == ["verified"]:
    execute_directory_suite("testing_llm", mode="dual_agent")
elif "verified" in command_args:
    execute_dual_agent_mode()
    spawn_testexecutor_agent()
    wait_for_evidence_package()
    spawn_testvalidator_agent()
    cross_validate_results()
else:
    execute_single_agent_mode()
    follow_systematic_validation_protocol()
```

## 📋 REFERENCE DOCUMENTATION

# /testllm - LLM-Driven Test Execution Command

## Purpose

Execute test specifications directly as an LLM without generating intermediate scripts or files. Follow test instructions precisely with real authentication and browser automation.

## Usage Patterns

```bash

# Default Directory Suite (No Arguments)

/testllm
/testllm verified

# Single-Agent Testing (Traditional)

/testllm path/to/test_file.md
/testllm path/to/test_file.md with custom user input
/testllm "natural language test description"

# Dual-Agent Verification (Enhanced Reliability)

/testllm verified path/to/test_file.md
/testllm verified path/to/test_file.md with custom input
/testllm verified "natural language test description"
```

### Default Behavior (No Arguments Provided)

- **Automatic Directory Coverage**: When invoked without a specific test file or natural language specification, `/testllm` automatically executes the full `testing_llm/` directory test suite using the [🚨 DIRECTORY TESTING PROTOCOL](#-directory-testing-protocol---mandatory-for-all-directory-based-tests).
- **Verified Mode Support**: `/testllm verified` with no additional arguments runs the same `testing_llm/` directory workflow, but with the dual-agent verification architecture for independent validation.
- **Extensible Overrides**: Providing any explicit file path, directory, or natural language description overrides the default and targets the requested scope.

## Core Principles

- **LLM-Native Execution**: Drive tests directly as Claude, no script generation
- **Real Mode Only**: NEVER use mock mode, test mode, or simulated authentication
- **Precise Following**: Execute test instructions exactly as written
- **Browser Automation**: Use Playwright MCP for real browser testing
- **Real Authentication**: Use actual Google OAuth with real credentials
- **🚨 TOTAL FAILURE PROTOCOL**: Apply [Total Failure Protocol](total_failure.md) - 100% working or TOTAL FAILURE

## 🚨 ANTI-FALSE-POSITIVE PROTOCOL (MANDATORY)

### Evidence File Verification (CRITICAL)

Before generating ANY test report, you MUST:

1. **Run File System Check**: Execute `ls -laR /tmp/<repo>/<branch>/`
2. **Compare Claims vs Reality**: Cross-reference every file mentioned in report against actual directory listing
3. **Remove Phantom Files**: Delete ANY file references that don't appear in the `ls` output
4. **Zero Tolerance**: If you claim a file exists, it MUST be verified by command output
5. **Include ls Output**: Include the actual `ls -la` output in the final report for transparency

### Exit Status Validation (CRITICAL)

Before declaring test SUCCESS, you MUST:

1. **Track All Exit Codes**: Monitor exit status of EVERY test file execution
2. **Per-Test Tracking**: Record exit code for each individual test file (format: test_file.py: exit_code)
3. **Aggregate Status**: If ANY test exits with code 1 or 124 (timeout), overall result is FAILURE
4. **Align Report with Reality**: FORBIDDEN to report "SUCCESS" with exit code 1
5. **Evidence of Success**: Success requires BOTH exit code 0 for ALL tests AND complete verified evidence

### Zero Partial Success Policy (CRITICAL)

Before declaring test SUCCESS, you MUST verify:

1. **Total Test Discovery**: Count ALL test files in scope (unit + integration)
2. **Execution Tracking**: Track which tests were executed vs skipped
3. **100% Execution Required**: If executed_count < total_count, report PARTIAL EXECUTION (not SUCCESS)
4. **Skip Justification**: Skipped tests MUST have documented reason in test file itself
5. **Deployed Environment Requirement**: If integration tests skipped locally (e.g., no emulator), REQUIRE validation against deployed preview environment
6. **No Partial Success**: FORBIDDEN to declare SUCCESS with partial execution

### Integration Test Enforcement (CRITICAL)

For ALL test runs that include integration tests, you MUST:

1. **Discover Integration Tests**: Search for test files matching integration test patterns
2. **Dependency Check**: Verify if integration test dependencies available (e.g., Firestore emulator)
3. **Pass or Deploy Validation**: Integration tests MUST either:
   - Pass locally with exit code 0, OR
   - Be validated against deployed preview environment, OR
   - Have explicit documented skip reason in test file
4. **FAIL if Neither**: If integration tests neither pass nor have deployed validation, FAIL the entire test run
5. **No Assumption Success**: CANNOT assume integration tests work without evidence

## Dual-Agent Architecture (Enhanced Reliability)

### Independent Verification System

When `verified` keyword is used, `/testllm` employs a dual-agent architecture to eliminate execution bias:

**TestExecutor Agent**:
- **Role**: Pure execution and evidence collection
- **Focus**: Follow specifications methodically, capture all evidence
- **Constraint**: Cannot declare success/failure, only "evidence collected"
- **Output**: Structured evidence package with neutral documentation

**TestValidator Agent**:
- **Role**: Independent validation with fresh context
- **Focus**: Critical evaluation of evidence against original requirements
- **Constraint**: Zero execution context, no bias toward success
- **Input**: Original test spec + evidence package only

### Bias Elimination Benefits

- **Execution Bias Removed**: Separate agent validates without execution investment
- **Fresh Perspective**: Validator sees only evidence, not execution challenges
- **Cross-Verification**: Both agents must agree for final success declaration
- **Systematic Quality**: Evidence-based validation prevents premature success claims

## Systematic Validation Protocol (MANDATORY)

### Anti-Pattern Prevention

- 🚨 **TOTAL FAILURE PROTOCOL ENFORCEMENT**: Apply [Total Failure Protocol](total_failure.md) before declaring any results
- ❌ **NO Partial Success Declaration**: Cannot claim success based on partial validation
- ❌ **NO Assumption-Based Conclusions**: Every claim requires specific evidence
- ❌ **NO Skipping Failure Conditions**: Must test both positive and negative cases
- ✅ **ALWAYS Use TodoWrite**: Track validation state systematically
- ✅ **ALWAYS Collect Evidence**: Screenshots, logs, console output for each requirement

## 🚨 DIRECTORY TESTING PROTOCOL - MANDATORY FOR ALL DIRECTORY-BASED TESTS

### When User Requests "testing_llm/ test cases" or Similar Directory-Based Testing:

**Default Invocation Note**: Running `/testllm` with no additional arguments automatically triggers this full protocol for the `testing_llm/` directory.

**🚨 CRITICAL RULE: NEVER TEST JUST ONE FILE WHEN DIRECTORY REQUESTED**

### Anti-Pattern Prevention (MANDATORY ENFORCEMENT)

- ❌ **FORBIDDEN**: Reading only one test file when directory/multiple tests requested
- ❌ **FORBIDDEN**: Declaring success after partial file execution
- ❌ **FORBIDDEN**: Assuming "working authentication" means "testing complete"
- ✅ **REQUIRED**: Complete directory inventory before any test execution
- ✅ **REQUIRED**: TodoWrite checklist encompassing ALL files in scope
- ✅ **REQUIRED**: Evidence collection from ALL test cases across ALL files

### Directory Testing Success Criteria

**PASS requires:**
- ✅ ALL test files in requested directory executed
- ✅ ALL test cases within each file completed with evidence
- ✅ Combined test matrix shows comprehensive coverage
- ✅ Evidence portfolio contains screenshots/logs from every test scenario
- ✅ No skipped files or partial execution within scope

**FAIL indicators:**
- ❌ Only executed subset of available test files
- ❌ Declared success based on single file completion
- ❌ Missing evidence from test cases in unexecuted files
- ❌ Partial coverage of requested directory scope

## Implementation Protocol

## Critical Rules

### Authentication Requirements

- ❌ AVOID mock mode, test mode for production testing (dev tools allowed for debugging with caution)
- ❌ NEVER use test-user-basic or simulated users for real workflow validation
- ✅ ALWAYS use real Google OAuth authentication for production testing
- ✅ ALWAYS require actual login credentials for authentic user experience testing
- ⚠️ **Dev Tools Exception**: Browser dev tools may be used for debugging issues, but with clear documentation of when/why used

### Browser Automation

- ✅ USE Playwright MCP as primary browser automation
- ✅ ALWAYS use headless mode for automation
- ✅ CAPTURE screenshots to the `/tmp/<repo_name>/<branch_name>/` results directory with descriptive names
- ✅ MONITOR console errors and network requests

### API Integration

- ✅ MAKE real API calls to actual backend servers
- ✅ VERIFY network requests in browser developer tools
- ✅ VALIDATE response data and status codes
- ✅ TEST end-to-end data flow from frontend to backend

### Evidence Collection

- ✅ SAVE all screenshots and artifacts to `/tmp/<repo_name>/<branch_name>/` (never inline)
- ✅ REFERENCE screenshots by filename in results and include the absolute path within `/tmp/<repo_name>/<branch_name>/`
- ✅ DOCUMENT exact error messages and console output
- ✅ PROVIDE specific line numbers and code references
- ✅ ALWAYS inform the user of the `/tmp/<repo_name>/<branch_name>/` directory location and list every file created within it
- 🚨 **MANDATORY FILE VERIFICATION**: Before mentioning ANY evidence file in reports, VERIFY it exists using `ls -la`
- 🚨 **NO PHANTOM FILES**: NEVER claim evidence files exist without explicit verification command output
- 🚨 **VERIFY BEFORE REPORTING**: After test completion, run `ls -la /tmp/<repo_name>/<branch_name>/` and ONLY list files that actually appear in output

## Error Handling

- **Authentication Failures**: Stop immediately, require real login
- **Server Connectivity**: Verify backend services are running
- **Browser Automation**: Ensure Playwright MCP is available
- **API Errors**: Document exact error messages and status codes
- **Screenshot Failures**: Save to filesystem, never rely on inline images

## Success Metrics

- All test steps executed without mock mode
- Real API calls made and documented
- Screenshots saved under `/tmp/<repo_name>/<branch_name>/` with proper naming
- Console errors captured and analyzed
- Findings classified by priority (CRITICAL/HIGH/MEDIUM)
- Actionable recommendations provided
- Final report clearly states the `/tmp/<repo_name>/<branch_name>/` directory path and inventories all artifacts within it
- **🚨 NEW REQUIREMENT**: Anti-False-Positive Checklist included in final report
- **🚨 NEW REQUIREMENT**: 100% test execution (no partial success)
- **🚨 NEW REQUIREMENT**: Integration tests passed OR deployed environment validated

### 🚨 EXIT STATUS VALIDATION (MANDATORY)

- **CRITICAL**: Test execution MUST track and report actual exit status for EACH test file
- **Status Code 0**: Success - all tests passed, all evidence collected, 100% execution
- **Status Code 1**: Failure - tests failed OR incomplete evidence OR partial execution
- **Status Code 124**: Timeout - test exceeded 5-minute limit (treated as FAILURE)
- **FORBIDDEN**: Reporting "TOTAL SUCCESS" with exit code 1 or 124
- **FORBIDDEN**: Reporting "SUCCESS" with partial execution (executed < total)
- **FORBIDDEN**: Reporting "SUCCESS" without integration test validation
- **REQUIRED**: Final report MUST align with actual exit status
- **REQUIRED**: Track exit code for EACH individual test file
- **VALIDATION**: If ANY test fails, overall status MUST be FAILURE
- **EVIDENCE ALIGNMENT**: Success requires:
  - Exit code 0 for ALL tests
  - 100% execution (executed_count == total_count)
  - Complete verified evidence portfolio
  - Integration tests passed OR deployed environment validated
  - Anti-False-Positive Checklist all items checked

## Anti-Patterns to Avoid

- ❌ Generating Python or shell scripts unless explicitly requested
- ❌ Using mock mode or test mode for any reason
- ❌ Simulating authentication instead of using real OAuth
- ❌ Relying on inline screenshots instead of saved files
- ❌ Making assumptions about test results without evidence
- ❌ Skipping steps or taking shortcuts in test execution

### Single-Agent Mode (Traditional)

When `/testllm` is invoked WITHOUT `verified` keyword:

**Single Agent Process:**
1. **Systematic Requirements Analysis** - Read spec, create TodoWrite checklist
2. **Environment Validation** - Verify servers, authentication, tools
3. **Test Execution** - Execute requirements with evidence collection
4. **Results Compilation** - Generate final report with findings

### Dual-Agent Mode (Enhanced Verification)

When `/testllm verified` is invoked:

**Phase 1: TestExecutor Agent Execution**
```
Task(
  subagent_type="testexecutor",
  description="Execute test specification with evidence collection",
  prompt="Follow test specification methodically. Create evidence package with screenshots, logs, console output. NO success/failure judgments - only neutral documentation."
)
```

**Phase 2: Independent Validation**
```
Task(
  subagent_type="testvalidator",
  description="Independent validation of test results",
  prompt="Evaluate evidence package against original test specification. Fresh context assessment - no execution bias. Provide systematic requirement-by-requirement validation."
)
```

**Phase 3: Cross-Verification**
1. **Compare Results** - TestExecutor evidence vs TestValidator assessment
2. **Resolve Disagreements** - Validator decision takes precedence in conflicts
3. **Final Report** - Combined analysis with both perspectives
4. **Quality Assurance** - Dual-agent verification eliminates execution bias

### Evidence Package Handoff (Dual-Agent Only)

1. **TestExecutor Creates**: Structured JSON evidence package + artifact files
2. **File System Storage**: Evidence saved to `/tmp/<repo_name>/<branch_name>/test_evidence_TIMESTAMP/`
3. **Validator Receives**: Original test spec + evidence package only
4. **Independent Assessment**: Validator evaluates without execution context
5. **Cross-Validation**: Final report combines both agent perspectives

### Quality Assurance Benefits

- **Single-Agent**: Systematic validation protocol prevents shortcuts
- **Dual-Agent**: Independent verification eliminates execution bias
- **Evidence-Based**: Both modes require concrete proof for all claims
- **Comprehensive**: Both success AND failure scenarios validated
- **🚨 TOTAL FAILURE PROTOCOL**: Apply [Total Failure Protocol](total_failure.md) for all result declarations
