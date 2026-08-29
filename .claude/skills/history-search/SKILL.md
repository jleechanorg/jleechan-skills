---
name: history-search
description: Multi-source conversation history search across Claude Code, Codex, and Hermes — runs all three in parallel.
type: search
scope: user
---

# /history Search Skill

> ⚠️ **QUOTA GUARD — this is the DEEP/heavy search skill.**
> The default `/history` command now uses `conversation-history-sparse/SKILL.md` (3 sources, tight budget).
> This skill is invoked only via `/history --deep` or when the sparse search explicitly returns insufficient results.
> **Model**: Default to `gpt-5.3-codex-spark` when parent session is Codex (for research/history lookup work). Override to `gpt-5.6-sol` only if Spark demonstrably fails.
> **Dedup**: Check for in-flight identical threads before spawning any parallel blocks:
> `sqlite3 ~/.codex/state_5.sqlite "SELECT id FROM threads WHERE first_user_message LIKE '%QUERY%' AND tokens_used=0 AND created_at_ms>(unixepoch('now')-1800)*1000 LIMIT 1;"`

Searches Claude Code JSONL, Codex SQLite threads, Hermes messages (FTS5), and Antigravity conversations in parallel.

## Sources

| Source | Data | Path |
|--------|------|------|
| Claude Code | JSONL per session | `~/.claude/projects/*/*.jsonl` |
| Codex | SQLite threads + first message | `~/.codex/state_5.sqlite` |
| Hermes | Messages with FTS5 | `~/.hermes/state.db` |
| Antigravity | Markdown exports | `~/Library/CloudStorage/Dropbox/conversation-backups/antigravity/` |
| OpenCode | Session diff JSON | `~/.local/share/opencode/storage/session_diff/` |
| Cursor | Prompt history + chats | `~/.cursor/prompt_history.json`, `~/.cursor/chats/` |

## Execution

When `/history <query>` is invoked, run these searches **in parallel** as subagents (or parallel Bash blocks), then merge and display results.

### Parallel block A — Claude Code JSONL search

```python
import json, glob, os, sys, datetime

query = "<QUERY>"  # inject search terms
limit = 20
results = []

files = sorted(
    glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")),
    key=os.path.getmtime, reverse=True
)

for path in files:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if query.lower() in line.lower():
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    role = obj.get("type") or obj.get("message", {}).get("role", "?")
                    content = ""
                    msg = obj.get("message", {})
                    if isinstance(msg.get("content"), str):
                        content = msg["content"]
                    elif isinstance(msg.get("content"), list):
                        for c in msg["content"]:
                            if isinstance(c, dict) and c.get("type") == "text":
                                content = c.get("text", ""); break
                    ts = obj.get("timestamp", "")
                    project = os.path.basename(os.path.dirname(path))
                    results.append({
                        "source": "claude",
                        "project": project,
                        "ts": ts,
                        "role": role,
                        "snippet": content[:200].replace("\n", " "),
                        "file": os.path.basename(path),
                    })
                    if len(results) >= limit:
                        break
    except Exception:
        pass
    if len(results) >= limit:
        break

for r in results:
    print(f"[Claude] {r['ts'][:10]} | {r['project'][:40]} | {r['role']} | {r['snippet']}")
```

### Parallel block B — Codex thread search

```python
import sqlite3, os, datetime

query = "<QUERY>"
db = os.path.expanduser("~/.codex/state_5.sqlite")
if not os.path.exists(db):
    print("[Codex] DB not found"); exit()

con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

like = f"%{query}%"
rows = cur.execute("""
    SELECT title, first_user_message, cwd, git_branch,
           datetime(created_at/1000,'unixepoch','localtime') as created
    FROM threads
    WHERE (title LIKE ? OR first_user_message LIKE ?)
      AND archived = 0
    ORDER BY created_at DESC
    LIMIT 20
""", (like, like)).fetchall()

for title, first_msg, cwd, branch, created in rows:
    snippet = (first_msg or "")[:200].replace("\n", " ")
    proj = os.path.basename(cwd) if cwd else "?"
    print(f"[Codex] {created[:10]} | {proj} | {branch or 'main'} | {title[:50]} | {snippet}")

con.close()
```

Note: Codex `state_5.sqlite` stores `created_at` in milliseconds (Unix ms). Use `created_at/1000` in epoch conversion.

### Parallel block C — Hermes FTS5 search

```python
import sqlite3, os

query = "<QUERY>"
db = os.path.expanduser("~/.hermes/state.db")
if not os.path.exists(db):
    print("[Hermes] DB not found"); exit()

con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

try:
    rows = cur.execute("""
        SELECT s.title, s.source, datetime(m.timestamp,'unixepoch','localtime') as ts,
               m.role, substr(m.content, 1, 200)
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)
        ORDER BY m.timestamp DESC
        LIMIT 20
    """, (query,)).fetchall()
except sqlite3.OperationalError:
    # Fallback to standard LIKE substring query on FTS parse errors (e.g. colons or hyphens)
    like_q = f"%{query}%"
    rows = cur.execute("""
        SELECT s.title, s.source, datetime(m.timestamp,'unixepoch','localtime') as ts,
               m.role, substr(m.content, 1, 200)
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.content LIKE ? OR m.tool_name LIKE ? OR m.tool_calls LIKE ?
        ORDER BY m.timestamp DESC
        LIMIT 20
    """, (like_q, like_q, like_q)).fetchall()

for title, source, ts, role, snippet in rows:
    clean = (snippet or "").replace("\n", " ")
    print(f"[Hermes] {ts[:10]} | {source} | {title or '?'[:50]} | {role} | {clean}")

con.close()
```

