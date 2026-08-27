#!/usr/bin/env bash
# dark-factory profile (callpath run dark-factory) — read-only auto-factory call-path health probe.
# Works from any cwd; resolves DARK_FACTORY_HOME (default ~/projects/dark-factory).
# Does NOT require factory-lite-harness.sh (decommissioned); overlay reads use sqlite.
set -euo pipefail

DF_HOME="${DARK_FACTORY_HOME:-$HOME/projects/dark-factory}"
export BR_DB="${BR_DB:-$DF_HOME/.beads/beads.db}"
br() { command br --db "$BR_DB" "$@"; }
OVERLAY_DB="${DAEMON_CXDB:-$HOME/.dark-factory/daemon-cxdb.sqlite}"
LOG_DIR="${HOME}/Library/Logs/dark-factory"
INTAKE="${DF_HOME}/daemon/factory-intake-from-gh.sh"
OVERLAY="${DF_HOME}/daemon/factory-overlay.sh"
RUST_RELEASE="${DF_HOME}/daemon/target/release/daemon"
RUST_DEBUG="${DF_HOME}/daemon/target/debug/daemon"
HARNESS="${DF_HOME}/daemon/factory-lite-harness.sh"
CONFIG="${DF_HOME}/config/daemon.toml"
[[ -f "$CONFIG" ]] || CONFIG="${DF_HOME}/daemon/config.toml"
[[ -f "$CONFIG" ]] || CONFIG="${DF_HOME}/daemon/contracts/daemon.toml.example"

PRS=""
ISSUES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prs) PRS="$2"; shift 2 ;;
    --issue) ISSUES="${ISSUES} $2"; shift 2 ;;
    -h|--help)
      echo "Usage: callpath.sh [--prs N,N,...]"
      echo "Read-only factory call-path health (DARK_FACTORY_HOME=${DF_HOME})"
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

now_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
worst="GREEN"

bump() {
  local v="$1"
  [[ "$v" == RED ]] && worst=RED
  [[ "$v" == AMBER && "$worst" != RED ]] && worst=AMBER
  return 0
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

# Subcommands required in daemon/factory-overlay.sh for the overlay-harness
# layer check (replaces the decommissioned factory-lite-harness.sh probes).
# See bead $USER-df94 and PR #167 (commit 10dc5b16a).
OVERLAY_HARNESS_SUBCOMMANDS=(
  init
  intake-upsert
  route-record
  capacity
  dispatch-record
  pr-opened
  autonomy-tick
  gate-assessment
  prev-gate-assessment
  ready
  reroll-verdict
  park
  park-duplicate
  bead-closed-check
  tick-summary
  recover-held
  unstick-dispatching
  redrive-pr
  list
)

# overlay_harness_check <overlay-script-path>
# Verifies factory-overlay.sh exists, is executable, AND implements every
# required subcommand. Prints:
#   - "ok/<count>" (e.g. "ok/19") on success
#   - "missing:<sub>" on the first missing subcommand (alphabetical probe order)
# Returns 0 if all subcommands present, 1 if the script is missing or any
# required subcommand is absent. Layer color logic relies on the prefix only.
overlay_harness_check() {
  local overlay_path="$1"
  if [[ ! -x "$overlay_path" ]]; then
    echo "missing:overlay"
    return 1
  fi
  local sub
  for sub in "${OVERLAY_HARNESS_SUBCOMMANDS[@]}"; do
    if ! grep -qE "^${sub}\)" "$overlay_path" 2>/dev/null; then
      echo "missing:${sub}"
      return 1
    fi
  done
  echo "ok/${#OVERLAY_HARNESS_SUBCOMMANDS[@]}"
  return 0
}

read_config() {
  local key="$1" default="$2"
  if [[ ! -f "$CONFIG" ]]; then
    echo "$default"
    return
  fi
  python3 - "$CONFIG" "$key" "$default" <<'PY'
import re, sys
path, key, default = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()
m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text, re.M)
if m:
    print(m.group(1))
else:
    m = re.search(rf'^\s*{re.escape(key)}\s*=\s*(\S+)', text, re.M)
    print(m.group(1) if m else default)
PY
}

