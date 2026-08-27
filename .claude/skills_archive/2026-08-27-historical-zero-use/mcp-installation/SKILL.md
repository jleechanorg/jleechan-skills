---
name: mcp-installation
description: "Use when adding/troubleshooting MCP servers. Installs to stable paths (npm -g, uvx, uv tool); updates ~/.config/mcp-daemon/start-mcp-daemons.sh for HTTP MCPs."
---

# MCP server installation — stable paths only


- **Install MCP servers with `npm install -g` (node) or `uvx`/`uv tool install` (Python) to stable locations under `~`** — never to a repo directory, worktree, or temp path (`/var/folders/`, `/tmp/`).
- HTTP MCPs (ports 8001–8009) are managed by `~/.config/mcp-daemon/start-mcp-daemons.sh`. When adding a new HTTP MCP, update the `SERVERS` array in that script — do not start it in an ad-hoc script.
- Register new MCPs in `~/.claude/settings.json` (user-global) and `~/.claude/mcp-strict.json` (strict-mode sessions).
- If a status check shows an MCP at a temp or repo path, that entry is stale — find the globally installed binary and update the config.
