---
description: /copilotc - Convergent Copilot (Autonomous GitHub Comment Resolution)
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

# /copilotc - Convergent Copilot (Autonomous GitHub Comment Resolution)

## 🎯 Purpose

**Universal composition command combining genesis + copilot for autonomous GitHub comment resolution**

Runs `/gene` (genesis execution) and `/copilot` in an autonomous loop until all serious GitHub comments are resolved.

## 🚀 Command Architecture - Universal Composition

**Pattern**: Autonomous genesis-driven PR comment resolution system

**Flow**:
```
1. `/gene "resolve all serious GitHub comments" 7 --iterate`
2. Auto-execute `/copilot` for each iteration
3. Continue until genesis criteria met (all serious comments resolved)
4. Success when GitHub shows clean PR status
```

## 🔄 Autonomous Operation Protocol

**FULLY AUTONOMOUS**: This command operates without user intervention until completion or iteration limit reached.

### Universal Composition Implementation

**Phase 1: Goal Definition & Genesis Setup**
```bash

# Execute genesis with GitHub comment resolution goal (7 iteration cap by default)

# Uses --iterate flag to skip initial Cerebras generation for faster iteration

/gene "resolve all serious GitHub comments and make PR mergeable" 7 --iterate
```

**Phase 2: Integrated Copilot Processing**
- Within each genesis iteration, automatically execute `/copilot`
- Use copilot's direct orchestration for rapid comment processing
- Validate resolution success after each copilot run
- Continue genesis-driven loops until all serious comments addressed

**Phase 3: Success Validation**
- Check GitHub PR status for remaining serious issues
- Verify comment thread resolution
- Confirm mergeable status
- Exit when genesis success criteria fully met

## 🎛️ Configuration Options

**Default Behavior**:
- **Max Iterations**: 7 (caps `/gene` cycles for focused execution)
- **Success Criteria**: All serious GitHub comments resolved + PR mergeable
- **Validation Method**: GitHub API status checks + comment analysis

**Custom Usage**:
```bash
/copilotc                    # Use default settings (7 iterations max)
/copilotc --max-iterations 5 # Custom iteration limit
```

## 🚨 Autonomous Operation Rules

**GENESIS-DRIVEN**: Uses `/gene` autonomous goal achievement system
- **No user prompts**: Continues until success or iteration limit
- **Smart iteration**: Each cycle improves PR state toward mergeable status
- **Evidence-based success**: GitHub API confirmation of comment resolution
- **Auto-learning**: Genesis system learns from each iteration

**COPILOT INTEGRATION**: Leverages `/copilot` fast processing within each iteration
- **Direct GitHub MCP**: Fast comment processing and resolution
- **Performance optimized**: 2-3 minute copilot cycles vs 20+ minute alternatives
- **Comprehensive coverage**: Processes all comment types systematically

## 🚨 PR BRANCH CONSTRAINTS - MANDATORY

**CRITICAL: STAY ON EXISTING PR BRANCH**
- ❌ **NEVER create new PRs** when working on existing PR comment resolution
- ❌ **NEVER switch branches** unless explicitly required for PR context
- ✅ **ALWAYS work on current PR branch** throughout entire copilotc execution
- ✅ **ALWAYS update existing PR** with comment resolution changes

**BRANCH DISCIPLINE PROTOCOL:**
- **Before execution**: Verify current branch matches target PR
- **During execution**: All commits stay on same branch
- **After execution**: Push updates to same PR, never create new PR

**GUARDRAILS & ENFORCEMENT (REQUIRED):**
- **Preflight:**
  - Resolve PR number and target branch via GitHub API
  - Verify `git rev-parse --abbrev-ref HEAD` == PR branch; abort if mismatch
  - Refuse to run if there is any uncommitted worktree state that could trigger unintended branch ops
- **Runtime:**
  - Disallow any command that opens a new PR (e.g., `/pushl --create-pr`); abort with error
  - Block `git checkout -b`, `git switch -c`, or branch-renaming commands
  - Ensure all pushes target the PR branch and the same PR number
- **Failure handling:**
  - If any guard triggers, stop immediately, post a PR comment with the violation details, and exit `FAILURE`

**EXIT CRITERIA ENFORCEMENT:**
- Success = Comments resolved ON CURRENT PR
- Failure = Creating duplicate/new PRs instead of fixing existing one
- Context awareness = Understand you're fixing existing PR, not creating new work

## 💡 Use Cases

**Perfect for**:
- PRs with multiple unresolved review comments
- Automated PR preparation for merge
- Continuous integration comment resolution
- Large PR cleanup and finalization

**Example Scenarios**:
- "Fix all the review comments on PR #123"
- "Clean up PR before merge approval"
- "Resolve CI failures and review feedback"
- "Make PR mergeable state"

## ⚡ Performance Expectations

**Target Performance**:
- **Per Iteration**: 2-3 minutes (copilot processing)
- **Total Time**: 10-25 minutes (depending on comment complexity)
- **Success Rate**: High (genesis + copilot proven systems)

**Success Pattern**: Most PRs achieve clean status within 3-5 iterations

## 🔗 Related Commands

- `/gene` - Genesis execution system (autonomous goal achievement)
- `/copilot` - Fast direct PR processing (2-3 minute cycles)
- `/fixprc` - Similar autonomous PR comment fixing (specialized variant)
- `/pr` - Complete development lifecycle (includes copilot phase)

## 🎯 Success Criteria

**Command completes successfully when**:
1. ✅ All serious GitHub comments resolved or addressed
2. ✅ PR shows mergeable status (no blocking issues)
3. ✅ Comment threads properly closed or acknowledged
4. ✅ CI/GitHub checks passing (where applicable)

**Iteration ends when**: Max iterations reached OR success criteria fully met

## Implementation Notes

**Universal Composition**: This command uses the universal composition system to intelligently orchestrate `/gene` and `/copilot` together, creating an autonomous loop optimized for GitHub comment resolution.

**Context Efficiency**: Genesis system includes context optimization and direct goal processing for efficient operation across multiple iterations.
