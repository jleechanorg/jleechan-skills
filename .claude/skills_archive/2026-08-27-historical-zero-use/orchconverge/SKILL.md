---
name: orchconverge
description: Autonomous convergence via orchestration — runs /converge repeatedly inside a tmux agent (managed by the existing /orch system) until success criteria are met, time limit reached, or max attempts reached, then executes a final /pushl → /reviewdeep → /copilot workflow. Use when the user wants to run /orchconverge, needs unattended multi-hour convergence on a goal, wants persistent tmux-based convergence agents that survive terminal closure, or asks about convergence daemon config, state persistence, tmux orchestration architecture, or convergence status/stop/resume.
---

# /orchconverge - Autonomous Convergence via Orchestration

**Autonomous convergence using existing `/orch` orchestration system to run /converge continuously until completion, time limits, or max attempts reached, followed by comprehensive review and finalization workflow.**

## Usage

```bash
/orchconverge <goal>                           # Start autonomous convergence with default limits
/orchconverge <goal> --max-attempts 15        # Custom attempt limit (default: 10)
/orchconverge <goal> --max-hours 6            # Custom time limit (default: 3 hours)
/orchconverge <goal> --interval 5             # Convergence attempt interval in minutes (default: 5)
/orchconverge --resume                        # Resume from existing state
/orchconverge --status --verbose              # Status monitoring
/orchconverge --stop --cleanup                # Emergency stop
```

Use TodoWrite to track progress through the phases below.

## Command Architecture - Integration with Existing /orch System

**`/orchconverge` = Existing Orchestration System + Convergence Agent + Final Review Workflow**

```
┌─ Orchestration Setup ─┐    ┌─ Convergence Agent ─┐    ┌─ Final Workflow ─┐
│ • TaskDispatcher      │ → │ • /converge Loop      │ → │ • /pushl          │
│ • Current Dir Agent   │   │ • Progress Tracking   │   │ • /reviewdeep     │
│ • A2A Coordination    │   │ • Safety Boundaries   │   │ • /copilot        │
└───────────────────────┘   └───────────────────────┘   └───────────────────┘
```

Implementation delegates to the existing orchestration system:
```bash
/orch "Autonomous convergence: <goal> with max-attempts=N max-hours=H interval=M in current directory"
```

## Execution workflow

### Phase 1: Orchestration Integration Setup

Delegate to existing `/orch` system.

1. **Convergence Task Creation**
   - Format goal as orchestration task description
   - Include convergence parameters (attempts, hours, interval)
   - Specify current working directory requirement
   - Define termination conditions and final workflow

2. **Orchestration System Delegation**
   - Use existing `TaskDispatcher` for agent creation
   - Leverage `orchestrate_unified.py` framework
   - Maintain file-based A2A coordination
   - Ensure agent runs in Claude's current directory

### Phase 2: Convergence Agent Execution via Orchestration

Agent created by existing orchestration system.

1. **Create Convergence Tmux Session**
   ```bash
   # Session name: convergence-{branch}-{timestamp}
   tmux new-session -d -s "convergence-$(git branch --show-current)-$(date +%s)"
   ```

2. **Deploy Convergence Agent**
   - Agent script: Execute `/converge <goal>` repeatedly
   - Monitor convergence state and progress
   - Handle failures and retry logic
   - Log all convergence attempts and results

3. **Agent Monitoring Loop**
   ```bash
   while [[ $attempts -lt $max_attempts && $elapsed_hours -lt $max_hours ]]; do
     # Execute /converge with goal
     claude /converge "$goal"

     # Check convergence status
     if [[ $? -eq 0 && $(check_success_criteria) == "true" ]]; then
       echo "CONVERGENCE ACHIEVED"
       break
     fi

     # Wait for next attempt
     sleep $((interval_minutes * 60))
     attempts=$((attempts + 1))
   done
   ```

### Phase 3: Progress Monitoring and State Management

Continuous monitoring via autonomous system.

1. **Real-time Status Tracking**
   - Current attempt number / max attempts
   - Elapsed time / max time limit
   - Last convergence result and progress
   - Success criteria completion percentage
   - Agent health and tmux session status

2. **Convergence Decision Logic**
   - **SUCCESS**: All success criteria met → Proceed to Phase 4
   - **IN_PROGRESS**: Making progress → Continue attempts
   - **STALLED**: No progress for 3+ attempts → Escalate strategy
   - **TIME_LIMIT**: Max hours reached → Proceed to Phase 4 with partial results
   - **ATTEMPT_LIMIT**: Max attempts reached → Proceed to Phase 4 with partial results

3. **Failure Recovery**
   - Tmux session crashes: Restart agent automatically
   - /converge failures: Log and retry with exponential backoff
   - Resource exhaustion: Implement graceful degradation
   - External blocks: Continue attempts with intelligent retry

### Phase 4: Final Workflow Execution

Comprehensive finalization workflow.

1. **Stop Autonomous Convergence**
   - Graceful daemon shutdown
   - Remove cron job
   - Preserve final state and logs
   - Clean up tmux sessions

