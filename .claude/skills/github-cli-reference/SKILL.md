---
name: github-cli-reference
description: Complete reference for GitHub CLI (gh) installation, authentication, and usage in Claude Code environment
type: reference
scope: project
---

# GitHub CLI Reference

## Purpose
Reference GitHub CLI installation, authentication, and commands for the current
authorized operation. Use the installed binary discovered with `command -v gh`;
run Step 0 in the current shell before the examples, which use the resolved `GH` path.

## Activation cues
- Requests to use GitHub CLI or `gh` commands
- Questions about GitHub API, PRs, issues, workflows
- Pull request operations (list, view, create, merge)
- GitHub repository queries
- Workflow run checks
- GitHub API operations
- Authentication errors or "command not found" errors

## Installation (One-Time Setup)

### Step 0: Check if Already Installed
```bash
GH="$(command -v gh || true)"
if [ -z "$GH" ] && [ -x "$HOME/.local/bin/gh" ]; then
    GH="$HOME/.local/bin/gh"
fi
if [ -n "$GH" ]; then
    echo "gh CLI already installed: $GH"
    "$GH" --version
else
    echo "gh CLI not found; installation is needed"
fi
```

### Step 1: Install Only When Missing

If `GH` is empty, inspect the current platform and use its supported installation
method from the [GitHub CLI installation instructions](https://cli.github.com/).
Complete installation within the task's existing authority, then rerun Step 0.
Preserve an existing working binary; a missing `~/.local/bin/gh` alone does not
mean GitHub CLI is absent.

### Step 2: Verify Installation
```bash
"$GH" --version
```
**Expected output**: the installed GitHub CLI version.

### Step 3: Test Authentication
```bash
"$GH" auth status
```
**Expected output**: `✓ Logged in to github.com account <username> (GITHUB_TOKEN)`
**Note**: GitHub CLI automatically uses the `GITHUB_TOKEN` environment variable - no prefix needed!

## Critical Usage Rules

### ✅ ALWAYS Do This:
1. **Use the installed binary**: resolve it with `command -v gh`; use `~/.local/bin/gh` when installed there
2. **GITHUB_TOKEN automatic**: No prefix needed - gh automatically uses environment variable
3. **Specify repo**: Add `--repo jleechanorg/your-project.com` for clarity

### ❌ NEVER Do This:
1. **Don't reinstall over a working binary**: inspect the current PATH and platform first
2. **Don't use /tmp**: Install to ~/.local/bin to comply with TEMPORARY FILE ISOLATION policy
3. **Don't add redundant prefix**: `GITHUB_TOKEN=$GITHUB_TOKEN` is unnecessary

## Command Reference

### Authentication & Status

#### Check auth status
```bash
"$GH" auth status
```

#### Check API rate limit
```bash
"$GH" api rate_limit --jq '.rate | {limit: .limit, remaining: .remaining}'
```

### Repository Operations

#### View repository info
```bash
"$GH" repo view jleechanorg/your-project.com
```

#### View repository info (JSON)
```bash
"$GH" repo view jleechanorg/your-project.com --json name,owner,isPrivate,defaultBranchRef,description
```

#### List branches
```bash
"$GH" api repos/jleechanorg/your-project.com/branches --jq '.[0:10] | .[] | {name: .name, protected: .protected}'
```

### Pull Request Operations

#### List open PRs
```bash
"$GH" pr list --repo jleechanorg/your-project.com --state open --limit 10
```

#### List all PRs (including closed)
```bash
"$GH" pr list --repo jleechanorg/your-project.com --state all --limit 20
```

#### View specific PR
```bash
"$GH" pr view '<PR_NUMBER>' --repo jleechanorg/your-project.com
```

#### View PR with JSON output
```bash
"$GH" pr view '<PR_NUMBER>' --repo jleechanorg/your-project.com --json number,title,state,author,createdAt,body
```

#### View PR checks/status
```bash
"$GH" pr checks '<PR_NUMBER>' --repo jleechanorg/your-project.com
```

#### Create PR
```bash
"$GH" pr create --repo jleechanorg/your-project.com --title "PR Title" --body "PR Description"
```

#### Create PR (interactive)
```bash
"$GH" pr create --repo jleechanorg/your-project.com --fill
```

#### Merge PR
```bash
"$GH" pr merge '<PR_NUMBER>' --repo jleechanorg/your-project.com --squash
```

#### View PR comments
```bash
"$GH" api repos/jleechanorg/your-project.com/pulls/'<PR_NUMBER>'/comments
```

### Issue Operations

#### List issues
```bash
"$GH" issue list --repo jleechanorg/your-project.com --limit 10
```

#### List open issues with labels
```bash
"$GH" issue list --repo jleechanorg/your-project.com --state open --label bug --limit 10
```

#### View specific issue
```bash
"$GH" issue view '<ISSUE_NUMBER>' --repo jleechanorg/your-project.com
```

#### Create issue
```bash
"$GH" issue create --repo jleechanorg/your-project.com --title "Issue Title" --body "Issue Description"
```

### Workflow Operations

#### List workflows
```bash
"$GH" workflow list --repo jleechanorg/your-project.com
```

#### List workflow runs
```bash
"$GH" run list --repo jleechanorg/your-project.com --limit 10
```

#### List workflow runs for specific workflow
```bash
"$GH" run list --repo jleechanorg/your-project.com --workflow "Workflow Name" --limit 10
```

#### View workflow run details
```bash
"$GH" run view '<RUN_ID>' --repo jleechanorg/your-project.com
```

#### Watch workflow run
```bash
"$GH" run watch '<RUN_ID>' --repo jleechanorg/your-project.com
```

### Label Operations

#### List labels
```bash
"$GH" label list --repo jleechanorg/your-project.com
```

#### Create label
```bash
"$GH" label create "label-name" --repo jleechanorg/your-project.com --description "Label description" --color "ff0000"
```

### GitHub API Direct Access

#### Get user info
```bash
"$GH" api user --jq '.login'
```

#### Get latest commit on main
```bash
"$GH" api repos/jleechanorg/your-project.com/commits/main --jq '{sha: .sha[0:7], author: .commit.author.name, message: .commit.message | split("\n")[0]}'
```

#### Get repository collaborators
```bash
"$GH" api repos/jleechanorg/your-project.com/collaborators
```

#### Get repository topics
```bash
"$GH" api repos/jleechanorg/your-project.com/topics
```

## Troubleshooting

### Error: "command not found: gh"
**Cause**: The binary is absent from the current PATH.
**Solution**: Inspect `command -v gh` and the known installation path; install for the current platform only if needed.

### Error: "You are not logged into any GitHub hosts"
**Cause**: No usable authentication is available to this invocation.
**Solution**: Inspect `gh auth status`. For an environment-token setup, check
`test -n "${GITHUB_TOKEN:-}" && echo "GITHUB_TOKEN is set"`. Never print the token.

### Error: "HTTP 404: Not Found"
**Cause**: Missing `--repo` flag or incorrect repo name
**Solution**: Add `--repo jleechanorg/your-project.com` to command

### Error: "Resource not accessible by integration"
**Cause**: Token lacks required permissions
**Solution**: Verify token scopes with `gh auth status`, ensure token has `repo` scope

### Binary not found: "~/.local/bin/gh"
**Cause**: gh CLI not installed yet
**Solution**: Run installation steps from "Installation (One-Time Setup)" section

## Advanced Patterns

### Check if gh is installed
```bash
if command -v gh >/dev/null 2>&1 || [ -x "$HOME/.local/bin/gh" ]; then
    echo "gh CLI is installed"
else
    echo "gh CLI not installed, run installation steps"
fi
```

### Get PR number from current branch
```bash
PR_NUMBER=$("$GH" pr list --repo jleechanorg/your-project.com --head $(git branch --show-current) --json number --jq '.[0].number')
echo "Current branch PR: #$PR_NUMBER"
```

### Check if PR exists for current branch
```bash
PR_EXISTS=$("$GH" pr list --repo jleechanorg/your-project.com --head $(git branch --show-current) --json number --jq 'length')
if [ "$PR_EXISTS" -gt 0 ]; then
    echo "PR exists for current branch"
else
    echo "No PR for current branch"
fi
```

### Get PR status with detailed info
```bash
"$GH" pr view '<PR_NUMBER>' --repo jleechanorg/your-project.com --json number,title,state,isDraft,mergeable,reviewDecision,statusCheckRollup
```

## Environment Variables

### GITHUB_TOKEN
- **Purpose**: Authentication token for GitHub API
- **Set automatically**: Available as environment variable
- **Usage**: GitHub CLI automatically uses this environment variable (no manual prefix needed)
- **Scopes**: Inspect the current account's permissions; do not assume administrative access.

## Integration with Other Tools

### Use with jq for JSON parsing
```bash
"$GH" pr list --repo jleechanorg/your-project.com --json number,title --jq '.[] | "\(.number): \(.title)"'
```

### Use in scripts
```bash
#!/bin/bash
set -e

# Define gh command
GH="$(command -v gh || true)"
if [ -z "$GH" ] && [ -x "$HOME/.local/bin/gh" ]; then
    GH="$HOME/.local/bin/gh"
fi
[ -n "$GH" ] || { echo "Run the installation steps first" >&2; exit 1; }
REPO="jleechanorg/your-project.com"

# Use in script
"$GH" pr list --repo $REPO --limit 5
```

### Use with grep for filtering
```bash
"$GH" pr list --repo jleechanorg/your-project.com | grep "OPEN"
```

## Best Practices

1. **Resolve the installed binary**: Prefer `command -v gh`, then the executable `~/.local/bin/gh` fallback.
2. **GITHUB_TOKEN automatic**: gh CLI automatically uses environment variable (no prefix needed)
3. **Always specify --repo**: Makes commands explicit and prevents errors
4. **Use --json with --jq**: For parsing specific fields from responses
5. **Check installation first**: Verify gh binary exists before using
6. **Use --limit**: Prevent overwhelming output for list commands
7. **Store in variable**: Define `GH` variable in scripts for reusability

## Quick Copy-Paste Commands

```bash
# Set up gh command variable for easy reuse
GH="$(command -v gh || true)"
if [ -z "$GH" ] && [ -x "$HOME/.local/bin/gh" ]; then
    GH="$HOME/.local/bin/gh"
fi
[ -n "$GH" ] || { echo "Run the installation steps first" >&2; exit 1; }
REPO="jleechanorg/your-project.com"

# Now you can use it like this:
"$GH" pr list --repo $REPO
"$GH" issue list --repo $REPO
"$GH" workflow list --repo $REPO
```

## Related Skills
- `pr-workflow-manager.md` - PR creation and management best practices
- `cloud-ops-credential-guard.md` - Token and credential management

## Reporting Expectations
When using gh CLI, always:
1. Confirm gh binary exists before running commands
2. Include the command without expanded credential values or token prefixes
3. Show relevant actual output with credentials redacted
4. Report diagnostic errors with credentials redacted
5. Verify authentication status if commands fail
