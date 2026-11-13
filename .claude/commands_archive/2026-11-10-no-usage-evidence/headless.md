---
description: /headless - Enhanced Planning + Headless Development
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Report Retirement

**Action Steps:**
1. Report that `/headless` is retired. Do not execute the historical implementation below; use the current approved task-scoped workflow documented in the repository instead.

## 📋 REFERENCE DOCUMENTATION

# /headless - Enhanced Planning + Headless Development

> Retired: this package does not export headless automation. The historical
> implementation below must not be executed.

**Purpose**: Combine `/handoff` planning with `/headless` automation - creates detailed analysis then generates copy-paste command for headless execution

**Usage**: `/headless [prompt]`

**Enhanced Workflow**:
1. **Phase 1 - Planning** (from `/handoff`):
   - Creates isolated git worktree with new branch
   - Generates detailed planning scratchpad with implementation plan
   - Analyzes requirements and creates step-by-step approach
   - Commits planning documentation and pushes branch

2. **Phase 2 - Command Generation**:
   - Builds comprehensive prompt with full context
   - Generates copy-pasteable headless command
   - User reviews plan and executes when ready

**Implementation**:
```bash
#!/bin/bash

# Get the prompt from arguments

PROMPT="$*"

if [ -z "$PROMPT" ]; then
    echo "❌ Error: No prompt provided"
    echo "Usage: /headless [prompt]"
    exit 1
fi

# Choose a task-specific branch name. Create worktrees only through the
# approved worktree workflow; never create a relative checkout under the repo.

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BRANCH_NAME="headless_${TIMESTAMP}"
echo "🚀 Creating headless development environment..."
echo "Branch: $BRANCH_NAME"
echo "Prompt: $PROMPT"

# Create the task worktree with `diskm worktree-new <repo-path> <branch>`.
# Use its reported path for WORKTREE_DIR and verify it is an approved root.
# Do not use a relative path, mktemp, or raw `git worktree add`.
WORKTREE_DIR="<approved path reported by diskm>"

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to create git worktree"
    exit 1
fi

# Change to worktree directory

cd "$WORKTREE_DIR"

echo "📁 Working in: $(pwd)"
echo "🎯 Running Claude Code headlessly..."

# Run Claude Code in headless mode with stream monitoring

claude -p "$PROMPT" --output-format stream-json --verbose --dangerously-skip-permissions

if [ $? -ne 0 ]; then
    echo "❌ Error: Claude Code execution failed"
    cd ..
    git worktree remove "$WORKTREE_DIR"
    exit 1
fi

echo "✅ Claude Code execution completed"
echo "🔄 Creating pull request..."

# Historical implementation omitted: the package no longer exports a PR or
# headless launcher.

echo "🎉 Headless development completed!"
echo "📂 Worktree location: $WORKTREE_DIR"
echo "🌿 Branch: $BRANCH_NAME"

# Return to original directory

cd ..
```

**Enhanced Features**:
- ✅ **Detailed Planning**: Creates comprehensive implementation plan (from `/handoff`)
- ✅ **Isolated Environment**: Separate git worktree prevents conflicts
- ✅ **User Control**: Review generated plan before execution
- ✅ **Rich Context**: Full prompt with specifications and requirements
- ✅ **Copy-Paste Ready**: Generated command with all context included
- ✅ **Documentation**: Planning scratchpad with step-by-step approach

**Safety Features**:
- Uses `--dangerously-skip-permissions` for true headless operation
- Creates isolated worktree to prevent conflicts with current work
- Automatic cleanup on failure
- Preserves original working directory

**Example Usage**:
```bash
/headless "Add user authentication system with login/logout functionality"
/headless "Fix the responsive design issues on mobile devices"
/headless "Implement automated testing for the payment processing module"
```

**Example Output**:
```
🚀 Enhanced Headless Development with Planning
Task: Add user authentication system
Branch: headless_20250718_143022
Worktree: headless_20250718_143022

📋 Phase 1: Creating Analysis and Planning
📁 Creating isolated worktree...
📁 Working in: /path/to/headless_20250718_143022
📋 Creating detailed planning scratchpad...

================================================================================
✅ PLANNING PHASE COMPLETE
================================================================================
📋 Planning file: roadmap/scratchpad_headless_20250718_143022.md
🌿 Branch: headless_20250718_143022 (pushed to remote)
📁 Worktree: /path/to/headless_20250718_143022

================================================================================
🤖 HEADLESS COMMAND READY (Copy & Paste)
================================================================================

claude -p "TASK: Add user authentication system

CONTEXT: Complete analysis and implementation plan available
WORKTREE: /path/to/headless_20250718_143022
BRANCH: headless_20250718_143022

SETUP: Already in isolated worktree with clean branch
GOAL: Add user authentication system
IMPLEMENTATION: See detailed plan below

FILES TO MODIFY: See specific file list in implementation section
SUCCESS CRITERIA: All requirements met with tests passing
TIMELINE: Implement according to step-by-step plan

FULL SPECIFICATION: /path/to/headless_20250718_143022/roadmap/scratchpad_headless_20250718_143022.md

START: Implement the detailed plan below" --output-format stream-json --verbose --dangerously-skip-permissions

================================================================================
📋 Next Steps:
1. Review the generated plan in: roadmap/scratchpad_headless_20250718_143022.md
2. Modify the plan if needed (add details, adjust approach)
3. Copy and paste the command above when ready to execute
4. The command will run Claude in headless mode in this worktree

✅ Ready for headless execution!
```

**Integration with Orchestration System**:
- Follows the proven agent architecture patterns from CLAUDE.md
- Uses the same headless flags that prevent interactive prompts
- Implements git worktree isolation for conflict prevention
- Provides stream-json monitoring for cost and progress tracking
