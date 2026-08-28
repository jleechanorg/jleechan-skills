# mem0 — OpenClaw Shared Memory

Query and write to the shared mem0 qdrant store (`openclaw_mem0`, 127.0.0.1:6333).
All agents (Claude, Codex, OpenClaw) share this store under `user_id=$USER`.

## Quick reference

```bash
# Search
python3 ~/.openclaw/scripts/mem0_shared_client.py search "<query>"

# Add a fact (with LLM extraction)
python3 ~/.openclaw/scripts/mem0_shared_client.py add "<text>"

# Add verbatim (no LLM, guaranteed write)
python3 ~/.openclaw/scripts/mem0_shared_client.py add "<text>" --no-infer

# Stats
python3 ~/.openclaw/scripts/mem0_shared_client.py stats
```

> Script path: `~/.openclaw/scripts/mem0_shared_client.py`
> Requires `~/.openclaw/openclaw.json` — symlinked to `~/project_jleechanclaw/jleechanclaw/openclaw.json`
> Also callable from any repo worktree: `python3 scripts/mem0_shared_client.py <cmd>`

## Store status

- **Collection:** `openclaw_mem0`
- **Host:** `127.0.0.1:6333` (qdrant docker, bind-mount at `~/.openclaw/qdrant_storage`)
- **Embedder:** OpenAI `text-embedding-3-small` (1536 dims) — requires `$OPENAI_API_KEY`
- **LLM for extraction:** `gpt-4o-mini`

## Ingestion (backfill)

The extractor at `scripts/mem0_extract_facts.py` scans three sources:

| Source | Path | Agent ID |
|--------|------|----------|
| OpenClaw | `~/.openclaw/agents/` | `claw-main` |
| Claude Code | `~/.claude/projects/` | `claude` |
| Codex | `~/.codex/sessions/` | `codex` |

Run a backfill (last 1 year = 525960 minutes):
```bash
cd ~/project_jleechanclaw/worktree_memory_followups3
python3 scripts/mem0_extract_facts.py --since 525960
```

Run incremental (last 65 min, for cron):
```bash
python3 scripts/mem0_extract_facts.py --since 65
```

Check state:
```bash
cat ~/.openclaw/memory/extraction-state.json | python3 -m json.tool | head -20
```

## Current ingestion status (as of 2026-03-14)

- **Tracked sessions:** 442 / ~2795 total (openclaw: 207, claude: 211, codex: 24)
- **Facts in store:** 166 points
- **Last run:** 2026-03-14T09:47:17Z
- **Status:** Partial — backfill of ~/.claude/projects (1502 dirs) and ~/.codex/sessions (1086) not complete

## When to use this skill

Use `/mem0` when the user asks to:
- Search memory for past decisions, branch names, bead IDs, preferences
- Add a new fact that should persist across agent sessions
- Check ingestion status or trigger a backfill
- Debug why an agent doesn't remember something
