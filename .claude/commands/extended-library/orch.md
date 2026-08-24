---
description: /orch - Alias for /orchestrate
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

# /orch - Alias for /orchestrate

**This is an alias**: See `/orchestrate` for full documentation.

**Usage**: `/orch [task_description] [OPTIONS]`

**Options** (default: --agent-cli gemini):
| Option | Description | Default |
|--------|-------------|---------|
| `--agent-cli <cli>` | Agent CLI to use (claude, codex, cursor, gemini, minimax). Supports chain (e.g., 'gemini,claude') | gemini |
| `--context <path>` | Path to markdown file to inject into agent prompt | - |
| `--branch <name>` | Force checkout of specific branch | - |
| `--pr <number>` | Existing PR number to update | - |
| `--mcp-agent <name>` | Pre-fill agent name for MCP Mail | - |
| `--bead <id>` | Pre-fill bead ID for tracking | - |
| `--validate <cmd>` | Validation command to run after completion | - |
| `--no-new-pr` | Block new PR creation | false |
| `--no-new-branch` | Block new branch creation | false |

**Examples**:
```bash
# Default: uses gemini CLI
/orch "Implement user authentication"

# Use Claude CLI instead
/orch --agent-cli claude "Fix the login bug"

# Use CLI chain with fallback
/orch --agent-cli gemini,claude "Build feature X"

# Update existing PR on specific branch
/orch --branch feature-x --pr 123 "Add tests for feature X"

# With context file and validation
/orch --context ./context.md --validate "./run_tests.sh" "Implement API endpoint"
```

**Full documentation**: [orchestrate.md](orchestrate.md)
