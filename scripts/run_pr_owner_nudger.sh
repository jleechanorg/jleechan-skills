#!/bin/bash
set -eo pipefail

for profile in "$HOME/.bash_profile" "$HOME/.bashrc"; do
  if [[ -f "$profile" ]]; then
    set +u
    # shellcheck source=/dev/null
    source "$profile" >/dev/null 2>&1 || true
    break
  fi
done
set -u
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"

unset GITHUB_TOKEN GH_TOKEN
if command -v gh >/dev/null && GH_TOKEN="$(gh auth token 2>/dev/null)"; then
  export GH_TOKEN
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$repo_root/scripts/pr_owner_nudger.py" "$@"
