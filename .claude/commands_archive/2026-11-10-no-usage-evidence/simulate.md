---
description: Predict next user prompt using $USER simulation
type: ai
execution_mode: immediate
---
## EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately.**

You already have the full conversation context. Use it directly — no JSONL parsing, no subprocess.

## EXECUTION WORKFLOW

### Step 1: Gather Workflow State

Run these commands IN PARALLEL to get current state:

1. `git status --porcelain=v2 --branch`
2. `gh pr view --json number,state,statusCheckRollup,isDraft 2>/dev/null || echo "NO_PR"`
3. `git rev-list --count origin/$(git branch --show-current)..HEAD 2>/dev/null || echo "0"`

### Step 2: Predict

Using your existing conversation context + workflow state, predict the next user message.

**Apply these guidelines:**

1. **What just happened?** What did the assistant last do? Did it succeed or fail?
2. **User's current goal?** What phase are they in? (SCOPING / IMPLEMENTATION / VERIFICATION / DEBUGGING / COMPLETION)
3. **Workflow constraints:** Don't predict "push to pr" if git is clean or no commits ahead. Don't predict "merge" if CI is failing.
4. **User's communication style:** Ultra-direct, imperative, no pleasantries. Terse. Authentic typos. Single-char responses ("c", "a", "y").
5. **Topic grounding:** At least 1 prediction must reference a specific topic from the conversation, not generic commands.
6. **Anti-vocab-collapse:** Don't default to the same 5 generic tokens (merge, push, continue, fix it, ok) unless the context actually supports them.
7. **Sequential patterns:** Look at last 3 user messages — what pattern are they in? (fix-verify-push, investigation loop, tight iteration)
8. **Answer detection:** If the assistant asked a question, predict the user's ANSWER, not a topic change.

### Step 3: Display Results

Output in this format:

```
============================================================
WORKFLOW STATE:
  Branch: <branch> | PR: <#number status> | CI: <status> | Git: <clean/dirty>
============================================================
PREDICTION:  <top prediction>
  ALT 1:     <second most likely>
  ALT 2:     <third most likely>
REASONING:   <1-2 sentences>
============================================================
```

### Notes
- Uses your existing conversation context directly — no subprocess, no `claude -p`
- For offline A/B benchmarking (baseline vs v2.2 with separate Sonnet instances): `python3 genesis/scripts/sim_ab_benchmark.py`

ARGUMENTS: $ARGUMENTS
