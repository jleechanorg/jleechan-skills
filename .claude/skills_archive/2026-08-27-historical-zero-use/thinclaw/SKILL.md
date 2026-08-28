---
name: thinclaw
description: Use thinclaw MCP server — thin inference-less bridge to OpenClaw Gateway for executing tools
type: skill
---

# thinclaw — Thin Inference-Less MCP Server

## What thinclaw is

thinclaw is a **zero-inference MCP server** that acts as a bridge between Claude Desktop/Cowork and the OpenClaw Gateway. It performs ZERO inference — only HTTP relay.

```
┌─────────────────┐  MCP stdio   ┌──────────────┐  HTTP REST  ┌──────────────────┐
│  Claude Desktop │ ───────────► │   thinclaw   │ ──────────► │  OpenClaw         │
│  Claude Cowork  │   zero LLM   │   (bridge)   │  /tools/    │  Gateway         │
│  Perplexity     │ ◄─────────── │  Node.js     │  invoke     │  localhost:18789 │
└─────────────────┘  tool result└──────────────┘ ◄────────── └──────────────────┘
```

**All reasoning happens in the calling AI.** thinclaw only proxies tool calls to the Gateway.

---

## Available Tools

Use these tools in Claude Desktop after thinclaw is installed and Claude Desktop is restarted.

### 1. openclaw_execute

Universal proxy — call ANY OpenClaw tool by name.

```
Tool: openclaw_execute
Arguments: {
  "tool": "bash",
  "params": { "command": "ls -la", "cwd": "/tmp" }
}
```

Supported tool names: `bash`, `read_file`, `grep`, `todo_list_write`, `slack_postMessage`, `whatsapp_send`, `memory_search`, etc.

### 2. run_shell

Shorthand for executing shell commands.

```
Tool: run_shell
Arguments: {
  "command": "find . -name '*.js' | head -10"
}
```

### 3. send_whatsapp

Send a WhatsApp message (requires `whatsapp_send` tool registered in Gateway).

```
Tool: send_whatsapp
Arguments: {
  "to": "+1234567890",
  "message": "Hello from thinclaw!"
}
```

### 4. schedule_cron

Schedule a recurring task via Gateway cron.

```
Tool: schedule_cron
Arguments: {
  "schedule": "*/5 * * * *",
  "task": "check-deployments"
}
```

### 5. trigger_cowork_workflow

Trigger a Claude Cowork workflow by writing a flag file to `~/AI_Bridge/inbox/`.

```
Tool: trigger_cowork_workflow
Arguments: {
  "workflow": "daily-standup",
  "context": { "channel": "#engineering", "time": "09:30" }
}
```

This creates `~/AI_Bridge/inbox/trigger-<timestamp>.json`. Cowork monitors this folder.

---

## Architecture Notes

- **Gateway must be running** at `http://localhost:18789`
- **Token** auto-read from `~/.openclaw/openclaw.json` or set via `GATEWAY_TOKEN`
- **AI_Bridge folder**: `~/AI_Bridge/{inbox,outbox,processed}` for cron → Cowork handoff
- **No inference** — thinclaw is a pure HTTP relay, zero LLM calls

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Gateway not responding | Start Gateway: `openclaw gateway start` |
| Token missing | Check: `cat ~/.openclaw/openclaw.json \| jq '.gateway.auth.token'` |
| Health check | `curl http://localhost:18789/health` |
| Tools not showing | Restart Claude Desktop after installing thinclaw |

---

## Installation (for reference)

thinclaw is installed via Claude Desktop config at `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "thinclaw": {
      "command": "node",
      "args": ["$HOME/thinclaw/server.js"],
      "env": { "GATEWAY_TOKEN": "..." }
    }
  }
}
```
