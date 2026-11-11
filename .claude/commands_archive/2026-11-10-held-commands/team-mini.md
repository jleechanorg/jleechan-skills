---
description: MiniMax-M3 fan-out for parallel work on a specific prompt
execution_mode: immediate
---

`/team-mini` runs the user's `<prompt>` on a fan-out of MiniMax-M3 coding
subagents. Subagents run in isolated git worktrees (or in shared session work
when no source-code writes are needed) and report back diff-stat / test counts
/ branch URLs. Use this when you want a cheap, parallel attempt at a coding
task and you trust each subagent to make an independent choice.

## How MiniMax enters Claude Code

`~/.bashrc` defines `claudem()`, which invokes the MiniMax-backed Claude
build:

```bash
claudem() {
  ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic" \
  ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY" \
  ANTHROPIC_MODEL="MiniMax-M3" \
  ANTHROPIC_SMALL_FAST_MODEL="MiniMax-M3" \
  claude --dangerously-skip-permissions --teammate-mode=tmux --model MiniMax-M3 "$@"
}
```

Three `subagent_type` values invoke `claudem()`:

| Agent type | Backed by | Use for |
|---|---|---|
| `minimax-pair-coder` | `claudem()` | Implementation (TDD, refactor, fix) |
| `minimax-pair-verifier` | `claudem()` | Code review, test-verification |
| `minimax` (default) | `claudem()` | Generic MiniMax task |

## Execution steps

1. **Decompose** the user's prompt into 2–6 independent subtasks. Subtasks
   must NOT contend on the same files; each must own its own slice.
2. **Fan out in a single message** — every `Agent` call in one block runs
   concurrently:

```python
Agent(
    subagent_type="minimax-pair-coder",
    isolation="worktree",        # fresh git worktree, auto-cleaned if unchanged
    run_in_background=true,
    name="<short-task-id>",
    description="<5-10 words>",
    prompt="""
You are a MiniMax-M3 coder working on <repo>.
Open a fresh worktree in /tmp/wt-<id> from origin/main.
<scope, constraints, exact file/line refs, expected diff stat>
Commit with prefix 'minimax: <subject>'. Push branch <id>/<topic>.
Do NOT merge to main. Report: diff stat, test delta, branch URL.
If blocked, STOP and report the blocker.
""",
)
```

3. **Use `minimax-pair-verifier`** for any task whose correctness matters and
   whose review is independent (e.g. concurrent with the fix worker, before
   merge). Pair-coder + pair-verifier in the SAME message = independent code
   and review in parallel.
4. **Aggregate** the results when agents complete. Do NOT auto-merge — send
   the user the branch URLs and let them pick what to fast-forward.

## Model rules

- Default: MiniMax-M3 (`claudem()`). No Sonnet, no Opus.
- For trivial reads/scans/formatting, set `model="haiku"` on a plain `Agent`
  call. **Do NOT pass `model` to `Agent` with `subagent_type=minimax-*`** —
  those types already pin the model.
- Pass `effort` only if a task is unusually hard to score (not normal).
- This command is strict about cost. Sonnet/Opus fan-outs go through `/team-claude`
  instead.

## Pre-spawn gotchas (any worktree agent)

- Confirm the target repo URL/branch first. Read `git remote -v` and
  `git log origin/main -1`.
- If the user names a PR (`ao spawn` flow), still clone the repo locally
  first; `isolation="worktree"` clones from the **current branch**, not
  from the PR head. Use `git fetch origin refs/pull/<N>/head:<clone>`
  then `git checkout <clone>` BEFORE the Agent call.
- The worktree path appears in `/tmp/wt-<id>` by convention (auto-cleaned
  unless the agent pushed a branch).

## Failure modes and what to do

- Agent returns nothing / blank: re-spawn once with the same prompt, then
  if still blank, escalate to user with the worktree path so they can read
  the .output file.
- Named agents dead-register (in team config `members[]` but never poll their
  inbox — no task claim, no file changes, `isActive` never flips; #24108
  class, hit 3/3 on 2026-07-11): treat ~5 min of zero signals as suspicion,
  nudge once, allow a short grace, then send `shutdown_request`s and run the
  SAME MiniMax coders as direct background CLI calls — full `claudem()` env
  (`ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic`
  `ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY"` `ANTHROPIC_API_KEY="$MINIMAX_API_KEY"`
  `ANTHROPIC_MODEL=MiniMax-M3`) + `claude --dangerously-skip-permissions -p`,
  WITHOUT `--teammate-mode=tmux`. Auth vars are REQUIRED — omitting them
  routes the call to the default account/model. Never start the fallback
  while a possibly-live lane may write the same files. Proven fallback:
  memory `teams-lanes-dead-minimax-cli-fallback`.
- Agent pushed to wrong branch: ask user how to handle, do not auto-clean.
- Two agents collide on the same files: stop both, re-decompose, re-spawn.

## Usage

```
/team-mini <prompt>
```

The `<prompt>` is interpreted as a high-level goal; decompose first, then fan
out. `Agent` is the spawn primitive. `TeamCreate` does NOT exist (removed in
claude-code v2.1.178 — every session has one implicit team; `name:` on the
Agent call is what makes a teammate, and `team_name` is deprecated/ignored).
`TaskCreate` / `TaskUpdate` / `TaskList` / `SendMessage` DO exist as deferred
tools — load them via ToolSearch (`select:TaskCreate,TaskUpdate,SendMessage`)
before use. Tool availability claims are version snapshots (locally verified
on claude-code ~v2.1.19x, 2026-07-11): re-verify via ToolSearch at runtime
rather than trusting this file if the CLI has since updated.
