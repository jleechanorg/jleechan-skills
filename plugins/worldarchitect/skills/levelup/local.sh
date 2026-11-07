#!/usr/bin/env bash
# /levelup local runner — real-server + real-LLM organic level-up playthrough.
#
# Runs testing_mcp/core/test_level_up_organic.py against EITHER a freshly
# auto-started local gunicorn server (default) OR an existing server / GCP
# preview URL (via --server <url>). Real Firebase + real LLM only — AGY CLI is
# the local default; remote previews use their configured provider. No mocks
# (the testing_mcp harness fails closed if any MOCK_*/TEST_MODE flag is set).
#
# Usage (run from the product repository root; <skill-dir> is this skill's directory):
#   <skill-dir>/local.sh                       # all scenarios, local server
#   <skill-dir>/local.sh --level-up-scenario single-organic
#   <skill-dir>/local.sh --server https://<preview-service-url>   # GCP preview
#   <skill-dir>/local.sh --class-name wizard --full
#
# Any extra args are passed straight through to the test (e.g. --server,
# --server-auth, --level-up-scenario, --class-name, --full, --model).
#
# Evidence bundle is written to /tmp/<repo>/<branch>/test_level_up_organic/latest/.
set -euo pipefail

# Resolve the product repository: PROJECT_ROOT wins, then its accepted REPO_ROOT
# alias, then the current working tree (verified by the testing_mcp/ check below).
# This script may be installed outside the repository (for example as a plugin);
# see docs/portability-env-vars.md ("PROJECT_ROOT / REPO_ROOT").
PROJECT_ROOT="${PROJECT_ROOT:-${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}}"
REPO_ROOT="${PROJECT_ROOT}"
if [ -z "${REPO_ROOT}" ] || [ ! -d "${REPO_ROOT}/testing_mcp" ]; then
  echo "PROJECT_ROOT not configured: run from the product repository root, or export PROJECT_ROOT (or its REPO_ROOT alias) to the product-repo checkout." >&2
  exit 2
fi
cd "${REPO_ROOT}"

# Real services only — auth bypass for local, never a mock LLM.
export TESTING_AUTH_BYPASS=true
export ALLOW_TEST_AUTH_BYPASS=true
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/mvp_site"

# Real-services contract: scrub any mock-enabling vars from the child env. These
# are commonly exported ambiently (e.g. SMOKE_TOKEN in a dev's shell profile for
# CI), so we clear+warn rather than hard-fail — this runner is real-services only
# by definition. The harness also fails closed via _assert_no_mock_services().
for v in TEST_MODE MOCK_SERVICES_MODE USE_MOCK_FIREBASE USE_MOCK_GEMINI SMOKE_TOKEN; do
  if [ -n "${!v:-}" ]; then
    echo "NOTICE: ${v} was set in the environment — unsetting it (this runner is real-services only)." >&2
    unset "${v}"
  fi
done

# Default to the full scenario sweep when the caller didn't pick one.
ARGS=("$@")
have_scenario=false
for a in "${ARGS[@]+"${ARGS[@]}"}"; do
  case "$a" in --level-up-scenario|--level-up-scenario=*) have_scenario=true ;; esac
done
if [ "${have_scenario}" = false ]; then
  ARGS=(--level-up-scenario all "${ARGS[@]+"${ARGS[@]}"}")
fi

echo "==> repo root : ${REPO_ROOT}"
echo "==> branch    : $(git branch --show-current 2>/dev/null || echo '<detached>')"
echo "==> head SHA  : $(git rev-parse --short HEAD 2>/dev/null || echo '<unknown>')"
echo "==> args      : ${ARGS[*]+"${ARGS[*]}"}"
echo "==> mode      : real Firebase + AGY CLI by default locally (no mocks)"
echo

exec python3 testing_mcp/core/test_level_up_organic.py "${ARGS[@]+"${ARGS[@]}"}"
