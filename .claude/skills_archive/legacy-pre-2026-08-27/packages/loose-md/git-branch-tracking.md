# Git Branch Tracking & PR Workflow

**Purpose**: Ensure proper remote branch tracking after creating PRs to avoid "no remote" and "no upstream" status issues.

## 🚨 Problem: Missing Remote Tracking

After creating a PR, the branch status may show:
```
Local: feature-branch (no remote) | Remote: no upstream
```

This happens when:
- Branch was created locally without `-u` flag
- Push was done with `HEAD:branch-name` instead of `-u origin branch-name`
- Tracking wasn't set up during initial push

## ✅ Solution: Always Set Upstream During Push

### Method 1: Use `-u` Flag (Recommended)

**When creating new branch and pushing**:
```bash
git checkout -b feature-branch
git add .
git commit -m "Feature implementation"
git push -u origin feature-branch  # ← Sets tracking automatically
```

**When pushing existing branch**:
```bash
git push -u origin HEAD  # ← Pushes current branch and sets tracking
```

### Method 2: Set Tracking After Push

If you already pushed without `-u`:
```bash
# Check current tracking status
git branch -vv

# Set upstream for current branch
git branch --set-upstream-to=origin/feature-branch feature-branch

# Verify tracking is set
git branch -vv
```

### Method 3: Git Config Default

Make all pushes set tracking by default:
```bash
git config --global push.autoSetupRemote true
```

Now any `git push` will automatically set tracking!

## 🎯 Best Practices for PR Workflow

### 1. Create Branch and Push with Tracking

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/new-feature

# Make changes
git add .
git commit -m "Implement new feature"

# Push with tracking (ALWAYS use -u)
git push -u origin feature/new-feature
```

### 2. Create PR Immediately After Push

```bash
# After push with -u
gh pr create --title "Add new feature" --body "Description"
```

### 3. Verify Tracking Status

```bash
# Check branch tracking
git branch -vv

# Should show:
# * feature/new-feature abc1234 [origin/feature/new-feature] Commit message
#                                ^^^ Tracking info shown
```

## 🔧 Common Commands

### Check Branch Info

```bash
# Show all branches with tracking info
git branch -vv

# Show remote branches
git branch -r

# Show all branches (local + remote)
git branch -a
```

### Fix Missing Tracking

```bash
# Option 1: Set tracking to existing remote branch
git branch --set-upstream-to=origin/$(git branch --show-current)

# Option 2: Push with -u to set tracking
git push -u origin HEAD

# Option 3: Enable auto-setup (one-time config)
git config --global push.autoSetupRemote true
```

### Update Remote References

```bash
# Fetch latest remote branch info
git fetch origin

# Prune deleted remote branches
git fetch --prune
git remote prune origin
```

## 📋 Git Status Header Format

**Correct format after proper setup**:
```
[Local: feature-branch | Remote: origin/feature-branch | PR: 2048 https://...]
```

**Incorrect format (missing tracking)**:
```
[Local: feature-branch (no remote) | Remote: no upstream | PR: N/A]
```

## 🚀 Automated PR Workflow

### Recommended Script Pattern

```bash
#!/bin/bash
# create-pr.sh - Create branch, commit, push with tracking, and create PR

BRANCH_NAME="${1:-feature/$(date +%s)}"
PR_TITLE="$2"
PR_BODY="$3"

# Create and switch to new branch
git checkout -b "$BRANCH_NAME"

# Make changes (assumes already staged)
git commit -m "$PR_TITLE"

# Push with tracking
git push -u origin "$BRANCH_NAME"

# Create PR
gh pr create --title "$PR_TITLE" --body "$PR_BODY" --base main

# Verify tracking
echo ""
echo "Branch tracking status:"
git branch -vv | grep "^\*"
```

Usage:
```bash
./create-pr.sh feature/add-validation "Add validation" "Implements input validation"
```

## ⚠️ Common Mistakes to Avoid

### Mistake 1: Using HEAD:branch-name

```bash
# ❌ WRONG - Doesn't set tracking
git push origin HEAD:feature-branch

# ✅ CORRECT - Sets tracking
git push -u origin feature-branch
# or
git push -u origin HEAD
```

### Mistake 2: Forgetting -u Flag

```bash
# ❌ WRONG - No tracking
git push origin feature-branch

# ✅ CORRECT - Sets tracking
git push -u origin feature-branch
```

### Mistake 3: Creating PR Before Push

```bash
# ❌ WRONG ORDER
gh pr create ...  # Fails - branch doesn't exist remotely yet
git push origin feature-branch

# ✅ CORRECT ORDER
git push -u origin feature-branch  # Push with tracking first
gh pr create ...  # Then create PR
```

## 🔍 Troubleshooting

### Issue: "no remote" in status

**Cause**: Branch not tracking any remote branch

**Fix**:
```bash
git branch --set-upstream-to=origin/$(git branch --show-current)
# or
git push -u origin HEAD
```

### Issue: "no upstream" in status

**Cause**: Same as "no remote" - missing tracking configuration

**Fix**: Same as above

### Issue: Push rejected (branch exists)

**Cause**: Trying to push with -u but remote branch exists

**Fix**:
```bash
# If you own the remote branch
git push -u origin HEAD

# If someone else created it
git branch --set-upstream-to=origin/existing-branch
git pull  # Merge remote changes
```

### Issue: Can't find remote branch

**Cause**: Remote branch deleted or never existed

**Fix**:
```bash
# Fetch latest remote info
git fetch origin

# Check if branch exists remotely
git branch -r | grep your-branch

# If doesn't exist, push with -u
git push -u origin your-branch
```

## 📚 Quick Reference

| Command | Purpose |
|---------|---------|
| `git push -u origin HEAD` | Push and set tracking |
| `git branch -vv` | Show tracking status |
| `git branch --set-upstream-to=origin/branch` | Set tracking manually |
| `git config push.autoSetupRemote true` | Auto-setup tracking (global) |
| `git fetch --prune` | Update remote refs, remove deleted |
| `git remote -v` | Show remote URLs |

## 🎯 Recommended Workflow

```bash
# 1. Create branch
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "Implement feature"

# 3. Push with tracking (CRITICAL)
git push -u origin feature/my-feature

# 4. Create PR
gh pr create --title "Add feature" --body "Description"

# 5. Verify tracking
git branch -vv

# Expected output:
# * feature/my-feature abc1234 [origin/feature/my-feature] Implement feature
```

## 💡 Pro Tips

1. **Use git aliases** for common workflows:
   ```bash
   git config --global alias.pushup '!git push -u origin HEAD'
   git config --global alias.track '!git branch --set-upstream-to=origin/$(git branch --show-current)'
   ```

2. **Enable auto-setup** to never worry about -u:
   ```bash
   git config --global push.autoSetupRemote true
   ```

3. **Check tracking before PR**:
   ```bash
   git branch -vv | grep "^\*" | grep -q "\[origin/" || echo "⚠️ No tracking set!"
   ```

4. **Include tracking in git status**:
   ```bash
   git status -sb  # Shows branch and tracking info
   ```

---

**Last Updated**: 2025-11-17
**Applies To**: Git 2.0+
**Related**: PR workflow, branch management, remote tracking
