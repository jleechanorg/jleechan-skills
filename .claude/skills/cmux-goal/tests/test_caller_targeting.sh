#!/usr/bin/env bash
# Validate caller targeting with synthetic cmux output; no cmux-send operation.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESOLVER="${SKILL_DIR}/bin/resolve_caller_target.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

mkdir -p "${TEST_ROOT}/bin"
cat > "${TEST_ROOT}/bin/cmux" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  identify)
    cat <<'JSON'
{"caller":{"workspace_ref":"workspace:21","surface_ref":"surface:50"},"focused":{"workspace_ref":"workspace:6","surface_ref":"surface:19"}}
JSON
    ;;
  current-workspace)
    echo "current-workspace must not be queried" >&2
    exit 1
    ;;
  send|send-key)
    echo "cmux-send must not be called by this validation" >&2
    exit 1
    ;;
  *)
    echo "unexpected cmux operation: ${1:-}" >&2
    exit 1
    ;;
esac
EOF
chmod +x "${TEST_ROOT}/bin/cmux"

target=$(CMUX_BIN="${TEST_ROOT}/bin/cmux" "$RESOLVER")
expected=$'workspace:21\tsurface:50'
if [[ "$target" != "$expected" ]]; then
  echo "FAIL: expected caller target '$expected', got '$target'"
  exit 1
fi

echo "PASS: caller workspace/surface extracted as $target"
echo "CALLER-TARGETING: PASS (1/1; no send operation)"
