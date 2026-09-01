---
description: Fake3 Command - Branch-Focused Iterative Fake Code Detection and Fixing
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### 🎯 WORKFLOW PHASES

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: Setup and Initialization

**Action Steps:**
1. Create or update iteration tracking scratchpad
2. Initialize Memory MCP context for fake patterns
3. **Get all branch changes**: `git diff --name-only origin/main...HEAD` and `git ls-files --others --exclude-standard` (for untracked files)
4. Check current branch status and PR context
5. Prepare fix tracking data structure for all branch-modified files

### Phase 2: Iterative Detection and Fixing (3 iterations max)

**Action Steps:**
For each iteration:
1. **Run Fake Detection** (`/fake` on all branch files)
   - Execute fake code audit on all branch-modified files (tracked + untracked)
   - Parse results to identify issues across entire branch changes
   - Categorize by severity (🔴 Critical, 🟡 Suspicious, ✅ Verified)
   - Include dynamically created files from command execution

2. **Apply Fixes**
   - Remove fake files marked for deletion
   - Replace placeholder comments with real implementations
   - Consolidate duplicate implementations
   - Fix mock/demo functions to real functionality
   - Verify integration points connect properly

3. **Test Fixes**
   - Run appropriate test suite for changed files
   - Verify no new failures introduced
   - Check integration still works
   - Document test results

4. **Update Progress**
   - Write iteration summary to scratchpad
   - Track: files fixed, issues resolved, tests passed
   - Note any remaining issues for next iteration
   - Calculate improvement metrics

5. **Check Completion**
   - If no fake code found, mark as complete
   - If 3 iterations done, summarize remaining work
   - Otherwise, continue to next iteration

### Phase 3: Learning and Finalization

**Action Steps:**
1. If any fake code was found across iterations:
    - Call `/learn` with summary of patterns found
    - Store new fake patterns in Memory MCP
    - Update detection strategies
2. Generate final report with all changes
3. Create comprehensive PR description

## 📋 REFERENCE DOCUMENTATION

# Fake3 Command - Branch-Focused Iterative Fake Code Detection and Fixing

**Purpose**: Automate 3 iterations of fake code detection and fixing for all files modified in the current branch with comprehensive tracking, testing, and learning capture

**Usage**: `/fake3` - Runs 3 iterations of fake detection, fixing, testing, and progress tracking **on all branch-modified files**

**Scope**: This command analyzes all files modified in the current branch (including dynamically created files), not just original PR changes

**Type**: Pure LLM-orchestrated command (leverages a Large Language Model to coordinate tasks without external dependencies, no Python dependencies)

## 🚨 COMMAND OVERVIEW

The `/fake3` command orchestrates a complete fake code remediation workflow:
1. **Detect**: Run `/fake` audit to identify fake/demo/placeholder code
2. **Fix**: Automatically fix identified issues
3. **Test**: Verify fixes work correctly
4. **Track**: Update scratchpad with progress
5. **Iterate**: Repeat 3 times or until clean
6. **Learn**: Call `/learn` if any fake code was found

## 📋 TRACKING FORMAT

### Scratchpad Structure

```markdown

# /fake3 Iteration Tracking - [branch_name]

## Overall Progress

- Start Time: [timestamp]
- Total Issues Found: [count]
- Total Issues Fixed: [count]
- Test Status: [PASS/FAIL]

## Iteration 1

**Detection Results:**
- Critical Issues: [count]
- Suspicious Patterns: [count]
- Files Analyzed: [count]

**Fixes Applied:**
- [file:line] - [fix description]
- [file:line] - [fix description]

**Test Results:**
- Tests Run: [count]
- Tests Passed: [count]
- New Failures: [list]

**Remaining Issues:**
- [description of unfixed issues]

## Iteration 2

[Similar structure]

## Iteration 3

[Similar structure]

## Final Summary

- Total Iterations: [1-3]
- Issues Fixed: [percentage]
- Code Quality Improvement: [metrics]
- Learnings Captured: [yes/no]
```

## 🛠️ IMPLEMENTATION DETAILS

### LLM Command Composition

The command works by intelligently composing existing commands and tools:
- Uses `/fake` for comprehensive fake code detection
- Uses file editing tools (Edit, MultiEdit) for applying fixes
- Uses `/test` commands for validation after changes
- Uses TodoWrite for tracking progress and tasks
- Uses `/learn` for capturing and persisting patterns
- Orchestrates the workflow through LLM understanding and decision-making

### LLM Orchestration Process

