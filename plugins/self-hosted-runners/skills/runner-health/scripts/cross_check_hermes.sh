#!/usr/bin/env bash
# cross_check_hermes.sh — prepare an optional Slack cross-check with a second agent
# Requires RUNNER_CROSSCHECK_SLACK_CHANNEL_ID and RUNNER_CROSSCHECK_SLACK_USER_ID;
# when either is unset the cross-check is disabled and the JSON says so.
# Usage: bash cross_check_hermes.sh <depth> "<question>"
#   depth: 1, 2, or 3 (number of cross-checks to perform)
#   question: the question text to post
# Outputs JSON to stdout. exit 0 on success.
#
# Note: This script assumes the calling agent will post via the Slack MCP tool,
# since the runner-health script doesn't have direct MCP access. This script
# instead provides:
#   1. The channel ID + user ID lookup
#   2. A deterministic polling loop
#   3. JSON output of the question posted
#
# The actual post + reply fetch is done by the LLM (using mcp__slack__* tools).
# This script handles the deterministic parts only.
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DEPTH="${1:-1}"
QUESTION="${2:-please verify runner health on your side}"
CHANNEL_ID="${RUNNER_CROSSCHECK_SLACK_CHANNEL_ID:-}"
USER_ID="${RUNNER_CROSSCHECK_SLACK_USER_ID:-}"

if [[ -z "$CHANNEL_ID" || -z "$USER_ID" ]]; then
  echo '{"timestamp":"'"$TS"'","depth":'"$DEPTH"',"error":"RUNNER_CROSSCHECK_SLACK_CHANNEL_ID / RUNNER_CROSSCHECK_SLACK_USER_ID not configured: cross-check disabled","hermes_response":null}'
  exit 0
fi

cat <<EOF
{
  "timestamp": "$TS",
  "depth": $DEPTH,
  "question": "$QUESTION",
  "channel_id": "$CHANNEL_ID",
  "user_id": "$USER_ID",
  "instructions": "Use the Slack MCP tools to: (1) post the question to channel $CHANNEL_ID tagging $USER_ID, (2) poll conversations_replies for the reply, (3) parse the reply, (4) return the reply text in this JSON's hermes_response field. The script itself cannot call MCP tools — this is a deterministic wrapper only.",
  "hermes_response": null,
  "error": null
}
EOF
exit 0
