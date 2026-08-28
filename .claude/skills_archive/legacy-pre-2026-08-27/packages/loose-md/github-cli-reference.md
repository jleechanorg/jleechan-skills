---
description: Complete reference for GitHub CLI (gh) installation, authentication, and usage in Claude Code environment
type: reference
scope: project
---

# GitHub CLI Reference

## Purpose
Provide comprehensive, copy-paste ready instructions for GitHub CLI (gh) installation and usage to prevent common mistakes like missing full paths or forgetting GITHUB_TOKEN environment variable prefix.

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
if [ -f ~/.local/bin/gh ]; then
    echo "✅ gh CLI already installed"
    ~/.local/bin/gh --version
else
    echo "gh CLI not found, proceeding with installation..."
fi
```

### Step 1: Download and Extract (Complies with TEMPORARY FILE ISOLATION)
```bash
# Only install if not already present
if [ ! -f ~/.local/bin/gh ]; then
    # Use mktemp for unique temporary directory (CLAUDE.md policy compliance)
    TMP_GH_DIR="$(mktemp -d)"
    cd "$TMP_GH_DIR"
    curl -sL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz -o gh.tar.gz
    tar -xzf gh.tar.gz
    mkdir -p ~/.local/bin
    cp gh_2.40.1_linux_amd64/bin/gh ~/.local/bin/gh
    chmod +x ~/.local/bin/gh
    cd - > /dev/null
    rm -rf "$TMP_GH_DIR"
fi
```

### Step 2: Verify Installation
```bash
~/.local/bin/gh --version
```
**Expected output**: `gh version 2.40.1 (2023-12-13)`

### Step 3: Test Authentication
```bash
~/.local/bin/gh auth status
```
**Expected output**: `✓ Logged in to github.com account <username> (GITHUB_TOKEN)`
**Note**: GitHub CLI automatically uses the `GITHUB_TOKEN` environment variable - no prefix needed!

## Critical Usage Rules

### ✅ ALWAYS Do This:
1. **Use full path**: `~/.local/bin/gh` (installed to user bin, not /tmp)
2. **GITHUB_TOKEN automatic**: No prefix needed - gh automatically uses environment variable
3. **Specify repo**: Add `--repo jleechanorg/your-project.com` for clarity

### ❌ NEVER Do This:
1. **Don't use**: Just `gh` (it's not in PATH unless you add ~/.local/bin)
2. **Don't use /tmp**: Install to ~/.local/bin to comply with TEMPORARY FILE ISOLATION policy
3. **Don't add redundant prefix**: `GITHUB_TOKEN=$GITHUB_TOKEN` is unnecessary

## Command Reference

### Authentication & Status

#### Check auth status
```bash
~/.local/bin/gh auth status
```

#### Check API rate limit
```bash
~/.local/bin/gh api rate_limit --jq '.rate | {limit: .limit, remaining: .remaining}'
```

### Repository Operations

#### View repository info
```bash
~/.local/bin/gh repo view jleechanorg/your-project.com
```

#### View repository info (JSON)
```bash
~/.local/bin/gh repo view jleechanorg/your-project.com --json name,owner,isPrivate,defaultBranchRef,description
```

#### List branches
```bash
~/.local/bin/gh api repos/jleechanorg/your-project.com/branches --jq '.[0:10] | .[] | {name: .name, protected: .protected}'
```

### Pull Request Operations

#### List open PRs
```bash
~/.local/bin/gh pr list --repo jleechanorg/your-project.com --state open --limit 10
```

#### List all PRs (including closed)
```bash
~/.local/bin/gh pr list --repo jleechanorg/your-project.com --state all --limit 20
```

#### View specific PR
```bash
~/.local/bin/gh pr view <PR_NUMBER> --repo jleechanorg/your-project.com
```

#### View PR with JSON output
```bash
~/.local/bin/gh pr view <PR_NUMBER> --repo jleechanorg/your-project.com --json number,title,state,author,createdAt,body
```

#### View PR checks/status
```bash
~/.local/bin/gh pr checks <PR_NUMBER> --repo jleechanorg/your-project.com
```

#### Create PR
```bash
~/.local/bin/gh pr create --repo jleechanorg/your-project.com --title "PR Title" --body "PR Description"
```

#### Create PR (interactive)
```bash
~/.local/bin/gh pr create --repo jleechanorg/your-project.com --fill
```

#### Merge PR
```bash
~/.local/bin/gh pr merge <PR_NUMBER> --repo jleechanorg/your-project.com --squash
```

#### View PR comments
```bash
~/.local/bin/gh api repos/jleechanorg/your-project.com/pulls/<PR_NUMBER>/comments
```

### Issue Operations

#### List issues
```bash
~/.local/bin/gh issue list --repo jleechanorg/your-project.com --limit 10
```

#### List open issues with labels
```bash
~/.local/bin/gh issue list --repo jleechanorg/your-project.com --state open --label bug --limit 10
```

#### View specific issue
```bash
~/.local/bin/gh issue view <ISSUE_NUMBER> --repo jleechanorg/your-project.com
```

#### Create issue
```bash
~/.local/bin/gh issue create --repo jleechanorg/your-project.com --title "Issue Title" --body "Issue Description"
```

### Workflow Operations

#### List workflows
```bash
~/.local/bin/gh workflow list --repo jleechanorg/your-project.com
```

#### List workflow runs
```bash
~/.local/bin/gh run list --repo jleechanorg/your-project.com --limit 10
```

#### List workflow runs for specific workflow
```bash
~/.local/bin/gh run list --repo jleechanorg/your-project.com --workflow "Workflow Name" --limit 10
```

#### View workflow run details
```bash
~/.local/bin/gh run view <RUN_ID> --repo jleechanorg/your-project.com
```

#### Watch workflow run
```bash
~/.local/bin/gh run watch <RUN_ID> --repo jleechanorg/your-project.com
```

### Label Operations

#### List labels
```bash
~/.local/bin/gh label list --repo jleechanorg/your-project.com
```

#### Create label
```bash
~/.local/bin/gh label create "label-name" --repo jleechanorg/your-project.com --description "Label description" --color "ff0000"
```

### GitHub API Direct Access

#### Get user info
```bash
~/.local/bin/gh api user --jq '.login'
```

#### Get latest commit on main
```bash
~/.local/bin/gh api repos/jleechanorg/your-project.com/commits/main --jq '{sha: .sha[0:7], author: .commit.author.name, message: .commit.message | split("\n")[0]}'
```

#### Get repository collaborators
```bash
~/.local/bin/gh api repos/jleechanorg/your-project.com/collaborators
```

#### Get repository topics
```bash
~/.local/bin/gh api repos/jleechanorg/your-project.com/topics
```

## Troubleshooting

### Error: "command not found: gh"
**Cause**: Used `gh` instead of full path
**Solution**: Always use `~/.local/bin/gh`

### Error: "You are not logged into any GitHub hosts"
**Cause**: `GITHUB_TOKEN` environment variable not set
**Solution**: Verify `GITHUB_TOKEN` is set with `echo $GITHUB_TOKEN` (should show token value)

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
if [ -f ~/.local/bin/gh ]; then
    echo "gh CLI is installed"
else
    echo "gh CLI not installed, run installation steps"
fi
```

