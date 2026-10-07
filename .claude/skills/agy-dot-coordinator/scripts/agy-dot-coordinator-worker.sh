#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh
# Periodic worker coordinating with the ChatGPT dot assistant across all accounts.
# Reminds dot to prioritize and drive work on cloud computer environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${COORDINATOR_STATE_DIR:-$HOME/.local/state/ai.gemini.agy-dot-coordinator}"
STATE_FILE="$STATE_DIR/state.json"
CONFIG_FILE="${DOT_CONFIG_FILE:-$HOME/.config/dot/config.json}"
COOLDOWN_SECS="${COOLDOWN_SECS:-1200}" # 20 minutes debounce between reminder rounds per account
POLL_INTERVAL_SECS=30
MAX_POLLS=10

# Prefer pinned Node v22.22.0 where Playwright is installed
if [[ -d "$HOME/.nvm/versions/node/v22.22.0/bin" ]]; then
  export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
  export DOT_NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
fi

if [[ -f "$SCRIPT_DIR/../../dot/scripts/dot.sh" ]]; then
  DOT_SCRIPT="$SCRIPT_DIR/../../dot/scripts/dot.sh"
elif [[ -f "$HOME/.claude/skills/dot/scripts/dot.sh" ]]; then
  DOT_SCRIPT="$HOME/.claude/skills/dot/scripts/dot.sh"
else
  DOT_SCRIPT="$HOME/.claude/skills/dot/scripts/dot.sh"
fi

DOT_SCRIPT="${COORDINATOR_DOT_SCRIPT:-$DOT_SCRIPT}"
PRIORITIES_FILE="${COORDINATOR_PRIORITIES_FILE:-$HOME/.config/dot/coordinator-priorities.txt}"
mkdir -p "$STATE_DIR"

LOCKFILE="${COORDINATOR_LOCK_FILE:-/tmp/ai.gemini.agy-dot-coordinator.lock}"
exec 200>"$LOCKFILE"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 200; then
    echo "[agy-dot-coordinator] Another coordinator instance is already running. Exiting cleanly."
    exit 0
  fi
else
  echo "flock unavailable; refusing concurrent coordinator execution." >&2
  exit 2
fi

FORCE=0
DRY_RUN=0
STATUS_ONLY=0
POLL_REPLY=1
USE_AGY=0
TARGET_ACCOUNT=""
CHANGE_ID="${COORDINATOR_CHANGE_ID:-}"
CHANGE_SUMMARY="${COORDINATOR_CHANGE_SUMMARY:-}"
URGENT="${COORDINATOR_URGENT:-0}"
FULL_ROLLUP="${COORDINATOR_FULL_ROLLUP:-0}"
MESSAGE_KIND=""
DELIVERY_KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift 1 ;;
    --full-rollup) FULL_ROLLUP=1; shift 1 ;;
    --dry-run) DRY_RUN=1; shift 1 ;;
    --status) STATUS_ONLY=1; shift 1 ;;
    --no-poll) POLL_REPLY=0; shift 1 ;;
    --use-agy) USE_AGY=1; shift 1 ;;
    --cooldown|-c) COOLDOWN_SECS="$2"; shift 2 ;;
    --cooldown=*) COOLDOWN_SECS="${1#*=}"; shift 1 ;;
    --account|-a) TARGET_ACCOUNT="$2"; shift 2 ;;
    --account=*) TARGET_ACCOUNT="${1#*=}"; shift 1 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

# Event IDs identify a meaningful task-state revision, not a poll timestamp.
# Only an authorized owner supplies these; this worker does not infer urgency.
if [[ "$URGENT" != 0 && "$URGENT" != 1 ]]; then exit 2; fi
if [[ "$FULL_ROLLUP" != 0 && "$FULL_ROLLUP" != 1 ]]; then exit 2; fi
if [[ "$URGENT" == 1 && "$FULL_ROLLUP" == 1 ]]; then
  echo "Urgent incidents are scoped notifications, not full rollups." >&2
  exit 2
