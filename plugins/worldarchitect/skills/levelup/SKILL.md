---
name: levelup
description: Run WorldArchitect's streamlined DeepSeek level-up checks on the current checkout or its exact PR preview.
scope: WorldArchitect AI level-up testing
---

# /levelup

The default command runs the two real-browser checks wired into the WorldArchitect daily job, using DeepSeek v4.1 Flash via OpenRouter.

- A story-ready Level 1 Paladin starts at 299 XP and exercises the real crossing, Level 2 review, Finish, and reload path.
- A separate fresh campaign follows browser character creation and ordinary gameplay through Level 2 and Level 3. It verifies each crossing, any repair, review, Finish, and saved state.

The results remain separate by scenario, and both affect the command exit status. Streaming receipts, state snapshots, and existing browser evidence are collected for each lane. The runner checks effective provider settings before gameplay and reports provider identity from streaming requests.

## Run

From the WorldArchitect checkout, the default selects the current PR's exact preview when available, then runs locally when no eligible preview exists.

```bash
.claude/skills/levelup/levelup.sh
```

The shared skill shim delegates to this repository-owned entry point. It resolves the product checkout from `PROJECT_ROOT`, then `REPO_ROOT`, then the current Git worktree. For example, when invoking the installed skill outside a checkout:

```bash
PROJECT_ROOT=/path/to/worldarchitect.ai ~/.claude/skills/levelup/local.sh
```

Pass `--local` to force a local server, `--server <url>` for an explicit target, or `--daily-scenario crossing-299` / `organic-level-3` to run one browser journey. `--model <registry-id>` overrides the default model.

Use `--mcp` to run the same two journeys through the MCP harness. Use `--diagnostics` or explicit legacy MCP scenario arguments to run the broader diagnostic sweep. These flags delegate to the WorldArchitect-owned runner and preserve its provider, auth, evidence, and test-account policy.

The GitHub `/levelup` preview workflow invokes the same streamlined MCP default against the PR preview.

## Failure handling

A missing checkout entrypoint fails before any test launches. A wrong effective or observed provider fails preflight and invalidates that lane. A successful repair is reported separately from the first crossing. Both browser lanes must pass for the default command to pass.
