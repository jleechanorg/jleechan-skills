---
description: /newbranch or /nb - Create new branch from latest main
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Context Analysis & Name Generation
1. **Analyze Context**: If the user did NOT provide a branch name, look at:
   - Recent conversation history
   - Current uncommitted changes (`git status`, `git diff --stat`)
   - Last 3 commit messages
2. **Generate Name**: If no name provided, propose a descriptive slug (e.g., `fix-auth-bug`, `feat-navigation-refactor`).
3. **Confirm with User**: (Optional/Implicit) Use the generated name when calling the script.

### Phase 2: Execute Branch Creation

**Action Steps:**
1. Execute the `newbranch.py` Python script.
2. Pass the branch name (either user-provided or generated) as the first argument.
3. Script handles: stashing changes, fetching origin/main, creating branch directly from `origin/main` (avoiding local `main` checkout), cherry-picking commits if requested.
4. Verify branch creation success and report new branch name.
5. Confirm working tree changes were restored.

## 📋 REFERENCE DOCUMENTATION

# /newbranch or /nb - Create a new branch from fresh `origin/main`

Creates a fresh branch from the latest `origin/main` while carrying forward your current working tree changes. This command is worktree-safe and does not require the local `main` branch to be available.

## Usage
- `/newbranch` - Creates a new branch with an auto-generated name based on context.
- `/nb` - Alias for /newbranch.
- `/nb feature-xyz` - Creates a branch named `feature-xyz`.
- `/nb bring in changes abc123` - Creates a branch named `bring-in-changes` and cherry-picks commit `abc123`.

## Behavior
1. Detects uncommitted changes and stashes them (including untracked files).
2. Fetches, checks out, and pulls the latest `origin/main`.
3. Creates the new branch directly from `origin/main`.
4. Optionally cherry-picks requested commits that exist on the previous branch.
5. Restores any stashed changes so your working tree matches your previous edits.
6. Pushes the branch and sets upstream tracking to `origin/<branch_name>`.

## Examples
```
/nb
→ Creates branch like dev1751992265

/nb my-feature
→ Creates branch named my-feature

/newbranch bugfix-123
→ Creates branch named bugfix-123

/nb bring in changes abc123 def456
→ Creates branch named bring-in-changes and cherry-picks abc123 + def456

/nb feature tweaks with commits
→ Creates branch named feature-tweaks and cherry-picks every local commit not on origin/main
```

## Error Cases
- Rebase conflicts → Command stops with instructions so you can resolve and continue
- Branch name already exists → Git will report error
- Network issues → Fetch may fail

## Implementation Notes
- Works in both regular repos and worktrees
- Always fetches and pulls the latest `origin/main` before creating the branch
- Cherry-picks requested commits from the previous branch when keywords like "bring in changes" are present
- Automatically sets up remote tracking to origin/<branch_name>
- ⚠️ **CRITICAL**: Must use Python script (.claude/commands/newbranch.py)
- ❌ **NEVER** manually run: `git branch --set-upstream-to=origin/main`
- ✅ **CORRECT**: Let script handle tracking with `git push -u origin <branch>`
