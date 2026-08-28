---
description: Best practices and automation helpers for creating and maintaining high-quality pull requests
type: usage
scope: project
---

# PR Workflow Manager

## Purpose
Provide Claude with best practices for creating and managing pull requests with proper upstream tracking, ensuring consistent PR workflows and preventing common git configuration issues.

## Activation cues
- Requests to create a PR, pull request, or merge request
- Questions about git upstream tracking or remote branch configuration
- Follow-up after pushing branches or creating PRs
- Troubleshooting PR-related git issues
- Team workflow standardization requests

## Primary commands
| Scenario | Command |
| --- | --- |
| Create PR with upstream | `gh pr create && git branch --set-upstream-to=origin/$(git branch --show-current)` |
| Set upstream for existing PR | `git branch --set-upstream-to=origin/$(git branch --show-current)` |
| Check upstream status | `git branch -vv` |
| Create PR from issue | `gh issue develop <number> --checkout && git push -u origin HEAD` |
| View PR status | `gh pr view` |
| List all PRs | `gh pr list` |

## Automation helper
Use the bundled script for complete PR creation with all best practices:
```bash
skills/pr_workflow_manager/scripts/create_pr_with_upstream.sh [--title "PR Title"] [--body "PR Description"]
```
The script:
1. Validates current branch is not main/master
2. Pushes branch with upstream tracking (`-u` flag)
3. Creates PR using `gh pr create`
4. Verifies upstream tracking is set
5. Displays PR URL and branch status

## Decision guide
1. **Creating new PR** → Use automation script OR `git push -u origin HEAD && gh pr create`
2. **PR already created but no upstream** → `git branch --set-upstream-to=origin/$(git branch --show-current)`
3. **Fixing PR after comments** → Commit changes, `git push` (upstream already set)
4. **Checking PR status** → `gh pr view` or `gh pr checks`
5. **Creating PR from issue** → `gh issue develop <number> --checkout && git push -u origin HEAD && gh pr create`

## Critical Rules
- **🚨 ALWAYS set upstream tracking**: Use `git push -u origin HEAD` OR manually set with `git branch --set-upstream-to=origin/BRANCH_NAME`
- **🚨 NEVER push without `-u` on first push**: Prevents "no tracking information" errors
- **🚨 CHECK upstream after PR creation**: Run `git branch -vv` to verify tracking is configured
- **🚨 USE automation script for consistency**: Ensures all steps are followed

## Upstream Tracking Benefits
- ✅ `git push` and `git pull` work without arguments
- ✅ Git status shows "ahead/behind" information
- ✅ `gh pr` commands work correctly
- ✅ Prevents accidental pushes to wrong branch
- ✅ Enables `git push --force-with-lease` safety

## Common Issues & Solutions

### Issue: "fatal: The current branch has no upstream branch"
**Solution**: `git branch --set-upstream-to=origin/$(git branch --show-current)`

### Issue: PR created but git status doesn't show tracking
**Solution**: Run upstream setup command above, then `git branch -vv` to verify

### Issue: Want to change PR base branch
**Solution**: `gh pr edit --base new-base-branch`

### Issue: Multiple commits, want to squash
**Solution**: `git rebase -i HEAD~N` (where N is number of commits), then `git push --force-with-lease`

## PR Description Best Practices
Include in every PR description:
1. **Summary**: What does this PR do?
2. **Changes**: Bullet list of specific changes
3. **Benefits**: Why is this valuable?
4. **Test Plan**: How was this tested?
5. **Related Issues**: Link to issues/tickets

## Workflow Integration
This skill integrates with:
- `/pr` command - Complete PR workflow automation
- `/push` command - Branch pushing with PR creation
- `/pushl` command - Push with automatic labeling
- Build/test/lint autopilot - Pre-PR validation

## PR Branch Verification (MANDATORY)

**CRITICAL: Always verify the correct PR remote branch before working on merge conflicts or PR operations.**

### Forbidden Actions
- Guessing or assuming PR branch names
- Using branch names that "look like" they match the PR number
- Working on branches without verifying they're the actual PR branch

### Required Steps
1. **Verify PR branch name**:
   - `gh pr view <number> --json headRefName`
   - Or: `git log --oneline --all --grep="<PR-number>"`
2. **Fetch the correct remote branch**: `git fetch origin <actual-branch-name>`
3. **Reset to the correct branch**: `git reset --hard origin/<actual-branch-name>`
4. **Verify before proceeding**: `git log --oneline -5`

### Example
```bash
# WRONG - Don't guess
git fetch origin pull/3096/head:pr-3096

# CORRECT - Verify first
gh pr view 3096 --json headRefName  # Returns actual branch name
git fetch origin claude/byok-settings-feature-0WgQP
git reset --hard origin/claude/byok-settings-feature-0WgQP
```

**Root Cause Prevention:** Multiple branches may exist with similar names. Always verify from PR metadata.

## Reporting expectations
- Confirm upstream tracking is set: `git branch -vv` output
- Display PR URL after creation
- Show current branch status and tracking information
- Highlight any issues with upstream configuration
- Provide next steps if PR creation partially fails