TARGET_REPO="$(read_config target_repo "$GITHUB_REPOSITORY")"
STAGE="$(read_config stage "?")"
FACTORY_LABEL="${FACTORY_LABEL:-factory}"

overlay_count() {
  local state="$1"
  if [[ ! -f "$OVERLAY_DB" ]]; then
    echo 0
    return
  fi
  sqlite3 "$OVERLAY_DB" "SELECT COUNT(*) FROM bead_overlay WHERE state='${state}';" 2>/dev/null || echo 0
}

overlay_total() {
  if [[ ! -f "$OVERLAY_DB" ]]; then
    echo 0
    return
  fi
  sqlite3 "$OVERLAY_DB" "SELECT COUNT(*) FROM bead_overlay;" 2>/dev/null || echo 0
}

daemon_process_line() {
  local bin="$1"
  [[ "$bin" == "missing" || ! -x "$bin" ]] && return 1
  pgrep -fl "$bin" 2>/dev/null | grep -v rustc | head -1 || true
}

coder_v="SKIP"
coder_note="factory-lite not running"
verifier_v="SKIP"
verifier_note="factory-lite not running"
if pgrep -f 'run-factory-lite.sh coder' >/dev/null 2>&1; then
  coder_v="AMBER"
  coder_note="alive"
  if tail -1 "$LOG_DIR/factory-lite-coder.log" 2>/dev/null | grep -q ' OK'; then
    coder_v="GREEN"
  fi
fi
if pgrep -f 'run-factory-lite.sh verifier' >/dev/null 2>&1; then
  verifier_v="AMBER"
  verifier_note="alive"
  if tail -1 "$LOG_DIR/factory-lite-verifier.log" 2>/dev/null | grep -q ' OK'; then
    verifier_v="GREEN"
  fi
fi
[[ "$coder_v" != SKIP ]] && bump "$([[ "$coder_v" == GREEN ]] && echo GREEN || echo AMBER)"
[[ "$verifier_v" != SKIP ]] && bump "$([[ "$verifier_v" == GREEN ]] && echo GREEN || echo AMBER)"

rust_bin="missing"
rust_v="RED"
if [[ -x "$RUST_RELEASE" ]]; then
  rust_bin="$RUST_RELEASE"
  rust_v="AMBER"
elif [[ -x "$RUST_DEBUG" ]]; then
  rust_bin="$RUST_DEBUG"
  rust_v="AMBER"
fi
rust_pid=""
if rust_line="$(daemon_process_line "$rust_bin")"; then
  [[ -n "$rust_line" ]] && rust_v="GREEN" && rust_pid="$rust_line"
fi
[[ "$rust_bin" == missing ]] && bump RED || bump "$([[ "$rust_v" == GREEN ]] && echo GREEN || echo AMBER)"

intake_v="RED"
intake_note="missing"
if [[ -f "$INTAKE" ]]; then
  intake_v="AMBER"
  intake_note="present"
  [[ -x "$INTAKE" ]] && intake_v="GREEN" && intake_note="executable"
fi
bump "$intake_v"

overlay_v="RED"
overlay_summary=""
overlay_db_note="missing"
if [[ -f "$OVERLAY_DB" ]]; then
  overlay_v="GREEN"
  overlay_db_note="ok $(du -h "$OVERLAY_DB" 2>/dev/null | awk '{print $1}')"
  for s in QUEUED DISPATCHING DISPATCHED ATTESTED READY HUMAN_HELD RE_ROLL; do
    c="$(overlay_count "$s")"
    overlay_summary="${overlay_summary}${s}=${c} "
  done
