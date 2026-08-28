# Automation & Orchestration Libraries Guide

**Purpose**: Comprehensive guide to the automation and orchestration libraries for PR automation and multi-agent task execution.

## Overview

The **automation library** (`automation/`) provides GitHub PR automation workflows, while the **orchestration library** (`orchestration/`) manages multi-agent task execution in tmux sessions with Agent-to-Agent (A2A) communication.

### Architecture

```
automation/jleechanorg_pr_automation/jleechanorg_pr_monitor.py
  → Discovers PRs needing fixes
  ↓
automation/orchestrated_pr_runner.py
  → Creates TaskDispatcher instance
  ↓
orchestration/task_dispatcher.py
  → Analyzes task → Generates agent specs
  ↓
orchestration/agent_system.py (A2A communication)
  → Spawns agents in tmux sessions
  ↓
  Agents execute /fixpr or /copilot commands
```

## Automation Library (`automation/`)

### Entry Points

**Main Modules:**
- `automation/jleechanorg_pr_automation/jleechanorg_pr_monitor.py` - Cross-organization PR monitoring
- `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py` - PR agent dispatcher
- `automation/orchestrated_pr_runner.py` - Simplified PR runner

### Core Functions

#### `dispatch_agent_for_pr(dispatcher, pr, agent_cli, model)`
Dispatches an agent to fix a PR (merge conflicts, failing tests).

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:676`

**Parameters:**
- `dispatcher`: `TaskDispatcher` instance
- `pr`: PR dict with `repo_full`, `number`, `branch`, `head_oid`
- `agent_cli`: CLI chain (e.g., `"claude"`, `"gemini,cursor"`)
- `model`: Optional model name (e.g., `"gemini-3-flash-preview"`)

**Returns**: `bool` - Success status

**Usage:**
```python
from orchestration.task_dispatcher import TaskDispatcher
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import (
    dispatch_agent_for_pr, ensure_base_clone, chdir
)

pr = {
    "repo_full": "jleechanorg/worktree_auto3",
    "repo": "worktree_auto3",
    "number": 123,
    "branch": "fix/issue-123",
    "head_oid": "abc123...",
}

base_dir = ensure_base_clone(pr["repo_full"])
with chdir(base_dir):
    dispatcher = TaskDispatcher()
    success = dispatch_agent_for_pr(
        dispatcher,
        pr,
        agent_cli="claude",
        model="claude-sonnet-4-5-20250929"
    )
```

#### `dispatch_agent_for_pr_with_task(dispatcher, pr, task_description, agent_cli, model)`
Dispatches agent with custom task description (for non-/fixpr workflows).

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:584`

**Usage:**
```python
task_description = """
Analyze the PR and identify security vulnerabilities.
Write a report to vulnerabilities.md summarizing findings.
Do not modify any code - analysis only.
"""

success = dispatch_agent_for_pr_with_task(
    dispatcher,
    pr,
    task_description,
    agent_cli="claude",
    model=None  # Use default model
)
```

#### `ensure_base_clone(repo_full)`
Ensures a clean base clone exists for worktree creation.

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:411`

**Returns**: `Path` to base clone directory

**Recovery Strategy**: If ANY git operation fails (fetch, reset, checkout), nukes and re-clones.

### Helper Functions

#### `post_pr_comment_python(repo_full, pr_number, body, in_reply_to)`
Posts GitHub PR comment using Python requests (avoids bash/macOS prompts).

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:109`

**Usage:**
```python
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import post_pr_comment_python

# General PR comment
post_pr_comment_python(
    "jleechanorg/repo",
    123,
    "✅ Tests passing after fixes"
)

# Reply to inline review comment
post_pr_comment_python(
    "jleechanorg/repo",
    123,
    "Fixed in latest commit",
    in_reply_to=456789  # Comment ID
)
```

#### `cleanup_pending_reviews_python(repo_full, pr_number, automation_user)`
Cleans up pending reviews (avoids bash/macOS prompts).

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:160`

**Usage:**
```python
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import cleanup_pending_reviews_python