### Get PR number from current branch
```bash
PR_NUMBER=$(~/.local/bin/gh pr list --repo jleechanorg/your-project.com --head $(git branch --show-current) --json number --jq '.[0].number')
echo "Current branch PR: #$PR_NUMBER"
```

### Check if PR exists for current branch
```bash
PR_EXISTS=$(~/.local/bin/gh pr list --repo jleechanorg/your-project.com --head $(git branch --show-current) --json number --jq 'length')
if [ "$PR_EXISTS" -gt 0 ]; then
    echo "PR exists for current branch"
else
    echo "No PR for current branch"
fi
```

### Get PR status with detailed info
```bash
~/.local/bin/gh pr view <PR_NUMBER> --repo jleechanorg/your-project.com --json number,title,state,isDraft,mergeable,reviewDecision,statusCheckRollup
```

## Environment Variables

### GITHUB_TOKEN
- **Purpose**: Authentication token for GitHub API
- **Set automatically**: Available as environment variable
- **Usage**: GitHub CLI automatically uses this environment variable (no manual prefix needed)
- **Scopes**: Full access (admin:org, repo, workflow, etc.)

## Integration with Other Tools

### Use with jq for JSON parsing
```bash
~/.local/bin/gh pr list --repo jleechanorg/your-project.com --json number,title --jq '.[] | "\(.number): \(.title)"'
```

### Use in scripts
```bash
#!/bin/bash
set -e

# Define gh command
GH="~/.local/bin/gh"
REPO="jleechanorg/your-project.com"

# Use in script
$GH pr list --repo $REPO --limit 5
```

### Use with grep for filtering
```bash
~/.local/bin/gh pr list --repo jleechanorg/your-project.com | grep "OPEN"
```

## Best Practices

1. **Always use full path**: Never assume `gh` is in PATH (use `~/.local/bin/gh`)
2. **GITHUB_TOKEN automatic**: gh CLI automatically uses environment variable (no prefix needed)
3. **Always specify --repo**: Makes commands explicit and prevents errors
4. **Use --json with --jq**: For parsing specific fields from responses
5. **Check installation first**: Verify gh binary exists before using
6. **Use --limit**: Prevent overwhelming output for list commands
7. **Store in variable**: Define `GH` variable in scripts for reusability

## Quick Copy-Paste Commands

```bash
# Set up gh command variable for easy reuse
GH="~/.local/bin/gh"
REPO="jleechanorg/your-project.com"

# Now you can use it like this:
$GH pr list --repo $REPO
$GH issue list --repo $REPO
$GH workflow list --repo $REPO
```

## Related Skills
- `pr-workflow-manager.md` - PR creation and management best practices
- `build-test-lint-autopilot.md` - Pre-PR validation
- `cloud-ops-credential-guard.md` - Token and credential management

## Reporting Expectations
When using gh CLI, always:
1. Confirm gh binary exists before running commands
2. Include full command with GITHUB_TOKEN prefix in output
3. Show actual output from gh commands
4. Report any errors with full error message
5. Verify authentication status if commands fail