2. **Execute Final Workflow Sequence**
   ```bash
   # Push all changes and create/update PR
   /pushl --auto-label --update-description

   # Comprehensive review of all convergence work
   /reviewdeep --focus-correctness

   # Autonomous PR analysis and fixing
   /copilot --autonomous
   ```

3. **Generate Convergence Report**
   - Location: `docs/convergence-reports/{branch}-{timestamp}.md`
   - Total attempts and time elapsed
   - Success criteria achievement percentage
   - Key learnings and patterns discovered
   - Commands used and their effectiveness
   - Final PR status and review results

**Comprehensive Workflow properties:**
1. **End-to-End Automation**: From goal to PR review completion
2. **Quality Assurance**: Automatic review and issue resolution
3. **Documentation**: Complete audit trail and reporting
4. **Integration**: Seamless integration with existing slash command ecosystem

## Autonomous Integration

### Convergence Daemon Integration

```python
# Initialize with orchconverge-specific config
config = ConvergenceConfig(
    max_runtime_hours=user_max_hours,
    max_iterations=user_max_attempts,
    worktree_dir=os.getcwd(),
    cron_interval_minutes=user_interval,
    convergence_command="/converge",
    goal_statement=user_goal
)

daemon = ConvergenceDaemon(config)
daemon.start(goal=user_goal)
```

### Tmux Integration Architecture

```python
# Create persistent convergence session
tmux = TmuxIntegration()
session_name = f"convergence-{branch}-{timestamp}"

# Deploy convergence agent script
agent_script = generate_convergence_agent_script(
    goal=user_goal,
    max_attempts=config.max_iterations,
    max_hours=config.max_runtime_hours,
    interval_minutes=config.cron_interval_minutes
)

# Start agent in tmux session
tmux.create_session(session_name, agent_script)
```

### State Persistence

```json
{
  "goal": "user goal statement",
  "start_time": "2025-08-19T10:00:00Z",
  "current_attempt": 3,
  "max_attempts": 10,
  "elapsed_hours": 1.5,
  "max_hours": 3,
  "last_result": "partial_success",
  "success_criteria": {
    "criterion_1": true,
    "criterion_2": false,
    "criterion_3": true
  },
  "convergence_log": [
    {
      "attempt": 1,
      "timestamp": "2025-08-19T10:00:00Z",
      "result": "partial_success",
      "progress": 60
    }
  ],
  "tmux_session": "convergence-main-1692441600",
  "status": "running"
}
```

## Command Integration Framework

### Primary Commands Used

- **`/converge`**: Core convergence execution within tmux agents
- **`/orch`**: Tmux agent creation and management
- **`/pushl`**: Git operations and PR creation/updates
- **`/reviewdeep`**: Comprehensive code and architectural review
- **`/copilot`**: Autonomous PR analysis and issue resolution

### Orchestration Pattern

```
/orchconverge "goal" --max-attempts N --max-hours H
├─ Phase 1: Autonomous Setup
│  ├─ Initialize ConvergenceDaemon with config
│  ├─ Set up state persistence
│  └─ Install monitoring systems
├─ Phase 2: Tmux Orchestration
│  ├─ /orch Create persistent convergence agent
│  ├─ Deploy /converge execution loop
│  └─ Monitor progress continuously
├─ Phase 3: Convergence Monitoring
│  ├─ Track attempts and time limits
│  ├─ Handle failures and recovery
│  └─ Make termination decisions
└─ Phase 4: Final Workflow
   ├─ /pushl Push changes and update PR
   ├─ /reviewdeep Comprehensive review
   └─ /copilot Autonomous PR processing
```

## Success Criteria Patterns

### Automatic Success Detection

- **Code Changes**: All files modified and tests passing
- **PR Status**: Created/updated with passing CI checks
- **Review Status**: No critical issues in /reviewdeep analysis
- **Documentation**: Required docs updated and complete
- **Integration**: No merge conflicts or blocking dependencies

### Progress Measurement

- **Quantitative**: Percentage of success criteria met
- **Qualitative**: Progress toward goal through /converge iterations
- **Temporal**: Rate of improvement over time
- **Blocking**: Identification of external dependencies preventing progress

## Configuration Options

### Default Configuration

```
Max Attempts: 10
Max Hours: 3
Interval: 5 minutes
Working Dir: Current branch directory
State File: convergence_state.json
Report Dir: docs/convergence-reports/
```

### Advanced Configuration

```bash
# Custom limits and intervals
/orchconverge "implement auth system" --max-attempts 20 --max-hours 6 --interval 10

# Resume from existing state
/orchconverge --resume

# Status monitoring
/orchconverge --status --verbose

# Emergency stop
/orchconverge --stop --cleanup
```

## Error Handling & Recovery

### Tmux Session Management

- **Session Crashes**: Automatic restart with state recovery
- **Agent Failures**: Retry with exponential backoff
- **Resource Exhaustion**: Graceful degradation and cleanup
- **Network Issues**: Intelligent retry with connectivity checks

### Convergence Failures

- **Blocking Dependencies**: Continue attempts with periodic retry
- **Invalid Goals**: Clarify and restart with refined goal
- **Tool Failures**: Switch to alternative command strategies
- **Context Exhaustion**: Implement context cleanup between attempts

