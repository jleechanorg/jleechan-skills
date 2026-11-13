# Test: Pair Command Execution

> **Execution:** An agent runs the steps below in order with full tool access and records RED/GREEN in the Status section.

## Test ID
test-pair-command-execution

## Status
- [ ] RED (failing) - Pair command doesn't work correctly
- [ ] GREEN (passing) - Pair command executes successfully
- [ ] REFACTORED

## Description
Validates that the `/pair` command successfully launches dual-agent pair programming sessions that complete a simple programming task. The test creates a simple Python program and uses the pair command to implement and verify it.

## Pre-conditions
- MiniMax CLI available in PATH (via Claude CLI with MiniMax provider)
- `MINIMAX_API_KEY` configured in environment
- tmux available for session management
- MCP Mail configured for agent communication
- Python 3.11+ available
- Network connectivity for MCP servers

## Test Program (Target)

### File: /tmp/pair_test_program/test_program.py
```python
#!/usr/bin/env python3
"""
Simple test program for /pair command testing.
This program will be created by the pair session as a test target.
"""

def hello_world():
    """Return a greeting message."""
    return "Hello from pair test program!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def main():
    print(hello_world())
    print(f"2 + 3 = {add(2, 3)}")


if __name__ == "__main__":
    main()
```

### File: /tmp/pair_test_program/test_pair_program.py
```python
#!/usr/bin/env python3
"""Unit tests for the pair test program."""
import pytest
from test_program import hello_world, add


def test_hello_world():
    """Test that hello_world returns expected message."""
    result = hello_world()
    assert result == "Hello from pair test program!"


def test_add_positive():
    """Test adding positive numbers."""
    assert add(2, 3) == 5


def test_add_negative():
    """Test adding negative numbers."""
    assert add(-1, 1) == 0


def test_add_zero():
    """Test adding zero."""
    assert add(0, 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Test Steps

### Step 1: Verify Test Program Exists
1. Check that `/tmp/pair_test_program/test_program.py` exists
2. Check that `/tmp/pair_test_program/test_pair_program.py` exists

### Step 2: Execute Pair Command
1. Run the pair command with a task to implement and test the program:
   ```bash
   cd /tmp/pair_test_program && python3 .claude/scripts/pair_execute.py --no-worktree --coder-cli minimax --verifier-cli minimax "Implement and run the tests in test_pair_program.py"
   ```

### Step 3: Verify Execution
1. Check tmux sessions for pair sessions
2. Verify both coder and verifier agents were launched
3. Monitor for completion

### Step 4: Verify Test Results
1. Run the tests manually to verify:
   ```bash
   cd /tmp/pair_test_program && python3 -m pytest test_pair_program.py -v
   ```

## Expected Results

**PASS Criteria**:
- ✅ Pair command launches successfully
- ✅ Coder agent implements the required functions
- ✅ Verifier agent runs tests and verifies they pass
- ✅ All 4 tests pass: test_hello_world, test_add_positive, test_add_negative, test_add_zero
- ✅ tmux session completes without errors

**FAIL Indicators**:
- ❌ Pair command fails to launch
- ❌ Coder doesn't implement the required functions
- ❌ Tests fail after pair execution
- ❌ tmux session errors or timeouts

## Test Matrix

| Test Case | Description | Expected Behavior |
|-----------|-------------|-------------------|
| **Case 1** | Pair launches successfully | Both coder and verifier sessions start |
| **Case 2** | Coder implements functions | test_program.py has working hello_world and add |
| **Case 3** | Verifier runs tests | pytest output shows all tests passing |
| **Case 4** | Session completes cleanly | tmux session terminates without errors |

## Manual Test Execution

As an LLM, execute this test by:

1. **Verify test files exist**:
   ```bash
   ls -la /tmp/pair_test_program/
   cat /tmp/pair_test_program/test_program.py
   cat /tmp/pair_test_program/test_pair_program.py
   ```

2. **Run the pair command**:
   ```bash
   cd /tmp/pair_test_program
   python3 $HOME/projects/worktree_pair2/.claude/scripts/pair_execute.py --no-worktree --coder-cli minimax --verifier-cli minimax "Implement the hello_world and add functions in test_program.py, then run pytest to verify all tests pass"
   ```

3. **Check results**:
   - Monitor tmux sessions: `tmux ls | grep pair`
   - Check test results: `cd /tmp/pair_test_program && python3 -m pytest test_pair_program.py -v`

## Verification Commands

```bash
# Check pair sessions
tmux ls | grep pair

# Run tests manually
cd /tmp/pair_test_program && python3 -m pytest test_pair_program.py -v

# Check program output
cd /tmp/pair_test_program && python3 test_program.py
```

## Bug Analysis

**If test fails, analyze**:
1. Did pair_execute.py launch successfully?
2. Did both coder and verifier agents start?
3. Did the coder implement the required functions?
4. Did the verifier run and verify the tests?
5. Were there any tmux or MCP communication errors?

## Implementation Notes

### RED Phase
This test should FAIL initially because:
- test_program.py doesn't have the required functions implemented
- test_pair_program.py imports will fail

### GREEN Phase
To pass this test, the pair command should:
1. Launch coder agent to implement hello_world() and add()
2. Launch verifier agent to run pytest
3. Verify all tests pass
4. Complete the session successfully
