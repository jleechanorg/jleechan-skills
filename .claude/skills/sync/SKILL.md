---
name: sync
description: /sync - Synchronize a local branch with a GitHub PR (fetch, switch/create branch, match remote PR state)
type: skill
scope: user
---

# /sync - Synchronize Local Branch with PR

## Description

Synchronizes local branch with a GitHub PR by fetching, switching/creating branch, and ensuring local copy matches remote PR state.

## Usage

- `/sync <pr_number>` - Sync with PR by number
- `/sync <pr_url>` - Sync with PR by GitHub URL

## Implementation

```bash

# Check for required tools

if ! command -v gh >/dev/null 2>&1; then
    echo "❌ Error: GitHub CLI (gh) is required but not installed"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "❌ Error: jq is required but not installed"
    exit 1
fi

# ALWAYS fetch latest info from remote first - ensures we know about ALL branches
# Fail hard if any remote fetch fails so we don't end up partially pruned
echo "🔄 Fetching latest info from all remotes..."
if ! git fetch --all --prune; then
    echo "❌ Error: Failed to fetch from all remotes. Please resolve git remote issues and try again."
    exit 1
fi
echo "✅ Remote refs updated"

# Parse input to extract PR number

if [[ "$1" =~ ^[0-9]+$ ]]; then
    PR_NUMBER="$1"
elif [[ "$1" =~ github\.com.*pull/([0-9]+) ]]; then
    PR_NUMBER=$(echo "$1" | grep -o 'pull/[0-9]*' | cut -d'/' -f2)
else
    echo "❌ Invalid input. Use PR number or GitHub PR URL"
    exit 1
fi

echo "🔄 Syncing with PR #$PR_NUMBER..."

# Get PR info using gh CLI

PR_INFO=$(gh pr view "$PR_NUMBER" --json headRefName,baseRefName,headRepository,headRepositoryOwner 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "❌ Failed to fetch PR #$PR_NUMBER info"
    exit 1
fi

# Extract branch information

HEAD_BRANCH=$(echo "$PR_INFO" | jq -r '.headRefName')
BASE_BRANCH=$(echo "$PR_INFO" | jq -r '.baseRefName')
HEAD_REPO=$(echo "$PR_INFO" | jq -r '(.headRepositoryOwner.login // "" )')
if [ -z "$HEAD_REPO" ]; then
    HEAD_REPO=$(echo "$PR_INFO" | jq -r '(.headRepository.nameWithOwner // "" )' | awk -F'/' '{print $1}')
fi
if [ -z "$HEAD_REPO" ]; then
    HEAD_REPO=$(gh api repos/:owner/:repo --jq .owner.login)
fi
REMOTE_BRANCH="$HEAD_BRANCH"  # Store original remote branch name

CURRENT_ORIGIN_URL=$(git remote get-url origin 2>/dev/null || echo "")
CURRENT_OWNER=""
if [[ "$CURRENT_ORIGIN_URL" == git@github.com:* ]]; then
    CURRENT_OWNER="${CURRENT_ORIGIN_URL#git@github.com:}"
    CURRENT_OWNER="${CURRENT_OWNER%%/*}"
elif [[ "$CURRENT_ORIGIN_URL" == https://github.com/* ]] || [[ "$CURRENT_ORIGIN_URL" == http://github.com/* ]]; then
    CURRENT_OWNER="${CURRENT_ORIGIN_URL#*://github.com/}"
    CURRENT_OWNER="${CURRENT_OWNER%%/*}"
fi
if [ -z "$CURRENT_OWNER" ]; then
    CURRENT_OWNER=$(gh api repos/:owner/:repo --jq .owner.login 2>/dev/null || echo "")
fi

echo "📋 PR #$PR_NUMBER: $HEAD_BRANCH -> $BASE_BRANCH (owner=$HEAD_REPO; repo=$CURRENT_OWNER)"

# Handle fork PRs using gh pr checkout

if [ -n "$HEAD_REPO" ] && [ -n "$CURRENT_OWNER" ] && [ "$HEAD_REPO" != "$CURRENT_OWNER" ]; then
    echo "🔗 Fork detected, using gh pr checkout for proper remote setup..."
    gh pr checkout "$PR_NUMBER"
else
    # Remote refs already fetched at start - proceed with branch operations

    # ALWAYS try to switch to a local branch mirroring the remote branch name
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    SWITCHED_TO_TARGET=false  # Track if we successfully switched to target branch

    # Check if local branch with target name already exists
    if git show-ref --verify --quiet "refs/heads/$HEAD_BRANCH"; then
        # Local branch exists - try to checkout
        if git checkout "$HEAD_BRANCH" 2>/dev/null; then
            echo "🔄 Switched to existing branch: $HEAD_BRANCH"
            SWITCHED_TO_TARGET=true
        else
            # Branch locked in another worktree - find which one
            # Note: git worktree list --porcelain outputs branch as refs/heads/branch-name
            # Use substr to capture full path including spaces (everything after "worktree ")
            WORKTREE_INFO=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$HEAD_BRANCH" '/^worktree /{path=substr($0,10)} /^branch / && $2==br {print path}' )
            if [ -z "$WORKTREE_INFO" ]; then
                WORKTREE_INFO="unknown location"
            fi
            echo "🔄 Attempting to resolve branch conflict with remote..."

            # Try to free the branch by switching the OTHER worktree off it,
            # so this directory can check it out directly (matches user intent:
            # "checkout the PR branch here" means HERE, not a differently-named
            # local mirror). Only ever touches the other worktree when it is
            # verified clean (no uncommitted changes) -- a dirty other worktree
            # is left completely alone and we fall back to the sync-branch path.
            FREED_OTHER_WORKTREE=false
            if [ "$WORKTREE_INFO" != "unknown location" ] && [ -d "$WORKTREE_INFO" ]; then
                OTHER_DIRTY=$(git -C "$WORKTREE_INFO" status --porcelain 2>/dev/null)
                if [ -n "$OTHER_DIRTY" ]; then
                    echo "⚠️ Branch $HEAD_BRANCH is checked out elsewhere with uncommitted changes: $WORKTREE_INFO"
                    echo "⚠️ Leaving that worktree untouched; falling back to a local sync branch here."
                else
                    OTHER_COMMIT=$(git -C "$WORKTREE_INFO" rev-parse HEAD 2>/dev/null)
                    if git -C "$WORKTREE_INFO" checkout --detach "$OTHER_COMMIT" 2>/dev/null; then
                        echo "✅ Switched other worktree off $HEAD_BRANCH (now detached at $OTHER_COMMIT): $WORKTREE_INFO"
                        FREED_OTHER_WORKTREE=true
                    else
                        echo "⚠️ Could not switch other worktree off $HEAD_BRANCH: $WORKTREE_INFO"
                    fi
                fi
            fi

            if [ "$FREED_OTHER_WORKTREE" = "true" ] && git checkout "$HEAD_BRANCH" 2>/dev/null; then
                echo "🔄 Switched to freed branch: $HEAD_BRANCH"
                SWITCHED_TO_TARGET=true
            else
            echo "⚠️ Checkout failed for $HEAD_BRANCH; creating a safe local sync branch instead."
            if [ "$WORKTREE_INFO" != "unknown location" ]; then
                echo "⚠️ Branch $HEAD_BRANCH is checked out elsewhere: $WORKTREE_INFO"
            fi

            # Create a unique local branch that still tracks the PR remote branch.
            # This avoids blocking the existing checked-out worktree and preserves both copies.
            SYNC_BRANCH_BASE="${HEAD_BRANCH}__sync-${PR_NUMBER}"
            SYNC_BRANCH="$SYNC_BRANCH_BASE"
            SYNC_SUFFIX=1
            while git show-ref --verify --quiet "refs/heads/$SYNC_BRANCH"; do
                SYNC_BRANCH="${SYNC_BRANCH_BASE}-${SYNC_SUFFIX}"
                SYNC_SUFFIX=$((SYNC_SUFFIX + 1))
            done

            if git checkout -b "$SYNC_BRANCH" --track "origin/$REMOTE_BRANCH" 2>/dev/null; then
                echo "✅ Created local sync branch: $SYNC_BRANCH (tracking origin/$REMOTE_BRANCH)"
                HEAD_BRANCH="$SYNC_BRANCH"
                SWITCHED_TO_TARGET=true
            else
                echo "❌ Failed to create local sync branch $SYNC_BRANCH"
                echo "🔄 Falling back to syncing content on current branch..."
                if ! git fetch origin "$REMOTE_BRANCH"; then
                    echo "❌ Failed to fetch origin/$REMOTE_BRANCH"
                    exit 1
                fi
                if ! git reset --hard "origin/$REMOTE_BRANCH"; then
                    echo "❌ Failed to reset to remote state"
                    exit 1
                fi
                echo "✅ Content synced to remote state"
                echo "📍 Stayed on $CURRENT_BRANCH and replaced content from origin/$REMOTE_BRANCH."
                HEAD_BRANCH="$CURRENT_BRANCH"
            fi
            fi
        fi
    else
        # No local branch exists - create it from remote
        if [ "$CURRENT_BRANCH" != "$HEAD_BRANCH" ]; then
            echo "🔄 Creating local branch to mirror remote: $HEAD_BRANCH"
            if git checkout -b "$HEAD_BRANCH" "origin/$REMOTE_BRANCH" 2>/dev/null; then
                echo "✅ Switched to new local branch: $HEAD_BRANCH"
                SWITCHED_TO_TARGET=true
            else
                echo "❌ Failed to create branch $HEAD_BRANCH"
                echo "🔄 Syncing content on current branch instead..."
                if ! git fetch origin "$REMOTE_BRANCH"; then
                    echo "❌ Failed to fetch origin/$REMOTE_BRANCH"
                    exit 1
                fi
                if ! git reset --hard "origin/$REMOTE_BRANCH"; then
                    echo "❌ Failed to reset to remote state"
                    exit 1
                fi
                echo "✅ Content synced to remote state"
                HEAD_BRANCH="$CURRENT_BRANCH"
            fi
        else
            # Edge case: Already on a branch with target name but ref doesn't exist
            # (can happen with corrupted refs or detached HEAD with matching name)
            echo "ℹ️ Already on target branch name; ensuring content is up to date..."
            SWITCHED_TO_TARGET=true
            if ! git fetch origin "$REMOTE_BRANCH"; then
                echo "❌ Failed to fetch origin/$REMOTE_BRANCH"
                exit 1
            fi
            if ! git reset --hard "origin/$REMOTE_BRANCH"; then
                echo "❌ Failed to reset to remote state"
                exit 1
            fi
            echo "✅ Content synced to remote state on $CURRENT_BRANCH"
        fi
    fi

    # Set upstream tracking only if we successfully switched to target branch
    # (Don't corrupt upstream tracking on fallback branches)
    if [ "$SWITCHED_TO_TARGET" = "true" ]; then
        echo "🔗 Setting upstream tracking..."
        git branch --set-upstream-to=origin/"$REMOTE_BRANCH" "$HEAD_BRANCH"

        # Pull latest changes
        echo "⬇️ Pulling latest changes..."
        if git pull origin "$REMOTE_BRANCH" 2>/dev/null; then
            echo "✅ Successfully pulled changes"
        else
            echo "⚠️ Pull failed, trying to reset to remote state..."
            if ! git reset --hard origin/"$REMOTE_BRANCH"; then
                echo "❌ Failed to reset to remote state"
                exit 1
            fi
            echo "✅ Reset to remote state successful"
        fi
    else
        echo "⚠️ Skipping upstream tracking (fell back to $HEAD_BRANCH, not target branch)"
        echo "📍 Content synced but branch name differs from PR branch"
    fi
fi

# Verify sync status

echo "🔍 Verifying sync status..."
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/"$REMOTE_BRANCH" 2>/dev/null || echo "unknown")

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo "✅ Local branch perfectly synced with remote"
else
    echo "⚠️ Local/remote mismatch detected"
    echo "   Local:  $LOCAL_COMMIT"
    echo "   Remote: $REMOTE_COMMIT"
fi

# Show current status

echo "📊 Current status:"
git status --short
echo "📍 Current branch: $(git rev-parse --abbrev-ref HEAD)"
echo "✨ Synced with PR #$PR_NUMBER ($REMOTE_BRANCH)"
```

## Success Criteria

- ✅ Branch exists locally and matches remote
- ✅ All changes from PR are present
- ✅ Clean working directory
- ✅ Upstream tracking configured
