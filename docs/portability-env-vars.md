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
   A conventional tool location (`$HOME/.hermes`, `$HOME/roadmap`) may be a default only when
   the skill checks that it exists and skips only the dependent steps when it does not; a
   missing optional tool never blocks an unrelated task.
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

An operator who wants to scan for their own leaks keeps a never-committed list of personal
host aliases, names and paths at `${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/personal-tokens.txt`
(one fixed string per line) and runs `grep -rn -F -f <that file> <paths>`.

## Repository and workspace

| Variable | Meaning | Derived from | Default |
|---|---|---|---|
| `PROJECT_ROOT` / `REPO_ROOT` | Root of the repository the task targets. `REPO_ROOT` is an accepted alias; `PROJECT_ROOT` wins when both are set | `git rev-parse --show-toplevel` | — |
| `GITHUB_REPOSITORY` | `owner/repo` the task targets | `gh repo view --json nameWithOwner -q .nameWithOwner` | — |
| `GITHUB_ORG` | GitHub org/owner for org-wide queries | `${GITHUB_REPOSITORY%%/*}` | — |
| `CLAUDE_HOME` | Claude Code home | — | `$HOME/.claude` |
| `CODEX_HOME` | Codex home | — | `$HOME/.codex` |
| `ROADMAP_DIR` | Durable planning/report repository | — | `$HOME/roadmap` if it exists and is a git repository; otherwise skip roadmap steps |
| `ROADMAP_GITHUB_REPO` | GitHub `owner/repo` of `ROADMAP_DIR` | `gh repo view` inside `ROADMAP_DIR` | — |
| `WIKI_ROOT` | Personal knowledge wiki checkout | — | unset: skip wiki steps |
| `PROJECTS_DIR` | Parent directory scanned for multiple checkouts (history search only) | — | unset: scan only `PROJECT_ROOT` |
| `ANTIGRAVITY_EXPORT_DIR` | Folder of exported Antigravity conversations (history search only) | — | unset: skip that source |
| `USER_SCOPE_ROOT` | User dotfiles / user-scope checkout | — | required where used |

## Hosts and remote machines

| Variable | Meaning | Default |
|---|---|---|
| `MAC_REMOTE_HOST` | SSH alias of a companion macOS host | required where used (examples use `mymac`) |
| `LINUX_REMOTE_HOST` | SSH alias of a companion Linux host | required where used (examples use `mylinux`) |
| `MAC_REMOTE_HOST_TS` / `LINUX_REMOTE_HOST_TS` | Optional tailnet aliases | unset: use the plain alias |

## Agent tooling

| Variable | Meaning | Derived from | Default |
|---|---|---|---|
| `HERMES_HOME` | Hermes agent home | — | `$HOME/.hermes` if it exists; otherwise skip Hermes steps |
| `AO_CONFIG_PATH` | Agent Orchestrator config file | — | `${HERMES_HOME:-$HOME/.hermes}/agent-orchestrator.yaml` when it exists, else required |
| `AO_REPO_ROOT` | Local Agent Orchestrator checkout | — | required where used |
| `AO_GITHUB_REPO` | GitHub `owner/repo` of Agent Orchestrator | — | required where used |
| `AO_PROJECT` | AO project name for `ao spawn --project` | — | required where used |
| `AO_NPM_PACKAGE` | AO CLI npm package | — | the tool's published package name |
| `AO_AGENT_GH_LOGIN` | GitHub login used by AO workers/bots | — | required where used |
| `OPERATOR_GH_LOGIN` | GitHub login of the human operator | `gh api user -q .login` | — |
| `MEM0_HOOKS_DIR` / `MEM0_PYTHON` | mem0 hook directory / interpreter | — | unset: skip mem0 steps / `python3` |
| `COMFYUI_HOME` | ComfyUI install | — | required where used |

The retired dark-factory and auto-factory tooling is gone from the catalog
(`docs/specs/2026-11-06-factory-tool-retirement.md`); its variables are not part of this
registry.

## Messaging and accounts

| Variable | Meaning | Default |
|---|---|---|
| `SLACK_OPERATOR_DM_CHANNEL` | Slack DM channel ID for operator notifications (explicit; no legacy personal-named variable and no fallback is read) | required where used |
| `SLACK_TEST_CHANNEL` | Slack channel for test posts | required where used |
| `SLACK_AUDIT_CHANNELS` | Comma-separated channel IDs `slack-audit` reads | required |
| `SLACK_WORKSPACE_DOMAIN` | Workspace domain for permalinks (prefer `chat.getPermalink`) | unset |
| `CLAW_CHANNEL` / `CLAW_BOT_ID` | Channel and bot user for `/claw` dispatch | required |
| `GMAIL_ACCOUNT` | Gmail address for the `gmail` skill | required |
| `CREDENTIAL_BLOCKLIST_FILE` | Machine-local list of identifiers that must never be pasted | `${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/credential-blocklist.txt` |

