#!/bin/bash
# Anti-Root Files Hook for Claude Code
# Prevents adding new files directly to project root directory
# Files should be organized in proper subdirectories

# Find project root by looking for .git directory
find_project_root() {
    local dir="$PWD"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/.git" ]] || [[ -f "$dir/CLAUDE.md" ]]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    echo "$PWD"  # Fallback to current directory
}

PROJECT_ROOT=$(find_project_root)
LOG_FILE="/tmp/claude_root_files_log.txt"

# Read JSON input from stdin
INPUT=$(cat)

# Extract file path from tool input
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check Write operations (new file creation)
if [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

# Skip if no file path
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Convert file path to absolute path if it's relative
if [[ "$FILE_PATH" = /* ]]; then
    ABSOLUTE_FILE_PATH="$FILE_PATH"
else
    ABSOLUTE_FILE_PATH="$PROJECT_ROOT/$FILE_PATH"
fi

# Get relative path from project root
RELATIVE_PATH=$(realpath --relative-to="$PROJECT_ROOT" "$ABSOLUTE_FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

# Get the directory part of the relative path
DIR_PATH=$(dirname "$RELATIVE_PATH")
FILENAME=$(basename "$RELATIVE_PATH")

# Allowed root files (whitelist)
ALLOWED_ROOT_FILES=(
    "README.md"
    "CLAUDE.md"
    "LICENSE"
    "requirements.txt"
    "package.json"
    "Dockerfile"
    "docker-compose.yml"
    ".gitignore"
    ".env.example"
    "Makefile"
    "setup.py"
    "pyproject.toml"
    "run_tests.sh"
    "deploy.sh"
    "integrate.sh"
)

# Check if it's a root-level file (no subdirectory)
if [[ "$DIR_PATH" == "." ]] || [[ "$RELATIVE_PATH" == "$FILENAME" ]]; then
    # Check if file is in allowed list
    IS_ALLOWED=false
    for allowed in "${ALLOWED_ROOT_FILES[@]}"; do
        if [[ "$FILENAME" == "$allowed" ]]; then
            IS_ALLOWED=true
            break
        fi
    done

    if [ "$IS_ALLOWED" = false ]; then
        # Block the operation
        cat <<EOF
{
  "decision": "block",
  "reason": "${RED}🚨 ROOT FILE POLLUTION DETECTED${NC}\\n\\nFile: $FILENAME\\nLocation: Project root\\n\\n${YELLOW}Files should be organized in proper directories:${NC}\\n• Documentation → docs/\\n• Tests → tests/ or testing_*/\\n• Scripts → scripts/ or .claude/scripts/\\n• Configs → configs/ or .config/\\n• Hooks → hooks/\\n• Examples → examples/\\n• Temporary → tmp/ or temp/\\n\\n${GREEN}Allowed root files:${NC} $(printf '%s, ' \"${ALLOWED_ROOT_FILES[@]}\" | sed 's/, $//')\\n\\nPlease move this file to an appropriate subdirectory.",
  "suppressOutput": false
}
EOF

        # Log the violation
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Root file blocked: $FILENAME" >> "$LOG_FILE"

        exit 0  # Don't exit with error, just block via decision
    fi
fi

# Allow the operation
echo '{"decision": "approve", "suppressOutput": true}'
