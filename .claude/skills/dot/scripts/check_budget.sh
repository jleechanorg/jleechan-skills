#!/usr/bin/env bash
# Enforce the LOC budgets documented in GUARDRAIL.md. Exits non-zero on breach.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

fail=0
check() { # name file cap
  local n
  n="$(wc -l < "$2" | tr -d ' ')"
  if [[ "$n" -gt "$3" ]]; then
    echo "BUDGET BREACH: $1 = $n LOC > cap $3 ($2)" >&2
    fail=1
  else
    echo "ok: $1 = $n LOC (cap $3)"
  fi
}

check "dot.sh" "scripts/dot.sh" 520

transport_modules=(scripts/*.mjs)
combined=$(wc -l < scripts/dot.sh)
for module in "${transport_modules[@]}"; do
  check "${module##*/}" "$module" 900
  combined=$(( combined + $(wc -l < "$module") ))
done
if [[ "$combined" -gt 1500 ]]; then
  echo "BUDGET BREACH: transport scripts combined = $combined LOC > cap 1500" >&2
  fail=1
else
  echo "ok: transport scripts combined = $combined LOC (cap 1500)"
fi

check "SKILL.md" "SKILL.md" 400
if [[ -f "../dot-coordinator/scripts/ping-dots.py" ]]; then
  combined=$(( $(wc -l < ../dot-coordinator/scripts/ping-dots.py) + $(wc -l < ../dot-coordinator/scripts/dot-coordinator-wrapper.sh) + $(wc -l < ../dot-coordinator/scripts/pi-lunaroute-adapter.sh) ))
  for alias in agy-dot-coordinator-wrapper.sh pi-lunaroute-adapter.sh ping-dots.py; do
    [[ ! -f "../agy-dot-coordinator/scripts/$alias" ]] || combined=$(( combined + $(wc -l < "../agy-dot-coordinator/scripts/$alias") ))
  done
  if [[ "$combined" -gt 150 ]]; then
    echo "BUDGET BREACH: coordinator launch glue = $combined LOC > cap 150" >&2
    fail=1
  else
    echo "ok: coordinator launch glue = $combined LOC (cap 150)"
  fi
  check "dot-coordinator/SKILL.md" "../dot-coordinator/SKILL.md" 400
fi

bash -n scripts/dot.sh

# node syntax gate: use PATH node, else common nvm/Homebrew locations; warn-and-skip if truly absent
NODE_BIN="$(command -v node || true)"
if [[ -z "$NODE_BIN" ]]; then
  NODE_BIN="$(ls -1 "$HOME"/.nvm/versions/node/*/bin/node /usr/local/bin/node /opt/homebrew/bin/node 2>/dev/null | tail -1 || true)"
fi
if [[ -n "$NODE_BIN" ]]; then
  for module in "${transport_modules[@]}"; do
    "$NODE_BIN" --check "$module"
  done
else
  echo "warn: node not found on runner; skipped mjs syntax check (LOC caps still enforced)" >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "GUARDRAIL FAILED — shrink scripts or get operator approval to bump GUARDRAIL.md caps." >&2
  exit 1
fi
echo "GUARDRAIL PASSED"
