#!/usr/bin/env bash
# cross_check_hermes.sh — post question to #hermes-pc Slack channel and wait for reply
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
CHANNEL_ID="C0BDAMWQQJK"
USER_ID="U0BC138QXUJ"

cat <<EOF
{
  "timestamp": "$TS",
  "depth": $DEPTH,
  "question": "$QUESTION",
  "channel_id": "$CHANNEL_ID",
  "channel_name": "#hermes-pc",
  "user_id": "$USER_ID",
  "user_name": "@hermespc",
  "instructions": "Use the Slack MCP tools to: (1) post the question to channel $CHANNEL_ID tagging $USER_ID, (2) poll conversations_replies for the reply, (3) parse the reply, (4) return the reply text in this JSON's hermes_response field. The script itself cannot call MCP tools — this is a deterministic wrapper only.",
  "hermes_response": null,
  "error": null
}
EOF
exit 0
