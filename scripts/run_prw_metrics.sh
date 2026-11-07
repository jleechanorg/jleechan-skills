#!/usr/bin/env bash
# run_prw_metrics.sh — Execution wrapper for 4-hour PRW metrics collection (bd-yq6x).
#
# Follows macOS launchd standards from .claude/skills/launchd/SKILL.md:
# 1. Sets canonical PATH
# 2. Sourced shell profile sourcing with nounset temporarily disabled
# 3. Dynamic GitHub CLI token resolution
# 4. Scoped state directory and atomic directory lock with stale-owner recovery
# 5. Catch-up collection deduplication after sleep
# 6. Preserves collector exit status and sanitized logs

# 1. Establish standard PATH for macOS launchd environment
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

# 2. Source user profile with nounset temporarily disabled to inherit environment
if [[ -f "$HOME/.bash_profile" ]]; then
  set +u
  source "$HOME/.bash_profile" 2>/dev/null || true
  set -u
elif [[ -f "$HOME/.bashrc" ]]; then
  set +u
  source "$HOME/.bashrc" 2>/dev/null || true
  set -u
elif [[ -f "$HOME/.zprofile" ]]; then
  set +u
  source "$HOME/.zprofile" 2>/dev/null || true
  set -u
fi

set -euo pipefail

# 3. Dynamic GitHub CLI token resolution without leaking credentials to logs
if [[ -z "${GH_TOKEN:-}" ]]; then
  RESOLVED_TOKEN="$(gh auth token 2>/dev/null || true)"
  if [[ -n "$RESOLVED_TOKEN" ]]; then
    export GH_TOKEN="$RESOLVED_TOKEN"
  fi
fi

# 4. Resolve repository root and state directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${PRW_METRICS_STATE_DIR:-}" ]]; then
  SCRATCH_HELPER="$HOME/.claude/skills/scratch-space/scripts/scratch-dir.sh"
  if [[ -f "$SCRATCH_HELPER" ]]; then
    PRW_METRICS_STATE_DIR="$(bash "$SCRATCH_HELPER" prw-metrics 2>/dev/null || echo "/tmp/prw-metrics")"
  else
    PRW_METRICS_STATE_DIR="/tmp/prw-metrics"
  fi
fi
mkdir -p "$PRW_METRICS_STATE_DIR"

# Source optional local operator runtime configuration if present
if [[ -f "$HOME/.config/prw-metrics/config.env" ]]; then
  set +u
  source "$HOME/.config/prw-metrics/config.env" 2>/dev/null || true
  set -u
fi
if [[ -f "$PRW_METRICS_STATE_DIR/config.env" ]]; then
  set +u
  source "$PRW_METRICS_STATE_DIR/config.env" 2>/dev/null || true
  set -u
fi

LOCK_DIR="$PRW_METRICS_STATE_DIR/lock"
PID_FILE="$LOCK_DIR/pid"

# Acquire atomic directory lock with stale-PID recovery
LOCK_ACQUIRED=false

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$PID_FILE"
    LOCK_ACQUIRED=true
    return 0
  fi

  # Lock directory already exists. Inspect PID
  if [[ -f "$PID_FILE" ]]; then
    LOCK_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$LOCK_PID" ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
      echo "Another prw-metrics instance (PID: $LOCK_PID) is currently running. Exiting cleanly."
      exit 0
    else
      echo "Stale lock detected (PID ${LOCK_PID:-unknown} is dead). Recovering lock..."
      rm -rf "$LOCK_DIR"
      if mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "$$" > "$PID_FILE"
        LOCK_ACQUIRED=true
        return 0
      fi
    fi
  else
    # Lock directory exists but PID file missing/corrupt
    echo "Stale lock detected (missing PID file). Recovering lock..."
    rm -rf "$LOCK_DIR"
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      echo "$$" > "$PID_FILE"
      LOCK_ACQUIRED=true
      return 0
    fi
  fi

  echo "Failed to acquire lock. Exiting cleanly."
  exit 0
}

cleanup() {
  if [[ "$LOCK_ACQUIRED" == "true" ]]; then
    rm -rf "$LOCK_DIR"
  fi
}
trap cleanup EXIT INT TERM

acquire_lock

# 5. Deduplicate catch-up triggers after system sleep
FORCE_RUN=false
for arg in "$@"; do
  if [[ "$arg" == "--force-run" || "$arg" == "--force" ]]; then
    FORCE_RUN=true
  fi
done
if [[ "${PRW_METRICS_FORCE_RUN:-}" == "1" ]]; then
  FORCE_RUN=true
fi

MIN_INTERVAL_SEC="${PRW_METRICS_MIN_INTERVAL_SEC:-900}"
LAST_SUCCESS_FILE="$PRW_METRICS_STATE_DIR/last_success_epoch"

if [[ "$FORCE_RUN" != "true" && -f "$LAST_SUCCESS_FILE" ]]; then
  LAST_EPOCH="$(cat "$LAST_SUCCESS_FILE" 2>/dev/null || echo 0)"
  CURRENT_EPOCH="$(date +%s)"
  ELAPSED=$(( CURRENT_EPOCH - LAST_EPOCH ))
  if (( ELAPSED < MIN_INTERVAL_SEC && ELAPSED >= 0 )); then
    echo "Deduplicating catch-up run: last successful run was ${ELAPSED}s ago (< ${MIN_INTERVAL_SEC}s). Skipping."
    exit 0
  fi
fi

# 6. Export publication configuration and execute collector
export PRW_METRICS_STATE_DIR
export PRW_METRICS_ROADMAP_REPO="${PRW_METRICS_ROADMAP_REPO:-$HOME/roadmap}"
export PRW_METRICS_PUBLISH="${PRW_METRICS_PUBLISH:-1}"

COLLECTOR_CMD="${PRW_METRICS_COLLECTOR_CMD:-python3 "$REPO_DIR/scripts/prw_metrics.py"}"

echo "Starting PRW metrics collection at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

set +e
eval "$COLLECTOR_CMD"
STATUS=$?
set -e

if [[ $STATUS -eq 0 ]]; then
  date +%s > "$LAST_SUCCESS_FILE"
  echo "PRW metrics collection succeeded at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  exit 0
else
  echo "ERROR: PRW metrics collection failed with exit status $STATUS" >&2
  exit $STATUS
fi
