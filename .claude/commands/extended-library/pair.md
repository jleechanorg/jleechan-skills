---
description: Launch ralph-pair (coder + deterministic verifier)
argument-hint: '[max_iterations]'
---

# /pair — Ralph with Deterministic Verification

Runs `ralph-pair.sh`, which is ralph.sh with an added verification step after each coder iteration.

## What it does

1. **Coder phase** — same as ralph: pipe PRD + CLAUDE.md to the agent
2. **Verifier phase** — runs `verifyCommand` for every unpassed story
3. Auto-marks stories as `passes: true` when their verifyCommand succeeds
4. When verify story VN passes, also marks paired implement story SN
5. Repeats until ALL stories verified or max iterations reached

## Routing

When `/pair` is invoked, execute:

```bash
bash ralph/ralph-pair.sh run $ARGUMENTS
```

Forward any optional `/pair` arguments after `run` so custom iteration counts and flags are preserved.

## Usage

```bash
# Default: 10 iterations with claude
bash ralph/ralph-pair.sh run

# Custom: 3 iterations
bash ralph/ralph-pair.sh run 3

# With a different tool
bash ralph/ralph-pair.sh run --tool codex

# Check status
bash ralph/ralph-pair.sh status
bash ralph/ralph-pair.sh status --watch
```

## How it differs from ralph.sh

| | ralph.sh | ralph-pair.sh |
|---|---|---|
| Completion check | Trusts `<promise>COMPLETE</promise>` | Runs verifyCommand per story |
| Verification | None | Deterministic (pytest, etc.) |
| Auto-marking | Coder must update prd_state.json | Verifier auto-marks on pass |
