# Orchestration System Tests

Comprehensive end-to-end tests for the multi-agent orchestration system.

## Overview

These tests verify the complete flow from `/orch` command to PR creation, ensuring:
- External dependencies are properly mocked
- Internal Python code flow is tested without mocking
- Redis integration works correctly
- Agent creation and coordination functions properly
- Error handling and fallback mechanisms work

## Test Structure

```
tests/
├── fixtures/           # Mock fixtures for external dependencies
│   ├── mock_tmux.py    # Mock tmux session management
│   ├── mock_claude.py  # Mock Claude CLI execution
│   └── mock_redis.py   # Mock Redis operations
├── test_orchestrate_unified.py      # Main orchestration system tests
├── test_task_dispatcher.py          # Task analysis and agent creation tests
├── test_a2a_integration.py          # A2A protocol integration tests
├── test_end_to_end.py               # Complete workflow integration tests
├── test_stale_task_prevention.py   # Stale task queue bug prevention tests
├── test_prompt_file_lifecycle.py   # Prompt file lifecycle management tests
├── test_task_execution_verification.py  # Task execution verification tests
├── test_tmux_session_lifecycle.py  # Tmux session lifecycle tests
├── run_tests.py                     # Test runner script
└── README.md                        # This file
```

## Running Tests

### Run All Tests
```bash
cd orchestration/tests
python3 run_tests.py
```

### Run Specific Test Module
```bash
python3 run_tests.py unified        # test_orchestrate_unified.py
python3 run_tests.py dispatcher     # test_task_dispatcher.py
python3 run_tests.py a2a            # test_a2a_integration.py
python3 run_tests.py end_to_end     # test_end_to_end.py
python3 run_tests.py stale_prevention  # test_stale_task_prevention.py
python3 run_tests.py prompt_lifecycle  # test_prompt_file_lifecycle.py
python3 run_tests.py task_verification # test_task_execution_verification.py
python3 run_tests.py tmux_lifecycle    # test_tmux_session_lifecycle.py
```

### List Available Tests
```bash
python3 run_tests.py --list
```

### Run with Verbose Output
```bash
python3 run_tests.py --verbose
```

## Test Categories

### 1. Basic Flow Tests (`test_orchestrate_unified.py`)
- **test_basic_task_flow**: Complete request → agent creation flow
- **test_redis_integration_success**: Redis coordination when available
- **test_redis_fallback_behavior**: File-based fallback when Redis unavailable
- **test_dependency_checking**: Required dependency verification
- **test_agent_workspace_creation**: Git worktree and branch creation
- **test_agent_prompt_includes_mandatory_steps**: PR creation requirements

### 2. Task Dispatcher Tests (`test_task_dispatcher.py`)
- **test_task_analysis_and_agent_creation**: Agent specification generation
- **test_dynamic_agent_creation_flow**: Complete agent creation process
- **test_agent_workspace_isolation**: Unique workspaces per agent
- **test_agent_name_collision_avoidance**: Unique naming under load
- **test_task_type_inference**: Automatic task categorization
- **test_priority_inference**: Priority detection from keywords
- **test_agent_limit_enforcement**: Concurrent agent limits
- **test_fresh_branch_from_main**: Clean branch creation policy

### 3. A2A Integration Tests (`test_a2a_integration.py`)
- **test_agent_registration_with_a2a**: Agent registration in A2A protocol
- **test_redis_message_broker_initialization**: MessageBroker setup
- **test_agent_capability_registration**: Capability-based registration
- **test_inter_agent_messaging_flow**: Message passing between agents
- **test_a2a_protocol_fallback_when_redis_unavailable**: Graceful degradation
- **test_task_result_reporting_through_a2a**: Result communication
- **test_agent_discovery_through_a2a**: Agent discovery mechanisms

### 4. End-to-End Tests (`test_end_to_end.py`)
- **test_complete_task_workflow_with_redis**: Full workflow with Redis
- **test_complete_task_workflow_without_redis**: Full workflow without Redis
- **test_agent_restart_with_existing_conversation**: Conversation continuity
- **test_multiple_agents_coordination**: Multi-agent scenarios
- **test_error_handling_and_recovery**: Graceful error handling
- **test_agent_completion_verification_flow**: Completion detection
- **test_dependency_integration**: All dependencies working together

### 5. Stale Task Prevention Tests (`test_stale_task_prevention.py`)
- **test_stale_prompt_file_cleanup_on_startup**: Cleanup of stale prompt files during startup
- **test_multi_run_task_isolation**: Task isolation between orchestration runs
- **test_agent_prompt_file_cleanup_before_creation**: Per-agent prompt file cleanup
- **test_task_prompt_freshness_verification**: Ensure prompts reflect current tasks
- **test_prompt_file_age_based_cleanup**: Age-based cleanup (5-minute threshold)
- **test_large_scale_stale_file_scenario**: Handle large numbers of stale files (289+)
- **test_concurrent_orchestration_safety**: Safe operation with concurrent instances

### 6. Prompt File Lifecycle Tests (`test_prompt_file_lifecycle.py`)
- **test_prompt_file_creation_contains_correct_task**: Verify prompt file content accuracy
- **test_prompt_file_cleanup_age_threshold**: Exact 5-minute age threshold testing
- **test_prompt_file_content_isolation**: Content isolation between different tasks
- **test_memory_leak_prevention**: Prevent accumulation of prompt files
- **test_cross_user_isolation**: Multi-user/context isolation
- **test_realistic_production_scenario**: Production bug scenario simulation

