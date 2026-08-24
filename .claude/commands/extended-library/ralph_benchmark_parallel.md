---
description: ralph_benchmark_parallel
type: llm-orchestration
execution_mode: llm-driven
---

# Ralph Parallel Benchmark Command

This command runs Ralph and Ralph-Pair in parallel, both using Minimax Claude Code.

## Setup

Before running, set the workspace path:
```bash
export WORKSPACE_PATH=/path/to/your/ralph-workspace
```

## What to Do

### Step 1: Launch Ralph (Regular) in tmux

In a NEW tmux session, run:
```bash
# Launch Ralph with minimax in tmux
tmux new-session -d -s ralph-bench-minimax 'cd $WORKSPACE_PATH && claudem --dangerously-skip-permissions -p "Run the following task: Execute /loop 10 /e ralph_iteration. This runs Ralph iteration command which should generate the Amazon clone benchmark until it passes."'
```

Wait 3 seconds, then check if it started:
```bash
tmux list-sessions | grep ralph-bench
```

### Step 2: Launch Ralph-Pair in tmux

In ANOTHER NEW tmux session, run:
```bash
# Launch Ralph-Pair with minimax in tmux
tmux new-session -d -s ralph-pair-bench-minimax 'cd $WORKSPACE_PATH && claudem --dangerously-skip-permissions -p "Run the following task: Execute /loop 10 /e ralph_pair_iteration. This runs Ralph-Pair iteration command which should generate the Amazon clone benchmark with verification until it passes."'
```

Wait 3 seconds, then check if it started:
```bash
tmux list-sessions | grep ralph-pair-bench
```

### Step 3: Monitor Both Sessions

Check status of both:
```bash
echo "=== Ralph (Regular) ==="
tmux capture-pane -t ralph-bench-minimax -p | tail -20

echo ""
echo "=== Ralph-Pair ==="
tmux capture-pane -t ralph-pair-bench-minimax -p | tail -20
```

### Step 4: Wait for Completion

Both will iterate up to 10 times. Check periodically:
```bash
# Watch both sessions
tmux list-windows -t ralph-bench-minimax
tmux list-windows -t ralph-pair-bench-minimax
```

### Step 5: Verify Results

Both Ralph and Ralph-Pair write to the same evidence directory (they run in the same workspace):
```bash
# Check results - both sessions write to the same directory
ls -la ralph/benchmarks/evidence/ 2>/dev/null || echo "No evidence yet"
```

## Success Criteria

Both sessions should produce:
- `evidence/amazon_clone_flow.webm` - Captioned video
- `evidence/final_order_confirmation.png` - Screenshot
- `python3 -m pytest -q` passing

## Notes

- Ralph runs regular iteration (coder only)
- Ralph-Pair runs coder + verifier after each iteration
- Both use Minimax M2.5 via `claudem()`
- Both run in parallel in separate tmux sessions