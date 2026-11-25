#!/usr/bin/env bash
# Regression tests for dot.sh `--secondary` account selection (feat/dot-secondary-account).
#
# `--secondary` names a configured secondary dot account via DOT_SECONDARY_ACCOUNT
# or config `secondary_account`. The contract under test:
#   1. `--account` wins over `--secondary` (explicit selector beats the alias)
#   2. DOT_SECONDARY_ACCOUNT wins over config `secondary_account`
#   3. `--secondary` with nothing configured exits 2 and never falls back to
#      `default_account` — silently using the primary for a secondary request is
#      an identity error the caller cannot detect from the output
#   4. `--secondary` alone does not change default-account behaviour
#
# Every case runs against a throwaway fixture config through DOT_CONFIG_FILE, so
# no test reads the operator's real ~/.config/dot/config.json, and no case opens
# a browser: only the stderr banner (account=... dir=...) is asserted.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOT_SH="$SCRIPT_DIR/../scripts/dot.sh"

PASS=0
FAIL=0
declare -a FAILURES=()

ok()  { PASS=$((PASS+1)); echo "  ok - $1"; }
bad() { FAIL=$((FAIL+1)); FAILURES+=("$1"); echo "  FAIL - $1"; }

SCRATCH="${DOT_TEST_SCRATCH:-$(mktemp -d "${TMPDIR:-/tmp}/dot-secondary-fixture.XXXXXX")}"
mkdir -p "$SCRATCH"
trap 'rm -rf "$SCRATCH"' EXIT

# fixture <name> <config-json> -> prints the config path
fixture() {
  local name="$1" body="$2" dir="$SCRATCH/$1"
  mkdir -p "$dir/profile/Default"
  printf '%s\n' "$body" > "$dir/config.json"
  printf '%s\n' "$dir/config.json"
}

# banner_account <config> [args...] -> prints the account= token from the banner.
# DOT_SKIP_DISPATCH=1 stops dot.sh after the resolver, so no Chrome is launched
# and no real profile is touched; only the banner is asserted. DOT_ACCOUNT and
# DOT_SECONDARY_ACCOUNT are inherited from the caller, so the ambient-hijack case
# is actually observable: hardcoding DOT_ACCOUNT= here would mask it. Callers that
# need them unset set them empty explicitly.
banner_account() {
  local cfg="$1"; shift
  DOT_CONFIG_FILE="$cfg" DOT_SKIP_DISPATCH=1 \
    timeout 60 bash "$DOT_SH" "$@" read 1 2>&1 \
    | sed -n 's/^dot\.sh: account=\([^ ]*\) .*/\1/p' | head -1
}

echo "dot.sh --secondary account selection"

# --- 1. --account beats --secondary -------------------------------------------
cfg="$(fixture explicit '{"default_account":"primary","secondary_account":"secondary","accounts":{"primary":{"url":"https://chatgpt.com/"},"secondary":{"url":"https://chatgpt.com/"}}}')"
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= banner_account "$cfg" --account explicit --secondary)"
[[ "$got" == "explicit" ]] && ok "--account overrides --secondary" \
  || bad "--account overrides --secondary (got '$got', want 'explicit')"

# --- 2. env override beats config ---------------------------------------------
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT=envsec banner_account "$cfg" --secondary)"
[[ "$got" == "envsec" ]] && ok "DOT_SECONDARY_ACCOUNT overrides config secondary_account" \
  || bad "DOT_SECONDARY_ACCOUNT overrides config secondary_account (got '$got', want 'envsec')"

# --- 3. config secondary_account is used when no env override -----------------
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= banner_account "$cfg" --secondary)"
[[ "$got" == "secondary" ]] && ok "config secondary_account selected by --secondary" \
  || bad "config secondary_account selected by --secondary (got '$got', want 'secondary')"

# --- 4. unconfigured --secondary fails closed (exit 2, no primary fallback) ---
bare="$(fixture bare '{"default_account":"primary","accounts":{"primary":{"url":"https://chatgpt.com/"}}}')"
out="$(DOT_CONFIG_FILE="$bare" DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= timeout 30 bash "$DOT_SH" --secondary read 1 2>&1)"
rc=$?
[[ "$rc" -eq 2 ]] && ok "--secondary with nothing configured exits 2" \
  || bad "--secondary with nothing configured exits 2 (got exit $rc)"