elif [[ -x "$HARNESS" ]]; then
  overlay_v="AMBER"
  overlay_db_note="harness-only legacy fallback (no sqlite)"
  for s in QUEUED DISPATCHED ATTESTED READY HUMAN_HELD; do
    c=$("$HARNESS" list "$s" 2>/dev/null | python3 -c 'import sys,json; d=sys.stdin.read().strip(); print(len(json.loads(d)) if d.startswith("[") else 0)' 2>/dev/null || echo 0)
    overlay_summary="${overlay_summary}${s}=${c} "
  done
else
  overlay_db_note="no db (harness decommissioned — sqlite path expected at ${OVERLAY_DB})"
  overlay_v="AMBER"
fi
bump "$([[ "$overlay_v" == RED ]] && echo RED || echo "$overlay_v")"

gh_v="SKIP"
gh_count=0
gh_note="gh unavailable"
gh_json="[]"
if have_cmd gh; then
  gh_json="$(gh issue list --repo "$TARGET_REPO" --label "$FACTORY_LABEL" --state open --json number,title --limit 50 2>/dev/null || echo '[]')"
  gh_count="$(printf '%s' "$gh_json" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)"
  if [[ "$gh_count" -gt 0 ]]; then
    gh_v="GREEN"
    gh_note="${gh_count} open on ${TARGET_REPO}"
  else
    gh_v="AMBER"
    gh_note="0 open factory issues on ${TARGET_REPO}"
  fi
  bump "$gh_v"
fi

br_v="SKIP"
br_factory=0
br_with_ext=0
br_orphan=0
br_note="br unavailable"
beads_json="{}"
if have_cmd br; then
  beads_json="$(br list --status open --json 2>/dev/null || echo '{}')"
  read -r br_factory br_with_ext br_orphan <<<"$(BEADS_JSON="$beads_json" python3 -c '
import json, os
data = json.loads(os.environ["BEADS_JSON"])
issues = data.get("issues") or []
factory = [i for i in issues if "factory" in (i.get("labels") or [])]
with_ext = [i for i in factory if i.get("external_ref")]
print(len(factory), len(with_ext), len(factory) - len(with_ext))
' || echo '0 0 0')"
  if [[ "$br_factory" -gt 0 ]]; then
    if [[ "$br_orphan" -eq 0 ]]; then
      br_v="GREEN"
      br_note="${br_factory} factory beads, all ${br_with_ext} linked via external_ref"
    else
      br_v="AMBER"
      br_note="${br_factory} factory beads, ${br_with_ext} with external_ref, ${br_orphan} orphan"
    fi
  else
    br_v="AMBER"
    br_note="0 open factory-labeled beads"
  fi
  bump "$br_v"
fi

config_v="AMBER"
config_note="config missing"
if [[ -f "$CONFIG" ]]; then
  config_v="GREEN"
  config_note="stage=${STAGE} target=${TARGET_REPO}"
fi
bump "$([[ "$config_v" == GREEN ]] && echo GREEN || echo AMBER)"

trace_step() {
  local name="$1" status="$2" detail="$3"
  printf "  %-22s %-5s %s\n" "$name" "$status" "$detail"
}