cleanup_pending_reviews_python(
    "jleechanorg/repo",
    123,
    "codex-bot"  # GitHub username
)
```

#### `has_failing_checks(repo_full, pr_number)`
Returns True if PR has any failing CI checks.

**Location**: `automation/jleechanorg_pr_automation/orchestrated_pr_runner.py:312`

### Configuration

**Environment Variables:**
- `GITHUB_TOKEN` - GitHub API authentication
- `GITHUB_ACTOR` - Automation username (for cleanup)
- `AUTOMATION_USERNAME` - Alternative to GITHUB_ACTOR
- `GH_HOST` - GitHub host (default: `github.com`)

**Constants:**
- `BASE_CLONE_ROOT` - `/tmp/pr-orch-bases` (base clones for worktrees)
- `WORKSPACE_ROOT_BASE` - `/tmp` (agent workspaces)
- `DEFAULT_TIMEOUT` - 30 seconds (baseline timeout)
- `CLONE_TIMEOUT` - 300 seconds
- `FETCH_TIMEOUT` - 120 seconds
- `API_TIMEOUT` - 60 seconds

## Orchestration Library (`orchestration/`)

### Entry Points

**Main Modules:**
- `orchestration/task_dispatcher.py` - Task analysis and agent creation
- `orchestration/agent_system.py` - Agent lifecycle management
- `orchestration/a2a_integration.py` - Agent-to-Agent communication
- `orchestration/agent_monitor.py` - Health monitoring

### Core Classes

#### `TaskDispatcher`
Main orchestration engine for task analysis and agent creation.

**Location**: `orchestration/task_dispatcher.py:48-142`

**Key Methods:**

##### `analyze_task_and_create_agents(task_description, forced_cli=None)`
Analyzes task and generates agent specifications.

**Parameters:**
- `task_description`: Detailed task instructions (str)
- `forced_cli`: Override CLI selection (e.g., `"claude"`, `"gemini,cursor"`)

**Returns**: `list[dict]` - Agent specifications

**Usage:**
```python
from orchestration.task_dispatcher import TaskDispatcher

dispatcher = TaskDispatcher()

task_description = """
Fix failing tests in PR #123.
Run pytest, identify failures, apply fixes.
Workspace: /tmp/repo/pr-123
"""

agent_specs = dispatcher.analyze_task_and_create_agents(
    task_description,
    forced_cli="claude"  # Force Claude CLI
)
# Returns: [{"name": "...", "cli": "claude", "task": "...", ...}]
```

##### `create_dynamic_agent(agent_spec)`
Spawns agent in tmux session with specified configuration.

**Parameters:**
- `agent_spec`: Agent specification dict with keys:
  - `name` (str): tmux session name
  - `cli` (str): CLI to use (`"claude"`, `"codex"`, `"gemini"`, `"cursor"`)
  - `task` (str): Task description
  - `workspace_config` (dict): `workspace_root`, `workspace_name`
  - `model` (str, optional): Model override

**Returns**: `bool` - Success status

**Usage:**
```python
agent_spec = {
    "name": "pr-123-fix",
    "cli": "claude",
    "task": "Fix failing tests in PR #123",
    "workspace_config": {
        "workspace_root": "/tmp/repo",
        "workspace_name": "pr-123"
    },
    "model": "claude-sonnet-4-5-20250929"
}

success = dispatcher.create_dynamic_agent(agent_spec)
# Spawns tmux session "pr-123-fix" running Claude CLI
```

### CLI Profiles

#### Supported CLIs (`CLI_PROFILES`)

**Location**: `orchestration/task_dispatcher.py:48-142`

| CLI | Binary | Model Override Env Var | Auth Method |
|-----|--------|------------------------|-------------|
| `claude` | `claude` | N/A (uses model flag) | OAuth (API key unset) |
| `codex` | `codex` | N/A | OAuth (API key unset) |
| `gemini` | `gemini` | `GEMINI_MODEL` (default: `gemini-3-flash-preview`) | OAuth (API key unset) |
| `cursor` | `cursor-agent` | `CURSOR_MODEL` (default: `composer-1`) | Cursor auth |

**CLI Chain Support**: Comma-separated chains (e.g., `"gemini,cursor"`) execute CLIs in sequence.

### CLI Validation

#### `validate_cli_two_phase(cli_name)`
Validates CLI availability and functionality with two-phase check.

**Location**: `orchestration/cli_validation.py`

**Parameters:**
- `cli_name`: CLI to validate (`"claude"`, `"codex"`, `"gemini"`, `"cursor"`)

**Returns**: `bool` - True if CLI is available and functional

**Usage:**
```python
from orchestration.cli_validation import validate_cli_two_phase

if validate_cli_two_phase("claude"):
    print("Claude CLI is available")
else:
    print("Claude CLI not found or not functional")
