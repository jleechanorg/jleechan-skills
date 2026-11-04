#!/usr/bin/env bash
# ezgha-fleet-watchdog.sh — enforce 6 mac + 10 linux runner invariant
#
# Detects when ezgha serve supervisor is alive but below configured count
# (a known ezgha design gap: serve replaces churned slots but does not
# aggressively top-up to N when below count). On detection, LOGS the
# shortfall always; it only restarts the supervisor on the affected host if
# EZGHA_WATCHDOG_ALLOW_RESTART=1 is set (fail-closed by default — see
# SKILL.md).
#
# Usage:
#   bash ezgha-fleet-watchdog.sh                  # check both hosts, alert if below target
#   bash ezgha-fleet-watchdog.sh --host mac       # only MacBook
#   bash ezgha-fleet-watchdog.sh --host linux     # only jeff-ubuntu
#   bash ezgha-fleet-watchdog.sh --dry-run        # report only, never restart even if opted in
#
# Env:
#   EZGHA_WATCHDOG_ALLOW_RESTART=1   # opt-in: actually execute the restart
#                                    # command once past the hysteresis
#                                    # threshold. Unset/0 = detect + log only.
#
# Exit codes:
#   0 = both hosts at or above configured count
#   1 = one or more hosts below count (fixed or reported)
#   2 = supervisor not installed (manual install needed)
#
# Logs to: /tmp/ezgha-watchdog.log

set -uo pipefail

EZGHA="${EZGHA_BIN:-$HOME/.cargo/bin/ezgha}"
LOG="/tmp/ezgha-watchdog.log"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DRY_RUN=0
HOST_FILTER=""

# Fail-closed by default (SKILL.md: "Restart-only remediation is UNAVAILABLE
# (fail-closed)" — a 2026-07-09..11 audit, bead rev-ft3i8 / GH issue #8329,
# found restarts can kill active jobs, create offline-busy 422 registrations,
# and cannot repair a dead/wrong-namespace backend). The watchdog always
# detects and logs a shortfall; it only executes the actual restart command
# when an operator has explicitly opted in via this env var — set it in the
# launchd/systemd unit only after confirming PR 67/70 (or equivalent) has
# landed and is proven live. Found by a real /advice pass on PR #8393,
# 2026-07-16: the live script restarted unconditionally with no way to
# disable it short of --dry-run (which also suppresses colima auto-start).
ALLOW_RESTART="${EZGHA_WATCHDOG_ALLOW_RESTART:-0}"

# Hysteresis state directory. Each invocation of this script is a single
# sample — launchd/systemd re-invoke it fresh every ~120s rather than
# running it as one long-lived loop — so the consecutive-shortfall count
# must persist on disk across invocations. Scoped under $HOME (like the
# ezgha config.toml this script already reads) so test suites that
# override HOME get automatic state isolation.
STATE_DIR="${EZGHA_WATCHDOG_STATE_DIR:-$HOME/.cache/ezgha-watchdog}"
mkdir -p "$STATE_DIR" 2>/dev/null

# SKILL.md: "Only alert if a slot has been missing for >2 watchdog cycles
# (4 minutes)." A restart fires once the consecutive below-target count
# EXCEEDS this threshold (i.e. on the 3rd consecutive sample).
HYSTERESIS_THRESHOLD=2

read_consecutive() {
  local file="$STATE_DIR/$1.consecutive"
  if [[ -f "$file" ]]; then cat "$file"; else echo 0; fi
}

write_consecutive() {
  local file="$STATE_DIR/$1.consecutive"
  echo "$2" > "$file"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST_FILTER="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,27p' "$0"
      exit 0
      ;;
    *) shift ;;
  esac
done

log() { echo "[$TS] $*" | tee -a "$LOG"; }

# Read the status of the Colima profile literally named "default".
# Filtering by name (not head -n 1) is critical because Colima can list
# multiple profiles and the first row may not be the one ezgha uses.
# `colima list --json` emits one JSON object per profile (NDJSON).
read_colima_state() {
  # Ask colima itself (NDJSON, one object per profile) -- NOT bare
  # `limactl list`. Bare limactl reads ~/.lima, which on this host contains
  # a STALE Stopped VM named "colima" (4CPU/100GiB relic), while the live
  # profile runs under colima's own Lima home (~/.colima/_lima, vz). The
  # stale row made this watchdog loop "auto-starting colima" forever with
  # exit 2 while the real VM was Running (2026-07-16, Mac twin of bead
  # ez-gh-actions-ghd2.6 dual-Lima namespace).
  colima list --json 2>/dev/null | python3 -c "
import json, sys
profile = 'default'
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        v = json.loads(line)
    except Exception:
        continue
    if isinstance(v, dict) and v.get('name') == profile:
        print(v.get('status', 'Unknown'))
        break
" 2>/dev/null
}


read_configured_count() {
  python3 -c '
import sys
import tomllib

try:
    config = tomllib.loads(sys.stdin.read())
except (tomllib.TOMLDecodeError, UnicodeDecodeError):
    raise SystemExit(0)

runner = config.get("runner")
count = runner.get("count") if isinstance(runner, dict) else None
if type(count) is int and count >= 0:
    print(count)
'
}


