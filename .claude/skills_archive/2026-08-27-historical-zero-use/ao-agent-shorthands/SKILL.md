---
name: ao-agent-shorthands
description: "Read ~/.hermes/agent-orchestrator.yaml BEFORE declaring an --agent <X> value unsupported. Lists plugin shorthands (wafer, minimax, agy)."
---

# AO provider agent shorthands (wafer, minimax, zai, agy/antigravity)


**MANDATORY — resolve `--agent` from config before declaring unsupported:**
When the user specifies `--agent <X>` and `<X>` is not a well-known CLI name you recognize, **read `~/.hermes/agent-orchestrator.yaml` (or the active AO config) FIRST.** The `defaults.agent` key and installed plugins define agent shorthands. Never scan `packages/agent-*/` directories as a substitute. Never declare an agent unsupported without reading the config.

```bash
# Step 1 — always do this when --agent value is unfamiliar:
head -20 ~/.hermes/agent-orchestrator.yaml   # check defaults.agent
```

| Shorthand | Binary / mechanism | Notes |
|-----------|-------------------|-------|
| `--agent agy` / `--agent antigravity` | `~/.local/bin/agy` (Google Antigravity / Gemini CLI) | **Default agent** in `~/.hermes/agent-orchestrator.yaml` (`defaults.agent: antigravity`) |
| `--agent wafer` | `claude` CLI → `https://pass.wafer.ai` | `WAFER_API_KEY`, default model `GLM-5.1` |
| `--agent minimax` | `claude` CLI → `https://api.minimax.io/anthropic` | `MINIMAX_API_KEY`, server-selected model |
| `z.ai/model` prefix | `claude` → `https://api.z.ai/api/anthropic` | `GLM_API_KEY`, model in prefix |

The `claude-code` plugin supports inline model prefixes for all three: `wafer.ai/GLM-5.1`, `z.ai/claude-4`, `MiniMax-M2.7`. Dedicated `--agent` plugins are preferred for wafer and minimax. Z.AI uses inline prefix only (no dedicated agent plugin).

**Integration tests:** `packages/integration-tests/src/agent-{wafer,minimax,zai}.integration.test.ts` — real tmux + real API, auto-skip when keys missing.