grep -q 'needs DOT_SECONDARY_ACCOUNT' <<<"$out" \
  && ok "--secondary failure explains how to configure it" \
  || bad "--secondary failure explains how to configure it (got: ${out:0:120})"
grep -q 'account=primary' <<<"$out" \
  && bad "--secondary must not silently fall back to default_account" \
  || ok "--secondary does not fall back to default_account"

# --- 5. no flag still uses default_account ------------------------------------
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= banner_account "$cfg")"
[[ "$got" == "primary" ]] && ok "no flag still selects default_account" \
  || bad "no flag still selects default_account (got '$got', want 'primary')"

# --- 6. DOT_SECONDARY_ACCOUNT must not hijack a default call -------------------
# Regression: a nested ${DOT_SECONDARY_ACCOUNT:-$(cfg ...)} expansion once read
# the env var on default calls too, so merely having it exported routed every
# invocation to the secondary account.
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT=secondary banner_account "$cfg")"
[[ "$got" == "primary" ]] && ok "DOT_SECONDARY_ACCOUNT does not affect a call without --secondary" \
  || bad "DOT_SECONDARY_ACCOUNT must not affect a call without --secondary (got '$got', want 'primary')"

# --- 7. ambient DOT_ACCOUNT must not hijack a --secondary call -----------------
# Regression: --secondary once fell through to ${DOT_ACCOUNT}, so any shell with
# DOT_ACCOUNT exported silently sent a secondary request to the primary account.
got="$(DOT_ACCOUNT=primary DOT_SECONDARY_ACCOUNT= banner_account "$cfg" --secondary)"
[[ "$got" == "secondary" ]] && ok "ambient DOT_ACCOUNT does not hijack --secondary" \
  || bad "ambient DOT_ACCOUNT must not hijack --secondary (got '$got', want 'secondary')"

# --- 8. --secondary stays fail-closed even when DOT_ACCOUNT is exported -------
bare2="$(fixture bare2 '{"default_account":"primary","accounts":{"primary":{"url":"https://chatgpt.com/"}}}')"
DOT_CONFIG_FILE="$bare2" DOT_ACCOUNT=primary DOT_SECONDARY_ACCOUNT= DOT_SKIP_DISPATCH=1 \
  timeout 30 bash "$DOT_SH" --secondary read 1 >/dev/null 2>&1
rc=$?
[[ "$rc" -eq 2 ]] && ok "--secondary with ambient DOT_ACCOUNT still exits 2" \
  || bad "--secondary with ambient DOT_ACCOUNT still exits 2 (got exit $rc)"

# --- 9. explicit --account beats both --secondary and the env ---------------
got="$(DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT=envsec banner_account "$cfg" --account explicit --secondary)"
[[ "$got" == "explicit" ]] && ok "explicit --account wins over --secondary and env" \
  || bad "explicit --account wins over --secondary and env (got '$got', want 'explicit')"

# --- 10. ambient DOT_SECONDARY must not hijack a default call ------------------
# Regression: the internal flag was once stored in DOT_SECONDARY, so an exported
# DOT_SECONDARY=1 turned every plain call into a secondary request (and hard-
# failed with exit 2 when no secondary was configured).
got="$(DOT_SECONDARY=1 DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= banner_account "$cfg")"
[[ "$got" == "primary" ]] && ok "ambient DOT_SECONDARY does not hijack a default call" \
  || bad "ambient DOT_SECONDARY must not hijack a default call (got '$got', want 'primary')"

DOT_CONFIG_FILE="$bare" DOT_SECONDARY=1 DOT_ACCOUNT= DOT_SECONDARY_ACCOUNT= DOT_SKIP_DISPATCH=1 \
  timeout 30 bash "$DOT_SH" read 1 >/dev/null 2>&1
rc=$?
[[ "$rc" -eq 0 ]] && ok "ambient DOT_SECONDARY leaves a default call working" \
  || bad "ambient DOT_SECONDARY leaves a default call working (got exit $rc, want 0)"

echo
if (( FAIL > 0 )); then
  echo "FAIL: $FAIL failure(s), $PASS passed"
  printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
echo "PASS: all $PASS checks passed"