ensure_colima_running() {
  # MacBook uses colima as the Docker backend. If colima VM is stopped,
  # ezgha serve refuses to spawn runners (fail-closed on policy.minimum_isolation=vm).
  # Detect and auto-start before declaring fleet state.
  local lima_state
  lima_state=$(read_colima_state)
  if [[ "$lima_state" == "Running" ]]; then
    return 0
  fi
  log "COLIMA: VM state=$lima_state — auto-starting colima"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return 1
  fi

  colima start 2>&1 | tee -a "$LOG" || log "COLIMA: start failed — manual intervention needed"
  # Verify it actually came up; colima has a "already running, ignoring" stuck state
  sleep 5
  lima_state=$(read_colima_state)
  if [[ "$lima_state" != "Running" ]]; then
    log "COLIMA: still not Running after start (state=$lima_state) — try 'colima stop --force && colima start'"
    return 2
  fi
  return 0
}

check_mac() {
  if [[ -n "$HOST_FILTER" && "$HOST_FILTER" != "mac" ]]; then return 0; fi
  if ! command -v "$EZGHA" >/dev/null 2>&1; then
    log "MAC: ezgha binary not found at $EZGHA"
    return 2
  fi

  # Ensure Docker backend (colima) is running BEFORE checking fleet state.
  ensure_colima_running || return $?

  local configured actual config_file="$HOME/.config/ezgha/config.toml"
  configured=$(read_configured_count < "$config_file" 2>/dev/null)
  actual=$("$EZGHA" status 2>/dev/null | grep -oE "managed containers: [0-9]+" | grep -oE "[0-9]+")

  if [[ -z "$configured" || -z "$actual" ]]; then
    log "MAC: cannot read state (config=$configured actual=$actual) — supervisor may be unable to spawn (check stderr for isolation policy errors)"
    return 2
  fi

  log "MAC: configured=$configured, managed=$actual"

  if [[ "$actual" -lt "$configured" ]]; then
    local consecutive
    consecutive=$(read_consecutive mac)
    consecutive=$((consecutive + 1))
    write_consecutive mac "$consecutive"
    log "MAC: BELOW TARGET ($actual < $configured) — consecutive=$consecutive"
    if [[ "$consecutive" -gt "$HYSTERESIS_THRESHOLD" ]]; then
      if [[ "$DRY_RUN" -eq 0 && "$ALLOW_RESTART" -eq 1 ]]; then
        log "MAC: consecutive shortfall exceeds $HYSTERESIS_THRESHOLD cycles — restarting ezgha serve via launchctl"
        launchctl kickstart -k "gui/$(id -u)/org.jleechanorg.ezgha" 2>&1 | tee -a "$LOG"
      else
        log "MAC: consecutive shortfall exceeds $HYSTERESIS_THRESHOLD cycles — restart SKIPPED (fail-closed default; set EZGHA_WATCHDOG_ALLOW_RESTART=1 to enable, only after confirming a live-deployed non-destructive recovery path)"
      fi
    else
      log "MAC: within normal churn window (consecutive=$consecutive <= $HYSTERESIS_THRESHOLD) — not restarting yet"
    fi
    return 1
  fi
  write_consecutive mac 0
  return 0
}

check_linux() {
  if [[ -n "$HOST_FILTER" && "$HOST_FILTER" != "linux" ]]; then return 0; fi
  local configured actual
  configured=$(ssh -o ConnectTimeout=5 jeff-ubuntu 'cat ~/.config/ezgha/config.toml 2>/dev/null' 2>/dev/null | read_configured_count)
  actual=$(ssh -o ConnectTimeout=5 jeff-ubuntu '$HOME/.cargo/bin/ezgha status 2>/dev/null | grep -oE "managed containers: [0-9]+" | grep -oE "[0-9]+"' 2>/dev/null)

  if [[ -z "$configured" || -z "$actual" ]]; then
    log "LINUX: cannot read state from jeff-ubuntu (ssh timeout or ezgha missing)"
    return 2
  fi

  log "LINUX: configured=$configured, managed=$actual"

  if [[ "$actual" -lt "$configured" ]]; then
    local consecutive
    consecutive=$(read_consecutive linux)
    consecutive=$((consecutive + 1))
    write_consecutive linux "$consecutive"
    log "LINUX: BELOW TARGET ($actual < $configured) — consecutive=$consecutive"
    if [[ "$consecutive" -gt "$HYSTERESIS_THRESHOLD" ]]; then
      if [[ "$DRY_RUN" -eq 0 && "$ALLOW_RESTART" -eq 1 ]]; then
        log "LINUX: consecutive shortfall exceeds $HYSTERESIS_THRESHOLD cycles — restarting ezgha.service via systemd"
        ssh -o ConnectTimeout=5 jeff-ubuntu "systemctl --user restart ezgha" 2>&1 | tee -a "$LOG"
      else
        log "LINUX: consecutive shortfall exceeds $HYSTERESIS_THRESHOLD cycles — restart SKIPPED (fail-closed default; set EZGHA_WATCHDOG_ALLOW_RESTART=1 to enable, only after confirming a live-deployed non-destructive recovery path)"
      fi
    else
      log "LINUX: within normal churn window (consecutive=$consecutive <= $HYSTERESIS_THRESHOLD) — not restarting yet"
    fi
    return 1
  fi
  write_consecutive linux 0
  return 0
}

# Aggregate host results: severity 2 (cannot read state) beats 1 (below target).
mac_rc=0
linux_rc=0
check_mac || mac_rc=$?
check_linux || linux_rc=$?
EXIT=0
for rc in "$mac_rc" "$linux_rc"; do
  if [[ "$rc" -gt "$EXIT" ]]; then
    EXIT=$rc
  fi
done

if [[ "$EXIT" -eq 0 ]]; then
  log "OK: both hosts at configured count"
elif [[ "$EXIT" -eq 2 ]]; then
  log "WARN: one or more hosts missing ezgha or unreachable — manual intervention needed"
fi

exit $EXIT