### Safety Mechanisms

- **Maximum Resource Usage**: Automatic termination if limits exceeded
- **Infinite Loop Prevention**: Hard limits on attempts and time
- **State Corruption**: Automatic state recovery from backups
- **External Interference**: Graceful handling of manual interruptions

## Monitoring and Observability

### Real-time Status

```bash
# Current status command
/orchconverge --status

# Sample output:
Goal: "implement complete authentication system"
Status: RUNNING (attempt 4/10)
Elapsed: 1h 23m / 3h 00m
Progress: 75% success criteria met
Last Result: partial_success (fixed tests, missing docs)
Tmux Session: convergence-auth-branch-1692441600
Next Attempt: 2m 37s
```

### Logging Integration

- **Convergence Logs**: All /converge attempts and results
- **Agent Logs**: Tmux session output and status
- **System Logs**: Daemon operation and state changes
- **Performance Logs**: Resource usage and timing metrics

## Benefits Over Standard /converge

### True Autonomy

- **Persistent Operation**: Continues even if terminal closes
- **Unattended Execution**: No manual intervention required
- **Automatic Recovery**: Handles failures and restarts autonomously
- **Resource Management**: Intelligent resource usage and cleanup

### Enhanced Reliability

- **Retry Logic**: Intelligent retry with exponential backoff
- **State Persistence**: Resume from any point after interruption
- **Failure Isolation**: Agent failures don't affect main system
- **Safety Boundaries**: Hard limits prevent runaway execution

## Example Usage

### Example 1: Feature Implementation

```bash
/orchconverge "implement complete user authentication with OAuth, tests, and documentation" --max-attempts 15 --max-hours 4
```

**Expected Flow**:
1. Creates tmux agent that runs `/converge` every 5 minutes
2. Each convergence iteration works toward authentication implementation
3. Monitors progress through success criteria (OAuth working, tests passing, docs complete)
4. After 4 hours or convergence, runs `/pushl` → `/reviewdeep` → `/copilot`
5. Generates comprehensive report with implementation timeline

### Example 2: Bug Fix Campaign

```bash
/orchconverge "fix all failing tests in the test suite and achieve 100% pass rate" --max-attempts 8 --interval 3
```

**Expected Flow**:
1. Agent attempts `/converge` every 3 minutes
2. Each iteration identifies and fixes failing tests
3. Tracks progress toward 100% pass rate
4. Terminates when all tests pass or 8 attempts reached
5. Creates PR with fixes and runs comprehensive review

### Example 3: Refactoring Project

```bash
/orchconverge "refactor legacy authentication code to use modern patterns while maintaining all functionality" --max-hours 6
```

**Expected Flow**:
1. Long-running refactoring with 6-hour time limit
2. Convergence iterations gradually modernize code
3. Maintains functionality through continuous testing
4. Comprehensive review ensures code quality
5. Final PR includes all refactoring changes

## Integration with Existing Systems

### Autonomous Convergence System

- **Reuses** existing `autonomous_convergence/` package
- **Extends** ConvergenceDaemon for /converge execution
- **Integrates** with TmuxIntegration for agent management
- **Leverages** StateManager for persistence across attempts

### Slash Command Ecosystem

- **Orchestrates** existing commands rather than reimplementing
- **Maintains** compatibility with current command interfaces
- **Enhances** workflow with autonomous operation
- **Preserves** individual command functionality for manual use

### GitHub Integration

- **Uses** existing GitHub MCP tools for PR operations
- **Maintains** review comment posting capabilities
- **Integrates** with existing PR labeling and description systems
- **Preserves** manual override capabilities when needed

## Limitations and Considerations

### Resource Constraints

- **Context Usage**: Manages context efficiently through state persistence
- **API Limits**: Respects GitHub and other API rate limits
- **Compute Resources**: Monitors system resources and degrades gracefully
- **Time Boundaries**: Hard time limits prevent excessive resource usage

### Scope Boundaries

- **Complex Goals**: May require goal decomposition for optimal results
- **External Dependencies**: Cannot bypass external system limitations
- **Permission Requirements**: Respects existing security and permission models
- **Manual Intervention**: Some tasks may still require human decision-making

### Technical Constraints

- **Tmux Availability**: Requires tmux for agent orchestration
- **Cron Access**: Needs cron permissions for autonomous scheduling
- **File System**: Requires write access for state persistence
- **Network Connectivity**: Depends on stable network for API operations

## Architecture Summary

**`/orchconverge`** combines the autonomous convergence system with tmux orchestration to create a truly autonomous convergence experience:

1. **Autonomous Setup**: Initializes convergence daemon and monitoring
2. **Tmux Orchestration**: Creates persistent agents running `/converge` continuously
3. **Progress Monitoring**: Tracks attempts, time, and success criteria
4. **Final Workflow**: Executes `/pushl` → `/reviewdeep` → `/copilot` upon completion
5. **Comprehensive Reporting**: Documents entire convergence journey

This creates a "set it and forget it" convergence system that works autonomously toward goals while maintaining full observability and safety boundaries.
