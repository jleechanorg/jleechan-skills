---
description: Legacy Python pair executor (pair_execute.py)
type: llm-orchestration
execution_mode: manual
---

# /pairv1 - Legacy Python Pair Executor

> **LEGACY**: This command uses the original `pair_execute.py` Python orchestrator.
> Prefer `/pair` (Teams-native) or `/pairv2` (LangGraph contract-gated) for new sessions.

## Usage

```bash
python3 .claude/pair/pair_execute.py "Task description"
python3 .claude/pair/pair_execute.py --coder-cli claude --verifier-cli claude "Task"
python3 .claude/pair/pair_execute.py --no-worktree "Task description"
python3 .claude/pair/pair_execute.py --brainstorm "Task description"
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--coder-cli` | `claude` | CLI for coder agent (`claude`, `codex`, `gemini`, `cursor`, `minimax`) |
| `--verifier-cli` | `codex` | CLI for verifier agent |
| `--no-worktree` | false | Run in current directory (no git worktree isolation) |
| `--brainstorm` | false | Run brainstorm phase before launching agents |
| `--max-iterations` | 60 | Max run attempts per agent (initial launch counts as 1) |
| `--interval` | 60 | Monitor check interval in seconds |
| `--coder-model` | — | Model for coder agent (e.g., `opus`, `sonnet`, `haiku`) |
| `--verifier-model` | — | Model for verifier agent (e.g., `gpt-5`) |
| `--model` | — | Legacy alias for `--coder-model` |
| `--claude-provider` | — | Global backend override for claude-family roles (`claude`\|`minimax`) |
| `--coder-claude-provider` | — | Coder backend override (requires `--coder-cli claude\|minimax`) |
| `--verifier-claude-provider` | — | Verifier backend override (requires `--verifier-cli claude\|minimax`) |

## Logging

Logs written to `/tmp/{repo_name}/{branch}/pair_logs/` with format `[YYYY-MM-DD HH:MM:SS] [PHASE] message`.

## Completion criteria

A session is complete when:

1. Coder signals `IMPLEMENTATION_READY`.
2. Verifier signals `VERIFICATION_COMPLETE`.
3. Lead synthesizes both outputs.

## When to use

- You need the original Python orchestration (no LangGraph, no contract gates).
- Debugging or reproducing behavior from the legacy executor.
- CI environments where `pair_execute_v2.py` is unavailable.

For all new work, prefer `/pair` (Teams-native) or `/pairv2` (contract-gated).
