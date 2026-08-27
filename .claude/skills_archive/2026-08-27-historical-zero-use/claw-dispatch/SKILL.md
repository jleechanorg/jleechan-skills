---
name: claw-dispatch
description: Use when dispatching work through the Hermes gateway with /claw, especially when the task may resolve slash commands or hand off into AO worker orchestration.
---

# Claw Dispatch

## Default behavior — AO workers first

**`/claw` defaults to spawning AO workers directly. Hermes gateway is the fallback, not the default.**

| Input | Default action |
|-------|---------------|
| PR number (`#633`, `PR 633`, `633`) | Expand to draft-first readiness followed by `/green`, then post to Slack → Hermes (5 attempt cap) |
| General task description | Post to Slack → Hermes |
| `--max-attempts N` | Override attempt cap (default 5 for PR tasks) |
| `--bidi` prefix | Hermes interactive session (streaming) |
| `--hermes` prefix | Force through Hermes gateway |
| Slash command resolution (e.g. `/green`) | Resolve skill then pass to Hermes via Slack |

**Project auto-detection for PR tasks:** resolve from current git remote (`git remote get-url origin`).

**When to use Hermes instead of AO:** only when the user explicitly says `--hermes`, uses `--bidi` for interactive output, or the task is explicitly a Hermes-native operation (routing config, gateway status, etc.).

## Overview

`/claw` routes work to AO workers by default. Use:
- `~/.claude/commands/ao.md`
- `~/.claude/skills/ao-operator-discipline/SKILL.md`

User-specified AO parameters remain mandatory.

## Requirements

- For AO tasks: `ao session ls` must not show ≥30 active sessions (spawn cap)
- For Hermes fallback: gateway must be healthy via `hermes gateway status`
- Slash command resolution must search `.claude/commands` first, then `.claude/skills`

## Execution

When invoked with a task description:

```bash
TASK_DESCRIPTION="$ARGUMENTS"
set -euo pipefail

LOGDIR="/tmp/hermes"
mkdir -p "$LOGDIR"
chmod 700 "$LOGDIR" 2>/dev/null || true
STATUS_LOG="$(mktemp "$LOGDIR/.claw-status-XXXXXXXX")"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/ai.hermes.prod.plist"

if [ -f "$LAUNCHD_PLIST" ]; then
  while IFS='=' read -r key value; do
    [ -n "$key" ] || continue
    export "$key=$value"
  done < <(
    python3 - "$LAUNCHD_PLIST" <<'PY'
import plistlib
import sys

path = sys.argv[1]
try:
    with open(path, "rb") as fh:
        data = plistlib.load(fh)
except FileNotFoundError:
    raise SystemExit(0)

env = data.get("EnvironmentVariables") or {}
for key in ("HERMES_HOME", "HERMES_LOG_LEVEL"):
    value = env.get(key)
    if value:
        print(f"{key}={value}")
PY
  )
fi

export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_CFG="$HERMES_HOME/config.yaml"

if [ ! -f "$HERMES_CFG" ]; then
  echo "Hermes config not found: $HERMES_CFG"
  exit 1
fi
if ! python3 -c "import yaml; yaml.safe_load(open('$HERMES_CFG'))" 2>/dev/null; then
  echo "Hermes config is not valid YAML: $HERMES_CFG"
  exit 1
fi

# Hermes gateway health check. The `hermes gateway status` CLI is unreliable —
# it can report "not running" / "draining" with phantom PIDs while the actual
# gateway is healthy. Trust the live health endpoint instead.
#
# Port resolution order:
#   1. $CLAW_HERMES_PORT (override for testing / staging / non-prod gateways)
#   2. `port:` under the `gateway:` block in $HERMES_CFG (canonical config)
#   3. Hard-coded default :8643 (current prod gateway port as of 2026-06-28;
#      see ~/.hermes/config.yaml)
#
# Note: the previous default of :8642 is stale — the live Hermes gateway has
# been on :8643 for some time. Hard-coding 8642 silently breaks /claw on
# healthy gateways. Always resolve from the YAML config or CLAW_HERMES_PORT.
HERMES_PORT="${CLAW_HERMES_PORT:-$(python3 -c "
import yaml, sys
try:
    with open('$HERMES_CFG') as fh:
        cfg = yaml.safe_load(fh) or {}
    gw = cfg.get('gateway') or {}
    p = gw.get('port')
    if isinstance(p, int):
        print(p)
    elif isinstance(p, str) and p.isdigit():
        print(p)
except Exception:
    pass
" 2>/dev/null)}"
HERMES_PORT="${HERMES_PORT:-8643}"
HEALTH_LOG="$(mktemp "$LOGDIR/.claw-health-XXXXXXXX")"
if ! curl -sS -m 3 "http://127.0.0.1:${HERMES_PORT}/health" >"$HEALTH_LOG" 2>&1; then
  echo "Hermes gateway is not reachable on :${HERMES_PORT}."
  echo "(Override via CLAW_HERMES_PORT=<port> or set gateway.port in $HERMES_CFG)"
  sed -n '1,20p' "$HEALTH_LOG"
  exit 1
fi
if ! grep -q '"status": "ok"' "$HEALTH_LOG"; then
  echo "Hermes gateway health check did not return ok."
  sed -n '1,20p' "$HEALTH_LOG"
  exit 1
fi

TASK_WITH_RESOLVED="$TASK_DESCRIPTION"

# PR shorthand expansion: when the task is a bare PR number (e.g. "6976", "PR 6976",
# "#6976"), expand it to the full draft-first readiness + `/green` task with repo auto-detection.
PR_NUMBER=$(printf '%s' "$TASK_DESCRIPTION" | python3 -c "
import sys, re
text = sys.stdin.read().strip()
m = re.match(r'^(?:PR\s*#?|#)\s*(\d+)$', text)
if m:
    print(m.group(1))
" 2>/dev/null)
if [ -n "$PR_NUMBER" ]; then
  # Auto-detect repo from current git remote
  REPO_SLUG=$(git remote get-url origin 2>/dev/null | python3 -c "
import sys, re
url = sys.stdin.read().strip()
m = re.match(r'(?:https?://github\.com/|git@github\.com:)([\w-]+/[\w-]+?)(?:\.git)?$', url)
if m:
    print(m.group(1))
" 2>/dev/null || echo "")
  if [ -n "$REPO_SLUG" ]; then
    PR_URL="https://github.com/${REPO_SLUG}/pull/${PR_NUMBER}"
  else
    PR_URL="PR #${PR_NUMBER}"
  fi
  TASK_WITH_RESOLVED="Keep ${PR_URL} draft while completing /es, /er, and /advice; then mark it ready and bring it to /green. Fix CI failures and merge conflicts, and treat CodeRabbit/Bugbot as advisory. Use /green ${PR_NUMBER} to verify. Act autonomously — do not ask for permission to fix things. IMPORTANT: attempt at most ${CLAW_MAX_ATTEMPTS:-5} fix-push-CI cycles. After reaching the limit, post a status summary of remaining blockers and stop — do not continue iterating."
  TASK_DESCRIPTION="$TASK_WITH_RESOLVED"
fi

# PR URL augmentation: when the task contains a GitHub PR URL, inject an explicit
# autonomy directive so Hermes acts without asking for confirmation.
PR_URL=$(printf '%s' "$TASK_DESCRIPTION" | python3 -c "
import sys, re
m = re.search(r'https://github\.com/[\w-]+/[\w-]+/pull/\d+', sys.stdin.read())
if m:
    print(m.group(0))
" 2>/dev/null)
if [ -n "$PR_URL" ]; then
  TASK_WITH_RESOLVED="${TASK_DESCRIPTION}

IMPORTANT: You are acting as an autonomous agent. If you find that CI checks are failing, review threads are unresolved, or the PR needs remediation, automatically route to AO for remediation (ao spawn --claim-pr N). Do NOT ask 'Would you like me to route to AO?' — just do it. The user invoked /claw to get autonomous action, not a status report."
fi

SLASH_CMD=$(printf '%s' "$TASK_DESCRIPTION" | python3 -c "
import sys, re
text = sys.stdin.read().strip()
clean = re.sub(r'https?://\\S+', '', text)
m = re.search(r'(?:^|\\s)/([\\w-]+)', clean)
if m:
    print(m.group(1))
" 2>/dev/null)

if [ -n "$SLASH_CMD" ]; then
  RESOLVED_CONTENT=""
  RESOLVED_SOURCE=""
  for search_dir in ".claude/commands" "$HOME/.claude/commands"; do
    if [ -f "$search_dir/$SLASH_CMD.md" ]; then
      RESOLVED_CONTENT=$(cat "$search_dir/$SLASH_CMD.md" 2>/dev/null)
      RESOLVED_SOURCE="$search_dir/$SLASH_CMD.md"
      break
    fi
  done
  if [ -z "$RESOLVED_CONTENT" ]; then
    for search_dir in ".claude/skills" "$HOME/.claude/skills"; do
      if [ -f "$search_dir/$SLASH_CMD/SKILL.md" ]; then
        RESOLVED_CONTENT=$(cat "$search_dir/$SLASH_CMD/SKILL.md" 2>/dev/null)
        RESOLVED_SOURCE="$search_dir/$SLASH_CMD/SKILL.md"
        break
      elif [ -f "$search_dir/$SLASH_CMD.md" ]; then
        RESOLVED_CONTENT=$(cat "$search_dir/$SLASH_CMD.md" 2>/dev/null)
        RESOLVED_SOURCE="$search_dir/$SLASH_CMD.md"
        break
      fi
    done
  fi
  if [ -n "$RESOLVED_CONTENT" ]; then
    echo "Resolved /$SLASH_CMD from $RESOLVED_SOURCE"
    TASK_WITH_RESOLVED="The user asked: $TASK_DESCRIPTION

Below is the full definition of /$SLASH_CMD (resolved from $RESOLVED_SOURCE). Execute it as instructed:

---
$RESOLVED_CONTENT
---"
  fi
fi

# Max-attempts override: --max-attempts N (default 5 for PR tasks; no cap for freeform tasks)
if printf '%s' "$TASK_WITH_RESOLVED" | grep -q -- '--max-attempts'; then
  CLAW_MAX_ATTEMPTS=$(printf '%s' "$TASK_WITH_RESOLVED" | grep -oE -- '--max-attempts[[:space:]]+[0-9]+' | awk '{print $2}' | head -1)
  TASK_WITH_RESOLVED=$(printf '%s' "$TASK_WITH_RESOLVED" | sed "s/--max-attempts[[:space:]]*[0-9]*//" | sed 's/^[[:space:]]*//')
  export CLAW_MAX_ATTEMPTS
fi

# Bidi mode: synchronous, streaming output
BIDI_MODE=false
CONTINUE_SESSION=""

if printf '%s' "$TASK_WITH_RESOLVED" | grep -q '^--bidi'; then
  BIDI_MODE=true
  TASK_WITH_RESOLVED=$(printf '%s' "$TASK_WITH_RESOLVED" | sed 's/^--bidi[[:space:]]*//')
fi

if printf '%s' "$TASK_WITH_RESOLVED" | grep -q '^--continue'; then
  CONTINUE_SESSION=$(printf '%s' "$TASK_WITH_RESOLVED" | sed 's/^--continue[[:space:]]*//' | awk '{print $1}')
fi

# --hermes: force the task to run inline in the gateway (skip the AO directive).
FORCE_HERMES=false
if printf '%s' "$TASK_WITH_RESOLVED" | grep -q '^--hermes'; then
  FORCE_HERMES=true
  TASK_WITH_RESOLVED=$(printf '%s' "$TASK_WITH_RESOLVED" | sed 's/^--hermes[[:space:]]*//')
fi

# General AO-dispatch directive (the documented "AO workers first" default).
# For freeform tasks — no PR URL (those already carry their own AO remediation
# directive above), not --bidi (interactive), not --hermes (forced inline) — tell
# the gateway to delegate to an AO worker unless the task is small enough to finish
# inline. The trivial-vs-AO judgment is the gateway LLM's to make (ZFC: the model
# decides, the skill only states the policy) — we never classify the task in code.
if [ "$BIDI_MODE" != true ] && [ "$FORCE_HERMES" != true ] && [ -z "${PR_URL:-}" ]; then
  TASK_WITH_RESOLVED="${TASK_WITH_RESOLVED}

IMPORTANT — dispatch policy: unless this is a very small task you can fully complete inline in a few steps, dispatch it to an AO worker (e.g. \`ao spawn\` / \`ao spawn --claim-pr N\`) rather than doing the whole thing inline in this gateway session. Default to AO for multi-file changes, PR/CI/build/deploy work, or anything beyond a few minutes; handle only genuinely small asks inline. You decide which side of that line this task is on. Act autonomously — do not ask whether to dispatch to AO, just route it."
fi

if [ "$BIDI_MODE" = true ]; then
  echo "Bidi mode: streaming Hermes response (synchronous)"
  hermes chat \
    -q "$TASK_WITH_RESOLVED" \
    --yolo \
    --max-turns 30 \
    --source tool \
    --pass-session-id
  echo ""
  echo "Session ended. To continue: /claw --continue <session_name>"
  exit 0
fi

if [ -n "$CONTINUE_SESSION" ]; then
  echo "Continuing Hermes session: $CONTINUE_SESSION"
  hermes chat \
    --continue "$CONTINUE_SESSION" \
    --yolo \
    --source tool
  exit 0
fi

# --status <logfile>: check on a running/completed claw session
if printf '%s' "$TASK_WITH_RESOLVED" | grep -q '^--status'; then
  STATUS_LOG=$(printf '%s' "$TASK_WITH_RESOLVED" | sed 's/^--status[[:space:]]*//' | awk '{print $1}')
  if [ ! -f "$STATUS_LOG" ]; then
    echo "❌ Log not found: $STATUS_LOG"
    exit 1
  fi
  LOG_LINES=$(wc -l <"$STATUS_LOG")
  LAST_LINE=$(tail -1 "$STATUS_LOG" 2>/dev/null)
  PID_RUNNING=$(pgrep -f "hermes chat" | head -1)
  echo "=== Claw Session Status ==="
  echo "Log: $STATUS_LOG ($LOG_LINES lines)"
  echo "Process: ${PID_RUNNING:-(completed)}"
  echo "Last output: $LAST_LINE"
  echo "--- Tail ---"
  tail -20 "$STATUS_LOG"
  exit 0
fi

# === Slack dispatch path ===
# /claw now posts to Slack instead of forking a hermes chat process. The
# gateway is already connected to Slack via Socket Mode; we hand the task
# to it through a channel message and watch the thread for the ack.
#
# Channel + bot ID are env-overridable; defaults match the live deployment.
CLAW_CHANNEL="${CLAW_CHANNEL:-C0B9W8D609M}"   # #claw-dispatch
CLAW_BOT_ID="${CLAW_BOT_ID:-U0AEZC7RX1Q}"     # @hermes bot user_id
CLAW_TOKEN="${SLACK_MCP_XOXP_TOKEN:-${HERMES_SLACK_USER_TOKEN:-}}"
if [ -z "$CLAW_TOKEN" ]; then
  echo "❌ No Slack user token (SLACK_MCP_XOXP_TOKEN) available — cannot dispatch via Slack."
  echo "   Set SLACK_MCP_XOXP_TOKEN (xoxp user token for $USER) in env or launchd plist."
  exit 1
fi

# Build message: strip any pre-existing <@U...> mentions from the task, then
# prepend [via /claw] provenance + @hermes. Caps at Slack's 39000 char safe limit.
TASK_TEXT=$(printf '%s' "$TASK_WITH_RESOLVED" | sed -E 's|<@[UW][A-Z0-9]+>||g; s/^[[:space:]]+//; s|[[:space:]]+$||')
MESSAGE="[via /claw] <@${CLAW_BOT_ID}> ${TASK_TEXT}"
MESSAGE="${MESSAGE:0:39000}"

# Post via chat.postMessage. Using --data-binary with python3 -c keeps the
# JSON encoding safe (no shell escaping of the message text).
POST_LOG="$LOGDIR/.claw-post-$(date +%s).json"
curl -sS -m 15 -X POST \
  -H "Authorization: Bearer $CLAW_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary "$(python3 -c "import json,sys; print(json.dumps({'channel': '$CLAW_CHANNEL', 'text': sys.argv[1]}))" "$MESSAGE")" \
  "https://slack.com/api/chat.postMessage" >"$POST_LOG" 2>&1

# Parse response
OK=$(python3 -c "import json; print(json.load(open('$POST_LOG')).get('ok', False))" 2>/dev/null)
if [ "$OK" != "True" ]; then
  ERR=$(python3 -c "import json; print(json.load(open('$POST_LOG')).get('error', 'unknown'))" 2>/dev/null)
  echo "❌ Slack post failed: ${ERR}"
  echo "   response: $POST_LOG"
  exit 1
fi

# Extract ts + construct thread URL (Slack archives URL pattern drops the dot)
THREAD_URL=$(python3 -c "
import json
d = json.load(open('$POST_LOG'))
ts = d.get('ts', '').replace('.', '')
ch = d.get('channel', '')
print(f'https://jleechanai.slack.com/archives/{ch}/p{ts}')
")
MSG_TS=$(python3 -c "import json; print(json.load(open('$POST_LOG')).get('ts', ''))")

echo "✅ Dispatched to Hermes via Slack"
echo "   channel: #claw-dispatch"
echo "   thread:  $THREAD_URL"
echo "   message_ts: $MSG_TS"

# Wait for Hermes ack (up to 30s) — reaction OR thread reply from Hermes.
# This is the Slack analog of the old "wait for first log line" check.
# 30s is generous because Hermes may be busy with other sessions; the message
# is already in the channel and durable, so a longer wait is purely diagnostic.
echo "⏳ Waiting for Hermes ack (up to 30s)..."
ACKED=0
for i in $(seq 1 30); do
  sleep 1
  # Reaction on the parent message (e.g. "On it…" emoji)
  REACT=$(curl -sS -m 3 -H "Authorization: Bearer $CLAW_TOKEN" \
    "https://slack.com/api/reactions.get?channel=${CLAW_CHANNEL}&timestamp=${MSG_TS}" 2>/dev/null)
  REACT_HIT=$(printf '%s' "$REACT" | python3 -c "import json,sys
try:
  d=json.load(sys.stdin)
  print(d.get('ok', False) and bool(d.get('message', {}).get('reactions')))
except: print(False)" 2>/dev/null)
  if [ "$REACT_HIT" = "True" ]; then
    echo "✅ Hermes acked (reaction at ${i}s)"
    ACKED=1
    break
  fi
  # Reply in thread (Hermes often replies with "On it…" text rather than a reaction)
  REPLIES=$(curl -sS -m 3 -H "Authorization: Bearer $CLAW_TOKEN" \
    "https://slack.com/api/conversations.replies?channel=${CLAW_CHANNEL}&ts=${MSG_TS}&limit=5" 2>/dev/null)
  REPLY_HIT=$(printf '%s' "$REPLIES" | python3 -c "import json,sys
try:
  d=json.load(sys.stdin)
  print(d.get('ok', False) and len(d.get('messages', [])) > 1)
except: print(False)" 2>/dev/null)
  if [ "$REPLY_HIT" = "True" ]; then
    echo "✅ Hermes acked (thread reply at ${i}s)"
    ACKED=1
    break
  fi
done
if [ "$ACKED" != "1" ]; then
  echo "⚠️  No ack within 30s — Hermes may be rate-limited, stuck, or the channel is wrong."
  echo "   Check: $THREAD_URL"
  exit 0  # message is posted; user can monitor the thread
fi

echo ""
echo "✅ Dispatched to Hermes via Slack"
echo "   Channel:  #claw-dispatch"
echo "   Thread:   $THREAD_URL"
echo "   Hermes:   U0AEZC7RX1Q (@hermes)"
echo "   Monitor:  open the thread URL above; Hermes acks within ~30s, then works the task in thread"
echo "   Re-check: /claw --status <logfile>"
```

