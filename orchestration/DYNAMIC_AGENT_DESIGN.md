# Dynamic Agent Orchestration Design

## Overview

This document describes the transformation of the orchestration system from static, predefined agent types to a pure dynamic agent system where agents are created on-demand based on natural language task descriptions.

## Architecture Transformation

### Before: Static Agent System
```
├── frontend-agent (predefined)
├── backend-agent (predefined)
├── testing-agent (predefined)
└── opus-master (coordinator)
```

### After: Dynamic Agent System
```
├── opus-master (coordinator - optional)
└── task-agent-* (created dynamically per task)
```

## Key Design Principles

### 1. Single Entry Point
- **Command**: `python3 orchestration/orchestrate_unified.py "task description"`
- **No predefined agent types** - agents understand tasks naturally
- **Dynamic naming**: `task-agent-{timestamp}` for uniqueness

### 2. Task-Based Agent Creation
```python
# User provides natural language task
"Fix all failing tests in the authentication module"

# System creates appropriate agent
task-agent-1234:
  - Understands task context
  - Has full development capabilities
  - Works in isolated environment
  - Self-terminates after PR creation
```

### 3. Isolated Work Environment
- Each agent gets fresh git worktree from main
- No cross-contamination between tasks
- Clean PR creation per task

### 4. Self-Contained Workflow
Each agent:
1. Starts with task description
2. Works in isolated tmux session
3. Commits to fresh branch
4. Creates PR automatically
5. Terminates cleanly

## Implementation Details

### Core Components

1. **orchestrate_unified.py**
   - Single entry point for all agent creation
   - Handles task parsing and agent spawning
   - Manages worktree creation

2. **task_dispatcher.py**
   - Dynamic agent capability discovery
   - Load balancing across agents
   - No hardcoded agent mappings

3. **start_system.sh**
   - Minimal setup (directories, Redis optional)
   - No static agent startup
   - Only starts opus-master if requested

### Agent Lifecycle

```
User Task → orchestrate_unified.py → Create Worktree → Spawn Agent → Execute Task → Create PR → Terminate
```

### Detailed tmux-Based Implementation

The lifecycle is implemented through tmux sessions that provide process isolation and real-time monitoring:

**Phase 1: Task Submission**
```python
# User types: /orch "Fix all failing tests"
# .claude/commands/orchestrate.md triggers:
orchestrate_unified.py orchestrate(task_description)
```

**Phase 2: Agent Specification**
```python
# task_dispatcher.py analyzes task and creates agent spec
agent_spec = {
    "name": "task-agent-fix-tests-1234",  # Unique name from task content
    "type": "development",
    "focus": "Fix all failing tests",
    "cli": "claude",  # or "codex" based on detection
    "prompt": "...",  # Full task prompt with completion instructions
    "workspace_config": {...}  # Optional custom workspace
}
```

**Phase 3: Workspace Isolation**
```python
# Create git worktree in isolated directory
worktree_path = "~/projects/orch_your-project.com/task-agent-fix-tests-1234/"
branch_name = "task-agent-fix-tests-1234-work"

subprocess.run([
    "git", "worktree", "add",
    "-b", branch_name,  # Create new branch
    worktree_path,      # At this location
    "main"              # From main branch
])
```

**Phase 4: Prompt Engineering**
```python
# Write comprehensive prompt to file
prompt_file = "/tmp/agent_prompt_task-agent-fix-tests-1234.txt"

prompt_content = f"""
Task: {task_description}

Agent Configuration:
- Name: {agent_name}
- Working Directory: {worktree_path}
- Branch: {branch_name} (fresh from main)

🚨 MANDATORY COMPLETION STEPS:
1. Complete the assigned task
2. Commit changes with proper attribution
3. Push branch to origin
4. Create PR using gh pr create
5. Write completion report to /tmp/orchestration_results/

🛑 EXIT CRITERIA:
- Task completed and tested
- All changes committed
- Branch pushed to origin
- PR created and verified
- Completion report written
"""

with open(prompt_file, "w") as f:
    f.write(prompt_content)
```

**Phase 5: Bash Script Generation**
```python
# Create execution script with error handling
bash_script = f"""
#!/bin/bash
# Signal handlers for graceful shutdown
trap 'echo "Agent interrupted" | tee -a {log_file}; exit 130' SIGINT
trap 'echo "Agent terminated" | tee -a {log_file}; exit 143' SIGTERM

# Log startup
echo "[$(date)] Starting agent {agent_name}" | tee -a {log_file}
echo "[$(date)] Working directory: {worktree_path}" | tee -a {log_file}

# Execute CLI based on profile
{cli_command} 2>&1 | tee -a {log_file}
CLI_EXIT=$?

# Log completion
if [ $CLI_EXIT -eq 0 ]; then
    echo "[$(date)] Agent completed successfully" | tee -a {log_file}
    echo '{{"agent": "{agent_name}", "status": "completed"}}' > {result_file}
else
    echo "[$(date)] Agent failed with exit code $CLI_EXIT" | tee -a {log_file}
    echo '{{"agent": "{agent_name}", "status": "failed", "exit_code": $CLI_EXIT}}' > {result_file}
fi

# Keep session alive for monitoring (1 hour)
echo "[$(date)] Session remains active for 1 hour" | tee -a {log_file}
sleep 3600
"""

script_path = Path(f"/tmp/{agent_name}_run.sh")
script_path.write_text(bash_script)
os.chmod(script_path, 0o700)
```

