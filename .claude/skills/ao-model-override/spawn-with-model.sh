#!/usr/bin/env bash
# spawn-with-model.sh — Spawn an AO worker with an inline model override,
# without mutating ~/.hermes/agent-orchestrator.yaml.
#
# Usage:
#   spawn-with-model.sh --project <id> --model <name> [--agent <plugin>] [--claim-pr <pr>] [--keep-config] "<task>"
#
# Examples:
#   spawn-with-model.sh --project mctrl-test --model claude-sonnet-4-6 "Add a shout() function under df_demo/"
#   spawn-with-model.sh -p worldarchitect -m claude-opus-4-7 -a claude-code --claim-pr 1234 "address review comments"
#
# Exit codes:
#   0 — spawn succeeded, session name printed on stdout (alone, on its own line)
#   2 — usage error
#   3 — config build / yq error
#   4 — ao spawn error
#
# Env:
#   AO_CONFIG_PATH — base config to copy from (default: ~/.hermes/agent-orchestrator.yaml)
#   AO_MODEL_OVERRIDE_KEEP_CONFIG=1 — keep the temp config file for inspection
#
set -euo pipefail

PROJECT=""
MODEL=""
AGENT="claude-code"
CLAIM_PR=""
TASK=""
KEEP_CONFIG="${AO_MODEL_OVERRIDE_KEEP_CONFIG:-0}"

usage() {
    cat <<EOF >&2
Usage: $(basename "$0") --project <id> --model <name> [--agent <plugin>] [--claim-pr <pr>] [--keep-config] "<task>"
EOF
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        -p|--project) PROJECT="$2"; shift 2 ;;
        -m|--model)   MODEL="$2";   shift 2 ;;
        -a|--agent)   AGENT="$2";   shift 2 ;;
        --claim-pr)   CLAIM_PR="$2"; shift 2 ;;
        --keep-config) KEEP_CONFIG=1; shift ;;
        -h|--help)    usage ;;
        --)           shift; TASK="${TASK}${TASK:+ }$*"; break ;;
        -*)           echo "unknown flag: $1" >&2; usage ;;
        *)            TASK="${TASK}${TASK:+ }$1"; shift ;;
    esac
done

[ -n "$PROJECT" ] || { echo "missing --project" >&2; usage; }
[ -n "$MODEL" ]   || { echo "missing --model" >&2; usage; }
[ -n "$TASK" ]    || { echo "missing task (positional)" >&2; usage; }

if ! command -v yq >/dev/null 2>&1; then
    echo "yq is required (brew install yq)" >&2
    exit 3
fi

SRC="${AO_CONFIG_PATH:-$HOME/.hermes/agent-orchestrator.yaml}"
if [ ! -f "$SRC" ]; then
    echo "base config not found: $SRC" >&2
    exit 3
fi

DST="$(mktemp -t ao-override-XXXX.yaml)"
trap '[ "$KEEP_CONFIG" = "1" ] || rm -f "$DST"' EXIT
cp "$SRC" "$DST"

# Patch: projects.<project>.modelByCli.<agent>.model = <model>
yq -i ".projects.\"$PROJECT\".modelByCli.\"$AGENT\".model = \"$MODEL\"" "$DST" \
    || { echo "yq patch failed" >&2; exit 3; }

# Verify the patch is present
PATCHED="$(yq -r ".projects.\"$PROJECT\".modelByCli.\"$AGENT\".model" "$DST")"
if [ "$PATCHED" != "$MODEL" ]; then
    echo "verification failed: expected $MODEL, got $PATCHED" >&2
    exit 3
fi

SPAWN_ARGS=(spawn -p "$PROJECT" --agent "$AGENT")
[ -n "$CLAIM_PR" ] && SPAWN_ARGS+=(--claim-pr "$CLAIM_PR")
SPAWN_ARGS+=("$TASK")

# AO_CONFIG_PATH overrides the bashrc export for this process tree only.
OUTPUT="$(AO_CONFIG_PATH="$DST" ao "${SPAWN_ARGS[@]}" 2>&1)" || {
    rc=$?
    echo "ao spawn failed (rc=$rc):" >&2
    echo "$OUTPUT" >&2
    exit 4
}

SESSION="$(printf '%s\n' "$OUTPUT" | awk -F= '/^SESSION=/{print $2; exit}')"
if [ -z "$SESSION" ]; then
    echo "no SESSION= line in ao spawn output:" >&2
    echo "$OUTPUT" >&2
    exit 4
fi

# Emit machine-readable line first, then human metadata to stderr
echo "$SESSION"
{
    echo "[spawn-with-model] project=$PROJECT agent=$AGENT model=$MODEL session=$SESSION"
    echo "[spawn-with-model] temp config: $DST $([ "$KEEP_CONFIG" = "1" ] && echo '(kept)' || echo '(will be removed on exit)')"
    echo "[spawn-with-model] verify model in worker pane:"
    echo "  tmux ls 2>/dev/null | grep ${SESSION} | head -1"
} >&2