pipeline_trace_infra() {
  echo "## Pipeline trace (call-path infrastructure)"
  local q d att rdy ht dispatching
  q="$(overlay_count QUEUED)"
  d="$(overlay_count DISPATCHED)"
  att="$(overlay_count ATTESTED)"
  rdy="$(overlay_count READY)"
  ht="$(overlay_count HUMAN_HELD)"
  dispatching="$(overlay_count DISPATCHING)"

  if [[ "$gh_v" == SKIP ]]; then
    trace_step "gh_label_factory" "SKIP" "$gh_note"
  else
    trace_step "gh_label_factory" "$([[ "$gh_v" == GREEN ]] && echo PASS || echo FAIL)" "$gh_note"
  fi

  trace_step "intake_normalizer" "$([[ "$intake_v" == GREEN ]] && echo PASS || echo FAIL)" "$intake_note ($INTAKE)"

  if [[ "$br_v" == SKIP ]]; then
    trace_step "br_bead_external_ref" "SKIP" "$br_note"
  elif [[ "$br_orphan" -eq 0 && "$br_factory" -gt 0 ]]; then
    trace_step "br_bead_external_ref" "PASS" "$br_note"
  elif [[ "$br_with_ext" -gt 0 ]]; then
    trace_step "br_bead_external_ref" "FAIL" "$br_note"
  else
    trace_step "br_bead_external_ref" "FAIL" "$br_note"
  fi

  if [[ -f "$OVERLAY_DB" ]]; then
    trace_step "overlay_QUEUED" "PASS" "db ok QUEUED=${q} total=$(overlay_total)"
  elif [[ -x "$HARNESS" ]]; then
    trace_step "overlay_QUEUED" "PASS" "harness legacy QUEUED=${q}"
  else
    trace_step "overlay_QUEUED" "SKIP" "no sqlite/harness; rust daemon uses ${OVERLAY_DB} when initialized"
  fi

  if [[ "$rust_v" == GREEN ]] || [[ "$coder_v" == GREEN || "$coder_v" == AMBER ]]; then
    trace_step "route" "PASS" "rust=${rust_v} factory-lite-coder=${coder_v}"
  else
    trace_step "route" "FAIL" "no rust daemon process and no factory-lite coder loop"
  fi

  if [[ "$dispatching" -gt 0 || "$d" -gt 0 ]] || [[ "$coder_v" == GREEN || "$coder_v" == AMBER ]]; then
    trace_step "dispatch" "PASS" "DISPATCHING=${dispatching} DISPATCHED=${d}"
  elif [[ "$q" -gt 0 ]]; then
    trace_step "dispatch" "FAIL" "QUEUED=${q} but nothing dispatching"
  else
    trace_step "dispatch" "SKIP" "no beads in queue"
  fi

  if [[ "$att" -gt 0 ]]; then
    trace_step "ATTESTED" "PASS" "${att} bead(s) ATTESTED"
  elif [[ "$d" -gt 0 || "$dispatching" -gt 0 ]]; then
    trace_step "ATTESTED" "FAIL" "dispatched but none attested yet"
  else
    trace_step "ATTESTED" "SKIP" "no beads at dispatch stage"
  fi

  if [[ "$rust_v" == GREEN && "$STAGE" != "?" ]]; then
    trace_step "verifier" "PASS" "rust daemon stage=${STAGE} verifier=${verifier_v}"
  elif [[ "$verifier_v" == GREEN || "$verifier_v" == AMBER ]]; then
    trace_step "verifier" "PASS" "factory-lite verifier ${verifier_note}"
  elif [[ "$att" -gt 0 ]]; then
    trace_step "verifier" "FAIL" "ATTESTED=${att} but no verifier plane running"
  else
    trace_step "verifier" "SKIP" "nothing to verify"
  fi

  if [[ "$rdy" -gt 0 ]]; then
    trace_step "READY" "PASS" "${rdy} bead(s) READY"
  elif [[ "$att" -gt 0 ]]; then
    trace_step "READY" "FAIL" "ATTESTED=${att} none READY yet (HUMAN_HELD=${ht})"
  else
    trace_step "READY" "SKIP" "pipeline has not reached attestation"
  fi
}

