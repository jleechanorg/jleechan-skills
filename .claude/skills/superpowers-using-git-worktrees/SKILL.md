---
name: superpowers-using-git-worktrees
description: Use when starting feature work that needs isolation from current workspace or before executing implementation plans - creates isolated git worktrees with smart directory selection and safety verification
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Use the shared worktree creator and its canonical isolated location.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

## Location and safety

Create worktrees with `diskm worktree-new` under the shared canonical root
`~/.worktrees/<repo>/<name>`, as required by
[worktree-protection](../worktree-protection/SKILL.md). The shared creator owns
path selection and worktree registration. Do not select project-local paths,
create a temporary worktree directory, edit `info/exclude`, or call raw
`git worktree add`.

Before creation, inspect the source checkout's branch and status. Preserve
unrelated dirty files and uncommitted work; do not reset, stash, or clean them
to make worktree creation succeed. After creation, verify the reported path,
branch, base commit, and clean status of the new checkout.

## Creation Steps

### 1. Create Worktree

```bash
diskm worktree-new <repo-path> <branch> --base <base-ref> --name <name>
```

The command prints the canonical worktree path. Change into that returned
directory before continuing. Select the base ref from repository policy or the
user's explicit instruction.

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
| Need a worktree | Use `diskm worktree-new` under `~/.worktrees/<repo>/<name>` |
| Source checkout has unrelated dirty work | Preserve it and continue without resetting or cleaning |
| Tests fail during baseline | Capture, classify, and investigate within scope |
| Setup is needed | Follow the repository bootstrap and shared environment |

## Common Mistakes

### Bypassing the shared worktree creator

- **Problem:** A hand-selected path or raw Git command can violate shared placement and registration rules.
- **Fix:** Use `diskm worktree-new` and verify its returned path and branch.

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Capture baseline failures and classify them before claiming a later change is a regression or a fix

### Hardcoding setup commands

- **Problem:** Breaks on projects using different tools
- **Fix:** Use the documented project bootstrap before deriving setup from manifests

## Example Workflow

```
You: I'm using the using-git-worktrees skill to set up an isolated workspace.

[Inspect the source checkout's branch and dirty status; preserve unrelated work]
[Create with diskm worktree-new from the repository's configured base ref]
[Verify the returned canonical path, branch, base commit, and clean new checkout]
[Run the repository bootstrap if needed]
[Run scoped baseline checks - 47 passing]

Worktree ready at ~/.worktrees/myproject/auth
Tests passing (47 tests, 0 failures)
Proceeding with the authorized auth implementation
```

## Red Flags

**Never:**
- Bypass `diskm worktree-new` with a project-local path or raw `git worktree add`
- Skip baseline test verification
- Hide failing baseline checks or claim a clean baseline without evidence
- Discard source-checkout work to make worktree creation succeed
- Skip applicable repository worktree instructions

**Always:**
- Use the canonical shared worktree root and creator
- Inspect and preserve source-checkout changes
- Use the repository setup and shared environment
- Verify clean test baseline

## Integration

**Called by:**
- **brainstorming** (Phase 4) - REQUIRED when design is approved and implementation follows
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** - Verify and deliver the authorized result; preserve the worktree unless cleanup is authorized
- **executing-plans** or **subagent-driven-development** - Work happens in this worktree
