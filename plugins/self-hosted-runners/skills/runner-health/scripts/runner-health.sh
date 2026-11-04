#!/usr/bin/env bash
# runner-health.sh — master wrapper: runs all 4 checks in parallel, writes Markdown report
# Usage: bash runner-health.sh [--cross-check N] [--no-report]
#   --cross-check N: invoke hermes-pc cross-check (N=1..3). Default 0.
#   --no-report: skip writing the Markdown file (console only).
#
# Exit codes:
#   0 = all checks completed (may have AMBER signals in output)
#   1 = some script had a hard error
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CROSS_CHECK=0
WRITE_REPORT=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cross-check) CROSS_CHECK="$2"; shift 2 ;;
    --no-report) WRITE_REPORT=0; shift ;;
    *) shift ;;
  esac
done

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TS_FN="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
REPORT_FILE="/tmp/runner-health-${TS_FN}.md"

# Run all 4 checks in parallel
PIDS=()
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

bash "$SCRIPT_DIR/check_api.sh" > "$TMPDIR/api.json" 2> "$TMPDIR/api.err" &
PIDS+=($!)
bash "$SCRIPT_DIR/check_docker.sh" > "$TMPDIR/docker.json" 2> "$TMPDIR/docker.err" &
PIDS+=($!)
bash "$SCRIPT_DIR/check_lima.sh" > "$TMPDIR/lima.json" 2> "$TMPDIR/lima.err" &
PIDS+=($!)
bash "$SCRIPT_DIR/check_jeff_ubuntu.sh" > "$TMPDIR/jeff_ubuntu.json" 2> "$TMPDIR/jeff_ubuntu.err" &
PIDS+=($!)
bash "$SCRIPT_DIR/check_session_conflict.sh" > "$TMPDIR/session_conflict.json" 2> "$TMPDIR/session_conflict.err" &
PIDS+=($!)

# Optional cross-check
if [[ "$CROSS_CHECK" -gt 0 ]]; then
  bash "$SCRIPT_DIR/cross_check_hermes.sh" "$CROSS_CHECK" "Please verify runner health on your side. (gh api orgs/jleechanorg/actions/runners — are 22/22 online, how many busy?)" > "$TMPDIR/hermes.json" 2> "$TMPDIR/hermes.err" &
  PIDS+=($!)
fi

# Wait for all
for pid in "${PIDS[@]}"; do
  wait "$pid" || true
done

# Read results
# Any check_*.sh script can write its error message to stderr (not stdout)
# on a hard-error path, leaving the redirected stdout file existing but
# EMPTY (zero bytes) rather than missing. `cat` on an existing empty file
# succeeds, so a bare `|| echo '{}'` never triggers and the capture becomes
# "" instead of "{}" -- this bit check_api.sh once (PR #8193 round 3) and
# is a standing risk for any sibling script's stdout/stderr convention.
#
# IMPORTANT: do NOT use `${content:-{}}` here. Bash misparses the brace
# after `-` and appends a spurious literal trailing `}` onto ANY non-empty
# $content, not just when the default fires -- e.g. content='{"x":1}' would
# evaluate to '{"x":1}}' (corrupted, extra brace), deterministically, every
# time. Verified on both bash 5.3.3 and macOS bash 3.2.57. Use an explicit
# if/else instead, which has no such parsing trap.
read_json_or_default() {
  local content
  content=$(cat "$1" 2>/dev/null)
  if [[ -z "$content" ]]; then
    printf '%s' '{}'
  else
    printf '%s' "$content"
  fi
}
API_JSON=$(read_json_or_default "$TMPDIR/api.json")
DOCKER_JSON=$(read_json_or_default "$TMPDIR/docker.json")
LIMA_JSON=$(read_json_or_default "$TMPDIR/lima.json")
JEFF_JSON=$(read_json_or_default "$TMPDIR/jeff_ubuntu.json")
HERMES_JSON=$(read_json_or_default "$TMPDIR/hermes.json")
SESSION_CONFLICT_JSON=$(read_json_or_default "$TMPDIR/session_conflict.json")

