# Orchestration Library (`jleechanorg-orchestration`)

Python package and CLI for AI CLI task execution (passthrough and async tmux modes).

## Table of Contents

- [Install from PyPI](#install-from-pypi)
- [Verify Install and Version](#verify-install-and-version)
- [CLI Entry Points](#cli-entry-points)
- [Primary Usage: ai_orch](#primary-usage-ai_orch)
- [Task Dispatcher Python Interface](#task-dispatcher-python-interface)
- [Legacy: orchestrate_unified (deprecated)](#legacy-orchestrate_unified-deprecated)
- [Design Summary](#design-summary)
- [Tech Stack (Summary)](#tech-stack-summary)
- [Local Development (Package Source)](#local-development-package-source)

## Install from PyPI

```bash
python3 -m pip install jleechanorg-orchestration
```

Upgrade:

```bash
python3 -m pip install --upgrade jleechanorg-orchestration
```

Install a specific version:

```bash
python3 -m pip install "jleechanorg-orchestration==0.1.40"  # omit version for latest
```

## Verify Install and Version

```bash
python3 -m pip show jleechanorg-orchestration
ai_orch --version
```

## CLI Entry Points

Console scripts installed by the package:

- `ai_orch`
- `orch` (alias)

Both map to `orchestration.runner:main`.

## Primary Usage: ai_orch

### Passthrough (default)

Run the selected CLI directly and stream output to stdout:

```bash
ai_orch "explain this code"
ai_orch --agent-cli codex "print 1"
ai_orch --agent-cli gemini "fix the bug"
```

### Async (detached tmux)

Spawn a detached tmux session and return immediately:

```bash
ai_orch --async "implement feature X"
ai_orch --async --resume "add error handling"   # resume existing session for this dir
ai_orch --async --worktree "refactor auth"      # create git worktree first, then async
```

**Flags:**
- `--agent-cli`: CLI to use (`claude`, `codex`, `gemini`, `minimax`, `cursor`)
- `--model`: model override for supported CLIs
- `--async`: spawn detached tmux session
- `--resume`: reuse existing session for this directory (requires `--async`)
- `--worktree`: create git worktree before async (requires `--async`)

## Task Dispatcher Python Interface

For programmatic multi-agent orchestration (used by `automation/`), use `TaskDispatcher` directly:

```python
from orchestration.task_dispatcher import TaskDispatcher

dispatcher = TaskDispatcher()

agent_specs = dispatcher.analyze_task_and_create_agents(
    "Fix failing tests in PR #123 and push updates",
    forced_cli="claude",
)

for spec in agent_specs:
    ok = dispatcher.create_dynamic_agent(spec)
    print(spec["name"], ok)
```

### Core methods

- `TaskDispatcher.analyze_task_and_create_agents(task_description: str, forced_cli: str | None = None) -> list[dict]`
- `TaskDispatcher.create_dynamic_agent(agent_spec: dict) -> bool`

### Agent spec fields used by `create_dynamic_agent`

- `name`: unique agent/session name
- `task`: full task instructions
- `cli` or `cli_chain`: selected CLI or fallback chain
- `workspace_config` (optional): workspace placement/settings
- `model` (optional): model override

## Legacy: orchestrate_unified (deprecated)

`orchestrate_unified.py` is retained as a stub for import compatibility. Its orchestration logic has moved to `runner.py`. Use `ai_orch` for passthrough/async or `TaskDispatcher` for programmatic agent creation.

## Design Summary

Full design details live in [`orchestration/design.md`](./design.md).

High-level design:

- Entry point is `ai_orch`/`orch` (mapped to `orchestration.runner:main`).
- Default flow is passthrough: invoke CLI directly, stream output.
- Async flow (`--async`) spawns detached tmux sessions with resume and optional worktree support.
- `TaskDispatcher` remains for programmatic multi-agent orchestration (automation, PR monitors).
- Coordination uses file-backed A2A/task state under `/tmp` (no Redis dependency).

## Tech Stack (Summary)

- Runtime: Python 3.11+
- Session/process isolation: `tmux`
- VCS/PR operations: `git`, `gh`
- Agent CLIs: `claude`, `codex`, `gemini`, `minimax`, `cursor-agent`
- Coordination: file-backed A2A/task state under `/tmp` (no Redis requirement)

Detailed architecture and implementation docs:

- `orchestration/design.md`
- `orchestration/A2A_DESIGN.md`
- `orchestration/AGENT_SESSION_CONFIG.md`

## Local Development (Package Source)

```bash
cd orchestration
python3 -m pip install -e .
python3 -m pytest tests -q
```

Use editable installs only for local package development.