fi
if [[ -n "$CHANGE_ID" || -n "$CHANGE_SUMMARY" || "$URGENT" == 1 || "$FULL_ROLLUP" == 1 ]]; then
  if [[ -z "$TARGET_ACCOUNT" || -z "$CHANGE_ID" || -z "$CHANGE_SUMMARY" ||
        ${#CHANGE_ID} -gt 160 || ${#CHANGE_SUMMARY} -gt 2000 ||
        "$CHANGE_ID" == *$'\n'* ]]; then
    echo "State changes require one --account, a stable change ID and bounded summary." >&2
    exit 2
  fi
fi
# Optional model sender lacks a message-bound receipt contract. Fail closed.
if [[ "$USE_AGY" == 1 ]]; then
  echo "--use-agy is unverified; use the direct receipt-verifying sender." >&2
  exit 2
fi

# Resolve account list (target single account or all configured rotation/accounts)
ACCOUNTS=()
if [[ -n "$TARGET_ACCOUNT" ]]; then
  ACCOUNTS=("$TARGET_ACCOUNT")
elif [[ -f "$CONFIG_FILE" ]]; then
  while IFS= read -r acc; do
    [[ -n "$acc" ]] && ACCOUNTS+=("$acc")
  done < <(python3 - "$CONFIG_FILE" <<'PY_CFG'
import json, re, sys
try:
    cfg = json.load(open(sys.argv[1]))
    if isinstance(cfg, dict):
        rot = cfg.get("rotation")
        accs = cfg.get("accounts")
        items = []
        if isinstance(rot, list):
            items = rot
        elif isinstance(rot, str) and re.match(r'^[a-zA-Z0-9_-]+$', rot):
            items = [rot]
        elif isinstance(accs, dict):
            items = list(accs.keys())
        for a in items:
            if isinstance(a, str) and re.match(r'^[a-zA-Z0-9_-]+$', a):
                print(a)
except Exception:
    pass
PY_CFG
  2>/dev/null)
fi

if [[ ${#ACCOUNTS[@]} -eq 0 ]]; then
  echo "No configured accounts; refusing to guess recipients." >&2
  exit 2
fi

for acc in "${ACCOUNTS[@]}"; do
  if [[ ! "$acc" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Invalid account key; refusing to select recipient." >&2
    exit 2
  fi
done

# Migrate prior consolidated or legacy state before reading eligibility or timestamps.
migrate_prior_state() {
  python3 - "$STATE_DIR" "$STATE_FILE" "$CONFIG_FILE" "${ACCOUNTS[@]}" <<'PY_MIGRATE'
import json, os, re, sys, tempfile

state_dir, state_file, config_file = sys.argv[1:4]
accounts = sys.argv[4:]

# 0. Fail closed on corrupt or non-object existing per-account state.
for acc in accounts:
    acc_file = os.path.join(state_dir, f"state_{acc}.json")
    if os.path.exists(acc_file):
        with open(acc_file) as pf:
            loaded = json.load(pf)
        if not isinstance(loaded, dict):
            raise ValueError(f"Corrupt per-account state: {acc_file} root must be a JSON object")

if not os.path.exists(state_file):
    sys.exit(0)

# Fail closed on corrupt consolidated state.
with open(state_file) as f:
    s = json.load(f)

if not isinstance(s, dict):
    raise ValueError("Corrupt state.json: root must be a JSON object")

def atomic_json(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".coordinator-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

# 1. Consolidated state migration:
# If state.json contains per-account records in s["accounts"], migrate any
# missing state_<account>.json so its receipt hold, delivered IDs, and timestamp
# are preserved before eligibility checks run.
if "accounts" in s:
    if not isinstance(s["accounts"], dict):
        raise ValueError("Corrupt state.json: 'accounts' must be a dictionary")
    for acc in accounts:
        acc_file = os.path.join(state_dir, f"state_{acc}.json")
        if os.path.exists(acc_file):
            with open(acc_file) as pf:
                cur = json.load(pf)
            if not isinstance(cur, dict):
                raise ValueError(f"Corrupt per-account state: {acc_file} root must be a JSON object")
            if acc in s["accounts"]:
                acc_data = s["accounts"][acc]
                if isinstance(acc_data, dict) and acc_data.get("delivery_unverified") and not cur.get("delivery_unverified"):
                    cur["delivery_unverified"] = True
                    atomic_json(acc_file, cur)
        elif acc in s["accounts"]:
            acc_data = s["accounts"][acc]
            if isinstance(acc_data, dict):
                atomic_json(acc_file, acc_data)

# 2. Legacy pre-multi-account state migration:
# If state.json lacks "accounts", it is a legacy single-account file.
# Attribute it only to a verifiable primary account from config (default_account first,
# then rotation[0]) so peer accounts do not inherit its cooldown. If config is absent
# or unverifiable, fail closed if an unverified hold is present; never guess.
elif s:
    primary_acc = None
    if os.path.exists(config_file):
        try:
            cfg = json.load(open(config_file))
            if isinstance(cfg, dict):
                raw_rot = cfg.get("rotation")
                raw_accs = cfg.get("accounts")
                raw_configured = []
                if isinstance(raw_rot, list):
                    raw_configured = raw_rot
                elif isinstance(raw_rot, str) and re.match(r'^[a-zA-Z0-9_-]+$', raw_rot):
                    raw_configured = [raw_rot]
                elif isinstance(raw_accs, dict):
                    raw_configured = list(raw_accs.keys())

                configured = [
                    a for a in raw_configured
                    if isinstance(a, str) and re.match(r'^[a-zA-Z0-9_-]+$', a)
                ]
                cand = cfg.get("default_account")
                if isinstance(cand, str) and re.match(r'^[a-zA-Z0-9_-]+$', cand) and cand in configured:
                    primary_acc = cand
                elif configured:
                    primary_acc = configured[0]
        except Exception:
            pass

    if primary_acc:
        primary_file = os.path.join(state_dir, f"state_{primary_acc}.json")
        existing_acc = None
        if os.path.exists(primary_file):
            with open(primary_file) as pf:
                loaded = json.load(pf)
            if not isinstance(loaded, dict):
                raise ValueError(f"Corrupt per-account state: {primary_file} root must be a JSON object")
            existing_acc = loaded

        if existing_acc is None:
            acc_data = dict(s)
            acc_data["account"] = primary_acc
        else:
            acc_data = existing_acc
            if s.get("delivery_unverified"):
                acc_data["delivery_unverified"] = True
            if "last_sent_epoch" in s and isinstance(s["last_sent_epoch"], (int, float)):
                acc_data["last_sent_epoch"] = max(acc_data.get("last_sent_epoch", 0), int(s["last_sent_epoch"]))
            if "delivered_change_ids" in s and isinstance(s["delivered_change_ids"], list):
                cur_ids = acc_data.get("delivered_change_ids", [])
                if isinstance(cur_ids, list):
                    acc_data["delivered_change_ids"] = list(dict.fromkeys(s["delivered_change_ids"] + cur_ids))[-128:]
                else:
                    acc_data["delivered_change_ids"] = s["delivered_change_ids"][-128:]

        atomic_json(primary_file, acc_data)

        upgraded = dict(s)
        upgraded.pop("delivery_unverified", None)
        upgraded["accounts"] = {primary_acc: acc_data}
        atomic_json(state_file, upgraded)
    elif s.get("delivery_unverified"):
        raise ValueError("Cannot attribute unverified delivery hold from legacy state; refusing execution")
PY_MIGRATE
}
if ! migrate_prior_state; then
  echo "Unreadable or corrupt prior state; refusing execution." >&2
  exit 2
fi

read_last_sent() {
  local acc="$1"
  local acc_file="$STATE_DIR/state_${acc}.json"
  if [[ -f "$acc_file" ]]; then
    python3 - "$acc_file" <<'PY_SENT' 2>/dev/null || echo 0
import json, sys
s = json.load(open(sys.argv[1]))
print(s.get("last_sent_epoch", 0))
PY_SENT
  elif [[ -f "$STATE_FILE" ]]; then
    python3 - "$STATE_FILE" "$acc" <<'PY_SENT' 2>/dev/null || echo 0
import json, sys
s = json.load(open(sys.argv[1]))
accs = s.get("accounts", {})
if "accounts" in s:
    print(accs.get(sys.argv[2], {}).get("last_sent_epoch", 0))
else:
    print(0)
PY_SENT
  else
    echo 0
  fi
}

read_last_status() {
  local acc="$1"
  local acc_file="$STATE_DIR/state_${acc}.json"
  if [[ -f "$acc_file" ]]; then
    python3 - "$acc_file" <<'PY_STATUS' 2>/dev/null || echo "UNKNOWN"
import json, sys
s = json.load(open(sys.argv[1]))
print(s.get("last_status", "UNKNOWN"))
PY_STATUS
  elif [[ -f "$STATE_FILE" ]]; then
    python3 - "$STATE_FILE" "$acc" <<'PY_STATUS' 2>/dev/null || echo "UNKNOWN"
import json, sys
s = json.load(open(sys.argv[1]))
accs = s.get("accounts", {})
if "accounts" in s:
    print(accs.get(sys.argv[2], {}).get("last_status", "UNKNOWN"))
else:
    print("NEVER_SENT")
PY_STATUS
  else
    echo "NEVER_SENT"
  fi
}

write_state() {
  local acc="$1"
  local epoch="$2"
  local status="$3"
  local summary="${4:-}"
  local acc_file="$STATE_DIR/state_${acc}.json"
  python3 -c '
import json, sys, time, os, tempfile

acc = sys.argv[1]
epoch = int(sys.argv[2])
status = sys.argv[3]
summary = sys.argv[4] if len(sys.argv) > 4 else ""
acc_file = sys.argv[5]
state_file = sys.argv[6]

data = {}
if os.path.exists(acc_file):
    with open(acc_file) as f:
        data = json.load(f)
elif os.path.exists(state_file):
    try:
        with open(state_file) as f:
            top_pre = json.load(f)
        if isinstance(top_pre, dict) and "accounts" in top_pre and acc in top_pre["accounts"]:
            data = top_pre["accounts"][acc]
    except Exception:
        data = {}
data.update({
    "account": acc,
    "last_sent_epoch": epoch,
    "last_sent_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch)),
    "last_status": status,
    "last_summary": summary
})
if status.startswith("UNVERIFIED_SEND"):
    data["delivery_unverified"] = True
if status == "SKIPPED_COMPOSER_BUSY":
    data["delivery_unverified"] = False
if status == "SUCCESS":
    data["delivery_unverified"] = False
    if sys.argv[7] == "rollup":
        data["last_rollup_epoch"] = epoch
    if sys.argv[8]:
        ids = data.get("delivered_change_ids", [])
        data["delivered_change_ids"] = (ids + [sys.argv[8]])[-128:]
def atomic_json(path, value):
    fd, tmp = tempfile.mkstemp(prefix=".coordinator-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
atomic_json(acc_file, data)

top_data = {}
if os.path.exists(state_file):
    with open(state_file, "r") as f:
        top_data = json.load(f)
    if not isinstance(top_data, dict):
        raise ValueError("Corrupt state.json: root must be a JSON object")
    if "accounts" in top_data and not isinstance(top_data["accounts"], dict):
        raise ValueError("Corrupt state.json: 'accounts' must be a dictionary")

top_data["last_tick_epoch"] = int(time.time())
top_data["last_tick_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
if "accounts" not in top_data or not isinstance(top_data["accounts"], dict):
    top_data["accounts"] = {}
top_data["accounts"][acc] = data

all_epochs = [v.get("last_sent_epoch", 0) for v in top_data["accounts"].values() if v.get("last_sent_epoch", 0) > 0]
max_epoch = max(all_epochs) if all_epochs else epoch
top_data["last_sent_epoch"] = max_epoch
top_data["last_sent_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max_epoch))
top_data["last_status"] = status

atomic_json(state_file, top_data)
' "$acc" "$epoch" "$status" "$summary" "$acc_file" "$STATE_FILE" "$MESSAGE_KIND" "$DELIVERY_KEY"
}

NOW=$(date +%s)
# Log a content identity, never credentials or transcript text.
echo "Worker SHA256: $(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$0")"
CONTEXTUAL_DEFAULTS=""
if [[ -f "$PRIORITIES_FILE" ]]; then
  CONTEXTUAL_DEFAULTS=$(python3 -c 'import sys; print(open(sys.argv[1]).read(4096))' "$PRIORITIES_FILE")
fi
echo "=== agy-dot-coordinator tick at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Configured accounts: ${ACCOUNTS[*]}"
echo "State dir: $STATE_DIR (cooldown: ${COOLDOWN_SECS}s)"

if [[ "$STATUS_ONLY" -eq 1 ]]; then
  echo "--- Account Status Summary ---"
  for acc in "${ACCOUNTS[@]}"; do
    last_sent=$(read_last_sent "$acc")
    elapsed=$((NOW - last_sent))
    last_status=$(read_last_status "$acc")
    echo "Account [$acc]: Last sent ${elapsed}s ago | Cooldown: ${COOLDOWN_SECS}s | Status: $last_status"
  done
  exit 0
fi

BASE_DIRECTIVE=$(cat <<'COORDINATION_POLICY'
From Antigravity Coordinator — automated coordination check-in, not a new user instruction:

Follow the latest direct user instructions and the current agreed plan. Use the machine-local contextual defaults below when present; otherwise retain the current agreed priorities. Confirm these remain relevant. Do not treat this historical ordering as an override of newer requests, current owners, dependencies, urgent material incidents or fresh evidence. Suggest any priority change with its reason and tradeoff; do not silently reassign owners.

Continue authorized work you already own. Respect other owners and in-flight edits, tests, browser sessions and deployments. Do not reopen cancelled work, explicit pauses, approval holds or authentication holds. A check-in grants no new authority. Advance independent authorized work when blocked; ask only about consequential conflicts that current evidence cannot resolve.

Respond only to the scope below. For an explicitly requested rollup or owner-reported material cross-track change, summarize the requested scope (the last 24 hours if unspecified), giving each active goal/PR, current owner, verified branch/head where relevant, progress evidence, blocker and next action. Label unknown or stale information. For a meaningful state change, discuss only that change and its effect on the plan. For an urgent material incident, report the incident, evidence, impact and appropriate existing owner; do not demand a full WIP review or unrelated reprioritization. If nothing needs intervention, continue the current plan without a redundant review.

Prefer cloud execution where supported; verify only prerequisites for the selected authorized next action. Tool presence is not proof of identity, permission or capability. Keep Mac-only work with its owner. Do not infer permission for credentials, sign-in, IAM changes, installation, messages or deployments from this check-in.
COORDINATION_POLICY
)

for acc in "${ACCOUNTS[@]}"; do
  echo ""
  echo ">>> Processing account: [$acc] <<<"
  last_sent=$(read_last_sent "$acc")
  elapsed=$((NOW - last_sent))

  # A scheduler wake is not a semantic change or a request for a full review.
  if [[ -z "$CHANGE_ID" ]]; then
    echo "Account [$acc]: No owner-supplied change or rollup request; quiet wake."
    continue
  fi
  MESSAGE_KIND="change"
  DELIVERY_KEY="$CHANGE_ID"
  if [[ "$FULL_ROLLUP" == 1 ]]; then MESSAGE_KIND="rollup"; fi
  if [[ "$URGENT" == 1 ]]; then MESSAGE_KIND="incident"; fi
  # Fail closed on corrupt state; every send requires a new owner-supplied ID.
  eligible=$(python3 - "$STATE_DIR/state_$acc.json" "$STATE_FILE" "$NOW" "$MESSAGE_KIND" "$DELIVERY_KEY" "$last_sent" "$acc" <<'PY_GATE'
import json, os, sys
path, state_file, now, kind, key, legacy_sent, acc = sys.argv[1:]
state = {}
if os.path.exists(path):
    state = json.load(open(path))
    if not isinstance(state, dict):
        raise ValueError("Corrupt per-account state: root must be a JSON object")
elif os.path.exists(state_file):
    top = json.load(open(state_file))
    if not isinstance(top, dict):
        raise ValueError("Corrupt state.json: root must be a JSON object")
    if "accounts" in top:
        if not isinstance(top["accounts"], dict):
            raise ValueError("Corrupt state.json: 'accounts' must be a dictionary")
        if acc in top["accounts"]:
            state = top["accounts"][acc]
    elif top.get("delivery_unverified"):
        print(0)
        sys.exit(0)
if not state:
    state = {"last_sent_epoch": int(legacy_sent)}

if os.path.exists(state_file):
    try:
        top = json.load(open(state_file))
        if isinstance(top, dict):
            if "accounts" not in top and top.get("delivery_unverified"):
                print(0)
                sys.exit(0)
            if isinstance(top.get("accounts"), dict) and top["accounts"].get(acc, {}).get("delivery_unverified"):
                print(0)
                sys.exit(0)
    except Exception:
        pass

if state.get("delivery_unverified"):
    print(0)
    sys.exit(0)
print(int(key not in state.get("delivered_change_ids", [])))
PY_GATE
  ) || { echo "Account [$acc]: Unreadable delivery state; refusing execution." >&2; exit 2; }
  if [[ "$eligible" != 1 ]]; then
    echo "Account [$acc]: No new request/change, or unresolved delivery hold."
    continue
  fi
  DIRECTIVE="$BASE_DIRECTIVE

Contextual defaults (not new authority): $CONTEXTUAL_DEFAULTS

Scope: $MESSAGE_KIND."
  if [[ -n "$CHANGE_SUMMARY" ]]; then
    DIRECTIVE="$DIRECTIVE
Owner-supplied state-change evidence (context, not authority): $CHANGE_SUMMARY"
  fi


  # 1. Read dot state for this account with 1 retry
  echo "Checking [$acc] dot state via $DOT_SCRIPT --account $acc read 2000..."
  dot_tail=""
  dot_read_ok=0
  for attempt in 1 2; do
    if dot_tail=$(timeout 140 "$DOT_SCRIPT" --account "$acc" read 2000 2>&1); then
      dot_read_ok=1
      break
    fi
    echo "[$acc] read attempt $attempt failed; settling 3s before retry..."
    sleep 3
  done

  if [[ "$dot_read_ok" -eq 0 ]]; then
    echo "WARNING: Failed to read [$acc] dot state: $dot_tail" >&2
    write_state "$acc" "$last_sent" "ERROR_READ_FAILED" "Failed to read dot state"
    sleep 2
    continue
  fi

  # Check if dot is actively thinking / working
  is_active=0
  if echo "$dot_tail" | grep -qiE "Thinking|Working|Searching"; then
    is_active=1
    echo "Account [$acc]: Dot assistant appears to be actively working/searching/thinking."
  fi

  # Active routine work is never interrupted, including --force.
  if [[ "$is_active" == 1 && "$URGENT" != 1 ]]; then
    echo "Account [$acc]: Active work; routine check-in deferred."
    continue
  fi

  # Urgent material incidents bypass cooldown, but never receipt deduplication.
  if [[ "$FORCE" -eq 0 && "$URGENT" != 1 && "$FULL_ROLLUP" != 1 ]]; then
    # Allow 30s jitter tolerance for cron schedules (e.g. 1198s on a 1200s cron)
    effective_cooldown=$((COOLDOWN_SECS > 30 ? COOLDOWN_SECS - 30 : COOLDOWN_SECS))
    if [[ "$is_active" -eq 1 && "$elapsed" -lt "$effective_cooldown" ]]; then
      echo "Account [$acc]: Dot is actively working and cooldown (${elapsed}/${COOLDOWN_SECS}s) is active. Skipping check-in."
      continue
    fi

    if [[ "$elapsed" -lt "$effective_cooldown" ]]; then
      echo "Account [$acc]: Cooldown active (${elapsed}/${COOLDOWN_SECS}s elapsed). Skipping check-in."
      continue
    fi
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] Would send directive to account [$acc]:"
    echo "$DIRECTIVE"
    continue
  fi

  export DOT_ROTATE_ON_LIMIT=0
  export DOT_WAIT_SECS=60
  export DOT_RETRY_SECS=15

  if [[ "$USE_AGY" -eq 1 ]]; then
    echo "Account [$acc]: Triggering agy coordinator prompt..."
    PROMPT="You are the Antigravity (agy) coordinator.
Communicate with the ChatGPT coordinator for account '$acc' using the /dot skill.
Instructions:
1. Inspect what the dot is doing by reading its conversation with dot.sh --account $acc.
2. Send this exact directive to account '$acc':
$DIRECTIVE
3. Make sure the message is sent cleanly using dot.sh --account $acc with DOT_WAIT_SECS=60 and report verified send status.
4. After sending, check for a reply until the dot finishes."

    agy_out=""
    agy_rc=0
    agy_out=$(timeout 480 agy -p "$PROMPT" --dangerously-skip-permissions --print-timeout 420s 2>&1) || agy_rc=$?

    echo "agy finished with exit code $agy_rc for [$acc]"
    if [[ "$agy_rc" -eq 0 ]]; then
      write_state "$acc" "$NOW" "SUCCESS" "Delivered and verified in-flight goals via agy"
    else
      if echo "$agy_out" | grep -qi "DOT_DRAFT_PRESENT"; then
        echo "Account [$acc]: Dot composer busy with peer draft; skipping this tick."
        write_state "$acc" "$last_sent" "SKIPPED_COMPOSER_BUSY" "Peer draft in composer"
      else
        echo "Account [$acc]: agy encountered an error (code $agy_rc)."
        write_state "$acc" "$last_sent" "ERROR_AGY_RC_$agy_rc"
      fi
    fi
  else
    # Direct verified delivery path (deterministic, zero token burn, draft-safe)
    echo "Account [$acc]: Sending directive via $DOT_SCRIPT --account $acc send..."
    msg_file=$(mktemp /tmp/dot_reminder_XXXXXXXX)
    printf '%s\n' "$DIRECTIVE" > "$msg_file"

    send_out=""
    send_rc=0
    # A crash during/after transport is ambiguous; persist the hold before sending.
    write_state "$acc" "$last_sent" "UNVERIFIED_SEND_PENDING" "Awaiting authoritative receipt"
    send_out=$(timeout 150 "$DOT_SCRIPT" --account "$acc" send "$msg_file" 2>&1) || send_rc=$?
    rm -f "$msg_file"

    echo "Account [$acc]: send result (rc=$send_rc):"
    echo "$send_out"

    # Only an exact transport receipt plus clean exit counts as success.
    # Nonzero/empty-composer results remain unverified; do not advance delivery state.
    if [[ "$send_rc" -eq 0 ]] && echo "$send_out" | grep -qx "DOT_SENT_VERIFIED"; then
      # Persist receipt before polling: termination during polling cannot replay it.
      write_state "$acc" "$NOW" "SUCCESS" "Verified direct transport receipt"
      echo "Account [$acc]: Successfully delivered and verified reminder."

      if [[ "$POLL_REPLY" -eq 1 ]]; then
        echo "Account [$acc]: Polling for dot reply (every ${POLL_INTERVAL_SECS}s, up to ${MAX_POLLS} cycles)..."
        poll_count=0
        while [[ $poll_count -lt $MAX_POLLS ]]; do
          poll_count=$((poll_count + 1))
          sleep "$POLL_INTERVAL_SECS"
          current_tail=$(timeout 140 "$DOT_SCRIPT" --account "$acc" read 2500 2>&1 || true)
          if echo "$current_tail" | grep -qiE "Thinking|Working|Searching|dot is typing"; then
            echo "[Poll $poll_count/$MAX_POLLS] Account [$acc]: Dot is actively working on reply..."
          else
            echo "Account [$acc]: Dot finished reply after ${poll_count} wait cycles."
            break
          fi
        done
      fi

    elif [[ "$send_rc" -eq 3 ]] &&
         echo "$send_out" | grep -q "DOT_DRAFT_PRESENT" &&
         ! echo "$send_out" | grep -qE "DOT_SENT_VERIFIED|DOT_SEND_UNVERIFIED"; then
      echo "Account [$acc]: Dot composer busy with peer draft; gracefully skipping this tick."
      write_state "$acc" "$last_sent" "SKIPPED_COMPOSER_BUSY" "Peer draft in composer"
    elif echo "$send_out" | grep -qi "DOT_CHROME_UNAVAILABLE"; then
      echo "Account [$acc]: Chrome automation unavailable."
      write_state "$acc" "$last_sent" "UNVERIFIED_SEND_CHROME_UNAVAILABLE"
    else
      echo "Account [$acc]: Failed to send reminder (rc=$send_rc)."
      write_state "$acc" "$last_sent" "UNVERIFIED_SEND_RC_$send_rc"
    fi
  fi
done

echo ""
echo "=== agy-dot-coordinator completed all accounts at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
exit 0
