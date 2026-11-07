---
name: minimax
description: Run PR automation jobs with the MiniMax API provider.
---

# MiniMax Automation Runner

**Usage**: Run the installed PR automation package's jobs using the MiniMax API
provider. `<pr-automation-cmd>` below stands for that package's command; resolve
it from the package's own documentation or your scheduler entries
(see `automation-run`), not from this file.

## Quick Start

Run fixpr automation with minimax:
```bash
<pr-automation-cmd> --fixpr --max-prs 10 --cli-agent minimax
```

Run fix-comment with minimax:
```bash
<pr-automation-cmd> --fix-comment --cli-agent minimax --max-prs 3
```

## How MiniMax Works in Automation

The `minimax` CLI agent runs Claude Code with the MiniMax API endpoint:

- **Binary**: Uses `claude` CLI binary
- **Auth**: Sets `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` for MiniMax proxy
- **Model**: MiniMax-M3.1-Flash

## Environment Variables

The automation automatically sets these from `MINIMAX_API_KEY`:
```bash
ANTHROPIC_AUTH_TOKEN="<MINIMAX_API_KEY>"
ANTHROPIC_API_KEY="<MINIMAX_API_KEY>"
ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
ANTHROPIC_MODEL="MiniMax-M3.1-Flash"
API_TIMEOUT_MS="3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
```

## Preflight Validation

If the CLI is missing, inspect the installed binary and PATH, then resolve the
missing dependency within the authorized task. Do not set `TESTING=true` to skip
preflight during a real automation run or count a skipped check as validation.

## Cron Jobs Using MiniMax

Inspect your own scheduler for the live entries. A typical schedule looks like:
```bash
# Fix-comment every hour at :45
45 * * * * <pr-automation-cmd> --fix-comment --cli-agent minimax --max-prs 3

# Fixpr every 30 minutes
*/30 * * * * <pr-automation-cmd> --fixpr --max-prs 10 --cli-agent minimax
```

## Troubleshooting

**Preflight fails with "minimax binary not found"**:
- This is a configuration/preflight check defect for this configured Claude profile: in this environment setup, there is no standalone `minimax` binary; MiniMax automation uses the `claude` CLI binary configured with MiniMax API environment variables.
- Ensure the `claude` CLI binary is installed and on PATH, and ensure the automation wrapper maps MiniMax invocations to `claude`.
- Do not bypass validation; verify `claude` and the environment mapping instead.

**API errors**:
- Check presence without printing the value: `test -n "${MINIMAX_API_KEY:-}" && echo "MINIMAX_API_KEY is set"`
- Check orchestration package is up to date: `pip show <automation-package>` (the package that provides `<pr-automation-cmd>`)
