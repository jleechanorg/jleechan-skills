---
description: /replicate
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### 1. PR Analysis Phase

**Action Steps:**
1. Parses the PR URL/number to identify the repository and PR
2. **🚨 MANDATORY PAGINATION PROTOCOL**: Checks total file count first using GitHub MCP tools
3. Uses GitHub MCP tools to fetch complete file changes with pagination verification
4. **Verification**: Ensures ALL files are analyzed, not just first 30 from API default
5. Reads every single delta line (additions and deletions)
6. Focuses on relevant directories (configurable)

### 2. Comparison Phase

**Action Steps:**
1. Compares PR changes with current branch implementation
2. Identifies missing functionality, methods, or improvements
3. Categorizes changes by importance and relevance
4. Detects potential conflicts or overlaps

### 3. Smart Merge Phase

**Action Steps:**
1. Applies missing changes that enhance functionality
2. Skips irrelevant changes (unrelated cleanup, different approaches)
3. Maintains current enhancements and improvements
4. Preserves existing functionality while adding new features
5. Handles conflicts intelligently

### 4. Validation Phase

**Action Steps:**
1. Verifies changes don't break existing functionality
2. Runs available tests to ensure stability
3. Generates detailed summary of what was replicated
4. Creates descriptive commit with comprehensive change log

## 📋 REFERENCE DOCUMENTATION

# /replicate

Analyze a GitHub PR and intelligently apply its missing functionality to the current branch.

## Usage

```
/replicate <PR_URL or PR_NUMBER>
```

## Examples

- `/replicate https://github.com/jleechanorg/your-project.com/pull/693`
- `/replicate PR#693`
- `/replicate 693`

## Description

The `/replicate` command automates the process of analyzing a pull request and replicating its functionality to your current branch. This is particularly useful when:
- You need to incorporate features from another PR
- You want to ensure feature parity with a reference implementation
- You're consolidating work from multiple branches

## How It Works

## Features

- **Intelligent Analysis**: Uses `/e` for thorough PR examination
- **Selective Application**: Only applies relevant improvements
- **Conflict Resolution**: Smart handling of overlapping changes
- **Comprehensive Reporting**: Detailed logs of what was replicated and why
- **Safety First**: Preserves existing functionality and enhancements

## Options

- **Focus Directories**: Specify which directories to analyze (e.g., `.claude/commands/`)
- **Exclude Patterns**: Skip certain file patterns or changes
- **Dry Run Mode**: Preview changes without applying them
- **Force Mode**: Apply changes even with conflicts (requires manual resolution)

## Implementation Details

The command leverages:
- **GitHub MCP integration for PR data fetching with mandatory pagination protocols**
- **🚨 CRITICAL**: Always verifies total file count before analysis to prevent missing files
- **Pagination handling**: Automatically detects large PRs and uses appropriate API pagination
- Advanced diff analysis algorithms
- Subagent orchestration for complex comparisons
- AST-based code understanding where applicable
- Smart merge strategies to avoid conflicts

## Success Stories

Originally developed after manually analyzing PR #693, this command automates what was a complex manual process. It has proven effective for:
- Feature consolidation across branches
- Ensuring implementation completeness
- Rapid feature adoption from other developers
- Maintaining consistency across similar implementations

## Error Handling

- **Invalid PR**: Clear error if PR doesn't exist or is inaccessible
- **Merge Conflicts**: Detailed conflict reports with resolution suggestions
- **Test Failures**: Automatic rollback option if tests fail post-merge
- **Network Issues**: Graceful handling of API failures with retry logic

## Best Practices

1. Always run on a clean working tree
2. Review the replication summary before committing
3. Run tests after replication to ensure stability
4. Use focus directories for large PRs to avoid noise
5. Consider dry run mode for complex PRs first

## Related Commands

- `/pr` - Create or manage pull requests
- `/review` - Review code changes
- `/integrate` - Integrate changes from main branch
