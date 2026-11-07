# Portability environment variables

Exported skills, commands, and scripts read machine-, account-, and repository-specific
values from the variables below instead of hardcoding them. This registry is the single
naming authority: reuse a name here before inventing one, and add new names here in the
same change that first reads them.

## Resolution rules

1. **Explicit variable**, if set and non-empty.
2. **Derived value** from the current repository or tool (column "Derived from").
3. **Documented default**, only where one is listed. A default must be valid on a fresh
   machine for any developer; personal hosts, checkout paths, and accounts are never defaults.
4. Otherwise stop with: `<VAR> not configured: <meaning>. Example: export <VAR>=<example>`.
   Never guess a host, path, repository, or account.

Tools resolve through `command -v <tool>`; a `*_BIN` override exists only where listed.
Users set values in their shell profile or in the optional, user-owned file
`${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env`, which a skill may source if present
but never writes.

```bash
[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env" ] &&
  . "${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env"
```

## Repository and workspace

| Variable | Meaning | Derived from | Default |
|---|---|---|---|
| `PROJECT_ROOT` / `REPO_ROOT` | Root of the repository the task targets | `git rev-parse --show-toplevel` | — |
| `GITHUB_REPOSITORY` | `owner/repo` the task targets | `gh repo view --json nameWithOwner -q .nameWithOwner` | — |
| `GITHUB_ORG` | GitHub org/owner for org-wide queries | `${GITHUB_REPOSITORY%%/*}` | — |
| `CLAUDE_HOME` | Claude Code home | — | `$HOME/.claude` |
| `CODEX_HOME` | Codex home | — | `$HOME/.codex` |
| `ROADMAP_DIR` | Durable planning/report repository | — | `$HOME/roadmap` (skip when absent) |
| `ROADMAP_GITHUB_REPO` | GitHub `owner/repo` of `ROADMAP_DIR` | `gh repo view` inside `ROADMAP_DIR` | — |
| `WIKI_ROOT` | Personal knowledge wiki checkout | — | unset: skip wiki steps |
| `PROJECTS_DIR` | Parent directory scanned for multiple checkouts (history search only) | — | unset: scan only `PROJECT_ROOT` |
| `USER_SCOPE_ROOT` | User dotfiles / user-scope checkout | — | required where used |

## Hosts and remote machines

| Variable | Meaning | Default |
|---|---|---|
| `MAC_REMOTE_HOST` | SSH alias of a companion macOS host | required where used (examples use `mymac`) |
| `LINUX_REMOTE_HOST` | SSH alias of a companion Linux host | required where used (examples use `mylinux`) |
| `MAC_REMOTE_HOST_TS` / `LINUX_REMOTE_HOST_TS` | Optional tailnet aliases | unset: use the plain alias |

## Agent tooling

| Variable | Meaning | Default |
|---|---|---|
| `HERMES_HOME` | Hermes agent home | `$HOME/.hermes` (skip Hermes steps when absent) |
| `AO_CONFIG_PATH` | Agent Orchestrator config file | `${HERMES_HOME:-$HOME/.hermes}/agent-orchestrator.yaml` when it exists, else required |
| `AO_REPO_ROOT` | Local Agent Orchestrator checkout | required where used |
| `AO_GITHUB_REPO` | GitHub `owner/repo` of Agent Orchestrator | required where used |
| `AO_PROJECT` | AO project name for `ao spawn --project` | required where used |
| `AO_NPM_PACKAGE` | AO CLI npm package | the tool's published package name |
| `AO_AGENT_GH_LOGIN` | GitHub login used by AO workers/bots | required where used |
| `OPERATOR_GH_LOGIN` | GitHub login of the human operator | `gh api user -q .login` |
| `DARK_FACTORY_HOME` / `DARK_FACTORY_HOLDOUTS` | dark-factory checkout / holdouts checkout | required where used |
| `DARK_FACTORY_REPO_URL` | Clone URL for dark-factory | required for install steps |
| `DARK_FACTORY_LOG_DIR` | dark-factory log directory | `${XDG_STATE_HOME:-$HOME/.local/state}/dark-factory` |
| `MEM0_HOOKS_DIR` / `MEM0_PYTHON` | mem0 hook directory / interpreter | unset: skip mem0 steps / `python3` |
| `COMFYUI_HOME` | ComfyUI install | required where used |

## Messaging and accounts

| Variable | Meaning | Default |
|---|---|---|
| `SLACK_OPERATOR_DM_CHANNEL` | Slack DM channel ID for operator notifications (scripts also read the deprecated legacy name for one release) | required where used |
| `SLACK_TEST_CHANNEL` | Slack channel for test posts | required where used |
| `SLACK_AUDIT_CHANNELS` | Comma-separated channel IDs `slack-audit` reads | required |
| `SLACK_WORKSPACE_DOMAIN` | Workspace domain for permalinks (prefer `chat.getPermalink`) | unset |
| `CLAW_CHANNEL` / `CLAW_BOT_ID` | Channel and bot user for `/claw` dispatch | required |
| `GMAIL_ACCOUNT` | Gmail address for the `gmail` skill | required |
| `CREDENTIAL_BLOCKLIST_FILE` | Machine-local list of identifiers that must never be pasted | `${XDG_CONFIG_HOME:-$HOME/.config}/credential-discipline/blocklist.txt` |

## Cloud projects (plugin skills only)

| Variable | Meaning | Default |
|---|---|---|
| `GCP_PROJECT_ID` | Google Cloud project | `gcloud config get-value project` |
| `FIREBASE_PROJECT_ID` | Firebase project | `GCP_PROJECT_ID` |
| `LLM_FORENSICS_DATASET` | BigQuery dataset for LLM request logs | required |
| `AI_UNIVERSE_MCP_URL` | AI Universe MCP server URL | required |

## Self-hosted runners (plugin `self-hosted-runners`)

| Variable | Meaning | Default |
|---|---|---|
| `RUNNER_HOST` | SSH alias of the runner host | required |
| `RUNNER_INSTALL_DIR` | Runner install root | `${XDG_DATA_HOME:-$HOME/.local/share}/self-hosted-runners` |
| `RUNNER_COMPOSE_DIR` | docker-compose directory for containerized runners | required where used |
| `RUNNER_EXPECTED_LINUX` / `RUNNER_EXPECTED_MAC` | Expected online runner counts | required for health thresholds |
| `RUNNER_LAUNCHD_LABEL` / `RUNNER_SYSTEMD_UNIT` | Service names supervising runners | required where used |
| `RUNNER_CROSSCHECK_SLACK_CHANNEL_ID` / `RUNNER_CROSSCHECK_SLACK_USER_ID` | Optional Slack cross-check | unset: cross-check disabled |

## Values that are deleted, not parameterized

Personal names, Firebase UIDs, campaign/document IDs, GCP project numbers, private
Slack message timestamps, session UUIDs, and private repository links are removed or
replaced by placeholders such as `<campaign-id>`. Neither a variable nor a plugin folder
makes them acceptable to ship.
