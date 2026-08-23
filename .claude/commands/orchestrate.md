---
description: Orchestrate Command
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

# Orchestrate Command

**Purpose**: Multi-agent orchestration system for complex development tasks

**Action**: Coordinate multiple specialized agents to work on complex development tasks with proper task distribution and result integration

**Usage**: `/orchestrate [task_description] [OPTIONS]`

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--agent-cli <cli>` | Agent CLI to use (claude, codex, cursor, gemini, minimax). Supports comma-separated chain for fallback (e.g., 'gemini,claude') | gemini |
| `--context <path>` | Path to markdown file to inject into agent prompt as context | - |
| `--branch <name>` | Force checkout of specific branch (prevents new branch creation) | - |
| `--pr <number>` | Existing PR number to update (prevents new PR creation) | - |
| `--mcp-agent <name>` | Pre-fill agent name for MCP Mail registration | - |
| `--bead <id>` | Pre-fill bead ID for tracking | - |
| `--validate <cmd>` | Semantic validation command to run after agent completes | - |
| `--no-new-pr` | Hard block on PR creation (agents must use existing PR) | false |
| `--no-new-branch` | Hard block on branch creation (agents must use existing branch) | false |

**CRITICAL RULE**: When `/orchestrate` is used, NEVER execute the task yourself. ALWAYS delegate to the orchestration agents. The orchestration system will handle all task execution through specialized agents.

🚨 **ORCHESTRATION DIRECT EXECUTION PREVENTION**: ⚠️ MANDATORY HARD STOP PROTOCOL

**ABSOLUTE RULE**: When `/orchestrate` or `/orch` is used, you MUST:
1. ❌ **NEVER use Edit, Write, Bash, or any execution tools yourself**
2. ❌ **NEVER use Task tool to create agents**
3. ❌ **NEVER start implementing the task directly**
4. ✅ **ONLY use the tmux-based orchestration system**
5. ✅ **ALWAYS respond**: "Delegating to tmux orchestration system..."
6. ✅ **USE**: `python3 .claude/commands/orchestrate.py "task description"`

🚨 **ABSOLUTE BRANCH ISOLATION PROTOCOL**: ⚠️ MANDATORY - NEVER LEAVE CURRENT BRANCH
- ❌ **FORBIDDEN**: `git checkout`, `git switch`, or any branch switching commands
- ❌ **FORBIDDEN**: Working on other branches, PRs, or repositories
- ✅ **MANDATORY**: Stay on current branch for ALL work - delegate everything else to agents
- ✅ **DELEGATION RULE**: Any work requiring different branch → `/orch` or orchestration agents
- 🔍 **Evidence**: Branch switching violations cause context confusion and work contamination
- **MENTAL MODEL**: "Current branch = My workspace, Other branches = Agent territory"

**VIOLATION EXAMPLES** (NEVER DO THESE):
- ❌ Using Task tool to create agents (Task tool ≠ orchestration system)
- ❌ Writing code to solve the problem yourself
- ❌ Running commands to implement features yourself
- ❌ Editing files to fix bugs yourself
- ❌ **BRANCH VIOLATIONS**: `git checkout other-branch`, `git switch main`
- ❌ **BRANCH VIOLATIONS**: Working on different PRs or repositories directly

**CORRECT BEHAVIOR**:
- ✅ Run orchestration command: `python3 .claude/commands/orchestrate.py "Fix bug X"`
- ✅ Monitor agent progress: `tmux attach -t agent-name`
- ✅ Check results: `/orch status`
- ✅ **BRANCH ISOLATION**: Stay on current branch, delegate other branch work to agents
- ✅ **BRANCH ISOLATION**: `/orch "Work on PR #123"` instead of `git checkout pr-branch`

- **Hard Stop Pattern**: `/orchestrate` or `/orch` prefix detected → immediate tmux agent delegation
- **User Urgency Safeguard**: "just decide", "just start", "you choose" are guidance for TMUX AGENTS, NOT permission for direct execution
- **Mental Model**: `/orch` = "create tmux agents to do this", NEVER "I should implement this directly"
- **Zero Exception Rule**: Orchestration commands ALWAYS trigger tmux agent creation regardless of user urgency
- **Behavioral Firewall**: Automatic "Delegating to tmux orchestration system..." response followed by tmux agent creation
- **Pattern Recognition**: Operational command classification → mandatory tmux protocol enforcement
- 🔍 **Evidence**: Session violation prevented by this protocol (see CLAUDE.md)
- **CRITICAL**: Task tool ≠ orchestration system. Orchestration = tmux agents only.

**🚨 CRITICAL BRANCH PROTECTION RULE**: When monitoring orchestration agents:
- ❌ **NEVER switch branches** without explicit user permission
- ❌ **NEVER leave the current branch** to investigate agent work
- ✅ **ALWAYS stay on your current branch** while agents work in their isolated workspaces
- ✅ **Request explicit approval** before any branch switch: "May I switch to branch X? Please approve with 'approve [number]'"
- 🔒 **Branch Context**: Your branch = your workspace. Agent branches = their workspaces. Never mix them!
- ⚠️ **Violation Impact**: Switching branches disrupts user's work context and can cause lost changes

**Implementation**:
- **Python Script**: `python3 .claude/commands/orchestrate.py [task_description]`
- **Shell Wrapper**: `./claude_command_scripts/orchestrate.sh` (if available)
- **Tmux Agents**: Creates real tmux sessions with Claude Code CLI agents
- **NOT Task Tool**: Task tool is for different purposes, orchestration uses tmux system
- **System Check**: ALWAYS checks system status first before executing tasks

**Features**:
- **Real tmux sessions**: Creates separate terminal sessions for each agent
- **Claude Code CLI integration**: Full access to all slash commands in each session
- **Task delegation**: Smart routing based on task content (UI→frontend, API→backend, etc.)
- **Progress monitoring**: Real-time status via `/orchestrate What's the status?`
- **Agent collaboration**: Direct connection to agent sessions for collaboration
- **Natural language**: Understands commands like "Build user authentication urgently"
- **Priority handling**: Recognizes urgent, ASAP, critical keywords
- **Agent reuse optimization**: Idle agents reused before creating new ones (50-80% efficiency gains)
- **Individual agent per task**: Each task gets dedicated agent with complete isolation
- **Resource efficiency**: Strategic reuse while maintaining task isolation

