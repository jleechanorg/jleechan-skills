---
description: Create a minimax-only agent team with haiku for work
type: agent-orchestration
execution_mode: immediate
---

## EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**

1. Parse the user's prompt from the command arguments
2. Create tasks using `TaskCreate` for each subtask (one per worker lane)
3. Spawn subagents using ONLY minimax-pair-coder / minimax-pair-verifier agent types (uses claudem() from bashrc) — NO sonnet or opus
4. Execute the requested work using the team

> **Note (added 2026-06-27)**: Earlier versions of this skill called `TeamCreate` as step 1. That primitive is NOT available in the current Claude Code session — `TeamCreate` is not in the tool list, and the `Agent` tool's `team_name` parameter is documented as deprecated. Skip the "create team" step entirely and dispatch `Agent` calls directly with `run_in_background=true` and a unique `name` per teammate.

## IMPORTANT: HOW MINIMAX WORKS

This command uses your `claudem()` bash function from ~/.bashrc which sets:
- `ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"`
- `ANTHROPIC_MODEL="MiniMax-M2.5"`
- `ANTHROPIC_SMALL_FAST_MODEL="MiniMax-M2.5"`

The `minimax-pair-coder` and `minimax-pair-verifier` agent types invoke `claudem()` internally.

## TEAM-MINI COMMAND

Usage: `/team-mini <prompt>`

This command creates a Claude team that uses ONLY:
- **MiniMax-M2.5** via `claudem()` bash function (minimax-pair-coder, minimax-pair-verifier)
- **Haiku** for quick/simple tasks (`model: "haiku"` in Task calls)

**NOT allowed:** sonnet, opus, or default Claude models (sonnet/opus will cost more)

### Pre-spawn verification for AO workers (CRITICAL)

If the task involves `ao spawn` for a PR-targeted worker, you MUST verify clone-before-spawn:

1. **Check if PR clone exists**: If spawning for a specific PR number, verify an isolated clone branch exists via `git fetch origin refs/pull/<PR>/head:<clone-branch>` before spawning
2. **Verify current branch**: Before `ao spawn`, confirm `git branch --show-current` is the CLONE branch, not the original PR branch
3. **Spawn AFTER clone**: `ao spawn` must come AFTER `git fetch` + `git checkout <clone>`, not before

**Why**: `ao spawn` does NOT create isolated PR clones — it lands on the current worktree branch. Without cloning first, workers push commits directly to live PRs.

### Execution Steps:

1. **Create tasks** for each worker lane (skip TeamCreate — not callable here).

2. **Spawn workers with model restrictions:**
   - Use `minimax-pair-coder` for main work (MiniMax-M2.5 via claudem)
   - Use `minimax-pair-verifier` for verification (MiniMax-M2.5 via claudem)
   - For simple quick tasks, use `model: "haiku"` in Task calls

3. **Execute the user's prompt** using the team — apply clone-before-spawn verification for any AO worker tasks

4. **Shutdown team** when complete

### Example:
```
/team-mini Write a test file that logs model usage to /tmp/test.log
```
