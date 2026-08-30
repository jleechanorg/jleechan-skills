---
description: /history_resume — search history for current branch/worktree and resume work with full context
type: llm-orchestration
execution_mode: immediate
---

# /history_resume

Auto-detect the current branch, worktree, and open PRs, then search all history sources and produce a **resume briefing** — what was being worked on, current state, and what to do next.

## Phase 0 — Gather current context (run in parallel)

Run ALL of the following bash blocks simultaneously:

### Block 1 — Git context
```bash
echo "=== BRANCH ===" && git branch --show-current
echo "=== STATUS ===" && git status --short
echo "=== LAST 5 COMMITS ===" && git log --oneline -5
echo "=== UPSTREAM ===" && git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "(no upstream)"
```

### Block 2 — Open PRs for current branch
```bash
BRANCH=$(git branch --show-current)
gh pr list --state open --head "$BRANCH" --json number,title,url,mergeable,reviewDecision,statusCheckRollup 2>/dev/null || echo "(no open PRs)"
```

### Block 3 — Recent Claude JSONL user messages for this project
```python
import json, glob, os

project_dir = os.getcwd()
project_key = project_dir.replace("/", "-").lstrip("-")
jsonl_dir = os.path.expanduser(f"~/.claude/projects/{project_key}")

files = sorted(
    glob.glob(f"{jsonl_dir}/*.jsonl"),
    key=os.path.getmtime, reverse=True
)

msgs = []
for path in files[:10]:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    msg = obj.get("message", {})
                    if msg.get("role") == "user":
                        content = ""
                        if isinstance(msg.get("content"), str):
                            content = msg["content"]
                        elif isinstance(msg.get("content"), list):
                            for c in msg["content"]:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    content = c.get("text", ""); break
                        ts = obj.get("timestamp", "")
                        if content and len(content) > 15 and not content.startswith("#"):
                            msgs.append((ts, content[:400]))
                except: pass
    except: pass

seen = set()
for ts, content in sorted(msgs, reverse=True)[:10]:
    k = content[:40]
    if k not in seen:
        seen.add(k)
        print(f"[{ts[:16]}] {content[:300]}")
        print()
```

### Block 4 — Recent Codex threads for this dir
```python
import sqlite3, os, sys

db = os.path.expanduser("~/.codex/state_5.sqlite")
if not os.path.exists(db): print("[Codex] not found"); sys.exit()

cwd = os.getcwd()
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

rows = cur.execute("""
    SELECT title, first_user_message, git_branch,
           datetime(created_at/1000,'unixepoch','localtime') as created
    FROM threads
    WHERE cwd LIKE ? AND archived = 0
    ORDER BY created_at DESC
    LIMIT 10
""", (f"%{os.path.basename(cwd)}%",)).fetchall()

for title, first_msg, branch, created in rows:
    snippet = (first_msg or "")[:300].replace("\n", " ")
    print(f"[{created}] branch={branch}")
    print(f"  title: {(title or '?')[:80]}")
    print(f"  msg:   {snippet[:250]}")
    print()

con.close()
```

## Phase 1 — CI failure triage (if PR found)

If an open PR was found in Block 2, extract the PR number and run:

```bash
gh pr view <PR_NUMBER> --json statusCheckRollup | python3 -c "
import sys, json
checks = json.load(sys.stdin).get('statusCheckRollup', [])
failures = [(c.get('name'), c.get('conclusion') or c.get('state')) for c in checks
            if (c.get('conclusion') or c.get('state','')) not in ('SUCCESS','SKIPPED','NEUTRAL','')]
for name, status in failures:
    print(f'FAIL: {status} | {name}')
if not failures:
    print('All checks passing or skipped')
"
```

## Phase 2 — Produce resume briefing

After collecting all parallel results, synthesize this **concise resume briefing**:

```
=== RESUME BRIEFING ===

Branch: <branch>
Directory: <cwd>
Last commit: <sha> <message>

Open PR: #<N> <title>
  URL: <url>
  Mergeable: <yes/no>  Review: <decision>

CI status:
  FAILING: <list of failing checks>
  PASSING: <count> checks

Uncommitted changes:
  <git status --short output, or "none">

What was being worked on:
  <2-3 sentence summary from history + PR context>

Suggested next step:
  <specific actionable recommendation based on CI failures, uncommitted changes, stop hook condition, last user message>
```

## Notes

- If no open PR exists for the branch, focus on `git status` and Codex/Claude history to infer the task.
- If there are uncommitted changes, highlight them prominently — they may be the in-progress work.
- Stop hook conditions found in history should be surfaced as the active goal.
- Use parallel execution for all Phase 0 blocks — never run sequentially.
