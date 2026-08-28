---
name: ao-operator-discipline
description: Use when spawning, steering, or auditing Agent Orchestrator workers, especially when the user specifies exact AO parameters such as codex, runtime, project, claim-pr, or PR targets.
---

# AO Operator Discipline

## Overview

AO parameters are commitments. If the user asks for Codex workers, PR-specific workers, a certain runtime, or a specific project, you must pass those parameters explicitly and then verify that AO actually honored them.

The failure pattern this skill prevents is simple: a worker exists, but it is the wrong worker.

## When to Use

Use this skill when:
- the user asks to use AO or `ao`
- you plan to run `ao spawn`, `ao send`, `ao session claim-pr`, or `ao status`
- the user specifies a worker type such as Codex, Claude, Gemini, or a runtime
- you are claiming PRs or creating a PR-focused worker fleet

Do not use this skill for tiny read-only checks like a one-off `ao status`.

## Agent Name Resolution — Read Config First

**Before evaluating any `--agent` value**, read the active AO config:

```bash
head -20 ~/.hermes/agent-orchestrator.yaml   # check defaults.agent and installed plugins
```

`--agent` values are resolved against the config, not against AO package plugin directories. If `<X>` in `--agent <X>` is not a well-known CLI name (codex, claude, claude-code, gemini), look it up in the config before concluding it's unsupported.

Known shorthands on this machine:
- `agy` / `antigravity` → `~/.local/bin/agy` (Google Antigravity / Gemini CLI) — **this is the default agent**
- `minimax` → claude CLI + MiniMax API redirect
- `wafer` → claude CLI + Wafer API redirect

**Never scan `packages/agent-*/` as a substitute for reading the config.**

## Required Rules

1. Treat user-specified AO parameters as hard requirements:
   - `--agent`
   - `--runtime`
   - `--project`
   - `--claim-pr`
   - target PR / branch / evidence standard

2. Never rely on AO defaults when the user asked for something specific.

3. After every `ao spawn`, verify the spawned session before trusting it.

4. If the verified session does not match the request, kill or replace it. Do not proceed with the wrong worker.

## Spawn Pattern

For Codex workers, use an explicit agent override:

```bash
unset GITHUB_TOKEN
ao spawn --project <project> --agent codex --claim-pr <pr> "<task>"
```

If the user specified another runtime too, pass it explicitly:

```bash
unset GITHUB_TOKEN
ao spawn --project <project> --agent codex --runtime tmux --claim-pr <pr> "<task>"
```

## Verification Checklist

Immediately after spawn, inspect the session file under `~/.agent-orchestrator/.../sessions/<session>` and confirm:

- `agent=codex` when Codex was requested
- `pr=<expected PR URL>` when a PR was specified
- `runtimeHandle.data.launchCommand` contains the expected CLI and model

Example verification:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path("~/.agent-orchestrator/<hash>-<project>/sessions/<session>").expanduser()
print(p.read_text())
PY
```

For Codex requests, expected launch shape:

```text
agent=codex
launchCommand=...'codex' ... --model 'gpt-5.4' ...
```

If you see `gemini`, `claude`, `MiniMax`, or another unexpected launcher, the spawn is wrong.

## Tmux Monitoring

After verification, check the tmux pane with at least 20 lines:

```bash
tmux capture-pane -pt <tmux-session>:0.0 -S -40
```

Look for:
- real PR-specific work
- tool use
- red/green testing
- review or CI inspection

Do not accept a welcome screen, generic prompt, or stale queued message as evidence the worker is on task.

## Recovery

If a worker was launched with the wrong agent or runtime:

```bash
ao session kill <session>
ao spawn --project <project> --agent codex --claim-pr <pr> "<task>"
```

Then re-run the verification checklist.

## Common Mistakes

- Spawning without `--agent codex` because “the config probably defaults correctly”
- Inspecting `ao status` only, instead of session metadata
- Treating “session exists” as proof that the worker matches the user’s request
- Monitoring only the last 5 lines of tmux output

## Minimum Completion Bar

Do not report success on AO setup until you have all of:
- explicit spawn command with required parameters
- verified session metadata
- verified launch command
- tmux evidence showing the worker is actually doing the assigned PR/task