## Post-dispatch output (MANDATORY)

After **every** `/claw` dispatch — AO or Hermes — always print these lines in your reply:

### AO spawn path
```
✅ AO worker spawned: <session-name>
   Attach:    ao attach <session-name>
   Status:    ao status <session-name>
   tmux:      tmux attach-session -t <container-id>-<session-name>
   Dashboard: http://localhost:3030
```
Get the session name from `ao session ls --project <project>` immediately after spawn. The dashboard URL is the live AO web UI (next.js on :3030 in prod, :3020 in dev).

### Hermes chat path (fallback)
```
✅ Hermes worker dispatched (PID: <pid>)
   Log:     <logfile>
   Monitor: tail -f <logfile>
   Kill:    kill <pid>
```
Always emit the exact logfile path so the user can monitor or kill.

### Slack path
```
✅ Dispatched to Hermes via Slack
   Channel:  #claw-dispatch
   Thread:   <thread_url>
   Hermes:   U0AEZC7RX1Q (@hermes)
   Monitor:  open the thread URL above; Hermes acks within ~30s, then works the task in thread
   Re-check: /claw --status <logfile>
```

**Never omit these lines.** The user must always know how to attach, monitor, or kill the worker without asking.

## Notes

- Hermes replaced OpenClaw as the live gateway agent
- slash commands are resolved before dispatch
- `/claw` sessions are hidden from normal Hermes session lists via `--source tool`
- `--yolo` bypasses tool approvals for autonomous runs
- when `/claw` leads to AO dispatch, spawned AO sessions must still be verified post-spawn

## Modes

| Prefix | Behavior |
|--------|----------|
| *(none)* | Async fire-and-forget with ack detection (✅ ACK / ❌ RATE_LIMITED / ❌ FAILED) |
| `--bidi` | Synchronous streaming — blocks until Hermes finishes, shows session ID for follow-up |
| `--continue <name>` | Resume a previous `--bidi` session interactively |
| `--status <logfile>` | Check tail + completion status of any async claw session |
