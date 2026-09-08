---
description: Integration Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# Integration Command

**Purpose**: Create fresh branch from main and cleanup test servers

**Action**: Conditionally stop test server → Run the global `integrate.sh` script → Prepare fresh branch

**Canonical implementation**:

```bash
GLOBAL_INTEGRATE_SCRIPT="$HOME/.claude/plugins/marketplaces/claude-commands-marketplace/scripts/integrate.sh"
test -x "$GLOBAL_INTEGRATE_SCRIPT" || {
  echo "Missing executable global integrate script: $GLOBAL_INTEGRATE_SCRIPT" >&2
  exit 1
}
bash "$GLOBAL_INTEGRATE_SCRIPT" "$@"
```

Run this script from the target repository working directory. It discovers the
current Git root itself. Do not require, copy, or invoke a repository-local
`./integrate.sh`. Forward the arguments supplied to `/integrate` unchanged; with
no arguments, invoke the global script with no trailing arguments.

**Usage**:
- `/integrate` - Creates dev{timestamp} branch
- `/integrate [branch-name]` - Creates branch with custom name
- `/integrate --force` - Override safety checks

**Examples**:
- `/integrate` - Creates dev1752251680 branch
- `/integrate newb` - Creates newb branch
- `/integrate feature/my-feature` - Creates feature/my-feature branch
- `/integrate fix/bug-123 --force` - Creates fix/bug-123 branch, overriding checks

**Enhanced Implementation**:
- **Auto-Learning**: Automatically trigger `/learn` to capture insights from completed work
- **Factory Evolution**: Automatically trigger `/factory-evolve --taxonomy` to surface reviewer-node gaps from recent work (structural G1+G2 check only — fast, no history search)
- Stop test server for current branch if manager is present and executable (skipped on main or detached HEAD)
- Execute the canonical global script with the optional branch name and flags
- Creates new branch from latest main
- Prepares fresh starting branch for new features
- Pulls latest changes from main
- Sets up custom or timestamp-based branch naming
- Conditionally releases branch-specific test server resources if manager is configured and succeeds
- **Learning Documentation**: Capture and document patterns from previous branch work

**Test Server Integration**:
- Conditionally stops test server for current branch before checkout/branch/stash (skipped on main or detached HEAD)
- Absent test server manager: explicitly SKIPPED and integration continues
- Existing nonexecutable manager or failing manager: reports error including original stderr and exits nonzero before checkout/branch/stash
- Successful stop: reports only that manager returned success (not proven orphan absence)
- Use `/push` to start server for new branch