```

**Constants:**
- `CLI_VALIDATION_TIMEOUT_SECONDS` - Timeout for CLI validation (default: 90s)
- `CLI_VALIDATION_TEST_PROMPT` - Test prompt for CLI validation

### Workspace Management

#### Workspace Structure
```
/tmp/
  ├── pr-orch-bases/          # Base clones for worktrees
  │   └── repo/               # Base clone (main branch)
  └── repo/                   # Workspaces
      └── pr-123-branch/      # Agent workspace (worktree)
```

**Key Concepts:**
- **Base Clone**: Clean main branch clone for creating worktrees
- **Workspace**: Git worktree for agent to work in (isolated from base)
- **Workspace Config**: `{"workspace_root": "/tmp/repo", "workspace_name": "pr-123-branch"}`

### A2A Communication

#### Agent-to-Agent (A2A) Protocol
File-based messaging system for inter-agent communication (no Redis dependency).

**Key Modules:**
- `orchestration/a2a_integration.py` - Core A2A protocols
- `orchestration/a2a_monitor.py` - A2A monitoring
- `orchestration/message_broker.py` - File-based message broker (stub; Redis removed)

**Usage** (for advanced use cases):
```python
from orchestration.a2a_integration import TaskPool, get_a2a_status

# Check A2A system status
status = get_a2a_status()
print(f"A2A available: {status['available']}")

# Task pool management (advanced)
pool = TaskPool()
pool.add_task(task_id="task-1", task_data={...})
```

## Common Usage Patterns

### Pattern 1: Dispatch Agent for PR (Simple)

```python
from orchestration.task_dispatcher import TaskDispatcher
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import (
    dispatch_agent_for_pr, ensure_base_clone, chdir
)

pr_data = {
    "repo_full": "jleechanorg/repo",
    "repo": "repo",
    "number": 123,
    "branch": "fix/issue",
    "head_oid": "abc123..."
}

base_dir = ensure_base_clone(pr_data["repo_full"])
with chdir(base_dir):
    dispatcher = TaskDispatcher()
    success = dispatch_agent_for_pr(
        dispatcher,
        pr_data,
        agent_cli="claude"
    )

print(f"Agent spawned: {success}")
```

### Pattern 2: Custom Task with Specific Model

```python
task_description = """
Analyze code quality in PR #123.
Generate report with metrics and recommendations.
Save to code_quality_report.md.
"""

base_dir = ensure_base_clone("jleechanorg/repo")
with chdir(base_dir):
    dispatcher = TaskDispatcher()
    success = dispatch_agent_for_pr_with_task(
        dispatcher,
        pr_data,
        task_description,
        agent_cli="gemini",
        model="gemini-3-flash-preview"
    )
```

### Pattern 3: CLI Chain (Multi-Agent)

```python
# Execute task with Gemini first, then Cursor validates
success = dispatch_agent_for_pr(
    dispatcher,
    pr_data,
    agent_cli="gemini,cursor"  # Chain: Gemini → Cursor
)
```

### Pattern 4: GitHub API Operations (No Bash)

```python
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import (
    post_pr_comment_python,
    cleanup_pending_reviews_python,
    get_github_token
)

# Post comment
post_pr_comment_python(
    "jleechanorg/repo",
    123,
    "✅ All tests passing"
)

# Cleanup pending reviews
cleanup_pending_reviews_python(
    "jleechanorg/repo",
    123,
    "automation-bot"
)

# Get GitHub token (for custom API calls)
token = get_github_token()
# Use token with requests library
```

## Monitoring and Debugging

### View Agent Logs

**Log Viewing Script:**
```bash
./orchestration/stream_logs.sh <session-name>
```

**Example:**
```bash
# View logs for agent session "pr-123-fix"
./orchestration/stream_logs.sh pr-123-fix
```

### Check tmux Sessions

```bash
# List all tmux sessions
tmux ls

# Attach to agent session (read-only)
tmux attach-session -t pr-123-fix -r

# Kill agent session
tmux kill-session -t pr-123-fix
```

### Agent Health Monitoring

**Available Monitors:**
- `orchestration/agent_monitor.py` - Real-time agent health tracking
- `orchestration/safe_agent_monitor.py` - Fail-safe monitoring
- `orchestration/dashboard.py` - Web-based dashboard

```bash
# Start monitoring dashboard
python3 orchestration/dashboard.py