The LLM performs the following steps for each iteration:
1. **Parse and Analyze**: Reads `/fake` output and categorizes issues using natural language understanding
2. **Plan Fixes**: Determines appropriate fix strategy for each issue based on context
3. **Execute Fixes**: Uses appropriate file editing tools to implement changes
4. **Validate**: Runs tests and analyzes results to ensure fixes don't break functionality
5. **Track Progress**: Updates scratchpad and TodoWrite with current status
6. **Learn**: Extracts patterns and insights for future detection improvements

### Fix Strategies

1. **Placeholder Comments**
   - Search for implementation in similar files
   - Generate minimal working implementation
   - Add proper error handling

2. **Mock Functions**
   - Connect to real services/APIs
   - Replace hardcoded data with dynamic values
   - Add configuration for endpoints

3. **Duplicate Implementations**
   - Identify canonical implementation
   - Update imports to use shared version
   - Remove redundant code

4. **Demo Files**
   - Assess if functionality needed
   - Either implement properly or remove
   - Update any references

### Safety Measures

- LLM creates backup branch before starting using git commands
- LLM commits after each successful iteration to preserve progress
- LLM evaluates test failures and stops if issues are catastrophic
- LLM preserves manual fixes between iterations by reading git history
- LLM maintains detailed change log in scratchpad for potential rollback

## 🔍 EXAMPLE EXECUTION

```console
/fake3

🚀 Starting /fake3 - Automated Fake Code Detection and Fixing
📍 Branch: feature-new-ui
🔄 Running iteration 1 of 3...

[Iteration 1]
Running /fake audit...
⚠️ Found 12 fake patterns across 8 files
Applying automated fixes...
  ✓ Fixed placeholder comment in ui_handler.py:45
  ✓ Connected mock API in data_service.py:78
  ✓ Removed duplicate logger in utils.py:23
Running tests...
  ✓ All tests passing (142/142)
Updated scratchpad with iteration 1 results

[Iteration 2]
Running /fake audit...
⚠️ Found 3 remaining patterns in 2 files
Applying automated fixes...
  ✓ Implemented error handling in api_client.py:102
  ✓ Fixed hardcoded demo data in config.py:45
Running tests...
  ✓ All tests passing (142/142)
Updated scratchpad with iteration 2 results

[Iteration 3]
Running /fake audit...
✅ No fake patterns detected!
🎉 Code is clean after 2 iterations

Calling /learn to capture patterns...
✅ Learned: Common placeholder patterns in API integrations
✅ Learned: Demo data often in config files
✅ Stored 5 new patterns in Memory MCP

📊 Final Summary:
- Total Issues Fixed: 15/15 (100%)
- Iterations Required: 2
- Tests Status: All Passing
- Learnings Captured: Yes

Ready to create PR with all changes!
```

## 🎯 SUCCESS CRITERIA

**Command succeeds when:**
- All detected fake code is fixed OR 3 iterations complete
- All tests pass after fixes
- Progress properly tracked in scratchpad
- Learnings captured via `/learn` (if applicable)
- Clean audit achieved OR remaining issues documented

**Command stops early if:**
- Clean audit achieved (no fake code found)
- Critical test failures that can't be auto-fixed
- File system errors or permission issues
- User interruption

## 📚 INTEGRATION WITH OTHER COMMANDS

- **Uses**: `/fake` for detection, `/learn` for knowledge capture
- **Compatible with**: `/test`, `/orchestrate`, `/pr`
- **Enhances**: `/copilot`, `/review`, `/integration`

## 🔧 CONFIGURATION

### Default Behavior

- Max iterations: 3 (built into the command specification)
- Fix confidence: LLM judges based on context and patterns
- Test runner: LLM auto-detects from project structure (e.g., `package.json` for JavaScript, `pytest.ini` for Python, `pom.xml` for Java)
- Scratchpad location: `roadmap/scratchpad_fake3_${current_branch}.md` (dynamically uses current git branch)

### LLM Decision Points

The LLM makes intelligent decisions about:
- When to stop iterations early (if clean)
- Which fix strategy to apply for each issue
- Whether a test failure is critical enough to halt
- What patterns to capture for learning

## 🚨 IMPORTANT NOTES

1. **Always commit** before running to preserve original state
2. **Review changes** after completion before creating PR
3. **Check test results** carefully for subtle regressions
4. **Memory MCP integration** enhances detection over time
5. **LLM creates backup branch** automatically for safety
6. **No Python files required** - this is a pure LLM command using composition

This command embodies the principle: "Automate repetitive quality improvements while learning from each execution through intelligent LLM orchestration."
