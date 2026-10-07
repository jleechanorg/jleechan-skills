#!/usr/bin/env bash
# dot-portfolio-coordinator-sender.sh
# Hardened, receipt-safe message delivery subcomponent reusing relative sibling dot transport.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${DOT_PORTFOLIO_STATE_DIR:-$HOME/.local/state/ai.gemini.dot-portfolio-coordinator}"
DOT_TRANSPORT="${DOT_TRANSPORT_SCRIPT:-$SCRIPT_DIR/../../dot/scripts/dot.sh}"
BINDINGS_FILE="${DOT_PORTFOLIO_BINDINGS_FILE:-$SCRIPT_DIR/../references/bindings.json}"

WORKER_SHA="dot-portfolio-coordinator-sender-v1"
COOLDOWN_SECS=7200

ACCOUNT="default"
AUTH_REF=""
FORCE=0
FULL_ROLLUP=0
STATUS_ONLY=0
STATUS_JSON=0
RECONCILE_RECEIPT=""
POLL_REPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account)
      ACCOUNT="$2"
      shift 2
      ;;
    --authorization-ref)
      AUTH_REF="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift 1
      ;;
    --full-rollup)
      FULL_ROLLUP=1
      shift 1
      ;;
    --status)
      STATUS_ONLY=1
      shift 1
      ;;
    --json)
      STATUS_JSON=1
      shift 1
      ;;
    --reconcile-receipt)
      RECONCILE_RECEIPT="$2"
      shift 2
      ;;
    --poll-reply)
      POLL_REPLY=1
      shift 1
      ;;
    --no-poll)
      POLL_REPLY=0
      shift 1
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

ACCOUNT_STATE_FILE="$STATE_DIR/account_${ACCOUNT}.json"
CONSOLIDATED_STATE_FILE="$STATE_DIR/state.json"
LOCK_FILE="$STATE_DIR/sender.lock"

# 1. Read-only status mode (strictly no lock, no write, no browser)
if [[ "$STATUS_ONLY" -eq 1 ]]; then
  if [[ "$STATUS_JSON" -eq 1 ]]; then
    python3 -c '
import json, os, sys, hashlib
account = sys.argv[1]
acc_file = sys.argv[2]
if os.path.exists(acc_file):
    with open(acc_file, "r") as f:
        data = json.load(f)
    raw = json.dumps(data, sort_keys=True)
    state_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    last_sent = data.get("last_sent_epoch", 0)
    pending = data.get("pending_delivery")
    retained = data.get("retained_event_ids", [])
else:
    state_sha = None
    last_sent = 0
    pending = None
    retained = []

status_rec = {
    "schema_version": 1,
    "account": account,
    "state_sha256": state_sha,
    "last_sent_epoch": last_sent,
    "delivery_unverified": pending is not None,
    "pending_delivery": pending,
    "retained_event_ids": retained,
    "worker_sha256": sys.argv[3]
}
print("COORDINATOR_STATUS " + json.dumps(status_rec))
' "$ACCOUNT" "$ACCOUNT_STATE_FILE" "$WORKER_SHA"
  fi
  exit 0
fi

# 2. Quiet wake check (no change ID and no summary -> quiet exit 0)
EVENT_ID="${COORDINATOR_CHANGE_ID:-}"
SUMMARY="${COORDINATOR_CHANGE_SUMMARY:-}"
URGENT="${COORDINATOR_URGENT:-0}"

