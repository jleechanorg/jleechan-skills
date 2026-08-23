---
description: /fixprc - Fix PR Comments (Autonomous PR Comment Resolution)
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

# /fixprc - Fix PR Comments (Autonomous PR Comment Resolution)

## 🎯 Purpose

**Autonomous PR comment fixing system combining genesis + copilot specialized for PR comment resolution**

Similar to `/copilotc` but specifically optimized for PR comment threads, code review feedback, and merge-blocking issues.

## 🚀 Command Architecture - PR-Focused Universal Composition

**Pattern**: Autonomous PR-specific comment resolution system powered by genesis

**Flow**:
```
1. `/gene "fix all PR comments and make PR mergeable" 7 --iterate`
2. Auto-execute `/copilot` with PR comment focus for each iteration
3. Continue until PR is clean and mergeable within the 7-iteration cap
4. Success when all PR comment threads resolved
```

## 🔄 Autonomous PR Processing Protocol

**FULLY AUTONOMOUS**: This command operates without user intervention until all PR comments are resolved.

### PR-Specialized Implementation

**Phase 1: PR Comment Analysis & Goal Setup**
```bash

# Execute genesis with PR-specific comment resolution goal (7 iteration cap by default)

# Uses --iterate flag to skip initial Cerebras generation for faster iteration

/gene "analyze and fix all PR comments, review feedback, and merge-blocking issues" 7 --iterate
```

**Phase 2: PR-Focused Copilot Processing**
- Within each genesis iteration, automatically execute `/copilot` with PR focus
- Prioritize merge-blocking comments and review feedback
- Address code quality issues identified in PR comments
- Handle CI failures and test issues mentioned in comments
- Validate PR mergeable status after each iteration

**Phase 3: PR Merge Readiness Validation**
- Check all PR comment threads for resolution status
- Verify no merge-blocking review feedback remains
- Confirm CI/checks passing (if mentioned in comments)
- Validate PR approval status and mergeable state
- Exit when PR is fully ready for merge

## 🎛️ PR-Specific Configuration

**Default Behavior**:
- **Max Iterations**: 7 (caps `/gene` cycles for focused PR remediation)
- **Success Criteria**: All PR comments resolved + Mergeable status achieved
- **Focus Areas**: Review feedback, merge conflicts, CI issues, code quality

**Custom Usage**:
```bash
/fixprc                     # Use default PR-optimized settings
/fixprc --max-iterations 5  # Custom iteration limit for simple PRs
```

## 🚨 PR-Focused Autonomous Rules

**PR-CENTRIC GENESIS**: Uses `/gene` with PR-specific success criteria
- **Merge-blocking priority**: Addresses comments preventing merge first
- **Review thread resolution**: Ensures all comment threads properly closed
- **CI integration**: Fixes issues mentioned in automated comments
- **Code quality focus**: Addresses review feedback on code improvements

**SPECIALIZED COPILOT INTEGRATION**: PR comment processing optimization
- **Comment thread tracking**: Systematic processing of all PR comment threads
- **Review feedback priority**: Addresses human reviewer feedback first
- **Automated comment handling**: Processes bot comments and CI feedback
- **Merge conflict resolution**: Handles merge-related comment issues

## 💡 PR-Specific Use Cases

**Perfect for**:
- PRs with extensive review feedback
- PRs blocked by multiple comment threads
- PRs with CI issues mentioned in comments
- Large PRs needing comprehensive comment resolution

**Example PR Scenarios**:
- "Code review requested 15 changes - fix them all"
- "PR has merge conflicts and failing tests"
- "Multiple reviewers left feedback - address everything"
- "CI bot identified security and quality issues"

## ⚡ PR Processing Performance

**Target Performance**:
- **Per Iteration**: 2-3 minutes (PR-focused copilot processing)
- **Total Time**: 8-25 minutes (depending on PR comment complexity)
- **Success Rate**: High (specialized for PR comment patterns)

**PR Success Pattern**: Most PRs become mergeable within 3-4 iterations

## 🔗 Related Commands

- `/copilotc` - General genesis-driven copilot (broader GitHub comment scope)
- `/copilot` - Single-pass fast PR processing
- `/gene` - Genesis execution system (autonomous goal achievement)
- `/pr` - Complete development lifecycle (includes PR creation + processing)

## 🎯 PR Success Criteria

**Command completes successfully when**:
1. ✅ All PR comment threads resolved or properly acknowledged
2. ✅ Review feedback fully addressed with code changes
3. ✅ PR shows mergeable status (no conflicts, passing checks)
4. ✅ All merge-blocking issues resolved
5. ✅ PR ready for approval and merge

**Iteration ends when**: Max iterations reached OR PR fully mergeable

## 🔄 Difference from /copilotc

**`/fixprc`** (PR Comment Focused):
- ✅ Specialized for PR comment threads and review feedback
- ✅ Tuned 7-iteration cap for PR comment patterns
- ✅ Merge-blocking issue prioritization
- ✅ Review thread resolution tracking

**`/copilotc`** (General GitHub Comments):
- ✅ Broader scope including issue comments, discussions
- ✅ General GitHub comment resolution (not just PRs)
- ✅ Shared genesis-driven iteration cap with flexibility for custom limits
- ✅ General mergeable status validation

## Implementation Notes

**PR-Specialized Composition**: This command uses universal composition optimized for PR comment resolution workflows, with specialized success criteria and validation methods focused on PR merge readiness.

**Context Efficiency**: Inherits genesis system optimizations while adding PR-specific processing patterns for maximum efficiency in comment resolution cycles.
