#!/usr/bin/env bash
# check_session_conflict.sh — detect GitHub/container session-conflict divergence
#
# Ported forward from closed PR #8033's check_github_session_state() /
# container_status_for() (formerly self-hosted-oss/ubuntu-runner-health.sh,
# fully retired by PR #8057 + #8216 in favor of the ezgha fleet). See bead
# rev-ws17d.
#
# A runner container can show "Up X minutes" locally while GitHub's API
# reports status=offline — the container's Runner.Listener is stuck retrying
# a stale session ("Runner connect error: Error: Conflict"). Neither ezgha
# serve's own churn-replacement NOR the ezgha-watchdog fleet-size check
# catches this: both only compare a local "managed container count" against
# the configured target — a session-conflicted container is still alive and
# still counted as "managed" locally, so nothing local flags the GitHub-side
# divergence. This script cross-checks every GitHub-offline runner against
# its local container state so the two failure classes are never conflated:
#   - session_conflict   : GitHub offline, container running     -> manual heal (delete GH registration + restart container)
#   - runner_offline      : GitHub offline, container not running -> ezgha serve / ezgha-watchdog will respawn it
#   - docker_unavailable  : GitHub offline, local Docker daemon unreachable (mac fleet)
#   - ssh_unreachable     : GitHub offline, jeff-ubuntu unreachable over SSH (Linux fleet)
#
# Runner naming (ezgha, since 2026-07-06): ez-mac-runner-<gen>-N (mac,
# local docker) and ez-runner-<gen>-N / ez-canary-runner-<gen>-N (Linux, via
# SSH to jeff-ubuntu). ezgha rotates the <gen> letter on supervisor restart
# (observed live: "b" -> "c"), so match on the stable prefix only, never a
# hardcoded generation letter.
#
# Outputs JSON to stdout, exit 0 on success (even with conflicts found —
# the JSON body carries the verdict), non-zero on hard error (gh/api down).
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ORG="${GH_ORG:-jleechanorg}"
HEALTH_TARGET="${JEFF_UBUNTU_HOST:-jeff-ubuntu}"
SSH_TIMEOUT="${JEFF_UBUNTU_TIMEOUT:-5}"
DOCKER_SOCK_PATH="${JEFF_UBUNTU_DOCKER_SOCK:-unix:///home/$USER/.lima/colima/sock/docker.sock}"

if ! command -v gh >/dev/null 2>&1; then
  echo '{"timestamp":"'"$TS"'","org":"'"$ORG"'","error":"gh CLI not installed","offline_count":null,"session_conflicts":[],"runner_offline":[],"docker_unavailable":[],"ssh_unreachable":[],"invalid_names":[]}'
  exit 127
fi

