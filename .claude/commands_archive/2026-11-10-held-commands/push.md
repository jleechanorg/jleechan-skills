---
description: Push Command
type: llm-orchestration
execution_mode: immediate
allowed-tools: Bash(git:*), Bash(gh:*)
# Note: /review and /testserver subcommands invoked in phases 2 and 5 below
# execute under their own command tool scopes — not restricted by this frontmatter.
---

## Live Context (injected at execution time)

- Current git status: !`git status`
- Changed files summary: !`git diff --stat HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# Push Command

**Purpose**: Full production-ready push workflow with comprehensive quality assurance and deployment automation

**Action**: Untracked files → `/review` → push if clean → update PR → `/testserver` → production readiness verification

**Usage**: `/push`

**Implementation**: This command uses Claude Code's command composition architecture where the `/push` markdown file defines the workflow that Claude executes directly through natural language understanding, eliminating the need for shell scripts.

## Command Composition

**`/push` = untracked file handling + `/review` + git operations + PR updates + `/testserver` + production verification**

The command orchestrates a complete production-ready push workflow:

### 1. File Justification & Untracked Files Analysis

**🚨 MANDATORY FILE JUSTIFICATION PROTOCOL CHECK**:
- **EVERY file change** must be justified before push proceeds
- **Required documentation**: Goal, Modification, Necessity, Integration Proof
- **Protocol compliance**: Verify NEW FILE CREATION PROTOCOL adherence
- **Categories validation**: Essential vs Enhancement vs Unnecessary classification

**Untracked Files Analysis**:
- Check for untracked files in working directory
- Intelligently analyze file context and relevance to current PR work
- **Apply FILE JUSTIFICATION PROTOCOL** to each file before inclusion
- Interactive selection for files to include (with justification required)
- Auto-suggest appropriate commit messages (with protocol compliance notes)

### 2. `/review` - Code Quality Gate

- Execute `/review` command for comprehensive code analysis
- Virtual [AI reviewer] performs systematic quality assessment
- Identifies bugs, security issues, performance problems, best practice violations
- Posts categorized review comments if issues found
- **Push blocked if critical issues detected**

### 3. Git Operations

- Validate commit messages and git state
- Push to remote only if `/review` passes quality checks
- Create PR if needed for new branches
- Verify push success and remote synchronization

### 4. PR Description Auto-Update

- Analyze commits since PR creation for significant changes
- Update PR description to reflect current implementation state
- Preserve existing test results and documentation

### 5. `/testserver` - Production Environment Setup

- Execute `/testserver start` for current branch
- Automatic port allocation and conflict resolution
- Branch-specific logging and process management
- Production-like environment initialization

### 6. Production Readiness Verification

- Health check endpoints validation
- Server startup verification and accessibility testing
- Log monitoring for critical errors
- Production deployment checklist completion

## Workflow Details

### Full Production Pipeline

```
1. Untracked file handling → Prepare complete changeset
2. /review execution → Quality assessment & issue detection
3. Quality gate check → Pass/fail determination
4. Git operations → Push only if quality checks pass
5. PR updates → Maintain project documentation
6. /testserver start → Production environment setup
7. Production verification → Readiness validation
```

### Review Integration

- **Quality Threshold**: Critical and important issues block push
- **Suggestion/Nitpick**: Warnings logged but don't block push
- **Review Comments**: Posted to PR for visibility and tracking
- **Status Reporting**: Clear indication of review results

## Untracked Files Handling

**Intelligent File Analysis**:
- Test files matching PR work (e.g., `test_*.py`, `test_*.js`)
- Documentation updates related to changes
- Supporting scripts or utilities
- Configuration or schema files

**Interactive Options**:
1. **Add all relevant** - Add files that appear related to PR work
2. **Select specific** - Choose individual files to include
3. **Skip** - Continue without adding untracked files
4. **Abort** - Cancel push to manually review files

**Auto-Suggested Commit Messages**:
- "Add JavaScript unit tests for [feature]"
- "Add browser tests for [functionality]"
- "Add supporting test utilities"
- "Update documentation for [changes]"

## PR Description Auto-Update

**Change Detection**:
- Architecture migrations (e.g., string → JSON)
- New test protocols or policies
- Breaking changes and compatibility impacts
- Major feature additions or modifications

**Update Behavior**:
- Preserves existing test results and links
- Adds new test outcomes and metrics
- Includes breaking change warnings if applicable
- Maintains PR history and context

## Test Server Integration via `/testserver`

**Production-Ready Server Management**:
- Executes `/testserver start` with current branch context
- Automatic port allocation (8081, 8082, 8083, etc.)
- Branch-specific process isolation and management
- Production-like configuration and environment setup

**Advanced Features**:
- PID tracking and process lifecycle management
- Conflict detection and automatic resolution
- Cleanup of stale processes from previous sessions
- Integration with development workflow state

**Server Accessibility**:
- Server accessible at `http://localhost:[allocated_port]`
- Logs stored in `/tmp/$PROJECT_NAME_logs/[branch].log`
- Real-time monitoring and health checking
- Automatic restart on critical failures

## Production Readiness Verification

**Health Check Protocol**:
- Server startup verification (response within 30 seconds)
- Basic endpoint accessibility testing
- Critical error detection in startup logs
- Database connection and API availability validation

**Production Checklist**:
- ✅ Code quality review passed
- ✅ Git operations completed successfully
- ✅ PR documentation updated
- ✅ Test server started and responsive
- ✅ No critical errors in logs
- ✅ Basic functionality verification

**Deployment Readiness Report**:
- Branch deployment status summary
- Server accessibility details (URL, port, logs)
- Quality assessment results
- Any warnings or issues requiring attention

## Quality Gate Behavior

### Review Results → Push Decision

- **🔴 Critical Issues**: Push blocked, must fix before proceeding
- **🟡 Important Issues**: Push blocked, requires attention
- **🔵 Suggestions**: Push allowed with warnings logged
- **🟢 Nitpicks**: Push allowed, comments posted for improvement
- **✅ Clean Review**: Push proceeds to production setup

### Production Gate Behavior

- **🔴 Server Failed**: Deployment blocked, investigate logs
- **🟡 Warnings Detected**: Deployment proceeds with monitoring
- **✅ All Systems Green**: Production-ready deployment complete

### Error Handling

- Clear reporting of blocking issues with specific locations
- Actionable feedback for resolving quality and deployment problems
- Option to override for emergency pushes (with confirmation)
- Comprehensive logging of review results and deployment status

## Benefits of Full Production Mode

- **End-to-End Quality**: From code review to running production environment
- **Deployment Confidence**: Every push includes production readiness verification
- **Automated Setup**: No manual server management or configuration
- **Comprehensive Monitoring**: Full visibility into code quality and deployment status
- **Production Parity**: Development environment matches production characteristics
- **Fail-Fast Principle**: Issues detected before they reach production
- **Streamlined Workflow**: Single command for complete development-to-deployment pipeline

## Command Dependencies

- **`/review`**: Code quality analysis and review comment generation
- **`/testserver`**: Production environment setup and server management
- **Git operations**: Version control and remote synchronization
- **PR management**: GitHub integration and documentation updates
