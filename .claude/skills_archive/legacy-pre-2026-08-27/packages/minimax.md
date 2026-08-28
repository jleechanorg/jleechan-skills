# MiniMax Automation Runner

**Usage**: Run jleechanorg-pr-monitor automation jobs using MiniMax API provider.

## Quick Start

Run fixpr automation with minimax:
```bash
jleechanorg-pr-monitor --fixpr --max-prs 10 --cli-agent minimax
```

Run fix-comment with minimax:
```bash
jleechanorg-pr-monitor --fix-comment --cli-agent minimax --max-prs 3
```

## How MiniMax Works in Automation

The `minimax` CLI agent runs Claude Code with the MiniMax API endpoint:

- **Binary**: Uses `claude` CLI binary
- **Auth**: Sets `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` for MiniMax proxy
- **Model**: MiniMax-M2.5

## Environment Variables

The automation automatically sets these from `MINIMAX_API_KEY`:
```bash
ANTHROPIC_AUTH_TOKEN=<MINIMAX_API_KEY>
ANTHROPIC_API_KEY=<MINIMAX_API_KEY>
ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
ANTHROPIC_MODEL="MiniMax-M2.5"
API_TIMEOUT_MS="3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
```

## Preflight Validation

If preflight fails (CLI not found), you can skip it with:
```bash
TESTING=true jleechanorg-pr-monitor --fixpr --cli-agent minimax
```

## Cron Jobs Using MiniMax

From crontab:
```bash
# Fix-comment every hour at :45
45 * * * * jleechanorg-pr-monitor --fix-comment --cli-agent minimax --max-prs 3

# Fixpr every 30 minutes
*/30 * * * * jleechanorg-pr-monitor --fixpr --max-prs 10 --cli-agent minimax
```

## Troubleshooting

**Preflight fails with "minimax binary not found"**:
- This is expected - minimax uses `claude` binary with minimax API
- Set `TESTING=true` to skip preflight validation

**API errors**:
- Verify `MINIMAX_API_KEY` is set: `echo $MINIMAX_API_KEY`
- Check orchestration package is up to date: `pip show jleechanorg-orchestration`
