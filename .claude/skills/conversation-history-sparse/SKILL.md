---
name: conversation-history-sparse
description: Sparse conversation history triage across Claude Code, Codex, Hermes, agy CLI, and Cursor with strict context budgets. Default for `/history`; covers all five canonical sources.
type: analysis
scope: project
---

# Conversation History Sparse

## Purpose

Infer what the current directory/worktree/branch has been doing by sampling only high-signal history from:
- `~/.claude/projects`  (Claude Code JSONL)
- `~/.codex/sessions`   (Codex rollout JSONL) + `~/.codex/state_5.sqlite` threads
- `~/.hermes/state.db`  (Hermes messages, FTS5)
- `~/.gemini/antigravity-cli/conversation_summaries.db` (agy CLI SQLite summaries + brain logs)
- `~/.cursor/prompt_history.json` + `~/.cursor/chats/` + `~/.cursor/projects/*/agent-transcripts/` (Cursor)

Use this skill whenever `/history` runs without `--deep`, when you need orientation
without loading full transcripts, or when you want a quick multi-source sweep.

## Fast CLI Helper

Run the dedicated sparse history search helper:

```bash
# Sparse overview across all 5 sources
python3 scripts/history_search.py

# Query with substring highlight across all sources
python3 scripts/history_search.py "query string"

# Single source with JSON output
python3 scripts/history_search.py "query" --source agy --json
```

## Hard Limits

- Never `cat` full history files.
- Prefer metadata and first/last small samples.
- Default sample budget:
  - At most 3 candidate files per source.
  - At most 3 user prompts per file.
  - At most 200 chars per prompt.
- For Hermes & agy (SQLite DBs): apply the same per-snippet 200-char cap; cap the
  total hits at ≤ 5 by default, ≤ 20 hard maximum. FTS5 MATCH on common words
  can return tens of thousands of rows — never `SELECT *` without a LIMIT.
- Exclude assistant thinking/tool payload blobs unless explicitly required.
- Search Hermes last — its FTS5 is the slowest of the sources.

## Output Formatting (ANSI helper)

