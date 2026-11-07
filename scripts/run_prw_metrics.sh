#!/usr/bin/env bash
# run_prw_metrics.sh — Execution wrapper for 4-hour PRW metrics collection (bd-yq6x).
#
# Follows macOS launchd standards from .claude/skills/launchd/SKILL.md:
# 1. Sets canonical PATH
# 2. Sourced shell profile sourcing with nounset temporarily disabled
# 3. Dynamic GitHub CLI token resolution
# 4. Scoped state directory, auto-export config sourcing, and atomic staging directory lock
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
REPO_ROOT="$REPO_DIR"

if [[ -z "${PRW_METRICS_STATE_DIR:-}" ]]; then
  SCRATCH_HELPER="$HOME/.claude/skills/scratch-space/scripts/scratch-dir.sh"
  if [[ -f "$SCRATCH_HELPER" ]]; then
    PRW_METRICS_STATE_DIR="$(bash "$SCRATCH_HELPER" prw-metrics 2>/dev/null || echo "/tmp/prw-metrics")"
  else
    PRW_METRICS_STATE_DIR="/tmp/prw-metrics"
  fi
fi
mkdir -p "$PRW_METRICS_STATE_DIR"

# Source configuration with set -a / set +a so assignments without export reach children
source_config() {
  local cfg="$1"
  if [[ -f "$cfg" ]]; then
    set +u
    set -a
    source "$cfg" 2>/dev/null || true
    set +a
    set -u
  fi
}

if [[ -n "${PRW_METRICS_CONFIG_FILE:-}" ]]; then
  source_config "$PRW_METRICS_CONFIG_FILE"
fi
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
source_config "$CONFIG_HOME/prw-metrics/config.env"
source_config "$PRW_METRICS_STATE_DIR/config.env"

# Verify python3 interpreter availability
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 command not found in PATH." >&2
  exit 1
fi

# 5. Acquire atomic directory lock with stale-owner recovery
LOCK_DIR="${PRW_METRICS_LOCK_DIR:-$PRW_METRICS_STATE_DIR/lock}"
PID_FILE="$LOCK_DIR/pid"
COMM_FILE="$LOCK_DIR/comm"
LOCK_ACQUIRED=0

acquire_lock() {
  local stage_dir="${LOCK_DIR}.tmp.$$"
  mkdir -p "$stage_dir"
  echo "$$" > "$stage_dir/pid"
  ps -p $$ -o comm= 2>/dev/null | tr -d ' ' > "$stage_dir/comm" || echo "bash" > "$stage_dir/comm"

  # Attempt atomic rename into LOCK_DIR
  if python3 -c 'import os,sys; os.rename(sys.argv[1], sys.argv[2])' "$stage_dir" "$LOCK_DIR" 2>/dev/null; then
    LOCK_ACQUIRED=1
    return 0
  fi

  # Clean up staging directory since rename failed
  rm -f "$stage_dir/pid" "$stage_dir/comm" 2>/dev/null || true
  rmdir "$stage_dir" 2>/dev/null || true

  # Lock directory already exists. Inspect owner PID and COMM
  local existing_pid=""
  local existing_comm=""
  if [[ -f "$PID_FILE" ]]; then
    existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi
  if [[ -f "$COMM_FILE" ]]; then
    existing_comm="$(cat "$COMM_FILE" 2>/dev/null || true)"
  fi

  local is_active=false
  local live_comm=""
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    live_comm="$(ps -p "$existing_pid" -o comm= 2>/dev/null | tr -d ' ' || true)"
    local live_base="$(basename "$live_comm" 2>/dev/null || true)"
    local exist_base="$(basename "$existing_comm" 2>/dev/null || true)"
    if [[ -n "$live_comm" ]] && { [[ "$live_comm" == "$existing_comm" ]] || [[ "$live_base" == "$exist_base" ]] || [[ "$live_base" =~ ^(bash|sh|zsh|python|python3)$ ]]; }; then
      is_active=true
    fi
  fi

  if [[ "$is_active" == "true" ]]; then
    echo "Another prw-metrics instance (PID: $existing_pid, comm: ${live_comm:-unknown}) is currently running. Exiting cleanly."
    exit 0
  fi

  # Stale lock detected (dead PID or recycled PID with different command). Recover lock.
  echo "Stale lock detected (PID ${existing_pid:-unknown} is dead or recycled). Recovering lock..."
  rm -f "$PID_FILE" "$COMM_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true

  # Retry atomic staging rename
  mkdir -p "$stage_dir"
  echo "$$" > "$stage_dir/pid"
  ps -p $$ -o comm= 2>/dev/null | tr -d ' ' > "$stage_dir/comm" || echo "bash" > "$stage_dir/comm"

  if python3 -c 'import os,sys; os.rename(sys.argv[1], sys.argv[2])' "$stage_dir" "$LOCK_DIR" 2>/dev/null; then
    LOCK_ACQUIRED=1
    return 0
  fi

  rm -f "$stage_dir/pid" "$stage_dir/comm" 2>/dev/null || true
  rmdir "$stage_dir" 2>/dev/null || true

  echo "Failed to acquire lock. Exiting cleanly."
  exit 0
}

cleanup() {
  if [[ "$LOCK_ACQUIRED" -eq 1 ]]; then
    if [[ -f "$PID_FILE" ]]; then
      local held_pid
      held_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
      if [[ "$held_pid" == "$$" ]]; then
        rm -f "$PID_FILE" "$COMM_FILE" 2>/dev/null || true
        rmdir "$LOCK_DIR" 2>/dev/null || true
      fi
    fi
  fi
}
trap cleanup EXIT INT TERM

acquire_lock

# 6. Deduplicate catch-up triggers after system sleep
FORCE_RUN=false
for arg in "$@"; do
  if [[ "$arg" == "--force-run" || "$arg" == "--force" ]]; then
    FORCE_RUN=true
  fi
done
if [[ "${PRW_METRICS_FORCE_RUN:-}" == "1" || "${PRW_METRICS_FORCE_RUN:-}" == "true" ]]; then
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

# 7. Fail closed if PRW_METRICS_ROADMAP_REPO is not set
if [[ -z "${PRW_METRICS_ROADMAP_REPO:-}" ]]; then
  echo "ERROR: PRW_METRICS_ROADMAP_REPO is not set. It must be explicitly configured via environment or config.env." >&2
  exit 1
fi

export PRW_METRICS_STATE_DIR
export PRW_METRICS_ROADMAP_REPO
export PRW_METRICS_PUBLISH="${PRW_METRICS_PUBLISH:-1}"

echo "Starting PRW metrics collection at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

set +e
if [[ -n "${PRW_METRICS_COLLECTOR_CMD:-}" ]]; then
  bash -c "$PRW_METRICS_COLLECTOR_CMD"
else
  python3 "$REPO_DIR/scripts/prw_metrics.py" --roadmap-repo "$PRW_METRICS_ROADMAP_REPO" --state-dir "$PRW_METRICS_STATE_DIR"
fi
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
