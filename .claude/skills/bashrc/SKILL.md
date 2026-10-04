---
name: bashrc
description: "Safe wrapper and settings editing playbook for ~/.bashrc — hardening protocol for editing Claude/claude CLI wrappers and model routing without breaking base claude behavior. Slash command: /bashrc."
scope: user
---

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

### Second failure: proxy-binary PATH guards go stale silently (2026-09-09)

- `~/.bashrc` had `if [ -x "$NVM_DIR/versions/node/v22.22.0/bin/codex" ]; then path_prepend_once ...; fi`
  intended to expose that nvm bin dir on `PATH`. The dir also held `codex-auth`
  (an unrelated npm package, the account switcher behind the `ca`/`csw`/`cstatus`
  aliases), which rode along on the same prepend.
- When the `codex` CLI's real install moved to a Claude plugin cache path (a bash
  function wrapping `command codex`), the guard's target file stopped existing.
  The guard silently stopped firing — `codex` didn't need it anymore, but
  `codex-auth` did, and lost its only `PATH` entry point with zero error output.
- Same stale-proxy pattern existed on a second machine (jeff-ubuntu), working only
  by luck because `codex` still happened to exist under nvm there.
- Root cause: the guard tested a *different* tool's existence as a cheap proxy for
  "is this directory worth adding to PATH," instead of testing the tool it was
  actually meant to protect.

## Before editing — history checks

- Run `/history "bashrc minimax minimax_M3 claude settings.json" --recent 14` to confirm recent context.
- Run `/ms "claude ANTHROPIC_BASE_URL MINIMAX_API_KEY"` to check if there is prior recovery notes.
- If either output shows unresolved confusion, pause and resolve before editing.

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
- Gating a `PATH`-prepend (`[ -x path/to/bin/<X> ]`) on a *different* binary's
  existence as a proxy for "is this directory good." Test the tool actually being
  protected (or test the directory itself), never a stand-in command that happens
  to share the same `bin/` — if the stand-in's install location ever moves, every
  other tool riding on that guard silently loses its `PATH` entry with no error.

## Preventing stale proxy guards

- When installing, moving, or reinstalling any CLI tool, grep both `~/.bashrc`
  and `~/.zshrc` for `-x .*bin/<toolname>` conditionals — anywhere that tool's
  name appears as an existence-check target, not just where it's the tool being
  installed. If the guard's target file no longer matches reality, fix or remove
  the guard, and check whether any *other* alias/binary was piggy-backing on that
  same `path_prepend_once` call.
- After any such edit, resolve every alias defined near the touched region in a
  real interactive shell — `bash -i -c 'alias <name>; command -v <target>'` — not
  just `bash -lc` (aliases don't expand in non-interactive shells even with `-l`,
  which can mask a real break as a false pass).

## Post-change acceptance checklist

- `~/.bashrc` changed only for wrapper function(s) unless explicitly asked to touch `~/.claude/settings.json`.
- Baseline `claude` path and wrapper `claudem` path are distinguishable.
- Environment stack for each entry point is documented in commit notes.
- Fresh shell smoke tests pass.
- Every `[ -x path/to/bin/<X> ]` PATH guard touched (or newly adjacent to an edit)
  tests the tool it's actually meant to protect, not a proxy binary that could move.
- If multiple machines share this pattern (e.g. Mac + jeff-ubuntu), the same check
  was re-verified on each — a guard working on one machine "by luck" is not proof
  it's correct on another.

## Record change summary

In the final note include:
- files changed,
- expected model path per command,
- exact validation commands + results.

If invoked without edit intent, treat this as a checklist and stop before mutating files.
