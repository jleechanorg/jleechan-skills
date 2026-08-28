---
description: Guidelines for autonomous execution in automation/orchestration contexts
type: usage
scope: project
---

# Autonomous Execution Guidelines

## Purpose
Provide clear guidelines for agents running in autonomous automation contexts (tmux sessions, background agents, orchestration workflows) where human interaction is not available.

## Activation cues
- Running in tmux session spawned by orchestration system
- Executing as part of automated PR fixing (fixpr, fixcomment workflows)
- Background agent tasks with no interactive terminal
- Any automation context where asking questions blocks progress

## Core Principle

**Success = Remote commits pushed**

In autonomous contexts:
- Exit 0 without commits = FAILURE
- Asking questions without proceeding = FAILURE
- Stopping for user input = FAILURE

## Critical Rules for Autonomous Execution

### 1. Git Dirty State Handling

**If you encounter unexpected staged changes or modified files after checkout:**

```bash
# Step 1: Inspect to understand context
git status
git diff --stat

# Step 2: Decide based on context
# - Previous failed run artifacts? → Clean
# - Irrelevant files (.beads/, temp files)? → Clean
# - Related to current PR? → Inspect and integrate

# Step 3: Clean automatically (NEVER ask user)
git reset --hard origin/<branch-name>
git clean -fd

# Step 4: Proceed with task
```

**CRITICAL**: 
- ✅ ALWAYS handle dirty state automatically
- ✅ Clean and proceed, don't block
- ❌ NEVER ask "Do you want me to keep/stash/discard?"
- ❌ NEVER stop with "Per instructions, I have to stop"

### 2. Decision Making

**Make autonomous decisions within task scope:**

- ✅ Clean dirty git state automatically
- ✅ Choose between equivalent approaches
- ✅ Fix obvious issues without confirmation
- ✅ Determine which tests to run
- ✅ Decide commit message phrasing

**Only ask questions for:**
- ❓ Ambiguous requirements affecting correctness
- ❓ Multiple valid architectural approaches with tradeoffs
- ❓ User preference choices that impact UX

**NEVER ask about:**
- ❌ Operational details (git state, temp files, etc.)
- ❌ Obvious bug fixes
- ❌ Standard code formatting/style choices
- ❌ Test execution strategy

### 3. Working Directory Assumptions

**In automation contexts, assume:**

- Working directory is temporary (`/tmp/your-project.com/pr-*`)
- Dirty state is safe to clean/reset
- Previous run artifacts can be discarded
- No valuable uncommitted work exists

**Therefore:**
- Clean aggressively without asking
- Reset to clean state if uncertain
- Focus on completing task, not preserving unknown state

### 4. Error Recovery

**When encountering issues:**

```python
# WRONG: Stop and ask
"I hit an error. Should I retry or abort?"

# RIGHT: Attempt recovery automatically
try_alternative_approach()
if still_fails:
    log_error_and_exit_1()  # Let orchestration system handle fallback
```

### 5. Success Criteria

**Only exit 0 if:**
- ✅ Remote commits pushed to PR branch
- ✅ All requested changes implemented
- ✅ Tests pass (if required by task)

**Exit 1 if:**
- ❌ Unable to make commits due to technical issue
- ❌ Tests fail and cannot be fixed
- ❌ Actual blocker preventing completion

**NEVER:**
- ❌ Exit 0 after asking question without proceeding
- ❌ Exit 0 with "I need more information to continue"
- ❌ Exit 0 with "waiting for user response"

## Examples

### ✅ CORRECT: Autonomous Dirty State Handling

```bash
# Agent encounters dirty state
git status
# On branch feature-x
# Changes not staged for commit:
#   modified: $PROJECT_ROOT/agents.py
#   modified: .beads/issues.jsonl

# Agent analyzes context
git diff --stat
# $PROJECT_ROOT/agents.py | 2 +-
# .beads/issues.jsonl | 1 +

# Agent decides: artifacts from previous run, safe to clean
git reset --hard origin/feature-x
git clean -fd

# Agent proceeds with task
gh pr checkout 123
# ... continues fixing PR
# ... makes commits
git push
# ✅ Exit 0 with commits made
```

### ❌ WRONG: Stopping to Ask

```bash
# Agent encounters dirty state
git status
# Changes not staged for commit:
#   modified: $PROJECT_ROOT/agents.py

# Agent stops and asks
"I hit unexpected local changes. Per instructions, I have to stop.
Do you want me to: 1) keep, 2) stash, 3) discard?"

# ❌ Exit 0 without making commits
# This is a FAILURE in automation context
```

### ✅ CORRECT: Autonomous Decision Making

```bash
# Agent fixing PR with multiple test failures

# Analyzes failures
./run_tests.sh $PROJECT_ROOT/tests/test_agents.py
# FAILED: test_faction_enablement (wrong field name)
# FAILED: test_minigame_settings (wrong field name)

# Makes autonomous decisions
# - Both failures: same root cause (factionMinigameEnabled → faction_minigame_enabled)
# - Fix: change all instances to snake_case
# - Tests to run: test_agents.py (directly affected)

# Implements fix
Edit $PROJECT_ROOT/agents.py (change field names)
Edit $PROJECT_ROOT/tests/test_agents.py (change test field names)

# Verifies
./run_tests.sh $PROJECT_ROOT/tests/test_agents.py
# ✅ All tests pass

# Commits and pushes
git add -A
git commit -m "[codex-automation-commit] fix PR #4018: correct field name to faction_minigame_enabled"
git push
# ✅ Exit 0 with commits made
```

## Integration with Other Skills

- **pr-workflow-manager**: Use PR workflow best practices, but handle dirty state autonomously
- **receiving-code-review**: Implement feedback, clean state automatically
- **build-test-lint-autopilot**: Run tests, decide which to execute autonomously

## Monitoring and Debugging

When running autonomously, provide clear logging:

```bash
echo "[AUTONOMOUS] Detected dirty state, cleaning automatically"
echo "[AUTONOMOUS] Decided to reset to origin/branch-name"
echo "[AUTONOMOUS] Proceeding with PR fixes after clean"
```

This helps debugging while maintaining autonomous execution.

## Summary

**In autonomous contexts:**
1. Handle dirty state automatically (clean and proceed)
2. Make decisions within task scope
3. Only exit 0 if commits are pushed
4. Never stop to ask operational questions
5. Provide clear logging for debugging

**Remember**: Automation contexts have no human watching. Asking questions = blocking forever = failure.