# Check agent health once (non-continuous)
python3 orchestration/agent_monitor.py --once
```

## Safety and Limits

### Timeout Configuration

**Orchestration Timeouts:**
- `AGENT_SESSION_TIMEOUT_SECONDS` - Max agent runtime (default: 3600s / 60 min)
- `CLI_VALIDATION_TIMEOUT_SECONDS` - CLI validation timeout (default: 90s)
- `RUNTIME_CLI_TIMEOUT_SECONDS` - Runtime CLI operation timeout

**Automation Timeouts:**
- `DEFAULT_TIMEOUT` - 30 seconds (baseline)
- `CLONE_TIMEOUT` - 300 seconds
- `FETCH_TIMEOUT` - 120 seconds
- `API_TIMEOUT` - 60 seconds

### Concurrent Agent Limits

**Configuration:**
- `DEFAULT_MAX_CONCURRENT_AGENTS` - Max agents per orchestration run

**Safety Manager:**
- `automation/jleechanorg_pr_automation/automation_safety_manager.py` - Rate limiting and safety checks

## Testing

### Automation Tests

```bash
# Run automation tests
vpython -m pytest automation/jleechanorg_pr_automation/tests/

# Specific test
vpython -m pytest automation/jleechanorg_pr_automation/tests/test_orchestrated_pr_runner.py
```

### Orchestration Tests

```bash
# Run orchestration tests
cd orchestration && python3 tests/run_tests.py

# Specific test
vpython -m pytest orchestration/tests/test_task_dispatcher_fix.py
```

## Troubleshooting

### Common Issues

**Issue**: Agent not spawning
- **Check**: CLI availability (`validate_cli_two_phase()`)
- **Check**: tmux session name conflicts (`tmux ls`)
- **Fix**: Kill existing session (`tmux kill-session -t <name>`)

**Issue**: GitHub API rate limiting
- **Check**: `GITHUB_TOKEN` environment variable set
- **Check**: Token permissions (read/write PRs, issues)
- **Fix**: Use authenticated gh CLI (`gh auth status`)

**Issue**: Base clone failures
- **Check**: `/tmp/pr-orch-bases/` disk space
- **Check**: Git remote connectivity
- **Fix**: Delete base clone and retry (auto-recovers)

**Issue**: Workspace conflicts
- **Check**: `/tmp/repo/` directory conflicts
- **Fix**: Clear workspace (`rm -rf /tmp/repo/pr-*`)

## Related Documentation

- `orchestration/CLAUDE.md` - Orchestration system overview
- `orchestration/A2A_DESIGN.md` - A2A communication architecture
- `orchestration/AGENT_SESSION_CONFIG.md` - Agent session configuration
- `.claude/skills/github-cli-reference.md` - GitHub CLI commands
- `.claude/skills/autonomous-execution.md` - Autonomous agent patterns

## Quick Reference

### Essential Imports

```python
# Automation
from automation.jleechanorg_pr_automation.orchestrated_pr_runner import (
    dispatch_agent_for_pr,
    dispatch_agent_for_pr_with_task,
    ensure_base_clone,
    chdir,
    post_pr_comment_python,
    cleanup_pending_reviews_python,
    get_github_token,
    has_failing_checks,
)

# Orchestration
from orchestration.task_dispatcher import (
    TaskDispatcher,
    CLI_PROFILES,
    GEMINI_MODEL,
    CURSOR_MODEL,
)
from orchestration.cli_validation import (
    validate_cli_two_phase,
    CLI_VALIDATION_TIMEOUT_SECONDS,
)
```

### Environment Variables

```bash
# GitHub
export GITHUB_TOKEN="ghp_..."
export GITHUB_ACTOR="automation-bot"

# Models
export GEMINI_MODEL="gemini-3-flash-preview"
export CURSOR_MODEL="composer-1"

# Orchestration
export AGENT_SESSION_TIMEOUT_SECONDS=3600
```

### File Structure

```
automation/
  ├── jleechanorg_pr_automation/
  │   ├── jleechanorg_pr_monitor.py      # Main PR monitor
  │   ├── orchestrated_pr_runner.py       # PR agent dispatcher
  │   ├── automation_safety_manager.py    # Safety limits
  │   └── codex_config.py                 # Automation config
  └── orchestrated_pr_runner.py           # Simplified runner

orchestration/
  ├── task_dispatcher.py                  # Task analysis & agent creation
  ├── agent_system.py                     # Agent lifecycle
  ├── a2a_integration.py                  # Agent-to-Agent communication
  ├── agent_monitor.py                    # Health monitoring
  ├── cli_validation.py                   # CLI validation
  └── constants.py                        # System constants
```
