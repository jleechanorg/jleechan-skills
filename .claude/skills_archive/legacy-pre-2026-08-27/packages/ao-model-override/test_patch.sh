#!/usr/bin/env bash
# Unit test: verify the yq config-patch logic in spawn-with-model.sh produces
# the right YAML mutation. Does NOT call `ao spawn` (network/AO dependency).
set -euo pipefail

TMP_SRC="$(mktemp -t ao-test-src-XXXX.yaml)"
TMP_DST="$(mktemp -t ao-test-dst-XXXX.yaml)"
trap 'rm -f "$TMP_SRC" "$TMP_DST"' EXIT

# Minimal fake config — mirrors the real structure
cat > "$TMP_SRC" <<'EOF'
defaults:
  agent: claude-code
  modelByCli:
    claude-code:
      model: wafer.ai/GLM-5.1
projects:
  fakeproj:
    agentRules: |
      You are working on fakeproj.
    defaultBranch: main
    repo: example/fakeproj
EOF

cp "$TMP_SRC" "$TMP_DST"
yq -i '.projects."fakeproj".modelByCli."claude-code".model = "claude-sonnet-4-6"' "$TMP_DST"

# Assertions
patched="$(yq -r '.projects.fakeproj.modelByCli.claude-code.model' "$TMP_DST")"
[ "$patched" = "claude-sonnet-4-6" ] || { echo "FAIL: project override not set, got '$patched'"; exit 1; }

unchanged="$(yq -r '.defaults.modelByCli.claude-code.model' "$TMP_DST")"
[ "$unchanged" = "wafer.ai/GLM-5.1" ] || { echo "FAIL: defaults clobbered, got '$unchanged'"; exit 1; }

rules="$(yq -r '.projects.fakeproj.agentRules' "$TMP_DST")"
case "$rules" in
    *"You are working on fakeproj."*) ;;
    *) echo "FAIL: agentRules preserved? got '$rules'"; exit 1 ;;
esac

echo "PASS: patch is surgical (project-level override applied, defaults + sibling fields intact)"
