---
name: ao-worker-dispatch
description: Checklist for dispatching AO workers — prevents recurring python binary, commit discipline, and branch drift failures
type: skill
---

# AO Worker Dispatch Checklist

## Mandatory prompt elements (add to EVERY ao spawn call)

### 1. Python binary
```
ALWAYS use `./vpython -m pytest` for ALL test runs.
NEVER use `python3`, `python3.11`, or any system Python.
./vpython activates the project venv which has all required deps (flask_cors, gunicorn, etc.).
```

### 2. Commit-early discipline
```
Commit after the FIRST test passes. Do not wait for all tests to pass.
Push and open a draft PR before you reach 30% context.
Rule: uncommitted work at >40% context = compaction risk = lost work.
```

### 3. Branch verification (post-compaction)
```
After ANY context compaction event:
1. Run: git branch --show-current
2. Verify it matches your assigned branch: [BRANCH]
3. If wrong: git checkout [BRANCH] before touching any file.
```

### 4. Scope discipline
```
PR1 means PR1 ONLY. Do not add PR2 features to a PR1 branch.
If you discover PR2 code in your working tree: git checkout -- <file> to discard it.
```

## Pre-dispatch verification (orchestrator responsibility)
Before calling `ao spawn`, verify:
- [ ] Task prompt includes `./vpython` instruction
- [ ] Task prompt includes commit-early checkpoint
- [ ] Task prompt names the exact branch (not just "create a branch")
- [ ] Task prompt specifies what belongs in THIS PR vs future PRs

## Nudge triggers (when to intervene)
Send a nudge if the worker:
- Uses `python3` or any non-`./vpython` test runner
- Has >4 changed files with 0 commits at >40% context
- Is referencing a PR number that is not its own PR
- Has been "thinking" (Gitifying/Ebbing/Booping) for >10 minutes with no output

## Evidence of this skill working
- wa-57: 12 nudges required (no skill existed) → target: 0 nudges for python/commit issues
- Tracked in bead: rev-ceo5