if [[ -z "$EVENT_ID" && -z "$SUMMARY" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"quiet\", \"reason\": \"no_input_event\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 0
fi

# 3. Input validation: Event ID and Summary constraints
if [[ -z "$EVENT_ID" || ${#EVENT_ID} -gt 160 || "$EVENT_ID" == *$'\n'* ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"invalid\", \"reason\": \"invalid_event_id\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 2
fi

if [[ -z "$SUMMARY" || ${#SUMMARY} -gt 2000 ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"invalid\", \"reason\": \"invalid_summary\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 2
fi

# 4. Explicit events require authorization-ref
if [[ -z "$AUTH_REF" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"invalid\", \"reason\": \"missing_authorization_ref\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 2
fi

# Verify binding resolution
AUTH_BINDING_JSON=$(python3 -c '
import json, os, sys
ref = sys.argv[1]
b_file = sys.argv[2]
if os.path.exists(b_file):
    with open(b_file, "r") as f:
        b_data = json.load(f)
    print(json.dumps(b_data.get(ref, {})))
else:
    print("{}")
' "$AUTH_REF" "$BINDINGS_FILE")

if [[ "$AUTH_BINDING_JSON" == "{}" || "$AUTH_BINDING_JSON" == "null" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"invalid\", \"reason\": \"unresolvable_authorization_ref\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 2
fi

# 5. Acquire lock
mkdir -p "$STATE_DIR"
exec 200>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 200; then
    echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"deferred\", \"reason\": \"lock_contention\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
    exit 0
  fi
fi

# 6. Check account state: existing hold and deduplication
ACCOUNT_CHECK=$(python3 -c '
import json, os, sys
acc_file = sys.argv[1]
event_id = sys.argv[2]
now = int(sys.argv[3])
cooldown = int(sys.argv[4])
force = int(sys.argv[5])
urgent = int(sys.argv[6])
full_rollup = int(sys.argv[7])

if os.path.exists(acc_file):
    with open(acc_file, "r") as f:
        d = json.load(f)
else:
    d = {"retained_event_ids": [], "last_sent_epoch": 0}

if d.get("pending_delivery"):
    print("HOLD")
    sys.exit(0)

if event_id in d.get("retained_event_ids", []):
    print("DUPLICATE")
    sys.exit(0)

last_sent = d.get("last_sent_epoch", 0)
if now < last_sent:
    print("CLOCK_ROLLBACK")
    sys.exit(0)

elapsed = now - last_sent
if urgent == 0 and full_rollup == 0 and force == 0 and elapsed < cooldown:
    print("COOLDOWN")
    sys.exit(0)

print("OK")
' "$ACCOUNT_STATE_FILE" "$EVENT_ID" "$(date +%s)" "$COOLDOWN_SECS" "$FORCE" "$URGENT" "$FULL_ROLLUP")

if [[ "$ACCOUNT_CHECK" == "HOLD" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"uncertain\", \"reason\": \"receipt_hold\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 3
fi

if [[ "$ACCOUNT_CHECK" == "DUPLICATE" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"duplicate\", \"reason\": \"already_received\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 0
fi

if [[ "$ACCOUNT_CHECK" == "CLOCK_ROLLBACK" || "$ACCOUNT_CHECK" == "COOLDOWN" ]]; then
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"deferred\", \"reason\": \"${ACCOUNT_CHECK,,}\", \"delivery_verified\": false, \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 0
fi

# 7. Persist pending attempt and uncertainty hold BEFORE transport
ATTEMPT_TS=$(date +%s)
python3 -c '
import json, os, sys
acc_file = sys.argv[1]
event_id = sys.argv[2]
ts = int(sys.argv[3])
binding = json.loads(sys.argv[4])

if os.path.exists(acc_file):
    with open(acc_file, "r") as f:
        d = json.load(f)
else:
    d = {"retained_event_ids": [], "last_sent_epoch": 0}

d["pending_delivery"] = {
    "account": d.get("account", sys.argv[5]),
    "event_id": event_id,
    "kind": "delta",
    "attempt_timestamp": ts,
    "authorization_binding": binding
}
tmp = acc_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
os.replace(tmp, acc_file)
' "$ACCOUNT_STATE_FILE" "$EVENT_ID" "$ATTEMPT_TS" "$AUTH_BINDING_JSON" "$ACCOUNT"

# 8. Transport execution
TMP_MSG=$(mktemp "/tmp/dot_msg_XXXXXX.txt")
echo "$SUMMARY" > "$TMP_MSG"

TRANSPORT_OUT=""
TRANSPORT_RC=0
TRANSPORT_OUT=$("$DOT_TRANSPORT" send-once "$TMP_MSG" 2>&1) || TRANSPORT_RC=$?
rm -f "$TMP_MSG"

# 9. Receipt Verification: Requires standalone DOT_SENT_VERIFIED and RC 0
if [[ "$TRANSPORT_RC" -eq 0 && "$TRANSPORT_OUT" == *"DOT_SENT_VERIFIED"* ]]; then
  # Commit authoritative delivery receipt in account state
  python3 -c '
import json, os, sys
acc_file = sys.argv[1]
event_id = sys.argv[2]
now = int(sys.argv[3])

with open(acc_file, "r") as f:
    d = json.load(f)

d["pending_delivery"] = None
d["last_sent_epoch"] = now
retained = d.get("retained_event_ids", [])
if event_id not in retained:
    retained.append(event_id)
# Bound dedup at last 128 IDs
d["retained_event_ids"] = retained[-128:]

tmp = acc_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
os.replace(tmp, acc_file)
' "$ACCOUNT_STATE_FILE" "$EVENT_ID" "$(date +%s)"

  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"delivered\", \"reason\": \"verified_by_transport\", \"delivery_verified\": true, \"event_id\": \"$EVENT_ID\", \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 0
else
  # Unverified / failed send: Pending delivery hold is RETAINED!
  echo "COORDINATOR_RESULT {\"schema_version\": 1, \"account\": \"$ACCOUNT\", \"outcome\": \"uncertain\", \"reason\": \"send_unverified\", \"delivery_verified\": false, \"event_id\": \"$EVENT_ID\", \"worker_sha256\": \"$WORKER_SHA\"}"
  exit 4
fi