pipeline_trace_issue() {
  local number="$1"
  local ext="${TARGET_REPO}#${number}"
  echo ""
  echo "### Issue #${number} (${ext})"
  local bead_id=""
  bead_id="$(BEADS_JSON="$beads_json" EXT="$ext" python3 -c '
import json, os
ext = os.environ["EXT"]
data = json.loads(os.environ["BEADS_JSON"])
for i in data.get("issues") or []:
    if i.get("external_ref") == ext:
        print(i.get("id", ""))
        break
' || true)"
  local ostate=""
  if [[ -n "$bead_id" && -f "$OVERLAY_DB" ]]; then
    ostate="$(sqlite3 "$OVERLAY_DB" "SELECT state FROM bead_overlay WHERE bead_id='${bead_id}';" 2>/dev/null || true)"
  fi

  trace_step "gh_label_factory" "PASS" "open issue #${number}"
  trace_step "intake_normalizer" "$([[ "$intake_v" == GREEN ]] && echo PASS || echo FAIL)" "$intake_note"
  if [[ -n "$bead_id" ]]; then
    trace_step "br_bead_external_ref" "PASS" "bead=${bead_id}"
  else
    trace_step "br_bead_external_ref" "FAIL" "no bead for ${ext}"
  fi
  if [[ -z "$bead_id" ]]; then
    trace_step "overlay_QUEUED" "SKIP" "no bead"
    trace_step "route" "SKIP" "no bead"
    trace_step "dispatch" "SKIP" "no bead"
    trace_step "ATTESTED" "SKIP" "no bead"
    trace_step "verifier" "SKIP" "no bead"
    trace_step "READY" "SKIP" "no bead"
    return
  fi
  case "$ostate" in
    QUEUED)
      trace_step "overlay_QUEUED" "PASS" "state=QUEUED"
      trace_step "route" "FAIL" "still QUEUED"
      trace_step "dispatch" "FAIL" "still QUEUED"
      trace_step "ATTESTED" "SKIP" ""
      trace_step "verifier" "SKIP" ""
      trace_step "READY" "SKIP" ""
      ;;
    DISPATCHING|DISPATCHED)
      trace_step "overlay_QUEUED" "PASS" "past intake"
      trace_step "route" "PASS" "state=${ostate}"
      trace_step "dispatch" "PASS" "state=${ostate}"
      trace_step "ATTESTED" "FAIL" "not yet attested"
      trace_step "verifier" "SKIP" ""
      trace_step "READY" "SKIP" ""
      ;;
    ATTESTED)
      trace_step "overlay_QUEUED" "PASS" "past intake"
      trace_step "route" "PASS" "routed"
      trace_step "dispatch" "PASS" "dispatched"
      trace_step "ATTESTED" "PASS" "state=ATTESTED"
      trace_step "verifier" "$([[ "$verifier_v" == GREEN || "$verifier_v" == AMBER || "$rust_v" == GREEN ]] && echo PASS || echo FAIL)" "verifier plane"
      trace_step "READY" "FAIL" "awaiting gates"
      ;;
    READY)
      trace_step "overlay_QUEUED" "PASS" "past intake"
      trace_step "route" "PASS" "routed"
      trace_step "dispatch" "PASS" "dispatched"
      trace_step "ATTESTED" "PASS" "attested"
      trace_step "verifier" "PASS" "gates passed"
      trace_step "READY" "PASS" "state=READY"
      ;;
    HUMAN_HELD|BUDGET_HELD|RE_ROLL|RECOVERY|REDISPATCHED|"")
      trace_step "overlay_QUEUED" "$([[ -n "$ostate" ]] && echo PASS || echo FAIL)" "state=${ostate:-missing}"
      trace_step "route" "$([[ "$ostate" == DISPATCHING || "$ostate" == DISPATCHED || "$ostate" == ATTESTED || "$ostate" == READY || "$ostate" == HUMAN_HELD ]] && echo PASS || echo FAIL)" "${ostate:-no overlay row}"
      trace_step "dispatch" "$([[ "$ostate" != QUEUED && -n "$ostate" ]] && echo PASS || echo SKIP)" "${ostate:-—}"
      trace_step "ATTESTED" "$([[ "$ostate" == ATTESTED || "$ostate" == READY || "$ostate" == HUMAN_HELD ]] && echo PASS || echo SKIP)" "${ostate:-—}"
      trace_step "verifier" "$([[ "$ostate" == HUMAN_HELD ]] && echo PASS || echo SKIP)" "held for human/evidence"
      trace_step "READY" "$([[ "$ostate" == READY ]] && echo PASS || echo FAIL)" "${ostate:-—}"
      ;;
    *)
      trace_step "overlay_QUEUED" "PASS" "state=${ostate}"
      trace_step "route" "PASS" ""
      trace_step "dispatch" "PASS" ""
      trace_step "ATTESTED" "SKIP" ""
      trace_step "verifier" "SKIP" ""
      trace_step "READY" "SKIP" ""
      ;;
  esac
}

