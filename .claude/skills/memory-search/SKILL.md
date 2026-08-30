---
name: memory-search
description: "Search across all memory systems — ~/roadmap, beads, claude memories, hermes sqlite, hermes briefings, hermes index, openclaw memories, wiki, history, and slack. Use whenever the user asks to search memories, find something in memories, or looks for anything that might have been captured in any memory store. Trigger on: 'search memories', 'find in my memories', '/ms', '/memory_search', 'search across all memories', 'look up in memory', 'did I save this somewhere', 'do I have anything about X in memory'."
---

# Memory Search

Lightweight parallel search across all memory sources. Cache hits bypass the full search.

## Cache

Cache dir: `~/llm_wiki/.cache/memory-search/`

- **Lookup**: Check cache first — if `query-hash.json` exists and TTL not expired, return cached results
- **Write**: After all sources return, write merged results to cache
- **TTL**: 1 hour default (override per-query if needed)
- **Key**: SHA-256 of canonicalized query (lowercased, stripped stop words)

## Memory Sources

1. **~/roadmap** — Project roadmaps and planning docs (`~/roadmap/`)
2. **beads** — Issue/bead tracking (`~/.claude/projects/*/memory/*.md` or `.beads/issues.jsonl`)
3. **claude memories** — Session memories (`~/.claude/projects/*/memory/`)
4. **hermes sqlite** — `~/.hermes/state.db` (3.6 GB Hermes state; table `messages`; FTS5 via `messages_fts`). **Note**: `~/.hermes/memory.db` is 0 bytes (empty); the data lives in `state.db`.
5. **hermes briefings** — `~/.hermes/memory/briefing-*.md` and `mcp-mail-ack-log.md`
6. **hermes index** — `~/.hermes/MEMORY.md`
7. **openclaw memories** — `~/openclaw-repo/MEMORY.md`, `~/.hermes/memory/`
8. **wiki** — `~/llm_wiki/` (via wiki-search)
9. **history** — `~/.claude/projects/*/*.jsonl`
10. **slack** — Slack messages, threads, and DMs via `mcp__slack__*` (channels the user has access to)

Note: Mem0 (Qdrant at localhost:6333) not directly searchable — skip.

## Codex model routing

In Codex sessions, every memory-search subagent and search task MUST set
`model: gpt-5.3-codex-spark` and `reasoning_effort: medium` explicitly.
Never spin up Sol for memory search; this fan-out is lookup and scan work.

## Execution

Run all searches in parallel via `/e` subagents:

```
/e Search ~/roadmap for "$QUERY". List files with matching snippets.

/e Search beads for "$QUERY" using: br search "$QUERY" --json 2>/dev/null | head -40. NEVER read .beads/issues.jsonl directly — it is 1MB+ and forbidden. Also check ~/.claude/projects/*/memory/*.md for matching bead IDs and titles.

/e Search ~/.claude/projects/*/memory/ for "$QUERY". Search MEMORY.md indexes and individual .md files. Show snippets.

/e Search ~/.hermes/state.db (Hermes state, 3.6GB): use the FTS5 index with Python fallback for safety — python3 -c "import sqlite3, os, datetime; db=os.path.expanduser('~/.hermes/state.db'); con=sqlite3.connect(f'file:{db}?mode=ro', uri=True); cur=con.cursor(); q='''$QUERY'''; m_q=f'%{q}%'; get_dt=lambda ts: datetime.datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S') if ts else ''; try: rows=cur.execute('''SELECT m.timestamp, m.role, substr(coalesce(m.content,m.tool_name,m.tool_calls),1,200) FROM messages_fts f JOIN messages m ON m.id=f.rowid WHERE messages_fts MATCH ? LIMIT 20''', (q,)).fetchall() except sqlite3.OperationalError: rows=cur.execute('''SELECT m.timestamp, m.role, substr(coalesce(m.content,m.tool_name,m.tool_calls),1,200) FROM messages m WHERE m.content LIKE ? OR m.tool_name LIKE ? OR m.tool_calls LIKE ? LIMIT 20''', (m_q, m_q, m_q)).fetchall(); print('\n'.join(f'[{get_dt(ts)}|{role}] {snip.strip().replace(\"\n\", \" \")}' for ts, role, snip in rows))" — FTS5 trigram tokenizer matches partial words without full-table LIKE scans. **Do NOT use `~/.hermes/memory.db` (0 bytes, no tables).**


/e Search ~/.hermes/memory/briefing-*.md and ~/.hermes/memory/mcp-mail-ack-log.md for "$QUERY" using: grep -m 5 -n "$QUERY" ~/.hermes/memory/briefing-*.md ~/.hermes/memory/mcp-mail-ack-log.md 2>/dev/null | head -20. The -m 5 per-file limit prevents reading full large files.

/e Search ~/.hermes/MEMORY.md for "$QUERY". Show matching entries.

/e Search ~/openclaw-repo/MEMORY.md and ~/.hermes/memory/ for "$QUERY". Show snippets.

/wiki-search $QUERY

/e Search ~/.claude/projects/*/*.jsonl for "$QUERY" using two-phase partial read: (1) grep -rl "$QUERY" ~/.claude/projects/*/*.jsonl 2>/dev/null | head -5 to get matching filenames without reading content; (2) for each file: grep -m 2 "$QUERY" <file> 2>/dev/null | cut -c1-200 to get up to 2 matching lines, truncated to 200 chars each. Full command: grep -rl "$QUERY" ~/.claude/projects/*/*.jsonl 2>/dev/null | head -5 | xargs -I{} grep -m 2 "$QUERY" {} 2>/dev/null | cut -c1-200 | head -20. The -m 2 flag stops grep after 2 matches per file so it never reads to EOF. DO NOT use grep -H without -m (reads full file).

/e Search Slack for "$QUERY" using mcp__slack__conversations_search_messages with search_query="$QUERY" and limit=10 (covers public, private, IM, MPIM — every channel the user has access to). For each match, extract: channel name + id, user, ts, snippet (first 200 chars of text), and a Slack permalink constructed as https://<workspace>.slack.com/archives/<channel_id>/p<ts_no_dot> (strip the dot from ts, e.g. 1781312751.587299 → 1781312751587299). Return the top 5 matches sorted by relevance. If conversations_search_messages returns 0 results OR fails (rate limit / scope), fall back to: (1) mcp__slack__channels_list with channel_types="public_channel,private_channel,im" to enumerate channels the user is in; (2) mcp__slack__conversations_history on the most recent 5 channels with limit=20 each, grep for the query locally; (3) mcp__slack__conversations_unreads for unreads. If the user names a specific channel/thread URL, you can also call mcp__slack__conversations_replies on the thread_ts — but only if explicitly given. DO NOT include this source if mcp__slack__ tools are not connected in the current session — log "Slack MCP unavailable" and skip.
```

## Aggregation

Wait for all 10 subagents. Merge results into sections:

```
# Memory Search: "$QUERY"

## ~/roadmap
[results]

## Beads
[results]

## Claude Memories
[results]

## Hermes SQLite
[results]

## Hermes Briefings
[results]

## Hermes Index
[results]

## OpenClaw
[results]

## Wiki
[results]

## History
[results]

## Slack
[results]
```

If a source returns nothing, mark as "— no matches". Sort by relevance within each section.
