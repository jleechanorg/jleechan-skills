# Agent Monitoring Safety Guide

## ⚠️ CRITICAL: Prevent Accidental SIGINT

The root cause of agent task-agent-5030's failure was sending keyboard input ('q') via tmux during monitoring.

## Safe Monitoring Practices

### ✅ DO: Read-Only Monitoring
```bash
# SAFE - Read only
tmux capture-pane -t task-agent-5030 -p | tail -50

# SAFE - Use safe monitor script
python3 orchestration/safe_agent_monitor.py task-agent-5030

# SAFE - List agents
tmux ls | grep agent
```

### ❌ DON'T: Send Keyboard Input
```bash
# DANGEROUS - Can interrupt agent!
tmux send-keys -t task-agent-5030 q     # Causes SIGINT!
tmux send-keys -t task-agent-5030 " "   # Can interfere!
tmux send-keys -t task-agent-5030 Enter # Unpredictable!
```

## Using Safe Agent Monitor

The `safe_agent_monitor.py` script provides risk-free monitoring:

```bash
# List all running agents
python3 orchestration/safe_agent_monitor.py -l

# Monitor specific agent once
python3 orchestration/safe_agent_monitor.py task-agent-5030

# Continuous monitoring (updates every 5s)
python3 orchestration/safe_agent_monitor.py task-agent-5030 -c

# Monitor all agents
python3 orchestration/safe_agent_monitor.py -a

# Custom interval
python3 orchestration/safe_agent_monitor.py task-agent-5030 -c -i 10
```

## Recovery If Accident Happens

If you accidentally interrupt an agent:

1. Check exit code:
   ```bash
   cat /tmp/orchestration_results/{agent-name}_results.json
   ```

2. Run recovery coordinator:
   ```bash
   python3 orchestration/recovery_coordinator.py
   ```

3. Recovery will analyze partial work and create continuation agent

## Prevention in Code

Future improvements to prevent this systemically:

1. **Stdin Redirect**: Run agents with stdin redirected to /dev/null
2. **Signal Handlers**: Add trap handlers to log why agent is exiting
3. **Non-Interactive Mode**: Add flag to ignore all keyboard input
4. **Monitoring API**: Create REST endpoint for safe status checking

## Lesson Learned

Exit code 130 (SIGINT) during monitoring = keyboard input accident!

Always use READ-ONLY monitoring methods.
