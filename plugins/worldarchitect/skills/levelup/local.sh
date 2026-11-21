#!/usr/bin/env bash
# Resolve this portable skill invocation to WorldArchitect's canonical runner.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}}"
PRODUCT_SKILLS_DIR=".claude/skills"
PRODUCT_SKILL_NAME="levelup"
ENTRYPOINT="${PROJECT_ROOT:+${PROJECT_ROOT}/${PRODUCT_SKILLS_DIR}/${PRODUCT_SKILL_NAME}/levelup.sh}"

if [ -z "${PROJECT_ROOT}" ] || [ ! -f "${PROJECT_ROOT}/testing_mcp/core/test_level_up_organic.py" ] || [ ! -f "${ENTRYPOINT}" ]; then
  echo "WorldArchitect checkout not found. Run from its product repository or set PROJECT_ROOT to that checkout." >&2
  exit 2
fi

cd "$PROJECT_ROOT"
exec bash "${ENTRYPOINT}" "$@"
