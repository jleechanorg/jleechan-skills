---
name: ao-worker-dispatch
description: Checklist for dispatching AO workers — python venv, commit discipline, branch drift, and post-push CodeRabbit verification
type: skill
---

# AO Worker Dispatch Checklist

**Canonical copy:** this file in the jleechanclaw harness repo (`skills/ao-worker-dispatch/SKILL.md`). Mirror to `~/.claude/skills/ao-worker-dispatch/SKILL.md` on machines that spawn AO workers (Cursor/Claude Code discover skills from `~/.claude/skills/`). See `docs/VERIFICATION_RULES_PLACEMENT.md` for why verification rules live here rather than only in global CLAUDE.md or per-repo CLAUDE.

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

## Spawn pattern — NEW work vs EXISTING PR (critical distinction)

### New work (feature, bead with no PR yet)
```bash
ao spawn <bead-id> -p <project>
ao send <session> --file <task-file>
```

### Existing PR fix (CR review, rebases, fixes to open PRs)
```bash
ao spawn <bead-id> -p <project>          # creates feat/<bead> branch
ao session claim-pr <PR-number> <session> # switches to actual PR branch, links PR so AO keeps session alive
ao send <session> "Fix PR #N (<branch>). Already on correct branch. Read: gh pr view N --json reviews. Fix actionable CR items. Use ./vpython. Commit early, push."
```

**Why claim-pr is mandatory for existing PRs**: Sessions on `feat/<bead>` branches with no PR get killed by AO cleanup. `claim-pr` switches the worktree to the real PR branch AND registers the PR linkage that prevents cleanup.

**Exception**: `claim-pr` fails if the PR branch is checked out in the main worktree. In that case, send a task telling the worker to `git fetch origin && git checkout -b local-fix origin/<branch>`.

## Overlap Detection (Pre-spawn)

Before spawning multiple workers on different beads, check for file-path overlap:

1. Run `br show <bead-id>` for each bead to get the description
2. Extract likely file paths from each description (e.g., "fix session-manager.ts" → `session-manager.ts`)
3. If two beads will modify the same file, **warn the operator**:
   - "bd-X and bd-Y both touch `session-manager.ts` — consider spawning only one, or steering the second away via `ao send`"
4. If overlap is confirmed, spawn the second worker with an explicit `ao send` after creation:
   - `ao send <session-id> "Do NOT modify [filename] — worker [other-session] is already handling it. Focus on [non-overlapping scope]."`

This prevents duplicate work where two workers independently fix the same pre-existing test failure or modify the same file.

## Pre-dispatch verification (orchestrator responsibility)
Before calling `ao spawn`, verify:
- [ ] Task prompt includes `./vpython` instruction
- [ ] Task prompt includes commit-early checkpoint
- [ ] Task prompt names the exact branch (not just "create a branch")
- [ ] Task prompt specifies what belongs in THIS PR vs future PRs
- [ ] **For existing PRs**: `ao session claim-pr <PR> <session>` is called immediately after spawn
- [ ] If the user specified an AO agent/runtime, the spawn command passes it explicitly (for example `--agent codex`)
- [ ] Check bead descriptions for overlapping file paths across workers

## Post-spawn verification (mandatory)

After every `ao spawn`, inspect the actual session metadata before trusting the worker:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path("~/.agent-orchestrator/<hash>-<project>/sessions/<session>").expanduser()
print(p.read_text())
PY
```

Confirm all of:
- `agent=<expected>`
- `pr=<expected PR URL>` when a PR was requested
- `runtimeHandle.data.launchCommand` contains the expected CLI

If the user asked for Codex workers, the session is invalid unless:
- `agent=codex`
- `launchCommand` contains `codex`

If verification fails, kill and respawn the session. Do not continue with a mismatched worker.

## Post-push CodeRabbit verification (worker responsibility)

CI passing does **not** imply CodeRabbit re-reviewed. The latest review can remain `CHANGES_REQUESTED` or `COMMENTED` until a new review is submitted **after** your fix push.

**After every push** that is meant to clear review feedback:

1. **Wait for GitHub checks** to finish (do not declare done while checks are `pending` or `in_progress`).
2. **Inspect CodeRabbit’s latest review** (must be tied to the current head or newer than your push):
   ```bash
   gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews \
     --jq '[.[] | select(.user.login=="coderabbitai[bot]")] | sort_by(.submitted_at) | .[-1] | {state, submitted_at}'
   ```
3. If state is not `APPROVED`, do **not** treat the PR as merge-ready. Post `@coderabbitai all good?` once checks have settled (see harness `CLAUDE.md` PR Green Loop), then re-check after a new review appears.
4. If the latest CR review’s `submitted_at` is **older than** the timestamp of your latest fix commit on the PR branch, assume review is **stale** until a new review lands.

Same pattern applies to other blocking checks: confirm the **bot state reflects the latest SHA**, not only that CI is green.

## Nudge triggers (when to intervene)
Send a nudge if the worker:
- Uses `python3` or any non-`./vpython` test runner
- Has >4 changed files with 0 commits at >40% context
- Is referencing a PR number that is not its own PR
- Has been "thinking" (Gitifying/Ebbing/Booping) for >10 minutes with no output
- Declares "done" or "ready for merge" while CodeRabbit’s latest review is not `APPROVED` at current head

## ao send broken pipe — retry pattern

`ao send <session> --file <path>` can fail with "Error: Broken pipe" on first attempt even when the session is alive. The session socket isn't ready to accept input immediately. **Retry once after a 1s delay.** This is not an auth or session death issue — it resolves on retry.

```bash
# Retry pattern for ao send
ao send wa-XXXX --file "$TASK_FILE" || {
  sleep 1
  ao send wa-XXXX --file "$TASK_FILE"
}
```

## Bead workspace context — br is workspace-sensitive

`br` (beads_rust) resolves the bead database from the **current working directory at invocation time**, not from the worktree the task targets. If you `cd` into a git worktree and run `br create`, the bead is written to the worktree's `.beads/` directory (a separate SQLite DB from `~/.beads/`). This means:
- `br list` from home won't see worktree beads
- `br list` from inside the worktree won't see home beads
- A bead ID like `$USER-xxxx` created from the worktree context is invisible from home `br show`

**Mitigation**: Always run `br` from the **same context** (home dir recommended) for consistency. If you suspect a bead went to the wrong DB, check both:
```bash
# Home beads DB
sqlite3 ~/.beads/beads.db "SELECT id, title FROM beads LIMIT 5;"
# Worktree beads DB (example path)
ls ~/.config/superpowers/worktrees/<project>/<worktree>/.beads/
sqlite3 ~/.config/superpowers/worktrees/<project>/<worktree>/.beads/beads.db "SELECT id, title FROM beads LIMIT 5;"
```

## Evidence of this skill working
- wa-57: 12 nudges required (no skill existed) → target: 0 nudges for python/commit issues
- Tracked in bead: rev-ceo5
