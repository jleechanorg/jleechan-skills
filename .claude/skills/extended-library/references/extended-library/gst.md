---
description: Alias for /gstatus command
type: git
execution_mode: immediate
allowed-tools: Bash
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute gstatus.py directly

**Action Steps:**
1. Locate and execute gstatus.py from .claude/commands/ directory
2. Display the complete GitHub status output to the user

## Implementation

Use the Bash tool to execute gstatus.py with proper path resolution:

```bash
# Resolve gstatus.py location using git root or fallback paths
if git_root=$(git rev-parse --show-toplevel 2>/dev/null); then
    script_path="$git_root/.claude/commands/gstatus.py"
    if [ -f "$script_path" ]; then
        python3 "$script_path" "$@"
    elif [ -f "$HOME/.claude/commands/gstatus.py" ]; then
        python3 "$HOME/.claude/commands/gstatus.py" "$@"
    else
        echo "❌ ERROR: Unable to locate gstatus.py"
        echo "  Checked: git root/.claude/commands/ and ~/.claude/commands/"
        exit 1
    fi
elif [ -f "$HOME/.claude/commands/gstatus.py" ]; then
    python3 "$HOME/.claude/commands/gstatus.py" "$@"
else
    echo "❌ ERROR: Unable to locate gstatus.py"
    echo "  Checked: git root/.claude/commands/ and ~/.claude/commands/"
    exit 1
fi
```

This provides comprehensive PR status including:
- Current branch and PR information
- CI/CD check status
- File changes summary
- Merge conflict detection

**Path Resolution**: Works from any directory within a git repo or falls back to ~/.claude global installation
