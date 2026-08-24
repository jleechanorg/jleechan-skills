---
description: Test Server Command
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

# Test Server Command

**Purpose**: Manage test servers for branches

**Action**: Start, stop, or list test servers

**Usage**: `/testserver [action] [branch]`

**Implementation**:
- `start [branch]` - Start test server for branch (defaults to current branch)
- `stop [branch]` - Stop test server for branch (defaults to current branch)
- `list` - List all running test servers
- `cleanup` - Stop all test servers

**Examples**:
- `/testserver start` - Start server for current branch
- `/testserver start feature-auth` - Start server for feature-auth branch
- `/testserver stop` - Stop server for current branch
- `/testserver list` - Show all running servers
- `/testserver cleanup` - Stop all servers

**Features**:
- Automatic port allocation (8081, 8082, 8083, etc.)
- Branch-specific logging
- Process management with PID tracking
- Conflict detection and resolution
- Cleanup of stale processes

**Integration**:
- `/push` automatically starts server for current branch
- `/integrate` automatically stops server for current branch
- Servers persist across development sessions
- Logs stored in `/tmp/$PROJECT_NAME_logs/[branch].log`
