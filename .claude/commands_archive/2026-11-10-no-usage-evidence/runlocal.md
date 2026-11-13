---
description: /runlocal
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

# /runlocal

Run the standard local development server script.

## Usage

```
/runlocal
/runlocal -- --port 9000 --watch
```

## What it does

Executes `./run_local_server.sh` from the repository root to start the local backend and any associated services. Any arguments entered after the command—such as `-- --port 9000 --watch`—are passed directly to the script.
