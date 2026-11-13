---
description: /ghfixtests
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

# /ghfixtests

Find recent PRs with failing tests and offer to fix them via Claude Code Action comments.

## Description

This command:
1. Scans the last 10-20 open PRs for failing unit tests
2. Shows a summary of which PRs have test failures
3. Asks if you want to post `@claude-code-action` comments to fix them
4. Posts the comments with context about what's failing

## Usage

```
/ghfixtests
```

## Behavior

1. **Scan PRs**: Check CI status of recent open PRs
2. **Filter failures**: Only show PRs where unit tests are failing
3. **Display summary**: Show PR number, title, and what's failing
4. **Interactive prompt**: Ask which PRs to fix (all, specific numbers, or none)
5. **Post comments**: Create targeted `@claude-code-action fix unit tests` comments with failure context

## Example Output

```
Found 3 PRs with failing tests:

1. PR #424: Fix JSON display bug
   ❌ 11 tests failing in TestGeminiResponse

2. PR #420: Debug: Raw JSON appearing in campaign logs
   ❌ Test suite failing (details not visible)

3. PR #415: Add new feature
   ❌ 2 tests failing in test_auth.py

Would you like to:
[a] Fix all failing PRs
[1,2,3] Fix specific PRs (comma-separated)
[n] Cancel

Your choice:
```

## Implementation Notes

- Uses `gh pr checks` to find failing tests
- Extracts error details where available
- Creates contextual fix messages for Claude
- Confirms before posting comments
