---
name: superpowers-using-git-worktrees
description: Use when starting feature work that needs isolation from current workspace or before executing implementation plans - creates isolated git worktrees with smart directory selection and safety verification
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

## Directory Selection Process

Follow this priority order:

### 1. Honor the user and repository preference

Use the location specified by the user or applicable repository instructions
without asking again. If neither specifies a location, continue below.

### 2. Check Existing Directories

```bash
# Check in priority order
ls -d .worktrees 2>/dev/null     # Preferred (hidden)
ls -d worktrees 2>/dev/null      # Alternative
```

**If found:** Use that directory. If both exist, `.worktrees` wins.

### 3. Choose an isolated default

If the user or repository specifies no location, choose a unique directory
outside the active checkout using `mktemp -d`, and report the absolute path.
Routine worktree placement does not need a new approval. Ask only if a real
storage/access constraint prevents an appropriate isolated location.

## Safety Verification

### For Project-Local Directories (.worktrees or worktrees)

**MUST verify directory is ignored before creating worktree:**

```bash
# Check if a project-local directory is ignored (respects local, global, and system gitignore)
# External paths (outside repo root) are already isolated and must not be checked or added to info/exclude.
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -n "$repo_root" ]; then
  abs_location=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$LOCATION" 2>/dev/null || true)
  abs_repo=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$repo_root" 2>/dev/null || true)
  if [[ -n "$abs_repo" && -n "$abs_location" && "$abs_location" == "$abs_repo"/* ]]; then
    git check-ignore -q "$abs_location" 2>/dev/null
    rc=$?
    if [ "$rc" -eq 1 ]; then
      exclude_file=$(git rev-parse --git-path info/exclude 2>/dev/null || true)
      if [ -n "$exclude_file" ]; then
        rel_entry="${abs_location#$abs_repo/}"
        mkdir -p "$(dirname "$exclude_file")"
        echo "$rel_entry" >> "$exclude_file"
      fi
    fi
  fi
fi
```

**If NOT ignored (for a project-local directory):**

For a user- or repository-selected project-local location inside the repository (where `git check-ignore` exited 1), authorized worktree setup includes adding its exact ignore entry to the repository-local `info/exclude` file (`git rev-parse --git-path info/exclude`), unless an explicit policy prohibits that change. Preserve unrelated entries and verify the selected path is ignored.

Never add external directories (such as paths outside the repository created by `mktemp -d`) to `info/exclude`. An external path causes `git check-ignore` to exit with status 128 rather than 1, and external paths are already outside the project tree.

Use an external location only when no location was specified, or when the user or repository permits that fallback. Ask only if an explicit constraint makes the selected location unusable; continue independent authorized work meanwhile. No unrelated tracked configuration commit is needed.

**Why critical:** Prevents accidentally committing worktree contents to repository.

### For directories outside the repository

No .gitignore verification needed - outside project entirely.

## Creation Steps

### 1. Create Worktree

```bash
worktree_path="$LOCATION/$BRANCH_NAME"

# Select the base ref from repository policy or the user's explicit instruction.
# Use HEAD only when neither provides a base.
BASE_REF="${BASE_REF:-HEAD}"
git worktree add "$worktree_path" -b "$BRANCH_NAME" "$BASE_REF"
cd "$worktree_path"
```

### 2. Run Project Setup

Use the repository's documented bootstrap and existing environment. Preserve
its package manager, lockfiles, and shared-venv requirements. Inspect the relevant
manifest only when setup is undocumented, and install/build only prerequisites
needed for the scoped task; do not run every recognized package manager or create
a duplicate per-worktree environment.

### 3. Verify Clean Baseline

Run the smallest repository-approved baseline checks covering the task. Respect
restrictions on full local suites and use documentation checks for docs-only work.

**If tests fail:** Capture and classify failures, investigate relevant failures,
and continue authorized work. Distinguish pre-existing failures from regressions;
ask only for missing authority or an unresolved decision that changes the task.

**If tests pass:** Report ready.

### 4. Report Location

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Proceeding with <next authorized task action>
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check repository policy, then choose an external unique directory |
| Selected project-local directory not ignored | Add its exact local exclude entry unless prohibited; never add external paths |
| Tests fail during baseline | Capture, classify, and investigate within scope |
| Setup is needed | Follow the repository bootstrap and shared environment |

## Common Mistakes

### Skipping ignore verification

- **Problem:** Worktree contents get tracked, pollute git status
- **Fix:** Always use `git check-ignore` before creating project-local worktree

### Assuming directory location

- **Problem:** Creates inconsistency, violates project conventions
- **Fix:** Follow priority: user/repository preference > existing isolated directory > external unique directory

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Capture baseline failures and classify them before claiming a later change is a regression or a fix

### Hardcoding setup commands

- **Problem:** Breaks on projects using different tools
- **Fix:** Use the documented project bootstrap before deriving setup from manifests

## Example Workflow

```
You: I'm using the using-git-worktrees skill to set up an isolated workspace.

[Check .worktrees/ - exists]
[Verify ignored - git check-ignore confirms .worktrees/ is ignored]
[Create worktree from the repository's configured base ref]
[Run the repository bootstrap if needed]
[Run scoped baseline checks - 47 passing]

Worktree ready at /Users/jesse/myproject/.worktrees/auth
Tests passing (47 tests, 0 failures)
Proceeding with the authorized auth implementation
```

## Red Flags

**Never:**
- Create worktree without verifying it's ignored (project-local)
- Skip baseline test verification
- Hide failing baseline checks or claim a clean baseline without evidence
- Override the user's or repository's worktree location
- Skip applicable repository worktree instructions

**Always:**
- Follow the user's and repository's directory preference, then choose a safe default
- Verify directory is ignored for project-local
- Use the repository setup and shared environment
- Verify clean test baseline

## Integration

**Called by:**
- **brainstorming** (Phase 4) - REQUIRED when design is approved and implementation follows
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** - Verify and deliver the authorized result; preserve the worktree unless cleanup is authorized
- **executing-plans** or **subagent-driven-development** - Work happens in this worktree
