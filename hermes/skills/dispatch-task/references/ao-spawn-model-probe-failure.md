---
kind: failure-mode
name: model-probe-failure
added: 2026-07-30
verified-dispatch: ai_universe-hjd (feature: bump gemini-3-flash-preview → gemini-3.6-flash)
changelog: dispatch-task v2.5.0
---

# SEVENTH FAILURE MODE — project-row `agentConfig.model` is unreachable from the daemon's claude-code CLI

## Trigger (verbatim pattern to spot)

`ao spawn` returns `✔ Session <id> created` (worktree is created, sqlite has the row, tmux pane exists). Worker briefly shows `Churned for 0s` or `Brewed for 0s`, then the input box shows:

```
There's an issue with the selected model (X). It may not exist or you may not have access. Run /model to pick a different model.
```

The `paste again to expand` line stays at the bottom of the box. The worker is idle; tmux is alive; the brief sits in the input buffer claiming space.

## Symptom vs adjacent failure modes

| Failure mode | Surface error | When it fires | Remediation timing |
|---|---|---|---|
| Fifth (opencode 3-cycle idle-exit) | empty TUI banner, no Read/Bash tool call | ≤30s after spawn | kill + respawn same way (rare to succeed) |
| Sixth (Sonnet-5 quota block) | `You've hit your weekly limit · resets Jul 27 at 8pm` | ≤30s after spawn | wait for quota reset (~7d) |
| **Seventh (this one)** | `There's an issue with the selected model (X). It may not exist or you may not have access` | ≤30s after spawn | **swap config NOW + respawn** |

The seventh failure mode is a **one-time config probe** failure, not a recurring quota exhaustion. The model may exist on the upstream provider but the local auth/alias setup on this host does not include it. Probe a known-good alias and verify in 2 seconds.

## Verified recipe (2026-07-30, ai_universe project)

**Step 1 — Probe a known-good alias.** On this host, `sonnet`, `opus`, `haiku` all return `PONG` to:

```bash
timeout 30 claude -p --model sonnet 'Reply with exactly: PONG' 2>&1 | tail -3
# Expected: PONG
# Failure: "There's an issue with the selected model (sonnet). ..." → that alias does not work; try the next one.
```

`MiniMax-M3` (the value that was set on the ai_universe project) returns the same error the worker showed. So the model name is the problem, not the network.

**Step 2 — Locate the project row and its current `agentConfig.model`.**

```bash
sqlite3 ~/.ao/data/ao.db "SELECT id, config FROM projects WHERE id='<project>';"
# Example output (before fix):
# ai_universe|{"agentConfig":{"model":"MiniMax-M3","permissions":"bypass-permissions"}, ...}
```

The `config` field is JSON; `agentConfig.model` is the bad value. The dispatcher is the source of truth — the yaml file is NOT authoritative (see the `CRITICAL — agent-orchestrator.yaml is NOT the live project registry` block in the parent SKILL.md).

**Step 3 — Swap the model value in-place.**

```bash
sqlite3 ~/.ao/data/ao.db "UPDATE projects SET config = json_set(config, '$.agentConfig.model', 'sonnet') WHERE id='<project>';"
# Verify:
sqlite3 ~/.ao/data/ao.db "SELECT id, config FROM projects WHERE id='<project>';"
# Expect: ai_universe|{"agentConfig":{"model":"sonnet","permissions":"bypass-permissions"}, ...}
```

**Step 4 — Kill the bad session.** The current ao-go CLI removed `--purge-session`; the canonical form is:

```bash
~/bin/ao session kill -p <project> <id>
# Output: "session <id> killed (workspace preserved)"
# Verify:
sqlite3 ~/.ao/data/ao.db "SELECT id, is_terminated, activity_state FROM sessions WHERE id='<id>';"
# Expect: <id>|1|exited
```

The `workspace_path` (`$HOME/.ao/data/worktrees/<project>/<id>`) is preserved. The worker did not write any commits during the brief idle, so the worktree is effectively empty — leave it; the respawn will allocate a fresh one.

**Step 5 — Respawn with the corrected config.**

```bash
GH_TOKEN_VAL="$(gh auth token)"
AO_TOKEN_VAL="$(gh auth token)"
cd ~/.openclaw && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c '~/bin/ao spawn --project <project> --harness claude-code --name <slug> --prompt "<short summary pointing at ./AO-TASK-BRIEF.md>"'
```

Note the spawn flag is `--project` (long-only), not `-p`. The current ao-go CLI rejects `-p` as `unknown shorthand flag: 'p' in -p`.

## Pre-flight (cheap; run before the first spawn of the day)

```bash
# 1. Inspect the project model config
sqlite3 ~/.ao/data/ao.db "SELECT json_extract(config, '$.agentConfig.model') FROM projects WHERE id='<project>';"

# 2. If the model is anything other than one of these known-good values:
#      sonnet, opus, haiku, claude-sonnet-4-6, claude-opus-4-6
#    treat it as suspect and probe.
```

If the model is `MiniMax-M3` or any other unfamiliar alias, run Step 1 from the verified recipe above BEFORE `ao spawn` to avoid the wasted worktree + tmux cycle.

## Why this matters

The probe failure happens **after** the spawn CLI returns `✔ Session created` and **after** the tmux pane materializes. The orchestrator's lifecycle worker does not detect the model-alias error and never invokes the Sixth-failure-mode idle-exit cleanup. The result is a zombie-worker state that:

- Costs one worktree slot on disk (consumed but useless).
- Costs one tmux session (consumed but useless).
- Locks one spot in the 20-cap (counts until manually reaped).
- Does not produce any work output.

Without this recipe, the dispatcher tends to either re-spawn with the same model (same failure repeats, more slots burn) or to laboriously re-decode the `config` JSON to find the right json_set path. The pre-flight probe takes 5 seconds and prevents the 60-second cleanup cycle.

## Anti-patterns

- **Re-spawning the same task with the same model after the failure**: same alias error repeats, no chance of success.
- **Patching only the spawn prompt** (`--model sonnet` in the spawn args): the daemon-level `agentConfig.model` is read, not the spawn-prompt flag. Verify with `ao agent ls` that the spawn-prompt `--model` is actually honored — on this host it is not.
- **Editing `agent-orchestrator.yaml`**: stale backup, ignored by the daemon. Use `sqlite3` on `~/.ao/data/ao.db` directly.
- **Leaving the zombie session in place**: it counts against the 20-cap. Kill it before respawn.
