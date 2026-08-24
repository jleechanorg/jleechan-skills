---
description: Push Lite Command - Enhanced Reliability with LLM Intelligence
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

# Push Lite Command - Enhanced Reliability with LLM Intelligence

**Purpose**: Enhanced reliable push to GitHub with LLM-powered PR intelligence, selective staging, error handling, and debugging capabilities

**Action**: Push current branch to origin with comprehensive reliability improvements and optional smart PR creation

**Basic Usage**:
- `/pushlite` or `/pushl` - Push current branch to origin
- `/pushlite pr` or `/pushl pr` - Push and create PR with LLM-generated content
- `/pushlite force` or `/pushl force` - Force push to origin
- `/pushlite smart` or `/pushl smart` - Use LLM-first approach for intelligent PR creation

**Enhanced Options**:
- `/pushlite --verbose` - Enable detailed debugging output
- `/pushlite --dry-run` - Preview operations without executing
- `/pushlite --include "*.py"` - Include only files matching pattern
- `/pushlite --exclude "test_*"` - Exclude files matching pattern
- `/pushlite -m "message"` - Custom commit message
- `/pushlite --smart` - Enable LLM analysis for PR content generation
- `/pushlite --update-description` - Refresh existing PR description vs origin/main  
- `/pushlite --labels-only` - Update PR labels without changing description
- `/pushlite --detect-outdated` - Check if PR description matches current changes

**Examples**:
- `/pushl` - Pushes current branch to origin/branch-name
- `/pushl pr` - Pushes and creates PR to main
- `/pushl force` - Force pushes current branch (use with caution)

**Implementation**:
Execute: `./claude_command_scripts/commands/pushlite.sh [arguments]`

**Key Features**:
- **Smart Untracked File Handling**: Interactive options for untracked files
- **Lightweight Operation**: No test automation or server management
- **Safety Checks**: Confirms actions before execution
- **PR Integration**: Optional PR creation with auto-generated content
- **Post-Push Linting**: Non-blocking code quality checks after successful push
- **Commit Hash URL Output**: Automatically displays GitHub commit URL after successful push
- **Intelligent Change Detection**: Automatically detects and stages uncommitted changes
- **Post-Push Verification**: Checks for uncommitted changes after push completion
- **Conditional Lint Fixes**: Auto-applies lint fixes to Python files being committed

**Untracked Files Options**:
1. **Add all** - Stages all untracked files with smart commit messages
2. **Select files** - Choose specific files interactively
3. **Continue** - Push without adding untracked files
4. **Cancel** - Abort the push operation

**Smart Commit Messages**:
- Detects file types (tests, docs, scripts, CI tools)
- Suggests appropriate commit messages
- Allows custom messages

**Comparison with /push**:
- **`/push`**: Quality gate workflow (linting BEFORE push, blocks on failures, full automation)
- **`/pushl`**: Fast iteration workflow (push FIRST, linting after, non-blocking)

**Safety Features**:
- Force push confirmation required

## LLM-First Smart PR Creation

**Workflow**: When using `smart` mode or `--smart` flag:

1. **Analyze Current Changes**: Claude analyzes git diff vs origin/main to understand what changed
2. **Generate Smart Content**: Creates intelligent PR title, description, and labels based on:
   - Git history and commit messages
   - File types and patterns changed
   - Scope and impact of changes
   - Conventional commit standards
3. **Execute Streamlined Push**: Calls pushlite with pre-generated content

**Benefits of LLM-First Approach**:
- **Intelligence**: Claude analyzes context, git history, and patterns for better PR content
- **Adaptability**: Content generation adapts to different types of changes
- **Consistency**: Ensures consistent PR quality and formatting
- **Maintainability**: Keeps shell script focused on operations, not intelligence

**Smart Mode Examples**:
- `/pushl smart` - Push with LLM-generated PR content
- `/pushl pr --smart` - Create PR with intelligent analysis
- `/pushl --smart --verbose` - See LLM analysis process

**Architecture**:
```
User Request → Claude Analysis → Smart Content → Pushlite Script → GitHub PR
```

**Migration Note**: The smart functionality from `/pushlite_smart` has been integrated directly into `/pushlite` for a unified experience

## 🤖 Auto-Generated PR Features

**Smart Labels** (based on git diff vs origin/main):
- **Type**: bug, feature, improvement, infrastructure, documentation, testing
- **Size**: small (<100), medium (100-500), large (500-1000), epic (>1000 lines)
- **Scope**: frontend, backend, fullstack (based on file types)
- **Priority**: critical, high, normal, low (based on keywords and file patterns)

**Smart Descriptions**:
- Analyzes complete diff vs origin/main (not just recent commits)
- Lists all changed files with line count statistics
- Auto-detects outdated descriptions (>20% file deviation)
- Generates comprehensive change summaries

**Outdated Description Detection**:
- Compares PR body file list vs current `git diff --name-only origin/main...HEAD`
- Flags PRs where line counts don't match actual `git diff --stat`
- Warns when PR description describes old changes

## 🚨 MANDATORY: FILE JUSTIFICATION PROTOCOL ENFORCEMENT

**CRITICAL**: Before any push operation, ALL file changes must comply with FILE JUSTIFICATION PROTOCOL

**Required Checks**:
1. **Goal Justification**: Every modified file must have clear purpose documentation
2. **Integration Verification**: Proof that integration into existing files was attempted first
3. **Necessity Validation**: Evidence that each file change is essential vs alternatives
4. **Protocol Compliance**: All changes must follow NEW FILE CREATION PROTOCOL hierarchy

**File Categories**:
- ✅ **ESSENTIAL**: Core functionality, bug fixes, security, production requirements
- ⚠️ **ENHANCEMENT**: Clear business value with integration evidence
- ❌ **UNNECESSARY**: Documentation that could be integrated, temporary files, redundant implementations

**Enforcement**: This command will validate each file change against justification criteria before pushing

**Use Cases**:
- Quick documentation updates (with integration justification)
- Small fixes that don't need full test environment (with necessity proof)
- When you want manual control over automation (with protocol compliance)
- Fast iteration during development (with file justification documentation)
- Adding CI tools, browser dependencies, or supporting files (with integration evidence)
