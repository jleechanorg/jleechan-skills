#!/usr/bin/env bash
# validate-cleanup-script.sh — Validates a generated launchd cleanup script
# Usage: validate-cleanup-script.sh <script_path>
# Exit 0 if all checks pass, exit 1 with error message(s) if any fail.
set -euo pipefail

SCRIPT_PATH="${1:-}"
ERRORS=()

if [[ -z "$SCRIPT_PATH" ]]; then
  echo "Usage: validate-cleanup-script.sh <script_path>" >&2
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "ERROR: File not found: $SCRIPT_PATH" >&2
  exit 1
fi

# Check 1: Executable bit
if [[ ! -x "$SCRIPT_PATH" ]]; then
  ERRORS+=("FAIL [executable]: Script is not executable. Run: chmod +x $SCRIPT_PATH")
fi

# Check 2: --dry-run flag present
if ! /usr/bin/grep -q -- '--dry-run' "$SCRIPT_PATH"; then
  ERRORS+=("FAIL [dry-run]: Script does not contain --dry-run flag handling. Every cleanup script must support --dry-run.")
fi

# Check 3: set -euo pipefail present
if ! /usr/bin/grep -q 'set -euo pipefail' "$SCRIPT_PATH"; then
  ERRORS+=("FAIL [set-euo]: Script does not contain 'set -euo pipefail'. Required for safety.")
fi

# Check 4: No hardcoded /Users/ paths (use $HOME instead)
if /usr/bin/grep -qE '"/Users/[^$]|'"'"'/Users/[^$]' "$SCRIPT_PATH" 2>/dev/null; then
  HARDCODED=$(/usr/bin/grep -nE '"/Users/[^$]|'"'"'/Users/[^$]' "$SCRIPT_PATH" || true)
  ERRORS+=("FAIL [hardcoded-path]: Found hardcoded /Users/ path(s). Use \$HOME instead:
$HARDCODED")
fi

# Check 5: No homebrew/non-system tools
FORBIDDEN_TOOLS=(brew nvm npm node pip pip3 rtk)
for tool in "${FORBIDDEN_TOOLS[@]}"; do
  # Match tool as standalone word in a command position (not inside a comment or string mentioning it)
  if /usr/bin/grep -qE "^[^#]*\b${tool}\b" "$SCRIPT_PATH" 2>/dev/null; then
    LINES=$(/usr/bin/grep -nE "^[^#]*\b${tool}\b" "$SCRIPT_PATH" || true)
    ERRORS+=("FAIL [system-tools]: Found use of non-system tool '${tool}'. launchd PATH is /usr/bin:/bin only. Lines:
$LINES")
  fi
done

# Check 6: External commands use absolute paths (warn only for common violations)
# Check for bare 'find', 'rm', 'wc', 'du' without leading /
if /usr/bin/grep -qE '^[^#/]*[[:space:]](find|rm -rf|rm -r|wc |du |stat )[^/]' "$SCRIPT_PATH" 2>/dev/null; then
  BARE_CMDS=$(/usr/bin/grep -nE '^[^#/]*[[:space:]](find|rm -rf|rm -r|wc |du |stat )[^/]' "$SCRIPT_PATH" || true)
  ERRORS+=("FAIL [absolute-paths]: External commands should use absolute paths (/usr/bin/find, /bin/rm, etc.) for launchd compatibility. Bare commands found:
$BARE_CMDS")
fi

# Report results
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  echo "PASS: $(basename "$SCRIPT_PATH") passes all validation checks (${#ERRORS[@]} errors)"
  exit 0
else
  echo "FAIL: $(basename "$SCRIPT_PATH") failed ${#ERRORS[@]} check(s):" >&2
  for err in "${ERRORS[@]}"; do
    echo "  $err" >&2
  done
  exit 1
fi