# Resolve a runner's container status, branching by fleet.
#   ez-mac-runner-*                    -> local docker daemon (runs on this host)
#   ez-runner-*, ez-canary-runner-*, …  -> Lima on jeff-ubuntu (checked over SSH)
# ezgha rotates a generation letter suffix on restart (observed live:
# ez-runner-b-N became ez-runner-c-N), so match on the stable "ez-mac-runner-"
# / "ez-" prefixes only — never hardcode the generation letter.
# Echoes the docker State string ("running", "exited", ...), the literal
# "missing" when the container is absent, "docker_unavailable" when the local
# Docker daemon can't be probed, or "ssh_unreachable" when the Linux check
# can't reach jeff-ubuntu.
container_status_for() {
  local name="$1"

  # Root-cause guard: $name is sourced from the GitHub API runner list
  # (org-admin-settable runner metadata) and is later interpolated into a
  # remote SSH command string. The upstream "^ez-" prefix test (line ~80)
  # is a routing filter, not a security boundary — it still allows shell
  # metacharacters (quotes, `;`, `$()`, backticks, etc.) through. Reject
  # anything outside the known-safe runner name charset before it ever
  # reaches a command line, local or remote. The first character must be
  # alphanumeric — a leading '-' would otherwise let a crafted runner name
  # be interpreted as an option/flag by whatever consumes it downstream
  # (argument-injection shape), even though the full charset is safe.
  if [[ ! "$name" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]; then
    echo "invalid_runner_name"
    return
  fi

  if [[ "$name" =~ ^ez-mac-runner- ]]; then
    local status
    if status="$(docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null)"; then
      printf '%s\n' "$status"
    elif docker info >/dev/null 2>&1; then
      echo "missing"
    else
      echo "docker_unavailable"
    fi
  else
    # Belt-and-suspenders: even though $name is already allowlist-validated
    # above, build the remote command with %q quoting so it can never be
    # interpreted as anything but a single literal argument by the remote
    # shell (defense in depth, not a substitute for the validation above).
    local remote_cmd
    remote_cmd="$(printf 'DOCKER_HOST=%q docker inspect --format %q %q 2>/dev/null || echo missing' \
      "$DOCKER_SOCK_PATH" '{{.State.Status}}' "$name")"
    ssh -o ConnectTimeout="$SSH_TIMEOUT" \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
        "$HEALTH_TARGET" \
        "$remote_cmd" \
        2>/dev/null || echo "ssh_unreachable"
  fi
}

GH_ERR_FILE="$(mktemp)"
trap 'rm -f "$GH_ERR_FILE"' EXIT

OFFLINE_OUT="$(gh api --paginate "orgs/${ORG}/actions/runners?per_page=100" \
  --jq '.runners[]? | select(.name | test("^ez-")) | select(.status == "offline") | .name' 2>"$GH_ERR_FILE")"
GH_RC=$?

if [[ $GH_RC -ne 0 ]]; then
  RAW_ERR="$(tail -1 "$GH_ERR_FILE")"
  if [[ -z "$RAW_ERR" ]]; then
    RAW_ERR="gh api failed (exit $GH_RC)"
  fi
  ERR_MSG="$(printf '%s' "$RAW_ERR" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')"
  echo '{"timestamp":"'"$TS"'","org":"'"$ORG"'","error":'"$ERR_MSG"',"offline_count":null,"session_conflicts":[],"runner_offline":[],"docker_unavailable":[],"ssh_unreachable":[],"invalid_names":[]}'
  exit 1
fi

declare -a offline_runners=()
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  offline_runners+=("$name")
done <<<"$OFFLINE_OUT"

declare -a session_conflicts=() runner_offline=() docker_unavailable=() ssh_unreachable=() invalid_names=()

for name in "${offline_runners[@]}"; do
  status="$(container_status_for "$name")"
  case "$status" in
    running) session_conflicts+=("$name") ;;
    docker_unavailable) docker_unavailable+=("$name") ;;
    ssh_unreachable) ssh_unreachable+=("$name") ;;
    invalid_runner_name) invalid_names+=("$name") ;;
    *) runner_offline+=("$name") ;;
  esac
done

json_array() {
  # Prints a JSON array from the given bash array args (possibly empty).
  local -a items=("$@")
  if [[ ${#items[@]} -eq 0 ]]; then
    printf '[]'
    return
  fi
  printf '%s\n' "${items[@]}" | python3 -c 'import json,sys; print(json.dumps([l.rstrip(chr(10)) for l in sys.stdin]))'
}

SESSION_CONFLICTS_JSON="$(json_array "${session_conflicts[@]}")"
RUNNER_OFFLINE_JSON="$(json_array "${runner_offline[@]}")"
DOCKER_UNAVAILABLE_JSON="$(json_array "${docker_unavailable[@]}")"
SSH_UNREACHABLE_JSON="$(json_array "${ssh_unreachable[@]}")"
INVALID_NAMES_JSON="$(json_array "${invalid_names[@]}")"

printf '{"timestamp":"%s","org":"%s","error":null,"offline_count":%d,"session_conflicts":%s,"runner_offline":%s,"docker_unavailable":%s,"ssh_unreachable":%s,"invalid_names":%s}\n' \
  "$TS" "$ORG" "${#offline_runners[@]}" \
  "$SESSION_CONFLICTS_JSON" "$RUNNER_OFFLINE_JSON" "$DOCKER_UNAVAILABLE_JSON" "$SSH_UNREACHABLE_JSON" "$INVALID_NAMES_JSON"
exit 0
