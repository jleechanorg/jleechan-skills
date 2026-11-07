#!/usr/bin/env bash
# host-di[REDACTED_OPENAI_KEY] — alert on low HOST free disk, auto-clean at critical threshold
#
# Provenance: 2026-07-03 incident (bead rev-g5bwl) — host disk hit 100% (285MB
# free/926GB) mid runner-fleet recovery, corrupting colima's containerd content
# store (blob I/O errors) and nearly re-crashing the fleet. mac-runner-di[REDACTED_OPENAI_KEY]
# (retired along with self-hosted-oss) only ever watched CONTAINER overlay space,
# never true HOST free space — this script closes that specific gap.
#
# This is deliberately independent of ezgha's own disk floor check
# (src/docker_backend.rs, min_free_disk_gb): that check measures disk "as seen
# by the docker daemon" and gates NEW container spawns. It does not see or
# clean host-side, non-docker files (evidence bundles, scratchpads, stray
# worktrees) — the actual root cause of the 2026-07-03 incident.
#
# Usage:
#   bash host-di[REDACTED_OPENAI_KEY]                  # check + clean if critical
#   bash host-di[REDACTED_OPENAI_KEY] --dry-run         # report only, never delete
#   bash host-di[REDACTED_OPENAI_KEY] --check-only      # alias for --dry-run
#
# Exit codes:
#   0 = free space at or above WARN_THRESHOLD_GB (healthy)
#   1 = free space below WARN_THRESHOLD_GB (alert logged)
#   2 = free space below CRITICAL_THRESHOLD_GB (auto-clean ran)
#
# Logs to: /tmp/host-di[REDACTED_OPENAI_KEY]

set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG="${HOST_DISK_GUARDIAN_LOG:-/tmp/host-di[REDACTED_OPENAI_KEY]}"
DRY_RUN=0

# Bead rev-g5bwl's stated thresholds.
WARN_THRESHOLD_GB="${HOST_DISK_GUARDIAN_WARN_GB:-50}"
CRITICAL_THRESHOLD_GB="${HOST_DISK_GUARDIAN_CRITICAL_GB:-20}"

# Bead rev-g5bwl's stated safe-cleanup targets, in order of least-to-most risky.
# The evidence and worktree roots are project-specific, so they have no default:
# an unset root skips that cleanup target. The scratchpad root is derived from the
# Claude Code per-user temp folder.
EVIDENCE_DIR="${HOST_DISK_GUARDIAN_EVIDENCE_DIR:-}"
EVIDENCE_MAX_AGE_DAYS=2
SCRATCHPAD_DIR="${HOST_DISK_GUARDIAN_SCRATCHPAD_DIR:-/tmp/claude-$(id -u)}"
SCRATCHPAD_MAX_AGE_DAYS=3
WORKTREE_GLOB="${HOST_DISK_GUARDIAN_WORKTREE_GLOB:-}"

# These 3 roots are env-var overridable (see bead rev-9qxkm). Reject the most
# catastrophic misconfigurations -- empty, "/", or exactly "$HOME" -- before
# any find/rm runs. This is deliberately NOT a strict allowlist prefix (e.g.
# "must be under /tmp"): the default macOS `mktemp -d` resolves under
# /var/folders/.../T, not /tmp, so a strict prefix would reject legitimate
# test/CI temp roots. ponytail: this is a denylist ceiling, not full path
# canonicalization -- upgrade to a real allowlist if this script ever runs
# with untrusted env input (today it only runs from a trusted launchd job).
refuse_if_catastrophic_root() {
  local label="$1" path="$2"
  local resolved
  resolved="$(cd "$path" 2>/dev/null && pwd -P)"
  [[ -n "$resolved" ]] || resolved="$path"
  if [[ -z "$resolved" || "$resolved" == "/" || "$resolved" == "$HOME" ]]; then
    log "ERROR: $label resolves to '$resolved', refusing to run (catastrophic root guard)"
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|--check-only) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,24p' "$0"
      exit 0
      ;;
    *) shift ;;
  esac
done

