---
name: repo-and-infra-locations
description: Key repository locations, ao CLI build paths, AO YAML config rules, port assignments, and ~/.hermes/ edit rules
type: reference
---

# Repository and Infrastructure Locations

## Key repositories

| Repo | Local path | origin | upstream |
|---|---|---|---|
| jleechanorg/agent-orchestrator (agento fork) | `$HOME/project_agento/agent-orchestrator` | `jleechanorg/agent-orchestrator` | `ComposioHQ/agent-orchestrator` |
| jleechanorg/jleechanclaw (orchestration) | `~/.hermes` | `jleechanorg/jleechanclaw` | — |

**Worktrees for agento**: create from `$HOME/project_agento/agent-orchestrator`, reset to `origin/main` before use.
**Do NOT use** `~/projects/agent-orchestrator` — its `origin` points to ComposioHQ directly (wrong for agent work).

## ao CLI — always from jleechanorg/agent-orchestrator

The `ao` binary is built from `jleechanorg/agent-orchestrator` — NOT from any ComposioHQ npm package.

- **Binary**: `$HOME/bin/ao` → `packages/cli/dist/index.js`
- **Repo**: `$HOME/project_agento/agent-orchestrator` (origin: `jleechanorg/agent-orchestrator`)
- **Package namespace**: `@jleechanorg/ao-core` — NOT `@composio/*`
- **Rebuild after updates**: `cd $HOME/project_agento/agent-orchestrator && npm run build`
- **If broken with `ERR_MODULE_NOT_FOUND @composio/ao-core`**: stale dist/; fix with `npm run build`
- **NEVER install from npm** (`npm i -g @composio/agent-orchestrator`) — always build from the local jleechanorg fork

## AO YAML config — no shell-style env var syntax

AO's YAML loader does **not** expand `${VAR:-default}` shell syntax. Config files must contain literal values.

**Before editing `~/.agent-orchestrator.yaml` or any `agent-orchestrator.yaml`**: check for `${` patterns and replace with actual values:
```bash
grep '\${' ~/.agent-orchestrator.yaml   # any hits = broken config
grep '\${' ~/.hermes/agent-orchestrator.yaml
```

## Port assignments — NEVER pick random ports

All local dev server ports are documented in `~/.bashrc` under `# PORT DOCUMENTATION`. Before choosing a port:
1. Read `~/.bashrc` to find the assigned port or available range
2. Use the env var if one exists (e.g., `WORLDCLAW_PORT=9400`, `REDIS_PORT=6379`)
3. If unassigned, pick from an unallocated range and add the assignment to `~/.bashrc`
4. **Never hardcode 3000, 8080, or other common defaults** — they collide

Key: 2000 (AI Universe), 3000-3099 (AI Universe frontend), 6000-6101 (Conversation MCP), 8080 (Firestore emulator), 8765 (MCP Agent Mail), 9010 (Mission Control), 9400-9499 (WorldAI Claw), 10000-11000 (Codex proxy), 45000 (FastMCP).

## ~/.hermes/ is a live repo — no direct edits (PR required)

**Do NOT directly edit files in `~/.hermes/`**. Edit in worktree → commit → PR → merge → `git pull`. Exceptions: `config.yaml` (via `hermes config set`), `cron/jobs.json` (live job mgmt), emergency hot-fixes.

## Config file locations

- **Claude Code global config**: `~/.claude/CLAUDE.md`
- **Codex global config**: `~/.codex/AGENTS.md`
- **Hermes agent model config**: `~/.claude/skills/hermes-models.md`
