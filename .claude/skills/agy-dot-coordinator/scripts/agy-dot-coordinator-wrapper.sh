#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-wrapper.sh
# Canonical cross-platform launchd / systemd wrapper for ai.gemini.agy-dot-coordinator
set -euo pipefail

# 1. Source user profile with nounset temporarily disabled (launchd/systemd skill standard)
if [[ -f ~/.bash_profile ]]; then
  set +u
  source ~/.bash_profile 2>/dev/null || true
  set -u
elif [[ -f ~/.bashrc ]]; then
  set +u
  source ~/.bashrc 2>/dev/null || true
  set -u
fi

# Ensure critical paths in PATH (prefer pinned Node 22 v22.22.0 where Playwright is installed)
if [[ -d "$HOME/.nvm/versions/node/v22.22.0/bin" ]]; then
  export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export DOT_NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
else
  export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls -1 "$HOME/.nvm/versions/node" 2>/dev/null | tail -1)/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
fi

# Dynamic credential resolution fallback
if [[ -z "${GH_TOKEN:-}" ]]; then
  GH_TOKEN="$(/usr/bin/env gh auth token 2>/dev/null || true)"
  export GH_TOKEN
fi

# Worker owns the single execution lock; installer uses the same lock.

# 3. Standard execution logs
LOG_PREFIX="[agy-dot-coordinator]"
echo "$LOG_PREFIX Starting job at $(date)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER="$SCRIPT_DIR/agy-dot-coordinator-worker.sh"

# 4. Invoke target worker
exec /bin/bash "$WORKER" "$@"