### 7. Task Execution Verification Tests (`test_task_execution_verification.py`)
- **test_agent_prompt_contains_exact_user_request**: Verify prompts match user requests
- **test_agent_workspace_reflects_task_context**: Workspace setup verification
- **test_task_context_isolation_between_agents**: Isolation between simultaneous agents
- **test_pr_context_detection_accuracy**: PR update vs create mode detection
- **test_task_prompt_includes_mandatory_completion_steps**: Completion requirement verification
- **test_unique_agent_naming_prevents_conflicts**: Agent naming collision prevention

### 8. Tmux Session Lifecycle Tests (`test_tmux_session_lifecycle.py`)
- **test_tmux_session_creation_for_agents**: Proper session creation for each agent
- **test_tmux_session_cleanup_on_startup**: Cleanup of completed sessions on startup
- **test_session_completion_detection_accuracy**: Accurate completion status detection
- **test_session_resource_leak_prevention**: Prevent resource leaks from accumulated sessions
- **test_active_agent_counting_excludes_idle_sessions**: Correct active agent counting
- **test_session_naming_uniqueness**: Unique session names under high load

## Mock Strategy

### What We Mock (External Dependencies)
- **tmux commands**: Session creation, listing, capture-pane operations
- **git operations**: Worktree creation, branch operations, commits
- **Claude CLI**: Subprocess execution of claude commands
- **Redis operations**: Connection, data storage, pub/sub messaging
- **GitHub CLI**: PR creation and management
- **File system**: Agent workspaces (using temp directories)

### What We DON'T Mock (Internal Code Flow)
- Python method calls between orchestration modules
- Task dispatcher logic and algorithms
- A2A protocol implementation
- Message broker coordination logic
- Agent creation workflows
- Capability scoring mechanisms

## Key Test Scenarios

### Scenario 1: Basic Task Flow
```python
# User types: /orch "Fix all failing tests"
# Verify: request → orchestration → task_dispatcher → agent creation
```

### Scenario 2: Redis Integration
```python
# Redis available → agent registers with A2A → messaging works
# Redis unavailable → graceful fallback to file coordination
```

### Scenario 3: Agent Creation
```python
# Agent gets: unique workspace, tmux session, git branch from main
# Agent prompt includes: mandatory PR creation steps
```

### Scenario 4: Multi-Agent Coordination
```python
# Complex task → multiple agents → unique names → Redis coordination
```

### Scenario 5: Error Handling
```python
# Git failures, Redis unavailable, dependency missing → graceful handling
```

## Assertions and Verification

### Code Flow Verification
- Assert method call order matches expected flow
- Assert correct parameters passed between components
- Assert no skipped steps in orchestration chain

### Agent Creation Verification
- Assert agent workspace created in correct location
- Assert tmux session started with correct name
- Assert git worktree created from main branch
- Assert Claude called with `--model sonnet`
- Assert prompt file includes mandatory PR creation steps

### A2A Protocol Verification
- Assert agent registered with correct capabilities
- Assert Redis messages published to correct channels
- Assert message broker handles agent discovery

### Error Handling Verification
- Assert graceful fallback when Redis unavailable
- Assert system continues operation despite component failures
- Assert meaningful error messages for debugging

## Success Criteria

- ✅ All code paths covered (>90% coverage target)
- ✅ External dependencies properly isolated through mocking
- ✅ Internal Python flow verified without artificial mocking
- ✅ Tests run quickly (<10 seconds total for full suite)
- ✅ Clear failure messages when orchestration flow breaks
- ✅ Easy to add new test scenarios as system evolves

## Mock Fixtures Usage

### Example: Using tmux fixture
```python
def test_agent_creation(self):
    with mock_tmux_fixture() as mock_tmux:
        # Run orchestration
        orchestration.orchestrate("test task")

        # Verify tmux session created
        self.assertGreater(len(mock_tmux.sessions), 0)

        # Check session details
        session_name = list(mock_tmux.sessions.keys())[0]
        self.assertTrue(session_name.startswith('task-agent-'))
```

### Example: Using Claude fixture
```python
def test_claude_execution(self):
    with mock_claude_fixture() as mock_claude:
        # Run orchestration
        orchestration.orchestrate("test task")

        # Verify Claude called with correct model
        self.assertTrue(mock_claude.assert_called_with_model('sonnet'))
```

### Example: Using Redis fixture
```python
def test_redis_coordination(self):
    with mock_redis_fixture() as mock_redis:
        # Run orchestration
        orchestration.orchestrate("test task")

        # Verify agent registered in Redis
        agent_keys = [k for k in mock_redis.hashes.keys() if k.startswith('agent:')]
        self.assertGreater(len(agent_keys), 0)
```

## Adding New Tests

1. **Choose appropriate test file** based on functionality
2. **Use relevant mock fixtures** for external dependencies
3. **Follow naming convention**: `test_descriptive_name`
4. **Include comprehensive assertions** for verification
5. **Add docstring** explaining what the test verifies
6. **Test both success and failure scenarios**

## Debugging Test Failures

1. **Run specific test**: `python3 run_tests.py test_name`
2. **Check mock call history**: `mock_object.call_history`
3. **Verify assertions**: Review what each assertion checks
4. **Check temp directories**: Tests create temporary workspaces
5. **Enable verbose output**: `python3 run_tests.py --verbose`

## Integration with CI/CD

These tests are designed to:
- Run quickly in CI environments
- Provide clear pass/fail status
- Generate meaningful error messages for debugging
- Work without external dependencies (Redis, tmux, etc.)
- Clean up temporary resources automatically