echo "# /callpath — ${now_utc} — verdict=${worst}"
echo "DARK_FACTORY_HOME=${DF_HOME}"
echo ""
echo "## Layers"
echo "  factory-lite-coder: ${coder_v} (${coder_note})"
echo "  factory-lite-verifier: ${verifier_v} (${verifier_note})"
echo "  rust-daemon: ${rust_v} (bin=${rust_bin})"
[[ -n "$rust_pid" ]] && echo "  rust-pid: ${rust_pid}"
# Override set -e propagation: capture the probe output + return code without
# tripping `set -euo pipefail` when the function reports a missing subcommand.
overlay_harness_result="$(overlay_harness_check "${OVERLAY}" || true)"
if [[ "${overlay_harness_result}" == ok/* ]]; then
  echo "  overlay-harness: GREEN (factory-overlay.sh; ${overlay_harness_result})"
else
  echo "  overlay-harness: RED (${overlay_harness_result})"
fi
echo "  overlay-db: ${overlay_v} (${overlay_db_note})"
echo "  gh-factory-issues: ${gh_v} (${gh_note})"
echo "  br-factory-beads: ${br_v} (${br_note})"
echo "  stage-config: ${config_v} (${config_note})"
echo ""
echo "## Overlay counts"
echo "  ${overlay_summary:-none}"
echo "  db=${OVERLAY_DB}"
if [[ -x "$HARNESS" ]]; then
  echo "  harness=${HARNESS} (optional legacy fallback)"
else
  echo "  harness=SKIP (decommissioned — sqlite/rust path)"
fi
echo ""
echo "## Config"
echo "  file=${CONFIG}"
echo "  stage=${STAGE} target_repo=${TARGET_REPO} label=${FACTORY_LABEL}"
echo ""

pipeline_trace_infra

if [[ -n "${ISSUES// /}" ]]; then
  issue_numbers="$(printf '%s\n' $ISSUES | sed '/^$/d')"
else
  issue_numbers="$(printf '%s' "$gh_json" | python3 -c 'import json,sys; [print(i["number"]) for i in json.load(sys.stdin)[:3]]' 2>/dev/null || true)"
fi
if [[ -n "$issue_numbers" ]]; then
  echo ""
  echo "## Pipeline trace (factory issues)"
  while read -r num; do
    num="$(echo "$num" | tr -d ' ')"
    [[ -n "$num" ]] && pipeline_trace_issue "$num"
  done <<< "$issue_numbers"
fi

if [[ -n "$PRS" ]]; then
  echo ""
  echo "## Target PR gates (--prs)"
  IFS=',' read -ra PR_ARR <<< "$PRS"
  for pr in "${PR_ARR[@]}"; do
    pr="$(echo "$pr" | tr -d ' ')"
    gh pr view "$pr" --repo "$TARGET_REPO" --json number,mergeable,mergeStateStatus,headRefName 2>/dev/null \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('PR #{} mergeable={} state={} branch={}'.format(d['number'], d.get('mergeable'), d.get('mergeStateStatus'), d.get('headRefName')))" \
      2>/dev/null || echo "PR #${pr} query failed"
  done
fi

if [[ -f "$LOG_DIR/daemon.jsonl" ]]; then
  echo ""
  echo "## Telemetry tail (daemon.jsonl)"
  tail -3 "$LOG_DIR/daemon.jsonl" 2>/dev/null || true
fi
