---
name: setup-org-runners
description: Set up GitHub Actions org-level self-hosted runners on a fresh macOS machine using Docker containers (myoung34/github-runner). Handles prerequisites, config, launchd services, and GitHub org settings.
---

# Setup Org-Level Self-Hosted GitHub Actions Runners

Self-contained skill to provision org-level GitHub Actions self-hosted runners on a new macOS machine.

## Prerequisites

Before running, ensure:
- Docker Desktop is installed and running
- `gh` CLI is authenticated with org admin access (`gh auth status`)
- A GitHub PAT with `admin:org` scope (stored securely — the skill will prompt for it)

## Step-by-step setup

### 1. Install directory structure

```bash
# Runner scripts
mkdir -p ~/.local/share/ao-runner
# Runner configs (one dir per scope — org or repo)
mkdir -p ~/.ao-runner.d/jleechanorg--org-runners
# Launchd log dirs
mkdir -p ~/Library/Logs/ao-runner
mkdir -p ~/Library/Logs/ao-runner-watchdog
```

### 2. Create start-runner.sh

Write `~/.local/share/ao-runner/start-runner.sh` (chmod +x):

```bash
#!/usr/bin/env bash
#
# start-runner.sh — Start GitHub Actions self-hosted runner Docker containers.
# Called by launchd-start.sh with RUNNER_ENV_FILE set to a per-scope .env file.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${RUNNER_ENV_FILE:-}" ]]; then
  echo "RUNNER_ENV_FILE must be set" >&2
  exit 1
fi

if [[ ! -f "$RUNNER_ENV_FILE" ]]; then
  echo "Missing env file: $RUNNER_ENV_FILE" >&2
  exit 1
fi

set -a
source "$RUNNER_ENV_FILE"
set +a

require_var() {
  if [[ -z "${!1:-}" ]]; then
    echo "Required variable not set: $1" >&2
    exit 1
  fi
}

require_var RUNNER_SCOPE
require_var LABELS

if [[ "$RUNNER_SCOPE" == "org" ]]; then
  require_var ORG_NAME
else
  require_var REPO_URL
fi

if [[ -z "${RUNNER_TOKEN:-}" && -z "${ACCESS_TOKEN:-}" ]]; then
  echo "Either RUNNER_TOKEN or ACCESS_TOKEN must be set" >&2
  exit 1
fi

RUNNER_IMAGE="${RUNNER_IMAGE:-myoung34/github-runner:ubuntu-noble}"
RUNNER_WORKDIR_CONTAINER="${RUNNER_WORKDIR_CONTAINER:-/_work}"
RUNNER_COUNT="${RUNNER_COUNT:-2}"
EPHEMERAL="${EPHEMERAL:-true}"
DISABLE_AUTO_UPDATE="${DISABLE_AUTO_UPDATE:-true}"
RUNNER_NAME_PREFIX="${RUNNER_NAME_PREFIX:-org-runner}"

SLUG="$(basename "$(dirname "$RUNNER_ENV_FILE")")"

case "$RUNNER_SCOPE" in
  repo|org) ;;
  *)
    echo "RUNNER_SCOPE must be 'repo' or 'org' (got: $RUNNER_SCOPE)" >&2
    exit 1
    ;;
esac

echo "[$(date)] Pulling runner image: $RUNNER_IMAGE"
docker pull "$RUNNER_IMAGE"

start_one_runner() {
  local idx="$1"
  local container_name="${RUNNER_NAME_PREFIX}-${SLUG}-${idx}"
  local volume_name="${container_name}-work"

  echo "[$(date)] Removing existing container: $container_name"
  docker rm -f "$container_name" 2>/dev/null || true
  docker volume rm -f "$volume_name" 2>/dev/null || true

  local -a TOKEN_ARGS=()
  if [[ -n "${RUNNER_TOKEN:-}" ]]; then
    TOKEN_ARGS+=(-e RUNNER_TOKEN="$RUNNER_TOKEN")
  else
    TOKEN_ARGS+=(-e ACCESS_TOKEN="$ACCESS_TOKEN")
  fi

  local -a SCOPE_ARGS=()
  if [[ "$RUNNER_SCOPE" == "org" ]]; then
    SCOPE_ARGS+=(-e ORG_NAME="$ORG_NAME")
  else
    SCOPE_ARGS+=(-e REPO_URL="$REPO_URL")
  fi

  local -a ARGS=(
    run -d
    --name "$container_name"
    --restart unless-stopped
    "${TOKEN_ARGS[@]}"
    "${SCOPE_ARGS[@]}"
    -e RUNNER_SCOPE="$RUNNER_SCOPE"
    -e RUNNER_NAME_PREFIX="$RUNNER_NAME_PREFIX"
    -e RANDOM_RUNNER_SUFFIX=true
    -e LABELS="$LABELS"
    -e RUNNER_WORKDIR="$RUNNER_WORKDIR_CONTAINER"
    -e EPHEMERAL="$EPHEMERAL"
    -e DISABLE_AUTO_UPDATE="$DISABLE_AUTO_UPDATE"
    -e ACTIONS_RUNNER_HOOK_JOB_STARTED=/pre-job-hook.sh
    -v "${volume_name}:${RUNNER_WORKDIR_CONTAINER}"
    -v "$SCRIPT_DIR/pre-job-hook.sh:/pre-job-hook.sh:ro"
  )

  docker "${ARGS[@]}" "$RUNNER_IMAGE"
  echo "[$(date)] Started: $container_name (volume: $volume_name)"
}

echo "[$(date)] Starting $RUNNER_COUNT runner(s) for $SLUG"
for i in $(seq 1 "$RUNNER_COUNT"); do
  start_one_runner "$i"
done
echo "[$(date)] All $RUNNER_COUNT runner(s) started for $SLUG"
```

