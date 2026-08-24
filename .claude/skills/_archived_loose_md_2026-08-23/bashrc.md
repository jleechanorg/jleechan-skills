# Bashrc Maintenance

## Purpose

Provide a hardening playbook for editing `~/.bashrc` safely, especially around
Claude/claude wrappers and model routing.

## Problem pattern from recent failures

### What broke

- `claudem()` was fixed, but plain `claude` still came from `~/.claude/settings.json`
  forcing MiniMax.
- Config was changed in one place (`~/.bashrc`) without checking all active config
  layers (`~/.claude/settings.json`, aliases, shell env exports).
- A debug command was executed with ungrouped `|` redirections, creating misleading
  `...: command not found` noise.

### Why it happened

- Missing precedence check across configuration layers.
- No explicit pre-change checklist.
- No final validation proving wrapper and base command use different env stacks.

## Safe edit protocol (required)

1. Read current values first

```bash
sed -n '1,220p' ~/.bashrc
cat ~/.claude/settings.json
cat ~/.claude/commands/claude* 2>/dev/null
```

2. Decide the intended ownership of each variable

- `~/.claude/settings.json`: global baseline for `claude`.
- `~/.bashrc`: explicit shell aliases/functions (for `claudem`, `claudee`, etc.).
- Never mix responsibilities.

3. Make only scoped edits

- If changing `claude` behavior, update `~/.claude/settings.json` only.
- If adding/switching a wrapper (for example `claudem`), keep it in `~/.bashrc` and
  avoid touching base `claude`.

4. Validate with a clean check matrix before ending

```bash
env | rg 'ANTHROPIC_BASE_URL|ANTHROPIC_MODEL|MINIMAX_API_KEY|ANTHROPIC_AUTH_TOKEN'
declare -f claude claudem || true
bash -lc "source ~/.bashrc >/dev/null 2>&1; declare -f claude; declare -f claudem"
```

5. Smoke test both entry points in a fresh shell

```bash
bash -lc "source ~/.bashrc >/dev/null 2>&1; claude --help >/tmp/claude_help.txt; head -n 2 /tmp/claude_help.txt"
bash -lc "source ~/.bashrc >/dev/null 2>&1; claudem --version"
```

6. Verify command outputs match intent

- `claude` should reflect default Anthropic settings from settings file (or explicit
  `--model` override).
- `claudem` should show `MiniMax-*` env in function output.

## Mandatory command ordering

When asked, always use `/history` and `/ms` before editing again:

- `/history "bashrc minimax anthropic model" --recent 14`
- `/ms "claude minimax ANTHROPIC_BASE_URL MINIMAX_API_KEY"`

If either search indicates unresolved assumptions, stop and reconcile before editing.

## Template for wrapper edits (copy this pattern)

```bash
claudem() {
  ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic" \
  ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY" \
  ANTHROPIC_MODEL="MiniMax-M3" \
  ANTHROPIC_SMALL_FAST_MODEL="MiniMax-M3" \
  claude --dangerously-skip-permissions --teammate-mode=tmux "$@"
}
```

## Anti-patterns

- Editing only `.bashrc` and assuming it controls all Claude behavior.
- Adding raw `ANTHROPIC_*` values to one layer without checking the other.
- Running shell greps with unescaped pipes in one-liners.
- Relying on output from `tmux`/shell without checking command exit codes and source context.

## Post-change acceptance checklist

- `~/.bashrc` changed only for wrapper function(s) unless explicitly asked to touch `~/.claude/settings.json`.
- Baseline `claude` path and wrapper `claudem` path are distinguishable.
- Environment stack for each entry point is documented in commit notes.
- Fresh shell smoke tests pass.
