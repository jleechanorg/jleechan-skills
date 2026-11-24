---
name: swarm-gemini
description: Run a parallel swarm using Antigravity/Gemini CLI's built-in `swarm` tool (shared message board) instead of `invoke_subagent` or `run_workflow`.
---

# /swarm-gemini — Antigravity Built-in Swarm (`swarm` tool)

Use the built-in **`swarm`** tool (`default_api:swarm`) directly to coordinate parallel workers on the shared message board. Do **not** fall back to `invoke_subagent` or `run_workflow` unless the built-in `swarm` tool is unavailable in the current runtime.

## How to run

1. Optionally set a short board title with `swarm(action="title", title="...")`.
2. Spawn workers with `swarm(action="add", name="<worker>", brief="<what it owns and what done looks like>", workspace="inherit|share|branch")`:
   - Use `share` or `branch` for writers editing/building concurrently; keep `inherit` for readers/verifiers.
   - Default `model="gemini-4-hydrogen-medium"` (`Gemini 4 Hydrogen (Medium)`, matching `flash` tier) unless the user requests another model.
   - Pass `tasks` or `n` when sharding homogeneous work across `<name>-1`..`<name>-<k>`.
3. End your turn without polling; the shared board wakes you when workers reply.
4. Verify real outputs before accepting completion, and `swarm(action="kill", name="...")` only after landing any `share`/`branch` work.