log() { echo "[$TS] $*" | tee -a "$LOG"; }

# Bead rev-a6pww: the original WARN tier was log-only, no proactive alert
# reached a human. Rather than inventing a new Slack-webhook mechanism, reuse
# ezgha's own already-configured webhook (it already alerts on fleet/canary
# issues from the same host) -- read it at runtime, never hardcode or commit
# it. Missing config/field/curl failure all degrade to a log line, never a
# hard failure: a broken alert channel must not block the (successful, tested
# independently) di[REDACTED_OPENAI_KEY] logic.
EZGHA_CONFIG="${HOST_DISK_GUARDIAN_EZGHA_CONFIG:-$HOME/.config/ezgha/config.toml}"
send_slack_alert() {
  local message="$1"
  if (( DRY_RUN )); then
    log "  [dry-run] would send slack alert: $message"
    return
  fi
  [[ -f "$EZGHA_CONFIG" ]] || { log "  slack alert skipped: $EZGHA_CONFIG not found"; return; }
  local webhook_url
  webhook_url="$(sed -n 's/^[[:space:]]*slack_webhook_url[[:space:]]*=[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p' "$EZGHA_CONFIG" | head -1)"
  [[ -n "$webhook_url" ]] || { log "  slack alert skipped: no slack_webhook_url in $EZGHA_CONFIG"; return; }
  if ! command -v curl >/dev/null 2>&1; then
    log "  slack alert skipped: curl not available"
    return
  fi
  if ! command -v jq >/dev/null 2>&1; then
    log "  slack alert skipped: jq not available"
    return
  fi
  # jq -Rs (raw input, slurp) guarantees correct JSON string encoding for
  # ANY input -- backslashes, newlines, control characters -- unlike a
  # manual printf + shell-parameter-expansion escape, which only handled
  # literal double-quotes and would emit invalid JSON for a message
  # containing a backslash or embedded newline (e.g. if a future alert
  # message ever includes a raw discovered filename/path).
  local payload
  payload="$(printf '%s' "$message" | jq -Rsc '{text: .}')"
  if curl -sS -X POST -H 'Content-type: application/json' --data "$payload" "$webhook_url" >/dev/null 2>&1; then
    log "  slack alert sent"
  else
    log "  slack alert failed to send (curl error, network, or invalid webhook)"
  fi
}

[[ -z "$EVIDENCE_DIR" ]] || refuse_if_catastrophic_root "HOST_DISK_GUARDIAN_EVIDENCE_DIR" "$EVIDENCE_DIR"
refuse_if_catastrophic_root "HOST_DISK_GUARDIAN_SCRATCHPAD_DIR" "$SCRATCHPAD_DIR"
[[ -z "$WORKTREE_GLOB" ]] || refuse_if_catastrophic_root "HOST_DISK_GUARDIAN_WORKTREE_GLOB" "$(dirname -- "$WORKTREE_GLOB")"

# df -g is BSD/macOS-specific (1-command GB output, no awk math needed).
# This script is explicitly Mac-host-scoped per bead rev-g5bwl ("Host disk
# guardrail for Mac runner host") — Linux runner hosts have their own
# separate hardening tracked under bead rev-runn001.
free_gb() {
  df -g / 2>/dev/null | awk 'NR==2 {print $4}'
}

FREE_GB="$(free_gb)"
if [[ -z "$FREE_GB" ]]; then
  log "ERROR: could not read host free disk space via 'df -g /' -- is this running on macOS?"
  exit 2
fi

log "Host free disk: ${FREE_GB}GB (warn<${WARN_THRESHOLD_GB}GB, critical<${CRITICAL_THRESHOLD_GB}GB)"

if (( FREE_GB >= WARN_THRESHOLD_GB )); then
  log "OK: ${FREE_GB}GB free, above warn threshold."
  exit 0
fi

