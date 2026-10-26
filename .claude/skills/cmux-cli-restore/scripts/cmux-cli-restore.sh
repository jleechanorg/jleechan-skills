#!/bin/bash
# cmux-cli-restore.sh — exit a stuck CLI in a cmux surface and restart it with its resume wrapper.
#
#   cmux-cli-restore.sh --workspace <ws> --surface <sf> [--dry-run] [--cli codex|claude|claude-wa]
#   cmux-cli-restore.sh --list-above-p1
#
# Exit the app cleanly (ctrl+c), sanitize the shell line (CSI-u residue from the
# enhanced keyboard protocol), restart with codexc / claudec / claudewac, accept a
# goal-resume dialog, then verify at the process level.
#
# Never restarts a lane that is waiting on a human, and never touches more than the
# surface(s) it is given.
set -uo pipefail

DRY_RUN=0
WS=""
SF=""
LIST=0
CLI_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --workspace) WS="${2:-}"; shift 2 ;;
    --surface)   SF="${2:-}"; shift 2 ;;
    --list-above-p1) LIST=1; shift ;;
    --cli) CLI_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

cmx() { command cmux "$@" 2>/dev/null; }
PS_BIN="${CMUX_CLI_RESTORE_PS:-ps}"
proc_list() { "$PS_BIN" -Ao tty,pid,etime,command 2>/dev/null; }
lane_pids_of() { # <raw listing> <tty> -> pids of the CLI on that tty
  printf '%s\n' "$1" | awk -v t="$2" '$1==t && ($0 ~ /codex resume|@openai\/codex|\/bin\/codex|(^| )claude( |$)/) {print $2}'
}

tty_of() { # ws sf -> ttysNNN  (single capture, parsed with awk; multi-pipe blanked under pipefail)
  local out want="$2"
  case "$want" in surface:*) : ;; *) want="surface:$want" ;; esac
  local tries=0
  while [[ $tries -lt 3 ]]; do
    out=$(cmx top --workspace "$1" --processes)
    local got
    got=$(printf '%s\n' "$out" | awk -v want="$want" 'index($0,want){ while (match($0,/tty=ttys[0-9]+/)) { print substr($0,RSTART+4,RLENGTH-4); exit } }')
    [[ -n "$got" ]] && { printf '%s' "$got"; return 0; }
    tries=$((tries+1)); sleep 1
  done
  return 1
}

cli_on_tty() { # tty -> codex|claude-wa|claude|agy|pi|shell
  local t="$1"
  [[ -z "$t" ]] && { echo unknown; return; }
  if ps -Ao tty,command | awk -v t="$t" '$1==t' | grep -qE 'codex resume|@openai/codex|/bin/codex|node .*codex'; then echo codex; return; fi
  if ps -Ao tty,command | awk -v t="$t" '$1==t' | grep -q 'agy.real'; then echo agy; return; fi
  if ps -Ao tty,command | awk -v t="$t" '$1==t' | grep -qE '(^| )pi( |$)'; then echo pi; return; fi
  if ps -Ao tty,command | awk -v t="$t" '$1==t' | grep -q 'claude'; then
    # claudewa exports CLAUDE_CONFIG_DIR=~/.claude-wa
    local pid
    pid=$(ps -Ao pid,tty,command | awk -v t="$t" '$2==t' | grep claude | head -1 | awk '{print $1}')
    if [[ -n "$pid" ]] && ps eww -o command= -p "$pid" 2>/dev/null | grep -q 'CLAUDE_CONFIG_DIR=/Users/[^ ]*/.claude-wa'; then
      echo claude-wa
    else
      echo claude
    fi
    return
  fi
  echo shell
}

resume_cmd() { case "$1" in codex) echo codexc;; claude) echo claudec;; claude-wa) echo claudewac;; *) echo "";; esac; }