### 3. Create launchd-start.sh

Write `~/.local/share/ao-runner/launchd-start.sh` (chmod +x):

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[$(date)] Waiting for Docker..."
for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    echo "[$(date)] Docker ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "[$(date)] Docker not available after 150s — aborting." >&2
    exit 1
  fi
  sleep 5
done

AO_RUNNER_D="${HOME}/.ao-runner.d"
if [[ ! -d "$AO_RUNNER_D" ]]; then
  echo "[$(date)] No configs ($AO_RUNNER_D does not exist) — nothing to start."
  exit 0
fi

echo "[$(date)] Starting runners for all configured scopes..."
started=0; failed=0
for repo_dir in "$AO_RUNNER_D"/*/; do
  env_file="${repo_dir}.env"
  if [[ -f "$env_file" ]]; then
    name="$(basename "$repo_dir")"
    echo "[$(date)] Starting runners for $name..."
    if RUNNER_ENV_FILE="$env_file" "$SCRIPT_DIR/start-runner.sh"; then
      started=$((started + 1))
    else
      echo "[$(date)] ERROR: Failed for $name — continuing." >&2
      failed=$((failed + 1))
    fi
  fi
done

echo "[$(date)] Startup complete. Started $started scope(s), failed $failed."
```

### 4. Create pre-job-hook.sh

Write `~/.local/share/ao-runner/pre-job-hook.sh` (chmod +x):

```bash
#!/usr/bin/env bash
echo "[$(date)] GitHub Actions job started on $(hostname)"
```

### 5. Create org runner .env

Write `~/.ao-runner.d/jleechanorg--org-runners/.env` (chmod 600):

```
ACCESS_TOKEN=<your-github-pat-with-admin:org-scope>
RUNNER_SCOPE=org
ORG_NAME=jleechanorg
LABELS=self-hosted,Linux,ARM64
RUNNER_COUNT=4
RUNNER_IMAGE=myoung34/github-runner:ubuntu-noble
EPHEMERAL=true
DISABLE_AUTO_UPDATE=true
RUNNER_NAME_PREFIX=org-runner
```

**IMPORTANT**: Replace `<your-github-pat-with-admin:org-scope>` with an actual PAT. The PAT needs: `admin:org`, `repo` scopes.

### 6. Configure GitHub org settings

```bash
# Allow public repos in default runner group
echo '{"allows_public_repositories": true}' | \
  gh api /orgs/jleechanorg/actions/runner-groups/1 -X PATCH --input -

# Set org-level runner labels variable (all repos inherit)
gh api /orgs/jleechanorg/actions/variables -X POST \
  -f name=SELF_HOSTED_RUNNER_LABELS \
  -f value='["self-hosted","Linux","ARM64"]' \
  -f visibility=all
```

### 7. Install launchd services

Write `~/Library/LaunchAgents/com.ao-runner.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ao-runner</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/USER/.local/share/ao-runner/launchd-start.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/USER/Library/Logs/ao-runner/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/USER/Library/Logs/ao-runner/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    <key>HOME</key>
    <string>/Users/USER</string>
  </dict>
</dict>
</plist>
```

Replace `USER` with your macOS username. Then bootstrap:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ao-runner.plist
```

### 8. Verify

```bash
# Check containers are running
docker ps --format '{{.Names}}\t{{.Status}}' | grep org-runner

# Check runners registered at org level
gh api /orgs/jleechanorg/actions/runners --jq '.runners[] | "\(.name)\t\(.status)\t[\(.labels | map(.name) | join(", "))]"'

# Check org variable
gh api /orgs/jleechanorg/actions/variables/SELF_HOSTED_RUNNER_LABELS --jq '.value'
```

## Troubleshooting

- **Containers in restart loop**: Usually expired `RUNNER_TOKEN`. Use `ACCESS_TOKEN` (PAT) instead — it auto-renews registration tokens.
- **Runners offline on GitHub**: Check `docker logs org-runner-jleechanorg--org-runners-1` for registration errors.
- **Runner group blocks public repos**: Re-run step 6 to set `allows_public_repositories: true`.
- **Repo not picking up org runners**: Check if a repo-level `SELF_HOSTED_RUNNER_LABELS` variable overrides the org one. Delete it if so.

## Architecture

```
~/.ao-runner.d/
  jleechanorg--org-runners/.env    ← org-level (serves ALL repos)
  jleechanorg--agent-orchestrator/.env  ← optional repo-level override
~/.local/share/ao-runner/
  launchd-start.sh    ← iterates ~/.ao-runner.d/*/.env
  start-runner.sh     ← starts Docker containers per .env
  pre-job-hook.sh     ← logs job start
~/Library/LaunchAgents/
  com.ao-runner.plist  ← starts on login
```

Runners use `myoung34/github-runner:ubuntu-noble` Docker image with `--restart unless-stopped`. They auto-register with GitHub using the PAT and labels specified in the .env.