if (( FREE_GB >= CRITICAL_THRESHOLD_GB )); then
  log "ALERT: ${FREE_GB}GB free, below warn threshold (${WARN_THRESHOLD_GB}GB) but above critical (${CRITICAL_THRESHOLD_GB}GB). No auto-clean at this tier -- monitor only."
  send_slack_alert "host-di[REDACTED_OPENAI_KEY] WARN: ${FREE_GB}GB free on $(hostname) (threshold ${WARN_THRESHOLD_GB}GB). No auto-clean yet -- intervene before it drops below ${CRITICAL_THRESHOLD_GB}GB."
  exit 1
fi

log "CRITICAL: ${FREE_GB}GB free, below critical threshold (${CRITICAL_THRESHOLD_GB}GB). Running auto-clean."
send_slack_alert "host-di[REDACTED_OPENAI_KEY] CRITICAL: ${FREE_GB}GB free on $(hostname) (threshold ${CRITICAL_THRESHOLD_GB}GB). Running auto-clean now (evidence bundles, scratchpads, merged-PR worktrees)."

clean_evidence_bundles() {
  [[ -n "$EVIDENCE_DIR" ]] || { log "  HOST_DISK_GUARDIAN_EVIDENCE_DIR not configured: evidence-bundle root to prune. Example: export HOST_DISK_GUARDIAN_EVIDENCE_DIR=/tmp/<repo>-evidence -- skipping"; return; }
  [[ -d "$EVIDENCE_DIR" ]] || { log "  evidence dir $EVIDENCE_DIR does not exist, skipping"; return; }
  local count=0
  while IFS= read -r -d '' path; do
    local size
    size="$(du -sk "$path" 2>/dev/null | awk '{print $1}')"
    if (( DRY_RUN )); then
      log "  [dry-run] would delete evidence bundle: $path (${size:-0}KB)"
    else
      rm -rf "$path"
      log "  deleted evidence bundle: $path (${size:-0}KB)"
    fi
    count=$((count + 1))
  done < <(find "$EVIDENCE_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+${EVIDENCE_MAX_AGE_DAYS}" -print0 2>/dev/null)
  log "  evidence bundles processed: $count (older than ${EVIDENCE_MAX_AGE_DAYS}d)"
}

clean_scratchpads() {
  [[ -d "$SCRATCHPAD_DIR" ]] || { log "  scratchpad dir $SCRATCHPAD_DIR does not exist, skipping"; return; }
  local count=0
  while IFS= read -r -d '' path; do
    if (( DRY_RUN )); then
      log "  [dry-run] would delete scratchpad: $path"
    else
      rm -rf "$path"
      log "  deleted scratchpad: $path"
    fi
    count=$((count + 1))
  done < <(find "$SCRATCHPAD_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+${SCRATCHPAD_MAX_AGE_DAYS}" -print0 2>/dev/null)
  log "  scratchpads processed in $SCRATCHPAD_DIR: $count (older than ${SCRATCHPAD_MAX_AGE_DAYS}d)"
}