target_session() { # <raw listing> <ws> <tty> -> explicit session id of the lane (empty if unknown)
  local raw="$1" ws="$2" t="$3" sid
  sid=$(printf '%s\n' "$raw" | awk -v t="$t" '$1==t' | grep -oE 'resume [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | awk '{print $2}' | head -1)
  if [[ -z "$sid" ]]; then
    sid=$(cmx top --workspace "$ws" --processes | grep -oE 'codex\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 | sed 's/^codex\.//')
  fi
  printf '%s' "$sid"
}

explicit_resume() { # cli sid -> command that resumes THAT conversation, not "--last"
  case "$1" in
    codex) [[ -n "$2" ]] && echo "codex resume $2" ;;
    claude) [[ -n "$2" ]] && echo "claude --resume $2" ;;
    *) echo "" ;;
  esac
}

session_file() { # cli tty [ws] [sf] -> path of newest session transcript for that lane
  local cli="$1" t="$2" sid cwd
  case "$cli" in
    codex)
      sid=$(ps -Ao tty,command | awk -v t="$t" '$1==t' | grep -oE 'resume [0-9a-f]{8}-[0-9a-f]{4}' | awk '{print $2}' | head -1)
      # fallback: cmux exposes the session as a `codex.<uuid>` status tag
      if [[ -z "$sid" ]]; then
        sid=$(cmx top --workspace "${3:-}" --processes 2>/dev/null \
              | grep -oE 'codex\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
              | head -1 | sed 's/^codex\.//')
      fi
      # last resort: the TUI prints "codex resume <uuid>" on exit
      if [[ -z "$sid" ]]; then
        sid=$(cmx capture-pane --workspace "${3:-}" --surface "${4:-}" --scrollback --lines 400 2>/dev/null \
              | grep -oE 'codex resume [0-9a-f]{8}-[0-9a-f]{4}' | tail -1 | awk '{print $3}')
      fi
      [[ -n "$sid" ]] && ls -t "$HOME"/.codex/sessions/*/*/rollout-*"$sid"*.jsonl 2>/dev/null | head -1
      ;;
    pi)
      cwd=$(ps -Ao pid,tty,command | awk -v t="$t" '$2==t' | grep -w pi | head -1 | awk '{print $1}')
      [[ -n "$cwd" ]] && { local p; p=$(lsof -a -p "$cwd" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'); \
        [[ -n "$p" ]] && ls -t "$HOME"/.pi/agent/sessions/*/*.jsonl 2>/dev/null | grep -F "$(basename "$p")" | head -1; }
      ;;
  esac
}

prompt_clean() { # ws sf -> 0 only if the capture SUCCEEDED and the last line is a clean prompt
  local out last
  out=$(cmx capture-pane --workspace "$1" --surface "$2" --lines 2) || return 1
  [[ -n "$out" ]] || return 1                      # failed/empty capture is never "clean"
  last=$(printf '%s\n' "$out" | tail -1)
  [[ "$last" =~ \$[[:space:]]*$ ]] && ! [[ "$last" =~ [0-9]\;[0-9]u ]]
}

saw_human_gate() { # ws sf -> 0 gate, 1 no gate, 9 capture failed (fail CLOSED)
  local out
  out=$(cmx capture-pane --workspace "$1" --surface "$2" --lines 30) || return 9
  [[ -n "$out" ]] || return 9
  printf '%s\n' "$out" | grep -qiE \
    'pending human merge approval|autonomy rule requires a live human renewal|eight-hour authorization expired|MERGE APPROVED'
}

list_above_p1() {
  local json p1scope
  json=$(mktemp); cmx workspace list --json > "$json"
  p1scope=$(python3 - "$json" <<'PY'
import json,sys,re
ws=json.load(open(sys.argv[1]))['workspaces']
p1=[w for w in ws if re.fullmatch(r'-+\s*P1(\s.*)?', w['title'].strip())]
if not p1: raise SystemExit(0)
for w in ws:
    if w['index'] < p1[0]['index']: print(w['ref'])
PY
)
  rm -f "$json"
  local tree; tree=$(mktemp); cmx tree --all --json > "$tree"
  python3 - "$tree" "$p1scope" <<'PY'
import json,sys
tree=json.load(open(sys.argv[1])); scope=set(sys.argv[2].split())
for w in tree['windows'][0]['workspaces']:
    if w['ref'] not in scope: continue
    for p in w['panes']:
        for s in p['surfaces']:
            if s.get('type')=='terminal':
                print(f"{w['ref']} {s['ref']} {w.get('title','')[:20]}")
PY
  rm -f "$tree"
}

if [[ $LIST -eq 1 ]]; then
  printf "%-22s %-24s %-10s %-8s %s\n" "workspace" "surface" "cli" "restart" "last session write"
  list_above_p1 | while read -r ws sf title; do
    t=$(tty_of "$ws" "$sf"); cli=$(cli_on_tty "$t"); cmd=$(resume_cmd "$cli")
    f=$(session_file "$cli" "$t" "$ws" "$sf"); age="-"
    [[ -n "${f:-}" ]] && age="$(( ($(date +%s) - $(stat -f %m "$f")) / 60 ))m ago"
    printf "%-22s %-24s %-10s %-8s %s\n" "$ws" "$sf" "${cli}" "${cmd:--}" "$age"
  done
  exit 0
fi

[[ -z "$WS" || -z "$SF" ]] && { echo "need --workspace <ws> --surface <sf> (or --list-above-p1)" >&2; exit 2; }

t=$(tty_of "$WS" "$SF")
if [[ -n "$CLI_OVERRIDE" ]]; then
  cli="$CLI_OVERRIDE"
else
  # Mandatory probe BEFORE classifying or typing. A surface we cannot read is a
  # surface we must not type into: an unreadable capture previously read as
  # "no human gate" and the script went on to send ctrl+c anyway.
  if ! cmx capture-pane --workspace "$WS" --surface "$SF" --lines 5 >/dev/null 2>&1; then
    echo "ABORT: cannot read surface $SF (capture failed); no keystroke sent"; exit 7
  fi
  cli=$(cli_on_tty "$t")
fi
cmd=$(resume_cmd "$cli")
echo "surface=$SF tty=${t:-?} cli=${cli} restart=${cmd:-(none)}"

case "$cli" in
  shell) echo "nothing to restore: surface is a bare shell"; exit 0 ;;
  unknown) echo "ABORT: could not resolve a CLI on that surface (tty=${t:-none}); nothing typed"; exit 3 ;;
  agy|pi) echo "no resume wrapper for $cli — relaunch it by hand and pick the conversation"; exit 3 ;;
