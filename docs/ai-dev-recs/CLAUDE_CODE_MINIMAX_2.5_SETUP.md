# Claude Code + MiniMax 2.5

Configure Claude Code to use MiniMax 2.5 as the model instead of Claude.

## Setup

Edit `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "<MINIMAX_API_KEY>",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_MODEL": "MiniMax-M2.5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M2.5"
  }
}
```

**Get API key:** https://platform.minimax.io/user-center/basic-information/interface-key

**Users in China:** Use `https://api.minimaxi.com/anthropic` as base URL.

## Why MiniMax 2.5?

| Model | Price |
|-------|-------|
| Claude Enterprise | $200/mo |
| **MiniMax 2.5** | **$20/mo** |

- Higher capacity than Claude Enterprise for 1/10th the price
- Large document processing
