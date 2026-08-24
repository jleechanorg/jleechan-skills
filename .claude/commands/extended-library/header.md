---
description: Header Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Usage in Workflow

**Action Steps:**
**Best Practice**: Use `/header` before ending responses to:
1. See complete git repository context with **one command**
2. Generate the required header with full PR inference
3. Create a reminder checkpoint to include it
4. Ensure consistent formatting with zero effort
5. Remove all friction in compliance

**Automated Memory Aid**:
6. The single command `$(git rev-parse --show-toplevel)/.claude/hooks/git-header.sh` provides essential repo context by default
7. Intelligently finds relevant PRs and shows sync status (add `--with-status` for full git status)
8. No need to remember multiple separate commands
9. Consistent, reliable output every time
10. Perfect for developing muscle memory

**Integration**:
11. End every response with the header (one simple command)
12. Use when switching branches or tasks
13. Make it a habit: "content first, header last"

## 📋 REFERENCE DOCUMENTATION

# Header Command

**Purpose**: Generate and display the mandatory branch header for CLAUDE.md compliance with full git status and intelligent PR inference

**Usage**: `/header` or `/usage`

**Action**: Execute single script to show git status and generate the required branch header with API usage statistics

## Implementation

**Single Command**: `$(git rev-parse --show-toplevel)/.claude/hooks/git-header.sh`

This script automatically:
1. Gets local branch name with sync status
2. Gets remote upstream info
3. Intelligently infers PR information:
   - Primary: Finds PR for current branch
   - Fallback: If no PR for current branch but uncommitted changes exist, suggests related open PRs
4. Formats everything into the required header

**Optional**: Pass `--with-status` to also show full `git status` output before the header.

**Benefits**:
- ✅ **Concise by default** - Header line only, no verbose git status dump
- ✅ **Intelligent PR inference** - Finds relevant PRs even when branch doesn't have direct PR
- ✅ **Automatic formatting** - Prevents formatting errors
- ✅ **Error handling** - Gracefully handles missing upstreams/PRs
- ✅ **Consistent output** - Same format every time
- ✅ **Optional verbosity** - Use `--with-status` when full git status is needed

## Output Format

Default output is just the mandatory header line:

```
[Local: <branch> | Remote: <upstream> | PR: <number> <url>]
```

With `--with-status` flag, git status is shown first:

```
=== Git Status ===
On branch dev1754541036
Your branch is ahead of 'origin/main' by 2 commits.
  (use "git push" to publish your local commits)

	modified:   .claude/hooks/git-header.sh

[Local: <branch> | Remote: <upstream> | PR: <number> <url>]
```

Examples:
- `[Local: main | Remote: upstream/main | PR: none]`
- `[Local: feature-x | Remote: upstream/main | PR: #123 https://github.com/user/repo/pull/123]`
- `[Local: dev-branch (ahead 2) | Remote: upstream/main | PR: (related to #456 https://github.com/user/repo/pull/456)]`

**NOTE**: Remote must NEVER be `origin/main`. Use actual remote name (e.g., `upstream/main`, `origin/branch-name`).

## Compliance Note

This command helps fulfill the 🚨 CRITICAL requirement in CLAUDE.md that EVERY response must end with the branch header. The enhanced output provides essential context about:
- Complete git repository working directory state
- Current working branch with sync status
- Remote tracking status  
- Intelligently inferred PR context (direct or related)
- API usage monitoring

Using this command makes compliance easier, provides complete repository context, and helps maintain the required workflow discipline.
