---
description: Review Status Command - Check PR CI and Review Comments
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

# Review Status Command - Check PR CI and Review Comments

**Purpose**: Check outstanding PRs for CI issues and important review comments

**Usage**: `/reviewstatus` - Review recent PRs for CI failures and critical feedback

## Command Behavior

The `/reviewstatus` command provides a comprehensive overview of:
1. **Recent PRs** (last 2 days) with their CI/build status
2. **Important review comments** from CodeRabbit, Copilot, and human reviewers
3. **Critical issues** that need immediate attention
4. **Older open PRs** that may need follow-up

## Output Format

```

## Summary of Outstanding PRs

### Recent PRs (Last 2 Days)

- PR #XXX: [Title] - CI: ✅/❌ - [Key issues]
- PR #XXX: [Title] - CI: ✅/❌ - [Key issues]

### Key Issues to Address

- **PR #XXX**: [Critical issue description]
- **PR #XXX**: [Important feedback]

### Older Open PRs

- PR #XXX: [Title] - [Age]
```

## Implementation Details

The command uses GitHub MCP tools to:
1. List recent pull requests (sorted by creation date)
2. Check CI status for each PR
3. Retrieve review comments and feedback
4. Identify critical issues (failing CI, blocking reviews, security concerns)
5. Summarize findings in a clear, actionable format

## Example Output

```

## Summary of Outstanding PRs

### Recent PRs (Last 2 Days) - All CI Passing ✅

1. **PR #775**: File deletion impact protocols - Minor doc improvements needed
2. **PR #773**: /arch command update - Minor grammar fixes
3. **PR #771**: Python type annotations - Import issue already fixed
4. **PR #769**: Memory MCP integration - Code quality improvements needed
5. **PR #768**: Slash command architecture - Scratchpad format already fixed

### Key Issues to Address

**PR #769** (Memory MCP) has the most review feedback needing attention:
- Code formatting issues
- Missing docstrings
- Type annotation modernization
- General code quality improvements

All recent PRs have passing CI, with most critical issues already addressed in follow-up commits.
```

## Benefits

- **Quick Overview**: See all PR status at a glance
- **CI Health**: Identify any failing builds immediately
- **Review Focus**: Know which PRs need attention
- **Prioritization**: Focus on critical issues first
- **Progress Tracking**: See what's been addressed vs outstanding

## Related Commands

- `/pr` - Create a new pull request
- `/copilot` - Run GitHub Copilot review on current branch
- `/review` - Detailed review of a specific PR
