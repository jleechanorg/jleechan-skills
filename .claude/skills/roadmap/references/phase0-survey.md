# Phase 0 survey (optional context gathering)

Supporting material for `/roadmap`. This file describes **only** how to gather
context before writing a board. It is not a workflow, it runs nothing on its own,
and it does not define output: the required structure and every reporting rule live
in [`../SKILL.md`](../SKILL.md) and remain mandatory.

Run these steps when the board needs history — prior docs, earlier decisions,
existing tracked items. Skipping them is valid, especially for a status-only board.

## 1. Prior memory

Read Claude auto-memories for roadmap-relevant context, filtered by keyword rather
than read in full.

```python
import subprocess, glob, os
try:
    git_root = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'], text=True).strip()
    project_key = git_root.replace('/', '-')   # keep the leading dash
    memory_dir = os.path.expanduser(f'~/.claude/projects/{project_key}/memory/')
    memory_files = glob.glob(os.path.join(memory_dir, '*.md'))
except Exception:
    memory_files = []

keywords = ['roadmap', 'planning', 'architecture', 'decision', 'goal']
relevant = []
for f in memory_files:
    try:
        with open(f, encoding='utf-8') as handle:
            if any(k in handle.read().lower() for k in keywords):
                relevant.append(f)
    except OSError:
        continue
```

Report any hits as `📍 From Memory`.

## 2. Existing roadmap documents

Look for an existing document that already covers this topic before creating a new
one. Search the roadmap repository, not the current code repository — the board
lives in the roadmap repo (see `../SKILL.md` § Output document).

```python
import subprocess, os, glob
roadmap_repo = subprocess.check_output(
    ['git', '-C', os.path.expanduser('~/roadmap'), 'rev-parse', '--show-toplevel'],
    text=True).strip()
docs = glob.glob(os.path.join(roadmap_repo, '*.md'))
```

For each candidate, show its title (first `#` heading, else filename) and
modification date. Flag a keyword match against filenames or the first five lines
as `EXISTING — consider updating`.

## 3. Tracked items

Find related open items so a board references them instead of duplicating them.

```bash
br list --status open
```

Abort only this step if `br` exits non-zero. Keyword-match the output against the
current task; report hits as `EXISTING BEADS — update these instead of creating new ones`.

## 4. Situation summary

Before writing the board, report concisely:

- N existing roadmap documents found (titles)
- N related open beads found (IDs and titles)
- N memory entries found
- Recommendation: update an existing document, or create a new one

Then write the board in the mandatory format from `../SKILL.md`.
