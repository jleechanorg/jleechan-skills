---
name: symphony-daemon
description: Set up and use the Symphony launchd daemon in repositories that include orchestration/symphony_overlay/daemon.
---

# Symphony Daemon (Portable Pattern)

Use this skill in repos that vendor `orchestration/symphony_overlay/daemon/*`.

## Platform Scope

- This workflow is **macOS-only** (uses `launchd` / `launchctl`).

## Variables

Set these at the start of every run:

- `REPO_ROOT`: absolute path to target repo (defaults to current directory)
- `SYMPHONY_ELIXIR_DIR`: absolute path to local `symphony/elixir`
- `PLUGIN`: plugin id from `orchestration/symphony_overlay/daemon/plugins`
- `PLUGIN_INPUT`: plugin input path (absolute, or relative to `REPO_ROOT`)

```bash
export REPO_ROOT="${REPO_ROOT:-$(pwd)}"
export SYMPHONY_ELIXIR_DIR="${SYMPHONY_ELIXIR_DIR:-$HOME/projects_reference/symphony/elixir}"
export PLUGIN="${PLUGIN:-leetcode_hard}"
export PLUGIN_INPUT="${PLUGIN_INPUT:-benchmarks/harness/leetcode_hard_5_alt.json}"

if [[ -f "$PLUGIN_INPUT" ]]; then
  export PLUGIN_INPUT_PATH="$PLUGIN_INPUT"
else
  export PLUGIN_INPUT_PATH="$REPO_ROOT/$PLUGIN_INPUT"
fi
```

## Preconditions

1. `python3`, `jq`, `launchctl` are available.
2. `SYMPHONY_ELIXIR_DIR` exists.
3. Repo contains `orchestration/symphony_overlay/daemon/`.
4. Plugin input exists.

Quick validation:

```bash
test "$(uname -s)" = "Darwin" || { echo "This skill requires macOS launchd"; exit 1; }
test -d "$SYMPHONY_ELIXIR_DIR" || { echo "Missing SYMPHONY_ELIXIR_DIR"; exit 1; }
test -f "$REPO_ROOT/orchestration/symphony_overlay/daemon/setup_launchd_daemon.py" || { echo "Missing setup script"; exit 1; }
test -f "$PLUGIN_INPUT_PATH" || { echo "Missing plugin input: $PLUGIN_INPUT_PATH"; exit 1; }
```

## Install or Update Daemon

```bash
cd "$REPO_ROOT"
SYMPHONY_TASK_PLUGIN="$PLUGIN" \
SYMPHONY_TASK_PLUGIN_INPUT="$PLUGIN_INPUT_PATH" \
SYMPHONY_ELIXIR_DIR="$SYMPHONY_ELIXIR_DIR" \
python3 orchestration/symphony_overlay/daemon/setup_launchd_daemon.py
```

## Enqueue Tasks

```bash
cd "$REPO_ROOT"
SYMPHONY_TASK_PLUGIN="$PLUGIN" \
SYMPHONY_TASK_PLUGIN_INPUT="$PLUGIN_INPUT_PATH" \
"$REPO_ROOT/orchestration/symphony_overlay/daemon/enqueue_plugin_tasks.sh"
```

## Switch Plugin/Input Without Reinstall

```bash
cd "$REPO_ROOT"
SYMPHONY_TASK_PLUGIN="swe_bench_verified" \
SYMPHONY_TASK_PLUGIN_INPUT="$REPO_ROOT/benchmarks/harness/swe_bench_verified_5.json" \
"$REPO_ROOT/orchestration/symphony_overlay/daemon/enqueue_plugin_tasks.sh"
```

## Troubleshooting

- Daemon not receiving tasks:
  - rerun `setup_launchd_daemon.py`
  - check metadata exists and has expected values:

```bash
cat "$HOME/Library/Application Support/orchestrator_benchmark/symphony_daemon/daemon_metadata.json"
```

- Plugin import errors:
  - confirm plugin exists under `daemon/plugins`
  - run plugin tests:

```bash
cd "$REPO_ROOT"
python3 -m pytest -q orchestration/symphony_overlay/daemon/tests/test_plugins.py
```

## Fairness and Isolation (Benchmark Use)

1. Use per-orchestrator `/tmp` directories.
2. Use unique port ranges per orchestrator.
3. Keep task specs/acceptance criteria identical across orchestrators.
4. End each attempt with either `benchmark_commit` or machine-readable `blocked_reason`.
