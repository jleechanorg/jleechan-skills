---
description: Post "@coderabbitai all good?" comment on the PR associated with the current branch
type: git
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

## 🚨 EXECUTION WORKFLOW

### Step 1: Get Current Branch and Find PR

Run the following to find the PR number for the current branch:

```bash
gh pr view --json number,url,title
```

If the command fails (no PR found), tell the user: "No open PR found for the current branch."

### Step 2: Post CodeRabbit Comment

Post a comment on the PR saying exactly `@coderabbitai all good?`:

```bash
gh pr comment <PR_NUMBER> --body "@coderabbitai all good?"
```

### Step 3: Confirm

Report to the user:
- The PR number and URL
- That the comment "@coderabbitai all good?" was successfully posted

## 📋 REFERENCE DOCUMENTATION

# /coderabbit - Trigger CodeRabbit Review

**Purpose**: Post `@coderabbitai all good?` on the PR associated with the current local branch, prompting CodeRabbit to re-review or confirm the PR.

**Usage**: `/coderabbit` or `/cr`

**What it does**:
1. Detects the PR linked to the current branch via `gh pr view`
2. Posts `@coderabbitai all good?` as a PR comment
3. Reports success with PR URL

**Alias**: `/cr`