**Phase 6: tmux Session Creation**
```python
# Create detached tmux session running the bash script
tmux_cmd = [
    "tmux",
    "new-session",
    "-d",                    # Detached (background)
    "-s", agent_name,        # Session name for identification
    "-c", worktree_path,     # Working directory
    "bash", str(script_path) # Execute our script
]

subprocess.run(tmux_cmd, check=True)
print(f"✅ Created {agent_name} in tmux session")
```

**Phase 7: CLI Invocation (Inside tmux)**

For **Claude CLI**:
```bash
# Inside tmux session, bash script executes:
claude --model sonnet \
    -p @/tmp/agent_prompt_task-agent-fix-tests-1234.txt \
    --output-format stream-json \
    --verbose \
    --dangerously-skip-permissions \
    2>&1 | tee -a /tmp/orchestration_logs/task-agent-fix-tests-1234.log
```

For **Codex CLI**:
```bash
# Inside tmux session, bash script executes:
codex exec --yolo < /tmp/agent_prompt_task-agent-fix-tests-1234.txt \
    2>&1 | tee -a /tmp/orchestration_logs/task-agent-fix-tests-1234.log
```

**Phase 8: Agent Execution**
```
Inside tmux session, the LLM agent:
1. Reads the comprehensive prompt
2. Understands the task and exit criteria
3. Works in the isolated git worktree
4. Makes code changes
5. Runs tests
6. Commits with proper attribution
7. Pushes branch to origin
8. Creates PR using gh CLI
9. Writes completion report
10. Exits (bash script keeps session alive)
```

**Phase 9: Monitoring Loop**
```python
# agent_monitor.py runs every 2 minutes
class AgentMonitor:
    def ping_agent(self, agent_name: str) -> dict:
        status = {}

        # Check tmux session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", agent_name],
            check=False
        )
        status["tmux_active"] = (result.returncode == 0)

        # Capture recent output
        if status["tmux_active"]:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", agent_name, "-p"],
                capture_output=True, text=True
            )
            status["recent_output"] = result.stdout.split('\n')[-5:]

        # Check workspace modifications
        workspace_path = f"~/projects/orch_your-project.com/{agent_name}/"
        if os.path.exists(workspace_path):
            stat = os.stat(workspace_path)
            status["last_modified"] = datetime.fromtimestamp(stat.st_mtime)

        # Check completion status
        result_file = f"/tmp/orchestration_results/{agent_name}_results.json"
        if os.path.exists(result_file):
            with open(result_file) as f:
                status["result"] = json.load(f)

        # Detect stuck agents (no activity for 10+ minutes)
        if status.get("last_modified"):
            time_since = datetime.now() - status["last_modified"]
            if time_since > timedelta(minutes=10):
                status["stuck"] = True
                # Auto-restart for converge agents
                if "converge" in agent_name:
                    self.restart_agent(agent_name)

        return status
```

**Phase 10: Completion and Cleanup**
```python
# Agent writes result file
result = {
    "agent": "task-agent-fix-tests-1234",
    "status": "completed",
    "pr_url": "https://github.com/user/repo/pull/123",
    "branch": "task-agent-fix-tests-1234-work",
    "completion_time": "2025-01-15T10:30:00Z"
}

# Session stays alive for 1 hour for debugging
# After 1 hour, script exits and tmux session closes

# Cleanup on next orchestration run:
orchestrate_unified.py._cleanup_stale_orchestration_state()
# - Removes old prompt files (>5 minutes old)
# - Kills completed tmux sessions
# - Cleans up result files
```

### Why tmux?

**Alternative approaches considered:**

1. **Direct subprocess**: No monitoring, can't inspect progress
2. **Screen**: Less widely available, harder to script
3. **Docker containers**: Overkill, adds complexity
4. **Background processes**: Hard to monitor, no visual inspection

**tmux advantages:**

- **Visual debugging**: `tmux attach -t agent-name` lets you watch agents work
- **Process isolation**: Each agent in own session, no interference
- **Persistence**: Survives terminal disconnects
- **Mature**: Battle-tested, available everywhere
- **Simple**: No additional dependencies beyond tmux binary
- **Monitoring friendly**: Easy to capture output, check status
- **Clean lifecycle**: Sessions auto-close after timeout

## Benefits

1. **Simplicity**: One command creates any agent needed
2. **Flexibility**: Agents adapt to task requirements
3. **Isolation**: Each task gets clean environment
4. **Scalability**: No artificial agent type limits
5. **Maintainability**: No static configuration to update

## Usage Examples

```bash
# Any development task
python3 orchestration/orchestrate_unified.py "Add user authentication to the API"

# Testing tasks
python3 orchestration/orchestrate_unified.py "Write integration tests for payment system"

# Bug fixes
python3 orchestration/orchestrate_unified.py "Fix memory leak in image processing"

# Infrastructure
python3 orchestration/orchestrate_unified.py "Set up CI/CD pipeline for staging"
```

## Status Coordination

Currently uses file-based coordination:
- `/tmp/orchestration_results/` for agent results
- `tasks/shared_status.txt` for status updates

Future enhancement: Optional Redis layer for real-time updates while maintaining file-based fallback.

## Migration from Static System

This PR completes the transformation by:
1. Removing all hardcoded agent type references
2. Eliminating static task files
3. Converting monitoring to support dynamic agents
4. Updating documentation to reflect new architecture

The system now operates as a pure dynamic agent orchestration platform.