## Cloud projects (plugin skills only)

| Variable | Meaning | Derived from | Default |
|---|---|---|---|
| `GCP_PROJECT_ID` | Google Cloud project. Required for a skill that reads or writes production data; other skills may derive it | `gcloud config get-value project` (non-production skills only) | — |
| `FIREBASE_PROJECT_ID` | Firebase project the task's data lives in. Required, never derived or inferred from `GCP_PROJECT_ID`, a GCP project number, or the current `gcloud` project: a production write must not pick up whatever project gcloud has active | — | required where used |
| `LLM_FORENSICS_DATASET` | BigQuery dataset for LLM request logs | — | required |
| `AI_UNIVERSE_MCP_URL` | AI Universe MCP server URL | — | required |

## Self-hosted runners (plugin `self-hosted-runners`)

| Variable | Meaning | Default |
|---|---|---|
| `RUNNER_HOST` | SSH alias of the runner host | required |
| `RUNNER_INSTALL_DIR` | Runner install root | `${XDG_DATA_HOME:-$HOME/.local/share}/self-hosted-runners` |
| `RUNNER_COMPOSE_DIR` | docker-compose directory for containerized runners | required where used |
| `RUNNER_EXPECTED_LINUX` / `RUNNER_EXPECTED_MAC` | Expected online runner counts | required for health thresholds |
| `RUNNER_LAUNCHD_LABEL` / `RUNNER_SYSTEMD_UNIT` | Service names supervising runners | required where used |
| `RUNNER_HOST_TIMEOUT` / `RUNNER_HOST_DOCKER_SOCK` | SSH connect timeout (seconds) and the remote Docker socket | `5` / `unix:///var/run/docker.sock` |
| `RUNNER_HEALTH_EXTRA_REPOS` | Extra `owner/repo` values `runner-health` includes besides `GITHUB_REPOSITORY` | unset: only `GITHUB_REPOSITORY` |
| `RUNNER_CROSSCHECK_SLACK_CHANNEL_ID` / `RUNNER_CROSSCHECK_SLACK_USER_ID` | Optional Slack cross-check | unset: cross-check disabled |

## PRW metrics and dashboard

| Variable | Meaning | Derived from | Default |
|---|---|---|---|
| `PRW_METRICS_REPOS` | Comma-separated list of `owner/repo` repositories to monitor | — | unset: uses repositories from input directory or state |
| `PRW_METRICS_ROADMAP_REPO` | Path to local clone of roadmap repository for dashboard publication | — | required where publication is enabled (fails closed if unset) |
| `PRW_METRICS_STATE_DIR` | Directory for persistent metric state snapshots and locks | `${HOME}/.claude/skills/scratch-space/scripts/scratch-dir.sh prw-metrics` | `/tmp/prw-metrics` |
| `PRW_METRICS_LOCK_DIR` | Path to active execution lock directory | — | `${PRW_METRICS_STATE_DIR}/lock` |
| `PRW_METRICS_CONFIG_FILE` | Path to optional operator configuration file | — | unset (checks `${XDG_CONFIG_HOME:-$HOME/.config}/prw-metrics/config.env`) |
| `PRW_METRICS_MIN_INTERVAL_SEC` | Minimum seconds between scheduled collection runs (sleep catch-up deduplication) | — | `900` |
| `PRW_METRICS_FORCE_RUN` | Force execution, bypassing the interval check (`1` or `true`) | — | `0` |
| `PRW_METRICS_COLLECTOR_CMD` | Collector command executed by `run_prw_metrics.sh` | — | `python3 $REPO_ROOT/scripts/prw_metrics.py --roadmap-repo $PRW_METRICS_ROADMAP_REPO --state-dir $STATE_DIR` |
| `PRW_METRICS_INPUT_DIR` | Path to cached scratch dataset directory | — | unset |
| `PRW_METRICS_TELEMETRY_DIR` | Path to retained telemetry store directory | — | unset (checks `${PRW_METRICS_ROADMAP_REPO}/dashboards/prw/telemetry`) |
| `PRW_METRICS_RECEIPTS_DIR` | Path to directory containing task receipts (`run.stats.json`, `start_*.json`, `completion_*.json`) | — | unset |
| `PRW_METRICS_OFFLINE` | Offline mode: skip live GitHub API and use cached data (`1` or `true`) | — | `0` |
| `PRW_METRICS_PUBLISH` | Publish dashboard to roadmap repo (`1` or `true`) | — | `0` |
| `PRW_METRICS_STALE_HOURS` | Threshold hours after which source cutoffs are marked STALE | — | `4.5` |

## Values that are deleted, not parameterized

Personal names, Firebase UIDs, campaign/document IDs, GCP project numbers, private
Slack message timestamps, session UUIDs, and private repository links are removed or
replaced by placeholders such as `<campaign-id>`. Neither a variable nor a plugin folder
makes them acceptable to ship.