**System Requirements**:
- Redis server running (for coordination)
- Orchestration system started: `./orchestration/start_system.sh start`
- Or started via: `./claude_start.sh` (auto-starts orchestration when not running git hooks)

**Automatic Behavior**:
- `/orch` commands automatically check if the orchestration system is running
- If not running, attempts to start it before executing the task
- Shows clear status messages about system state
- **Memory Integration**: Automatically queries Memory MCP for:
  - Past mistakes and learnings related to the task
  - Previous similar orchestration patterns
  - Known issues and their solutions
  - This helps agents avoid repeating past errors
  - **Note**: If Memory MCP is unavailable, tasks proceed without memory context (non-blocking)

**Agent Types**:
- **Frontend Agent**: UI, React components, styling (`frontend-agent`)
- **Backend Agent**: APIs, database, server logic (`backend-agent`)
- **Testing Agent**: Tests, QA, validation (`testing-agent`)
- **Opus Master**: Coordination and oversight (`opus-master`)
- **Task Agents**: Dynamic agents with reuse optimization (`task-agent-*`)

**Examples**:
```bash
# Basic usage (defaults to gemini CLI)
/orchestrate implement user authentication with tests and documentation
/orchestrate refactor database layer with migration scripts
/orchestrate add new feature with full test coverage and UI updates
/orchestrate optimize performance across frontend and backend

# Specify agent CLI
/orchestrate --agent-cli claude "Fix security vulnerability in auth module"
/orchestrate --agent-cli codex "Generate test suite for API endpoints"

# CLI chain with fallback (tries gemini first, falls back to claude)
/orchestrate --agent-cli gemini,claude "Implement complex feature X"

# Update existing PR on specific branch
/orchestrate --branch feature-x --pr 123 "Add more tests and fix review comments"

# With context file injection
/orchestrate --context ./design-doc.md "Implement according to the design spec"

# With validation command
/orchestrate --validate "./run_tests.sh" "Fix the failing tests"

# Hard blocks (prevent new PR/branch creation)
/orchestrate --no-new-pr --branch main "Update documentation only"
/orchestrate --no-new-branch --branch feature-y "Continue work on feature-y"

# Combined options
/orchestrate --agent-cli gemini --context ./spec.md --pr 456 --validate "pytest" "Implement feature from spec"

# Status and monitoring
/orchestrate What's the status?
/orchestrate connect to sonnet 1
/orchestrate monitor agents
/orchestrate help me with connections
```

**Natural Language Commands**:
- **Task Delegation**: "Build X", "Create Y", "Implement Z urgently"
- **System Monitoring**: "What's the status?", "monitor agents", "How's the progress?"
- **Agent Connection**: "connect to sonnet 1", "collaborate with sonnet-2"
- **Help**: "help me with connections", "show me connection options"

**Quick Commands**:
- **Start system**: `./orchestration/start_system.sh start`
- **Check status**: `/orchestrate What's the status?`
- **Connect to frontend**: `tmux attach -t frontend-agent`
- **Connect to backend**: `tmux attach -t backend-agent`
- **Connect to testing**: `tmux attach -t testing-agent`
- **Monitor all**: `tmux list-sessions | grep -E '(frontend|backend|testing|opus)'`

## Important Notes

- **Working Directory**: The orchestration system creates agent workspaces as subdirectories. Always ensure you're in the main project directory when running orchestration commands, not inside an agent workspace
- **Monitoring**: Use `tmux attach -t [agent-name]` to watch agent progress
- **Results**: Check `/tmp/orchestration_results/` for agent completion status
- **Cleanup**: Run `orchestration/cleanup_agents.sh` to remove completed agent worktrees
- **Branch Context**: Agents inherit from your current branch, so their changes build on your work