is_expected_origin() {
  case "$1" in
    https://github.com/$GITHUB_REPOSITORY | \
    https://github.com/$GITHUB_REPOSITORY.git | \
    git@github.com:$GITHUB_REPOSITORY | \
    git@github.com:$GITHUB_REPOSITORY.git | \
    ssh://git@github.com/$GITHUB_REPOSITORY | \
    ssh://git@github.com/$GITHUB_REPOSITORY.git)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Worktree cleanup is the highest-risk target (deletes a git working tree),
# so it gets four independent safety gates before anything is removed:
#   1. The worktree's own `origin` remote must actually be
#      $GITHUB_REPOSITORY -- a same-named branch in an unrelated
#      repo checkout under the glob must never be trusted by branch-name
#      lookup alone (bead rev-9qxkm).
#   2. The worktree's branch must have an associated PR that is CONFIRMED
#      merged, AND the worktree's current HEAD SHA must match that PR's
#      headRefOid exactly -- a reused/rebased branch name is not proof the
#      checked-out commit was ever part of the merged PR.
#   3. The worktree must have zero uncommitted changes (git status --porcelain
#      empty) -- never discard in-progress work, merged PR or not.
#   4. `git worktree remove` is called WITHOUT --force, so git's own
#      "worktree has changes" refusal is the REAL backstop even if gate 3
#      somehow missed something (a TOCTOU race between the status check and
#      this call, for example). --force previously bypassed this refusal
#      entirely, which defeated the backstop this comment claimed existed
#      (bead rev-9qxkm) -- if git refuses, log and skip, never escalate to a
#      raw rm -rf.
clean_merged_pr_worktrees() {
  [[ -n "$WORKTREE_GLOB" ]] || { log "  HOST_DISK_GUARDIAN_WORKTREE_GLOB not configured: glob of disposable worktrees. Example: export HOST_DISK_GUARDIAN_WORKTREE_GLOB='/tmp/<repo>-*' -- skipping worktree cleanup"; return; }
  [[ -n "${GITHUB_REPOSITORY:-}" ]] || { log "  GITHUB_REPOSITORY not configured: owner/repo whose merged-PR worktrees may be removed. Example: export GITHUB_REPOSITORY=owner/repo -- skipping worktree cleanup"; return; }
  command -v gh >/dev/null 2>&1 || { log "  gh CLI not available, skipping worktree cleanup"; return; }
  local count=0

  shopt -s nullglob
  # shellcheck disable=SC2206 # intentional glob expansion into an array;
  # nullglob (set above) makes an unmatched pattern expand to zero elements
  # instead of the literal glob string.
  local wt_candidates=($WORKTREE_GLOB)
  shopt -u nullglob

  for wt_path in "${wt_candidates[@]}"; do
    [[ -d "$wt_path/.git" || -f "$wt_path/.git" ]] || continue

    local branch
    branch="$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null)"
    [[ -n "$branch" && "$branch" != "HEAD" ]] || { log "  skip $wt_path: detached HEAD or unreadable branch"; continue; }

    local wt_remote
    wt_remote="$(git -C "$wt_path" remote get-url origin 2>/dev/null)"
    if ! is_expected_origin "$wt_remote"; then
      log "  skip $wt_path (branch $branch): origin remote is not $GITHUB_REPOSITORY, refusing branch-name-only trust"
      continue
    fi

    if [[ -n "$(git -C "$wt_path" status --porcelain 2>/dev/null)" ]]; then
      log "  skip $wt_path (branch $branch): uncommitted changes present"
      continue
    fi

    local wt_head
    wt_head="$(git -C "$wt_path" rev-parse HEAD 2>/dev/null)"

    local merged_sha
    merged_sha="$(gh pr list --repo "$GITHUB_REPOSITORY" --head "$branch" --state merged --json headRefOid --jq '.[0].headRefOid // empty' 2>/dev/null)"
    if [[ -z "$merged_sha" ]]; then
      log "  skip $wt_path (branch $branch): no merged PR found for this branch"
      continue
    fi
    if [[ "$wt_head" != "$merged_sha" ]]; then
      log "  skip $wt_path (branch $branch): worktree HEAD ($wt_head) does not match merged PR head ($merged_sha) -- branch reused or rebased since merge, refusing"
      continue
    fi

    if (( DRY_RUN )); then
      log "  [dry-run] would remove merged-PR worktree: $wt_path (branch $branch)"
      count=$((count + 1))
      continue
    fi

    local rm_output rm_rc
    rm_output="$(git -C "$wt_path" worktree remove "$wt_path" 2>&1)"
    rm_rc=$?
    if [[ $rm_rc -ne 0 ]]; then
      log "  skip $wt_path (branch $branch): git worktree remove refused (native dirty/lock check): $rm_output"
      continue
    fi
    if [[ -n "$rm_output" ]]; then
      while IFS= read -r line; do log "    $line"; done <<< "$rm_output"
    fi
    log "  removed merged-PR worktree: $wt_path (branch $branch)"
    count=$((count + 1))
  done
  log "  merged-PR worktrees processed: $count"
}

clean_evidence_bundles
clean_scratchpads
clean_merged_pr_worktrees

NEW_FREE_GB="$(free_gb)"
log "Auto-clean complete. Free disk: ${FREE_GB}GB -> ${NEW_FREE_GB:-unknown}GB"

exit 2
