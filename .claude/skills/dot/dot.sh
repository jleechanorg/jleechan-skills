#!/usr/bin/env bash
# Entry point kept for callers of the skill root; the implementation lives in scripts/.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/dot.sh" "$@"