## 🚨 AGENT TASK PATIENCE

Agent tasks require TIME - wait for completion before ANY declaration:
- ⚠️ Orchestrate agents work autonomously and may take 5-10+ minutes
- ❌ NEVER declare success OR failure without checking completion status
- ❌ NEVER make declarations based on quick checks (10s, 30s, 60s too soon)
- ✅ ALWAYS check tmux output for "Task completed" message
- ✅ ALWAYS verify PR creation in agent output before declaring results
- 🔍 Evidence: Agent task-agent-5819 succeeded with PR #851 after 270 seconds
- 📋 Proper verification: tmux output → "Task completed" → PR URL → verify PR exists
- ⚠️ Status warnings like "agent may still be working" mean WAIT, don't declare

## 🔄 PR UPDATE MODE vs CREATE MODE

**CRITICAL**: Agents must detect whether to UPDATE existing PRs or CREATE new ones:

### 🔍 PR Update Pattern Detection

The orchestration system recognizes these patterns as PR UPDATE requests:
- **Explicit PR references**: "fix PR #123", "update pull request #456", "adjust PR #789"
- **Contextual PR references**: "adjust the PR", "fix the pull request", "update that PR"
- **Action words with PR**: "modify", "fix", "adjust", "update", "enhance", "improve" + "PR/pull request"
- **Continuation phrases**: "continue with PR", "add to the PR", "the PR needs", "PR should also"

### 🆕 PR Create Patterns (Default)

These patterns trigger NEW PR creation:
- **No PR mentioned**: "implement feature X", "fix bug Y", "create Z"
- **Explicit new work**: "create new PR for", "start fresh PR", "new pull request"
- **Independent tasks**: Tasks that don't reference existing work

### 📢 User Feedback

Orchestration will clearly indicate the detected mode:
```
🔍 Detected PR context: #950 - Agent will UPDATE existing PR
   Branch: feature-xyz
   Status: OPEN
```
OR
```
🆕 No PR context detected - Agent will create NEW PR
   New branch will be created from main
```

### ⚠️ Edge Cases

- **Merged/Closed PRs**: Agent will warn and ask for confirmation
- **Multiple PR mentions**: Agent will ask which PR to update
- **Ambiguous "the PR"**: System will show recent PRs and ask for selection
- **Branch conflicts**: Agent will attempt rebase/merge with clear messaging

## 🔄 Agent Reuse Optimization

**🚨 CRITICAL: Agent Reuse Architecture for Efficiency**

The orchestration system implements intelligent agent reuse to optimize resource utilization while maintaining task isolation.

### **Agent Reuse Strategy**:

1. **Check for Idle Agents**: Before creating new agents, check for idle existing agents
2. **Reuse When Available**: Reuse idle agents for new tasks (50-80% efficiency gains)
3. **Create When Needed**: Create new agents only when no idle agents available
4. **Maintain Isolation**: Each task still gets dedicated agent execution
5. **Resource Optimization**: Strategic reuse without compromising task quality

### **Individual Agent Per Task Architecture**:

- ✅ **Parallel Execution**: All tasks processed simultaneously (one agent per task)
- ✅ **Resource Efficiency**: Idle agents reused before creating new ones (50-80% token savings)
- ✅ **Complete Isolation**: Each agent has dedicated workspace and task focus
- ✅ **No Task Conflicts**: Worktrees and separate sessions prevent collisions
- ✅ **100% Coverage**: Every task gets individual agent (no partial processing)
- ✅ **Scalable**: Handle 10+ tasks with optimal resource utilization
- ✅ **Fault Tolerant**: One agent failure doesn't affect others
- ✅ **Real-time Visibility**: Monitor all individual agents' progress

### **Agent Lifecycle Management**:

```bash

# CORRECT: Agent reuse optimization workflow

for TASK in $TASK_LIST; do
    /orchestrate "$TASK with agent reuse preference"
done

# Each task execution with reuse:

# 1. Check for idle agents first

# 2. Reuse existing idle agent if available

# 3. Create new agent only if no idle agents

# 4. Execute task in complete isolation

# 5. Mark agent as idle after completion (available for reuse)

```

### **Performance Benefits**:

- **Token Savings**: 50-80% reduction in agent creation overhead
- **Resource Efficiency**: Better utilization of active agents
- **Faster Execution**: Reduced agent startup time through reuse
- **Cost Optimization**: Lower API costs through strategic reuse
- **Scalability**: Handle more concurrent tasks with same resources

### **Safety Guarantees**:

- ❌ **No Task Contamination**: Each task gets clean agent state
- ❌ **No Shared Context**: Agents don't share previous task context
- ✅ **Fresh Workspace**: Each task gets isolated worktree regardless of reuse
- ✅ **Complete Independence**: Task execution is fully independent
- ✅ **Error Isolation**: Agent reuse doesn't propagate errors between tasks