### Parallel block D — Antigravity Markdown search

```python
import os, glob, re

query = "<QUERY>"
antigrav_dir = os.path.expanduser("~/Library/CloudStorage/Dropbox/conversation-backups/antigravity/")
if not os.path.exists(antigrav_dir):
    print("[Antigravity] No exports found")
else:
    results = []
    for path in sorted(glob.glob(f"{antigrav_dir}/*.md"), key=os.path.getmtime, reverse=True)[:50]:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if query.lower() in content.lower():
                # Extract title and first match
                title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                title = title_match.group(1)[:60] if title_match else os.path.basename(path)[:60]
                # Find snippet around match
                idx = content.lower().find(query.lower())
                start = max(0, idx - 50)
                end = min(len(content), idx + 150)
                snippet = content[start:end].replace("\n", " ").strip()
                # Get date from file
                ts = os.path.getmtime(path)
                import datetime
                date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                results.append((date, title, snippet))
        except Exception:
            pass
    for date, title, snippet in results[:20]:
        print(f"[Antigravity] {date} | {title[:60]} | {snippet[:150]}")

### Parallel block E — OpenCode session diff search

```python
import os, glob, json

query = "<QUERY>"
session_dir = os.path.expanduser("~/.local/share/opencode/storage/session_diff/")
if not os.path.exists(session_dir):
    print("[OpenCode] No sessions found")
else:
    results = []
    for path in sorted(glob.glob(f"{session_dir}/*.json"), key=os.path.getmtime, reverse=True)[:100]:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if query.lower() in content.lower():
                title = os.path.basename(path).replace(".json", "")[:60]
                idx = content.lower().find(query.lower())
                start = max(0, idx - 50)
                snippet = content[start:start+200].replace("\n", " ").strip()
                ts = os.path.getmtime(path)
                import datetime
                date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                results.append((date, title, snippet))
        except Exception:
            pass
    for date, title, snippet in results[:20]:
        print(f"[OpenCode] {date} | {title[:60]} | {snippet[:150]}")

### Parallel block F — Cursor prompt history search

```python
import os

query = "<QUERY>"
hist_path = os.path.expanduser("~/.cursor/prompt_history.json")
if not os.path.exists(hist_path):
    print("[Cursor] No prompt history found")
else:
    results = []
    with open(hist_path, encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if query.lower() in line.lower():
                clean = line.strip()[:200]
                results.append(clean)
                if len(results) >= 20:
                    break
    for prompt in results:
        print(f"[Cursor] | {prompt[:150]}")

### Parallel block G — git fsck --lost-found scan

For each worktree under candidate locations (passed as a positional arg, defaulting to `$HOME/projects/`):

```bash
for wt in $(git -C <location> worktree list --porcelain | grep -E '^worktree ' | awk '{print $2}'); do
  dangling=$(git -C "$wt" fsck --lost-found --no-reflogs --no-progress 2>/dev/null | grep "^dangling commit" || true)
  if [ -n "$dangling" ]; then
    for sha in $dangling; do
      subject=$(git -C "$wt" log -1 --format="%h %s" "$sha" 2>/dev/null)
      files=$(git -C "$wt" diff-tree --no-commit-id --name-only -r "$sha" 2>/dev/null | wc -l)
      echo "[fsck:$wt] $subject ($files files)"
    done
  fi
done
```

**Why**: when investigating "lost" work, dangling commits are the first place to look. The 2026-06-22 PR-B'' incident had 751 dangling commits in the candidate worktree, one of which (`7d72209`) held the full 13-file diff the parent agent declared "lost."

## Output format

After collecting results from all parallel blocks, display as:

```
=== History Search: "<query>" ===

📁 Claude Code  (N matches)
  2026-05-14 | -Users-$USER-worldarchitect | user | "text snippet..."
  ...

🤖 Codex  (N matches)
  2026-05-10 | worldarchitect | main | "thread title" | "first message..."
  ...

⚡ Hermes  (N matches)
  2026-05-16 | slack | "session title" | user | "message snippet..."
  ...

🚀 Antigravity  (N matches)
  2026-05-23 | "conversation title" | snippet...
  ...

📦 OpenCode  (N matches)
  2026-05-22 | session_diff_id | "snippet..."
  ...

🖥️ Cursor  (N matches)
  "prompt from history..."
  ...
```

## Memory read (Phase 0)

Before running search, check Claude project memory for relevant context:

```bash
project_key=$(git rev-parse --show-toplevel 2>/dev/null | sed 's|/|-|g')
grep -i "<QUERY>" ~/.claude/projects/${project_key}/memory/*.md 2>/dev/null | head -5
```

## Filter flags

- `--recent N` — restrict to last N days: add `AND ts > unixepoch('now','-N days')` to SQL
- `--source claude|codex|hermes` — skip the other two blocks
- `--limit N` — cap each source at N (default 20)
- `--date YYYY-MM` — filter by month: `LIKE '2026-05%'` on timestamps

## Notes

- Codex `first_user_message` can be very large (entire system prompts). Truncate display to 200 chars.
- Claude JSONL files are ordered newest-first by mtime. Stop after `limit` matches total, not per file.
- Hermes FTS5 uses standard SQLite FTS5 syntax: `"exact phrase"`, `word1 AND word2`, `word*` prefix.
- Hermes `messages_fts` indexes `content + tool_name + tool_calls` — tool results also searchable.
