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
