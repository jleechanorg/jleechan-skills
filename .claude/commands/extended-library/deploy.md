---
description: /deploy
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execution Logic

**Action Steps:**
1. Change into the repository root for consistent relative paths
2. Look for `deploy.sh` at:
   - `<project-root>/deploy.sh`
   - `<project-root>/scripts/deploy.sh`
3. Exit with a clear error message if neither location exists
4. Execute the discovered script (respecting its executable bit or running with `bash`)

## 📋 REFERENCE DOCUMENTATION

# /deploy

Automates project deployments using the standard `deploy.sh` workflow with safety checks.

## Usage

```
/deploy [target]
```

Examples:
- `/deploy` – run default deployment
- `/deploy staging` – pass arguments through to the deploy script
- `/deploy stable` – deploy the stable channel release

## What it does

- Runs the canonical deployment script used by the repository
- Forwards any additional arguments directly to `deploy.sh`
- Prints the script path being executed for transparency
- Works whether `deploy.sh` lives in the project root or `scripts/` directory

## Implementation

```bash
./claude_command_scripts/commands/deploy.sh [args]
```

The deployment command delegates all business logic to the existing `deploy.sh`, ensuring the same tested workflow is used in every environment.