PARSER="$SCRIPT_DIR/parse_fields.py"

# Extract fields via dedicated Python helper (avoids heredoc/pipe conflicts)
read -r ONLINE BUSY LINUX_BUSY MAC_BUSY LINUX_ONLINE MAC_ONLINE <<<"$(python3 "$PARSER" api "$API_JSON")"
DOCKER_LINE=$(python3 "$PARSER" docker "$DOCKER_JSON")
LIMA_LINE=$(python3 "$PARSER" lima "$LIMA_JSON")
JEFF_LINE=$(python3 "$PARSER" jeff "$JEFF_JSON")
SESSION_CONFLICT_LINE=$(python3 "$PARSER" session_conflict "$SESSION_CONFLICT_JSON")

# Verdict via helper (lima state is shown separately, not used in verdict
# math; session-conflict divergence — see check_session_conflict.sh /
# bead rev-ws17d — overrides the generic per-arch online-count verdict)
VERDICT_RESULT=$(python3 "$PARSER" verdict "$API_JSON" "$DOCKER_JSON" "$JEFF_JSON" "$SESSION_CONFLICT_JSON")
VERDICT="${VERDICT_RESULT%%|*}"
REASON="${VERDICT_RESULT#*|}"

if [[ "$CROSS_CHECK" -gt 0 ]]; then
  HERMES_LINE="cross-checked (see report)"
else
  HERMES_LINE="not invoked (use --cross-check N)"
fi

echo "=== runner-health @ $TS ==="
echo "GitHub API:       $ONLINE/22 online ($LINUX_ONLINE Linux + $MAC_ONLINE Mac), $BUSY/$ONLINE busy ($LINUX_BUSY Linux + $MAC_BUSY Mac busy)"
echo "Docker:           $DOCKER_LINE"
echo "Lima:             $LIMA_LINE"
echo "jeff-ubuntu:      $JEFF_LINE"
echo "Session conflict: $SESSION_CONFLICT_LINE"
echo "hermes-pc:        $HERMES_LINE"
echo ""
echo "VERDICT: $VERDICT${REASON:+ — $REASON}"
echo ""

# Markdown report
if [[ "$WRITE_REPORT" -eq 1 ]]; then
  cat > "$REPORT_FILE" <<MDEOF
# Runner Health Report — $TS

## Verdict: $VERDICT

${REASON:+**Reason:** $REASON}

## Check 1: GitHub API
\`\`\`json
$API_JSON
\`\`\`

## Check 2: Docker (local)
\`\`\`json
$DOCKER_JSON
\`\`\`

## Check 3: Lima VM
\`\`\`json
$LIMA_JSON
\`\`\`

## Check 4: jeff-ubuntu
\`\`\`json
$JEFF_JSON
\`\`\`

## Check 5: Session conflict (GitHub offline vs container Up)
\`\`\`json
$SESSION_CONFLICT_JSON
\`\`\`

## Check 6: hermes-pc cross-check
$(if [[ "$CROSS_CHECK" -gt 0 ]]; then
  echo "Cross-check invoked (depth=$CROSS_CHECK). LLM agent posts question to #hermes-pc and parses reply."
  echo ""
  echo "\`\`\`json"
  echo "$HERMES_JSON"
  echo "\`\`\`"
else
  echo "Not invoked. Re-run with \`--cross-check <1|2|3>\` to enable."
fi)

## Notes

- All scripts are deterministic bash. Re-run any check standalone: \`bash $SCRIPT_DIR/check_<name>.sh\`
- Report regenerated on each invocation; persistent by user copy.
- Per /runner-health SKILL.md: GREEN = 22/22 + ≥1 busy + no restart loops; AMBER = local signal ambiguous; RED = <22 or all idle
- Related skills: \`self-hosted-runner-preflight\` (fix-oriented), \`org-runner-audit\` (read-only list)
MDEOF
  echo "Report written: $REPORT_FILE"
fi

# Exit code
if [[ "$VERDICT" == "RED" ]]; then
  exit 2
elif [[ "$VERDICT" == "AMBER" ]]; then
  exit 1
fi
exit 0
