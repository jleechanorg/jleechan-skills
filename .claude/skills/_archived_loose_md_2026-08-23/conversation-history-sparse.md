---
description: Sparse conversation history triage for current repo/worktree using ~/.claude/projects and ~/.codex/sessions with strict context budgets.
type: analysis
scope: project
---

# Conversation History Sparse

## Purpose

Infer what the current directory/worktree/branch has been doing by sampling only high-signal history from:
- `~/.claude/projects`
- `~/.codex/sessions`

Use this skill when you need orientation, forensic context, or session continuity without loading full transcripts.

## Hard Limits

- Never `cat` full history files.
- Prefer metadata and first/last small samples.
- Default sample budget:
  - At most 3 candidate files per source.
  - At most 3 user prompts per file.
  - At most 200 chars per prompt.
- Exclude assistant thinking/tool payload blobs unless explicitly required.

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

### 3) Sample Claude prompts only (sparse)

Use a small parser to print:
- newest 2-3 JSONL files
- first 3 user prompts per file (truncated)

Do not print full JSONL lines.

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

Then sample only recent user messages from the newest file.

### 5) Synthesize result

Return:
- Current branch/PR intent from git.
- Recent request themes from Claude history.
- Recent request themes from Codex history.
- One concise statement: "This worktree appears focused on X because Y+Z evidence."

## Output Template

```text
Branch/PR:
- ...

Claude history (sparse):
- ...

Codex history (sparse):
- ...

Inference:
- ...
```

## Safety

- Read-only operations only.
- Do not modify `~/.claude/projects` or `~/.codex/sessions`.
- Keep excerpts short to avoid pulling excessive context into the session.
