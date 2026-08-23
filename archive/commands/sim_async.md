---
description: Async A/B simulation - runs predictions via claude -p subprocess
type: ai
execution_mode: immediate
---
## EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately.**

This is the "async" version that assembles context and pipes it to a separate `claude -p` Sonnet instance. Use `/sim` for the faster inline version.

## EXECUTION WORKFLOW

### Phase 1: Gather Conversation Context

**Action Steps:**
1. Determine the current working directory (cwd)
2. Find the Claude project conversation directory by converting the cwd path: replace `/` with `-` (e.g., `/home/user/projects/myrepo` becomes `~/.claude/projects/-home-user-projects-myrepo/`)
3. Find the most recent large JSONL file (sort by mtime, pick the biggest recent one)
4. Extract the last 5-8 user messages from that file using `tail -200` + JSON parsing
5. If arguments were provided (e.g., `/sim_async streaming convo`), use those as additional context

### Phase 1.5: Gather Workflow State (P6)

**Run these commands IN PARALLEL to gather current workflow state:**

1. **Git status:** `git status --porcelain=v2 --branch` — determines clean/dirty, branch name, ahead/behind
2. **PR info:** `gh pr view --json number,state,mergeable,statusCheckRollup,isDraft 2>/dev/null || echo "NO_PR"` — PR existence, status, CI
3. **Commits ahead of remote:** `git rev-list --count origin/$(git branch --show-current)..HEAD 2>/dev/null || echo "0"` — whether already pushed
4. **Commits behind main:** `git rev-list --count HEAD..origin/main 2>/dev/null || echo "0"` — drift from main

**Parse results into this structured format:**
```
[WORKFLOW_STATE]
GIT_CLEAN: <true if no modified/untracked files>
PR_EXISTS: <true/false>
PR_STATUS: <OPEN/MERGED/CLOSED/NONE>
PR_NUMBER: <number or NONE>
CI_STATUS: <PASSING/FAILING/PENDING/NONE>
CI_FAILING_CHECKS: <list of failing check names, or empty>
BRANCH: <current branch name>
AHEAD_OF_REMOTE: <number of unpushed commits, 0 = already pushed>
BEHIND_MAIN: <number of commits behind main>
STATUSLINE: [Local: <branch> | Remote: <upstream> | PR: <number> <url>]
```

### Phase 1.9: Cache Context for Reuse

**After gathering conversation history and workflow state, save to `/tmp/genesis_sim_context/` for reuse:**

1. `mkdir -p /tmp/genesis_sim_context`
2. Write `/tmp/genesis_sim_context/context.txt` — the full formatted context section (conversation history + workflow state)

This enables `python3 genesis/scripts/sim_ab_benchmark.py --cached` to reuse the same context.

### Phase 2: Run TWO Predictions (A/B)

**Always run BOTH a baseline and the full prompt, using the SAME context gathered above.**

#### Prompt A (Baseline)

Build a minimal prompt — just the conversation history + workflow state + a simple instruction:

```
You are predicting what a developer will type next in a Claude Code CLI session.

Here is the conversation history:
<full conversation history from Phase 1>

Current state:
<workflow state from Phase 1.5>

What is the most likely next message this user will type? Output ONLY the predicted message, nothing else. No explanation, no quotes, no markdown - just the raw text.
```

Pipe to `claude -p --model sonnet` via Bash. Save prompt to `/tmp/genesis_sim_context/prompt_baseline.txt`.

#### Prompt B (Latest v2.2)

1. Read the simulation prompt file: `genesis/jleechan_simulation_stage2_predict.md` (from project root)
2. Append the SAME conversation history and workflow state gathered in Phase 1/1.5
3. Append the task instruction:

```
### YOUR TASK:
Based on everything above, generate EXACTLY ONE predicted next prompt this user would type. Output ONLY the predicted prompt, nothing else. No explanation, no analysis, no markdown formatting, no quotes - just the raw prompt text as the user would type it.
```

Pipe to `claude -p --model sonnet` via Bash. Save prompt to `/tmp/genesis_sim_context/prompt_v22.txt`.

### Phase 3: Display Results

**Show both predictions side by side:**

```
============================================================
WORKFLOW STATE:
  Branch: <branch> | PR: <#number status> | CI: <status> | Git: <clean/dirty>
============================================================
A (baseline):  <baseline prediction>
B (v2.2):      <v2.2 prediction>
============================================================
```

### Notes
- Use `sonnet` model for both prompts (not haiku - quality matters)
- The simulation prompt is at `genesis/jleechan_simulation_stage2_predict.md` relative to project root
- Both prompts get the IDENTICAL conversation history and workflow state - the only difference is the system prompt
- If the JSONL conversation files aren't found, just use whatever context the user provided as args
- The workflow state is CRITICAL for accuracy — it prevents predicting already-completed actions
- If gh CLI or git commands fail, set those fields to UNKNOWN and continue
- The purpose of A/B is to measure whether the elaborate prompt is actually better than just asking directly

ARGUMENTS: $ARGUMENTS
