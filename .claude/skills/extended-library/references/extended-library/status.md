---
allowed-tools: Bash, Read, Edit
description: Show comprehensive PR status including recent files, CI, merge conflicts, and GitHub state
---

# /status - Comprehensive PR Status Dashboard

Shows a complete overview of the PR associated with the current branch including:
- 15 most recent changed files
- CI status with test results and URLs  
- Merge conflicts and GitHub merge state
- Review status and bot feedback
- Branch header information

## Current Context
- Working directory: !`pwd`
- Branch and PR status: !`"$(git rev-parse --show-toplevel)/.claude/hooks/git-header.sh" --status-only 2>/dev/null || true`

## Status Execution
!`python3 "$(git rev-parse --show-toplevel)/.claude/commands/status.py" "$ARGUMENTS" 2>/dev/null || true`

## Information Displayed

### 📁 Recent File Changes (15 most recent)
- File paths with modification timestamps
- Lines added/removed for each file
- File types and change patterns

### 🔄 CI & Testing Status
- GitHub Actions workflow status
- Individual check results with URLs
- Test failure details and logs
- Required vs optional checks

### 🔀 Merge State
- GitHub mergeable status
- Merge conflicts with file details
- Branch protection requirements
- Merge readiness indicators

### 👥 Review & Comments
- Review approvals and changes requested
- Bot feedback (CodeRabbit, Copilot, etc.)
- Open discussions and threads
- Blocking vs non-blocking feedback

### 🎯 Action Items
- What needs to be fixed for mergeability
- Prioritized list of blockers
- Quick fix suggestions
- Integration with /fixpr command

## GitHub API Integration

The command uses multiple GitHub API endpoints for authoritative data:
- Pull request files and changes
- Status checks and workflow runs
- Reviews and comments
- Merge state and conflicts
- Branch protection rules

## Usage Examples

```bash
# Show status for current PR
/status

# Refresh and show updated status
/status --refresh

# Show extended details
/status --verbose
```

## Integration Points

Works naturally with:
- `/header` - Branch and PR identification
- `/fixpr` - Automated fix application  
- `/copilot` - PR workflow orchestration
- Testing commands - Verify status accuracy