esac
[[ -z "$cmd" ]] && { echo "ABORT: no resume command for cli=$cli; nothing typed"; exit 3; }

saw_human_gate "$WS" "$SF"; gate=$?
case "$gate" in
  0) echo "REFUSING: this lane is blocked on a human gate, not a wedged CLI"; exit 4 ;;
  9) echo "ABORT: gate check could not read the surface; no keystroke sent"; exit 7 ;;
esac

if [[ $DRY_RUN -eq 1 ]]; then echo "dry-run: would ctrl+c, sanitize, type '$cmd', accept goal dialog, verify"; exit 0; fi

# 0. snapshot the pids that were already there, BEFORE any keystroke. Baseline
#    acquisition must succeed: an empty baseline makes a surviving old pid look
#    new in the post-snapshot (dot reviews at d2592291 / 05cbaafe).
t_pre=$(tty_of "$WS" "$SF")
if [[ -z "$t_pre" ]]; then
  echo "ABORT: could not resolve the surface tty before restart; no keystroke sent"; exit 9
fi
pre_raw=$(proc_list); pre_rc=$?
if [[ $pre_rc -ne 0 || -z "$pre_raw" ]]; then
  echo "ABORT: process listing failed before restart (exit $pre_rc); cannot prove a new pid later; no keystroke sent"; exit 9
fi
pre_pids=$(lane_pids_of "$pre_raw" "$t_pre" | sed '/^$/d' | sort -u)

