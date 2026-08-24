---
description: /localserver
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
The `/localserver` launcher performs the following steps before starting the servers:

1. **Project Root Detection**: Changes into the repository root so relative paths behave correctly.
2. **Script Discovery**: Checks for `run_local_server.sh` in:
   - `<project-root>/run_local_server.sh`
   - `<project-root>/scripts/run_local_server.sh`
3. **Validation**: Exits with a clear error if neither location exists.
4. **Execution**: Runs the discovered script (forwarding any arguments) using its executable bit if set, or via `bash` otherwise.

This ensures `/localserver` works whether the helper script lives at the repository root or inside the `scripts/` directory.

## 📋 REFERENCE DOCUMENTATION

# /localserver

Starts the local development server for testing with health verification.

## Usage

```
/localserver
```

## What it does

Executes the dedicated `./claude_command_scripts/commands/localserver.sh` launcher which locates and runs `run_local_server.sh` from either the project root or `scripts/` directory. The launcher provides:

1. **Dual Server Setup**: Flask backend + React v2 frontend on separate ports
2. **Aggressive Cleanup**: Interactive server cleanup with options to kill all servers or specific ports
3. **Dynamic Port Assignment**: Automatically finds available ports starting from defaults (Flask: 8081, React: 3002)
4. **Force Port Clearing**: Ensures target ports are available by killing conflicting processes
5. **Virtual Environment**: Automatically sets up and activates Python virtual environment
6. **Comprehensive Health Checks**: Validates both servers with curl before declaring success
7. **API Testing**: Tests actual API endpoints to ensure backend is responding correctly

## Enhanced Features Integrated

### Aggressive Cleanup

- **Lists all running servers** with branch names and PIDs
- **Interactive cleanup options**:
  - `[a]` Kill all servers (aggressive cleanup) - default
  - `[p]` Kill processes on target ports only
  - `[n]` Keep all servers running
- **Force port clearing** for default Flask (8081) and React (3002) ports

### Health Verification

- **Flask backend**: `curl http://localhost:{FLASK_PORT}/` with retry logic
- **React frontend**: `curl http://localhost:{REACT_PORT}/` with extended timeout
- **API connectivity**: Tests `/api/campaigns` endpoint for proper authentication response
- **Failure handling**: Kills servers and exits on Flask failure, warns on React issues
- **Success criteria**: Flask must respond, React warnings allowed (common startup delay)

### Dynamic Port Management

- **Smart port finding**: Starts from defaults, finds next available if occupied
- **Port conflict resolution**: Clears target ports before finding alternatives
- **Reliable assignment**: Uses server-utils.sh functions for robust port management

## Implementation

```bash
./claude_command_scripts/commands/localserver.sh [optional-args]
```

All the enhanced features (cleanup, health checks, port management) are now integrated into the main server launcher script, providing a single, robust solution for local development.

## Server URLs

- **Flask Backend**: `http://localhost:{FLASK_PORT}` (dynamic port starting from 8081)
- **React Frontend**: `http://localhost:{REACT_PORT}` (dynamic port starting from 3002)
- **Test Mode Access**: `http://localhost:{REACT_PORT}?test_mode=true&test_user_id=test-user-123`

## Notes

- Both servers run in separate terminals/processes for independent debugging
- Testing mode enabled (TESTING=true) for mock AI responses
- Health checks are mandatory - script only declares success after validation
- Aggressive cleanup ensures clean startup environment
