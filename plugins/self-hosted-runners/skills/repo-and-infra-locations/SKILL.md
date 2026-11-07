---
name: repo-and-infra-locations
description: Template for looking up this machine's repository checkouts, ao CLI build path, AO YAML config rules, port assignments, and Hermes edit rules from machine-local configuration
type: reference
---

# Repository and Infrastructure Locations (machine-local template)

This skill does not ship anyone's inventory. Each operator records their own
locations in machine-local configuration, and the agent reads them at run time.
When a value is missing, report `<VAR> not configured` and stop; never guess a
path, host, or repository.

## Where the values come from

1. Environment variables from the shell profile, or from the optional user-owned
   file `${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env` (source it if present;
   never write it):

   ```bash
   [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env" ] &&
     . "${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env"
   ```

2. Values derived from the current repository (`git rev-parse --show-toplevel`,
   `gh repo view --json nameWithOwner -q .nameWithOwner`).

| Variable | Meaning | If unset |
|---|---|---|
| `AO_REPO_ROOT` | Local Agent Orchestrator checkout used to build `ao` | stop: `AO_REPO_ROOT not configured` |
| `AO_GITHUB_REPO` | GitHub `owner/repo` that `AO_REPO_ROOT`'s `origin` must match | stop |
| `AO_CONFIG_PATH` | Agent Orchestrator YAML | `${HERMES_HOME:-$HOME/.hermes}/agent-orchestrator.yaml` when it exists |
| `HERMES_HOME` | Hermes agent home (a live git checkout) | `$HOME/.hermes`; skip Hermes steps when absent |
| `CLAUDE_HOME` / `CODEX_HOME` | Agent homes | `$HOME/.claude` / `$HOME/.codex` |

## Key repositories

Verify a checkout before using it, rather than trusting a remembered path:

```bash
: "${AO_REPO_ROOT:?AO_REPO_ROOT not configured: path to your Agent Orchestrator checkout}"
: "${AO_GITHUB_REPO:?AO_GITHUB_REPO not configured: owner/repo of that checkout}"
git -C "$AO_REPO_ROOT" remote get-url origin   # must point at $AO_GITHUB_REPO
```

- Create Agent Orchestrator worktrees from `$AO_REPO_ROOT` and reset them to
  `origin/main` before use.
- Do not use a clone whose `origin` points at a different owner than
  `AO_GITHUB_REPO` (for example a direct upstream clone) for agent work.

## ao CLI

- **Binary**: resolve with `command -v ao`; it should point at
  `$AO_REPO_ROOT/packages/cli/dist/index.js` when you build from source.
- **Rebuild after updates**: `cd "$AO_REPO_ROOT" && npm run build`.
- **If broken with `ERR_MODULE_NOT_FOUND`** for an `ao-core` package: stale `dist/`;
  rebuild with `npm run build`.
- Install from npm only if your setup documents that package (`AO_NPM_PACKAGE`);
  otherwise build from `$AO_REPO_ROOT`.

## AO YAML config — no shell-style env var syntax

AO's YAML loader does **not** expand `${VAR:-default}` shell syntax. Config files
must contain literal values. Before editing the AO config, check for `${` patterns
and replace them with actual values:

```bash
AO_CONFIG="${AO_CONFIG_PATH:-${HERMES_HOME:-$HOME/.hermes}/agent-orchestrator.yaml}"
[ -f "$AO_CONFIG" ] || { echo "AO_CONFIG_PATH not configured: AO YAML not found at $AO_CONFIG" >&2; exit 2; }
grep -n '\${' "$AO_CONFIG"   # any hit = broken config
```

## Port assignments — never pick random ports

Keep your port map in one machine-local place (for example a commented
`# PORT DOCUMENTATION` block in your shell profile, or a file under
`${XDG_CONFIG_HOME:-$HOME/.config}/`). Before choosing a port:

1. Read that port map and use the assigned port or range.
2. Prefer an existing `<SERVICE>_PORT` environment variable when one is set.
3. If the service has no assignment, pick from an unallocated range and record it
   in the same machine-local map.
4. Never hardcode common defaults such as 3000 or 8080; they collide.

If no port map exists on this machine, say so and ask the operator before
binding a port.

## `$HERMES_HOME` is a live repository — no direct edits

When `$HERMES_HOME` is a git checkout, do not edit its tracked files in place.
Edit in a worktree, commit, open a PR, merge, then `git -C "$HERMES_HOME" pull`.
Exceptions: settings changed through `hermes config set`, live scheduler state,
and emergency hot-fixes the operator explicitly approves.

## Config file locations

- **Claude Code global config**: `${CLAUDE_HOME:-$HOME/.claude}/CLAUDE.md`
- **Codex global config**: `${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- **Hermes agent model config**: the `hermes-models` skill, if installed
