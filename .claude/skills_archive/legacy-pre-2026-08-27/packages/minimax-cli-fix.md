# ⚠️ STALE — DO NOT TRUST THIS SKILL ⚠️

**Archived 2026-06-13.** This skill recommends `MiniMax-M2.5` (and `M2.5` for `ANTHROPIC_SMALL_FAST_MODEL`), but **the current `claudem` wrapper in `~/.bashrc` uses `MiniMax-M3` — and M3 is the correct, working model** (verified live at `https://api.minimax.io/v1/models`).

**Why this skill is wrong:** It was written before the user's bashrc was tuned to `M3`. The model name was changed and the skill was not updated. The "model may not exist" TUI error in Claude Code v2.1.177 is the **Claude Max session-limit error** (resets ~3:40pm), not a real validation failure — do not change model names to chase it.

**Authoritative source of truth (in order):**
1. `~/.bashrc` `claudem()` — the actually-working wrapper
2. `https://api.minimax.io/v1/models` — the live model registry
3. `~/.claude/projects/-Users-$USER/memory/feedback_2026-06-13_dont_second_guess_working_setup.md` — the post-mortem
4. **This archived skill — DO NOT TRUST.** M3 is real. M2.5 is the wrong fix.

If you came here to "fix" a TUI error: stop. Verify the model against the live API first.

---

# Running Claude with MiniMax

**Usage**: Use this skill when you need to run Claude Code CLI with MiniMax API.

## Quick Start

In an interactive shell, use the `claudem` bash function:

```bash
claudem --version
claudem -p "Your prompt here"
```

## Environment Variables

The `claudem` function sets these required variables:

```bash
ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY"  # NOT ANTHROPIC_API_KEY
ANTHROPIC_MODEL="MiniMax-M2.5"
ANTHROPIC_SMALL_FAST_MODEL="MiniMax-M2.5"
API_TIMEOUT_MS="3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
```

## Common Commands

```bash
# Version check
claudem --version

# Interactive prompt
claudem -p "Explain this code"

# With specific prompt file
claudem -p @/path/to/prompt.txt

# Continue previous conversation
claudem --continue

# Skip permissions (for automation)
claudem --dangerously-skip-permissions -p "Your prompt"
```

## Troubleshooting

If you get "quota/rate limit" errors:
1. Verify `MINIMAX_API_KEY` is set: `echo $MINIMAX_API_KEY`
2. Check `ANTHROPIC_AUTH_TOKEN` is being used (not `ANTHROPIC_API_KEY`)
3. Ensure `ANTHROPIC_BASE_URL` is set to `https://api.minimax.io/anthropic`
