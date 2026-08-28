# mem0 — Hermes Shared Memory

Query and write to the shared mem0 qdrant store (`hermes_mem0`, 127.0.0.1:6333).
All agents (Claude, Codex, Hermes) share this store under `user_id=$USER`.

## Quick reference

```bash
# Search
python3 ~/.hermes/scripts/mem0_shared_client.py search "<query>"

# Add a fact (with LLM extraction)
python3 ~/.hermes/scripts/mem0_shared_client.py add "<text>"

# Add verbatim (no LLM, guaranteed write)
python3 ~/.hermes/scripts/mem0_shared_client.py add "<text>" --no-infer

# Stats
python3 ~/.hermes/scripts/mem0_shared_client.py stats
```

> Script path: `~/.hermes/scripts/mem0_shared_client.py`
> Requires `~/.hermes/hermes.json` with `plugins.entries.hermes-mem0.config.oss`
> Also callable from any repo worktree: `python3 scripts/mem0_shared_client.py <cmd>`

## Store status

- **Collection:** `hermes_mem0`
- **Host:** `127.0.0.1:6333` (qdrant docker, Hermes-managed storage)
- **Embedder:** Read from `~/.hermes/hermes.json` (`hermes-mem0` plugin)
- **LLM for extraction:** Read from `~/.hermes/hermes.json` (`hermes-mem0` plugin)

## Ingestion (backfill)

The extractor at `scripts/mem0_extract_facts.py` scans three sources:

| Source | Path | Agent ID |
|--------|------|----------|
| Hermes | `~/.hermes/` | `hermes` |
| Claude Code | `~/.claude/projects/` | `claude` |
| Codex | `~/.codex/sessions/` | `codex` |

Run a backfill (last 1 year = 525960 minutes):
```bash
cd ~/.hermes
python3 scripts/mem0_extract_facts.py --since 525960
```

Run incremental (last 65 min, for cron):
```bash
cd ~/.hermes
python3 scripts/mem0_extract_facts.py --since 65
```

Check state:
```bash
cat ~/.hermes/memory/extraction-state.json | python3 -m json.tool | head -20
```

## Current ingestion status

Use `python3 ~/.hermes/scripts/mem0_shared_client.py stats` for live status.

## When to use this skill

Use `/mem0` when the user asks to:
- Search memory for past decisions, branch names, bead IDs, preferences
- Add a new fact that should persist across agent sessions
- Check ingestion status or trigger a backfill
- Debug why an agent doesn't remember something
