#!/usr/bin/env bash
set -uo pipefail

if [[ "${CODEX_RTK_SKIP:-0}" == "1" ]]; then
  exec cat
fi

payload="$(cat)"
output="$(printf '%s' "$payload" | rtk hook claude "$@" 2>/dev/null || true)"

if [[ -z "$output" ]]; then
  printf '%s\n' '{"continue":true}'
  exit 0
fi

if command -v jq >/dev/null 2>&1; then
  rewritten="$(printf '%s' "$output" |
    jq -r '.hookSpecificOutput.updatedInput.command // ""' 2>/dev/null || true)"

  # `rtk find` explicitly rejects these compound predicate/action tokens.
  if [[ "$rewritten" =~ ^rtk[[:space:]]+find([[:space:]]|$) ]] &&
    [[ " $rewritten " =~ [[:space:]](-exec(dir)?|-not|!|-o|-or|-a|-and)[[:space:]] ]]; then
    printf '%s\n' '{"continue":true}'
    exit 0
  fi

  # RTK currently maps `rg --files` to unsupported `rtk grep --files`.
  if [[ "$rewritten" == "rtk grep --files"* ]]; then
    printf '%s\n' '{"continue":true}'
    exit 0
  fi
fi

printf '%s\n' "$output"