# Resolve THIS lane's conversation from the same baseline. 'codexc' is
# 'codex resume --last', which can select a different, newer conversation in the
# same directory, so aim at the explicit id (dot review at c15525f0).
target=$(target_session "$pre_raw" "$WS" "$t_pre")
if [[ "$cli" == "codex" ]]; then
  if [[ -z "$target" ]]; then
    echo "ABORT: cannot resolve this lane's conversation id; 'codexc' could pick a different conversation in the same directory. Nothing sent."; exit 11
  fi
  cmd=$(explicit_resume codex "$target")
  echo "target conversation: $target -> '$cmd'"
fi

# 1. exit
for _ in 1 2 3; do
  cmx send-key --workspace "$WS" --surface "$SF" ctrl+c >/dev/null; sleep 3
  prompt_clean "$WS" "$SF" && break
done
# 2. sanitize the shell line (CSI-u residue: 9;5u, 17;5u, 5u)
if ! prompt_clean "$WS" "$SF"; then
  cmx send-key --workspace "$WS" --surface "$SF" ctrl+c >/dev/null; sleep 2
fi
if ! prompt_clean "$WS" "$SF"; then
  echo "ABORT: prompt still not clean after 3 ctrl+c; leaving the surface untouched" >&2
  cmx capture-pane --workspace "$WS" --surface "$SF" --lines 4 >&2
  exit 5
fi

# 3. restart — every input is checked; a silent send failure is not a restart
cmx send --workspace "$WS" --surface "$SF" "$cmd" >/dev/null || { echo "ABORT: send of '$cmd' failed; nothing restarted"; exit 8; }
sleep 1
cmx send-key --workspace "$WS" --surface "$SF" enter >/dev/null || { echo "ABORT: Enter failed; '$cmd' may sit unsent"; exit 8; }
sleep 15
# 4. accept a goal-resume dialog if one opened
if cmx capture-pane --workspace "$WS" --surface "$SF" --lines 10 | grep -q 'Resume goal'; then
  cmx send-key --workspace "$WS" --surface "$SF" enter >/dev/null; sleep 8
fi
# 5. verify at the process level
t2=$(tty_of "$WS" "$SF")
if [[ -z "$t2" || "$t2" != "$t_pre" ]]; then
  echo "UNVERIFIED: tty changed or unreadable (pre=${t_pre:-none} post=${t2:-none}); cannot compare pids" >&2; exit 6
fi
post_raw=$(proc_list); post_rc=$?
if [[ $post_rc -ne 0 || -z "$post_raw" ]]; then
  echo "UNVERIFIED: process listing failed after restart (exit $post_rc); cannot prove a new pid" >&2; exit 9
fi
post_pids=$(lane_pids_of "$post_raw" "$t2" | sed '/^$/d' | sort -u)
new_pids=$(comm -13 <(printf '%s\n' "$pre_pids" | sed '/^$/d' | sort -u) <(printf '%s\n' "$post_pids" | sed '/^$/d' | sort -u))
if [[ -n "$new_pids" ]]; then
  if [[ "$cli" == "codex" ]]; then
    post_target=$(target_session "$post_raw" "$WS" "$t2")
    if [[ "$post_target" != "$target" ]]; then
      echo "FAILED: resumed conversation '${post_target:-unknown}' but the lane was '${target}' — 'resume --last' picked another session" >&2
      exit 10
    fi
    echo "RESTARTED same conversation $target, new pid(s)=$(printf '%s' "$new_pids" | tr '\n' ' ')"
    exit 0
  fi
  echo "RESTARTED new pid(s)=$(printf '%s' "$new_pids" | tr '\n' ' ')"
  exit 0
fi
echo "UNVERIFIED: no NEW CLI process on ${t2:-?} (pre-restart pids: $(printf '%s' "${pre_pids:-none}" | tr '\n' ' ')); an old process surviving is not a restart" >&2
exit 6
