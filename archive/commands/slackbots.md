---
description: Slack bot setup and userscope refresh for MCP Mail (history-first, browserclaw-auth assist)
type: orchestration
execution_mode: immediate
---

# /slackbots [check|auth|verify]

Use `~/.hermes/skills/devops/slackbots-setup/SKILL.md` to perform MCP Mail bot setup and userscope refresh.

Default mode: `check`.

- `check`:
  - Run `/history "mcp mail bot A0A3WSV6BM1"` and `/history "SLACK_USER_TOKEN"`
  - Review prior setup attempts for scope or token issues.
- `auth`:
  - Run `/browserclaw learn --url https://api.slack.com/apps/A0A3WSV6BM1/oauth --output-dir /tmp/slackbots-browserclaw-auth --headless --manual --goal "Capture Slack MCP Mail OAuth and permissions setup context"`
  - Open `https://api.slack.com/apps/A0A3WSV6BM1/oauth` in the authenticated browser flow, set user/bot scopes, and complete reinstall.
- `verify`:
  - Run the auth/test probes in the skill and confirm both post + mark/read actions now succeed for user scope needs.