Apply terminal coloring to every per-source line so multi-source results are visually
distinct. The user invokes `/history` to **see** the matches — bold-yellow highlight
of the matched query substring plus per-source colored labels is what makes the
output readable at a glance. Respect `NO_COLOR=1` (https://no-color.org/) and
non-TTY outputs (e.g. piped to file) by stripping ANSI codes.

```python
import os, re, sys

# Disable colors when explicitly requested or stdout isn't a TTY.
USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

ANSI = {
    "claude": "\033[34m",      # blue
    "codex":  "\033[36m",      # cyan
    "hermes": "\033[35m",      # magenta
    "agy":    "\033[33m",      # yellow
    "cursor": "\033[32m",      # green
    "head":   "\033[1;37m",    # bold white
    "match":  "\033[1;33m",    # bold yellow (substring highlight)
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}

def color(name: str, text: str) -> str:
    if not USE_COLOR:
        return text
    c = ANSI.get(name, "")
    return f"{c}{text}{ANSI['reset']}" if c else text

def ansify(source: str, body: str, query: str = "") -> str:
    """Wrap a result line: colored [Source] label + yellow-highlight matches.
    Highlight is applied to the BODY ONLY — never the label — so a query that
    happens to equal the source name (e.g. query='claude' for `[Claude]`) does
    not visually tangle the brackets."""
    label = color(source, f"[{source.title()}]")
    line_body = body
    if query and USE_COLOR:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        line_body = pattern.sub(lambda m: color("match", m.group(0)), line_body)
    return f"{label} {line_body}"

def head(text: str) -> str:
    return color("head", text)
```

Use `ansify("claude", "...", query)`, `ansify("codex", "...", query)`,
`ansify("hermes", "...", query)`, `ansify("agy", "...", query)`, and
`ansify("cursor", "...", query)` for each result line. Wrap section headers in
`head(...)`. The Query itself is **always** a literal substring highlight (display
only); it never drives routing or intent — the workflow above decides.

## Workflow

### 1) Establish local git intent first

```bash
git branch --show-current
git log --oneline -n 8
gh pr view --json number,title,headRefName,baseRefName,state,url
```

### 2) Find exact Claude project folder for cwd

```bash
find ~/.claude/projects -maxdepth 1 -type d | rg "worktree[-_]$(basename "$PWD")|$(basename "$PWD")"
find ~/.claude/projects -type f -name '*.jsonl' -print0 | \
  xargs -0 rg -n --max-count 20 --fixed-strings "\"cwd\":\"$PWD\"" 2>/dev/null
```

### 3) Sample Claude prompts only (sparse + colored)

Use a small parser to print:
- newest 2-3 JSONL files
- first 3 user prompts per file (truncated)

Do not print full JSONL lines. Wrap each prompt line with `ansify("claude", ...)` so the
per-source label is blue and the matched query substring is yellow.

```python
import json, glob, os, re, sys

use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
colors = {"claude": "\033[34m", "head": "\033[1;37m", "match": "\033[1;33m", "reset": "\033[0m"}
def color(name, text):
    return f"{colors[name]}{text}{colors['reset']}" if use_color else text
def head(text): return color("head", text)
def ansify(source, body, query=""):
    if query and use_color:
        body = re.sub(re.escape(query), lambda m: color("match", m.group(0)), body, flags=re.I)
    return f"{color(source, '[' + source.title() + ']')} {body}"

query = os.environ.get("HIST_QUERY", "")
# Broad recency is intentional on this developer machine: start with cwd-matched
# files when available, then fill the bounded sample from other local projects.
all_files = glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
cwd_project_key = os.getcwd().replace("/", "-")
cwd_matches = [p for p in all_files if cwd_project_key in os.path.dirname(p)]
files = (
    sorted(cwd_matches, key=os.path.getmtime, reverse=True)
    + sorted([p for p in all_files if p not in cwd_matches], key=os.path.getmtime, reverse=True)
)[:3]
shown = 0
for path in files:
    proj = os.path.basename(os.path.dirname(path))
    print(head(f"📁 Claude Code — {proj}"))
    n = 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                obj = json.loads(line)
                msg = obj.get("message", {})
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                content = c.get("text", ""); break
                    if content and len(content) > 15:
                        n += 1
                        ts = obj.get("timestamp", "")[:16]
                        snippet = content[:200].replace("\n", " ")
                        print(ansify("claude", f"{ts} | {snippet}", query))
                        if n >= 3: break
            except Exception:
                pass
    shown += 1
    if shown >= 3: break
```

### 4) Find matching Codex rollout sessions for cwd

```bash
python3 - <<'PY'
from pathlib import Path
import os
cwd = os.getcwd()
files = []
for p in Path.home().glob(".codex/sessions/*/*/*/rollout-*.jsonl"):
    try:
        with open(p, "r", encoding="utf-8") as f:
            if cwd in f.readline():
                files.append(p)
    except Exception:
        pass
for p in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
    print(p)
PY
```

Then sample only recent user messages from the newest file. Also probe
`~/.codex/state_5.sqlite threads WHERE cwd LIKE '%<basename>%' ORDER BY created_at DESC LIMIT 5`
for the thread view (title + first message, 200 chars each). Wrap each row with
`ansify("codex", ..., query)` so the label is cyan and the matched substring is yellow.

```python
import sqlite3, os
db = os.path.expanduser("~/.codex/state_5.sqlite")
if not os.path.exists(db):
    print("[Codex] DB not found"); raise SystemExit
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

basename = os.path.basename(os.getcwd())
q   = os.environ.get("HIST_QUERY", "")
like = f"%{q}%" if q else f"%{basename}%"

# Title/first-message match if a query is set; cwd-bucket match otherwise.
date_expr = """
    CASE WHEN created_at > 100000000000
         THEN datetime(created_at/1000, 'unixepoch', 'localtime')
         ELSE datetime(created_at, 'unixepoch', 'localtime')
    END
"""
if q:
    sql = f"""
        SELECT title, substr(first_user_message,1,200), cwd, git_branch,
               {date_expr} as created
        FROM threads
        WHERE (title LIKE ? OR first_user_message LIKE ?) AND (archived = 0 OR archived IS NULL)
        ORDER BY created_at DESC LIMIT 5
    """
    params = (like, like)
else:
    sql = f"""
        SELECT title, substr(first_user_message,1,200), cwd, git_branch,
               {date_expr} as created
        FROM threads
        WHERE (cwd LIKE ? OR cwd IS NULL) AND (archived = 0 OR archived IS NULL)
        ORDER BY created_at DESC LIMIT 5
    """
    params = (f"%{basename}%",)

rows = cur.execute(sql, params).fetchall()
for t, m, cwd_, branch, ts in rows:
    proj  = (cwd_ or "?").rsplit("/", 1)[-1]
    title = (t or "?")[:40]
    snippet = (m or "").replace("\n", " ")[:200]
    body = f"{ts[:10]} | {proj} | {branch or 'main'} | {title} | {snippet}"
    print(ansify("codex", body, q))
con.close()
```

### 5) Sample Hermes messages (sparse FTS5 + colored)

Hermes is user-scoped, not cwd-scoped — search globally via FTS5 with a tight LIMIT.
Always read `~/.hermes/state.db` in **read-only** mode and never dump full `content`.
Wrap every result line with `ansify("hermes", ..., query)` so the label is magenta
and matched substrings are yellow.

```python
import sqlite3, os, sys

query = "<QUERY>"  # injected by /history
db = os.path.expanduser("~/.hermes/state.db")
if not os.path.exists(db):
    print("[Hermes] state.db not found"); sys.exit()

con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

# Per-snippet 200-char cap; LIMIT 5 by default (20 hard cap, enforced by /history --limit).
LIMIT = 5

try:
    rows = cur.execute("""
        SELECT s.title, s.source,
               datetime(m.timestamp,'unixepoch','localtime') as ts,
               m.role, substr(m.content, 1, 200)
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (query, LIMIT)).fetchall()
except sqlite3.OperationalError:
    # Fallback for FTS5 parse errors (colons, hyphens, multi-byte chars)
    like_q = f"%{query}%"
    rows = cur.execute("""
        SELECT s.title, s.source,
               datetime(m.timestamp,'unixepoch','localtime') as ts,
               m.role, substr(m.content, 1, 200)
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.content LIKE ? OR m.tool_name LIKE ? OR m.tool_calls LIKE ?
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (like_q, like_q, like_q, LIMIT)).fetchall()

for title, source, ts, role, snippet in rows:
    clean = (snippet or "").replace("\n", " ")
    body  = f"{ts[:10]} | {source} | {(title or '?')[:50]} | {role} | {clean}"
    print(ansify("hermes", body, query))

con.close()
```

> Note: `messages_fts` indexes only the `content` column. Tool-name / tool-call
> hits require the `LIKE` fallback. FTS5 syntax: `"exact phrase"`, `word1 AND word2`,
> `word*` prefix.

### 6) Sample agy CLI conversations (sparse SQLite)

agy CLI (Antigravity CLI wrapper at `~/.local/bin/agy`) stores conversation
metadata in a SQLite summaries DB. Read-only, capped at ≤5 rows. Per-snippet
200-char cap. Wrap every result line with `ansify("agy", ..., query)` so the
label is yellow and matched substrings are yellow-highlighted.

```python
import sqlite3, os

query = "<QUERY>"  # injected by /history
db = os.path.expanduser("~/.gemini/antigravity-cli/conversation_summaries.db")
if not os.path.exists(db):
    print("[Agy] conversation_summaries.db not found")
else:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.cursor()

    q   = os.environ.get("HIST_QUERY", "")
    cwd_basename = os.path.basename(os.getcwd())
    like_q = f"%{q}%" if q else f"%{cwd_basename}%"

    LIMIT = 5
    try:
        rows = cur.execute("""
            SELECT conversation_id, title, substr(preview, 1, 200),
                   step_count, last_modified_time, workspace_uris, agent_name
            FROM conversation_summaries
            WHERE (title LIKE ? OR preview LIKE ? OR workspace_uris LIKE ?)
              AND (killed = 0 OR killed IS NULL)
            ORDER BY last_modified_time DESC
            LIMIT ?
        """, (like_q, like_q, like_q, LIMIT)).fetchall()
    except sqlite3.OperationalError:
        # Fallback: most-recent N conversations matching the basename heuristic
        rows = cur.execute("""
            SELECT conversation_id, title, substr(preview, 1, 200),
                   step_count, last_modified_time, workspace_uris, agent_name
            FROM conversation_summaries
            WHERE workspace_uris LIKE ?
              AND (killed = 0 OR killed IS NULL)
            ORDER BY last_modified_time DESC
            LIMIT ?
        """, (f"%{cwd_basename}%", LIMIT)).fetchall()

    for cid, title, preview, steps, mtime, ws, agent in rows:
        snippet = (preview or "").replace("\n", " ")[:200]
        steps_str = f"steps={steps}" if steps is not None else "steps=?"
        body = f"{(mtime or '')[:10]} | {(title or '?')[:40]} | {agent or 'agy'} | {steps_str} | {snippet}"
        print(ansify("agy", body, q))
    con.close()
```

When the DB is missing entirely (agy CLI not installed), print a single
`[Agy] conversation_summaries.db not found` line and continue.

### 7) Sample Cursor conversations (sparse JSON + chats)

Cursor stores a flat prompt history file plus per-conversation chat blobs and agent transcripts.
Read-only. Per-snippet 200-char cap. ≤3 prompt hits total. Wrap every line with
`ansify("cursor", ..., query)` so the label is green and matched substrings
are yellow.

```python
import json, os, glob

query = "<QUERY>"  # injected by /history
q   = os.environ.get("HIST_QUERY", "")
hist_path = os.path.expanduser("~/.cursor/prompt_history.json")
LIMIT = 3
hits = 0

if os.path.exists(hist_path):
    try:
        with open(hist_path, encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        if isinstance(data, list):
            for entry in reversed(data):
                text = ""
                if isinstance(entry, dict):
                    text = entry.get("prompt") or entry.get("text") or entry.get("content") or ""
                elif isinstance(entry, str):
                    text = entry
                if not text:
                    continue
                if q and q.lower() not in text.lower():
                    continue
                snippet = text[:200].replace("\n", " ")
                ts = ""
                if isinstance(entry, dict):
                    ts = (entry.get("timestamp") or entry.get("ts") or "")[:16]
                print(ansify("cursor", f"prompt_history {ts} | {snippet}", q))
                hits += 1
                if hits >= LIMIT:
                    break
    except Exception:
        pass

# Then sample recent chat files (avoid full reads — first 1-2KB each).
chats_dir = os.path.expanduser("~/.cursor/chats")
if os.path.isdir(chats_dir) and hits < LIMIT:
    chat_files = sorted(glob.glob(f"{chats_dir}/**/*.json*", recursive=True),
                        key=lambda p: os.path.getmtime(p), reverse=True)[:2]
    for path in chat_files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                chunk = f.read(2048)
            snippet = chunk[:200].replace("\n", " ")
            if q and q.lower() not in snippet.lower():
                continue
            label = os.path.basename(path)[:50]
            print(ansify("cursor", f"chat {label} | {snippet}", q))
            hits += 1
            if hits >= LIMIT:
                break
        except Exception:
            pass

if hits == 0:
    print(ansify("cursor", "no matches in prompt_history or chats/", q))
```

> Note: `prompt_history.json` may be very large (>150 KB). The snippet is read
> as parsed JSON then sliced — never `cat` the raw file. Chat JSON files are
> sampled via `f.read(2048)` so we never pull a full conversation into context.

### 8) Synthesize result

Return:
- Current branch/PR intent from git.
- Recent request themes from Claude history.
- Recent request themes from Codex history.
- Recent Hermes hits (per-snippet 200 chars only).
- Recent agy conversations (preview/title only).
- Recent Cursor prompts (one-liner each).
- One concise statement: "This worktree appears focused on X because Y+Z evidence."

## Output Template

```text
Branch/PR:
- ...

📁 Claude Code (N matches)        ← head() — bold white
  [Claude] 2026-08-01T23:54 | Is /history doing the sparse search?...
                                  ↑ blue label
                                  "sparse search" highlighted yellow

🤖 Codex (N matches)              ← head() — bold white
  [Codex] 2026-08-01 | wt-pr-8661 | pr-8661-iter | PR #8661 review...
                                  ↑ cyan label
                                  "PR" highlighted yellow

⚡ Hermes (N matches)             ← head() — bold white
  [Hermes] 2026-08-01 | slack | PR review | assistant | Reviewer B re-run is dispatched...
                                  ↑ magenta label
                                  "Reviewer" highlighted yellow (if it was the query)

🌐 agy CLI (N matches)           ← head() — bold white
  [Agy] 2026-08-01 | Fix CR lint error | agy | steps=42 | ...
                                  ↑ yellow label
                                  matched substring highlighted yellow

🖥️  Cursor (N matches)           ← head() — bold white
  [Cursor] prompt_history 2026-08-01 | How do I scaffold a new feature?
                                  ↑ green label
                                  "scaffold" highlighted yellow

Inference:
- ...
```

## Safety

- Read-only operations only.
- Open Hermes DB **and agy conversation_summaries.db** with `mode=ro` URI —
  never write to `~/.hermes/state.db` or `~/.gemini/antigravity-cli/`.
- Do not modify `~/.claude/projects`, `~/.codex/sessions`, `~/.cursor/chats/`,
  or `~/.gemini/history.jsonl`.
- Keep excerpts short to avoid pulling excessive context into the session.
- ANSI highlighting is **display-only** — never let it influence search/routing.
- When the user types `/history --deep`, escalate to
  `~/.claude/skills/history-search/SKILL.md` (7 sources, larger budget).
