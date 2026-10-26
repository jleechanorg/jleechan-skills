---
name: ao-worker-dispatch
description: Checklist for dispatching AO workers — repository-owned test runners, commit discipline, branch drift, and review feedback
type: skill
---

# AO Worker Dispatch Checklist

**Canonical copy:** this file in the jleechanclaw harness repo (`skills/ao-worker-dispatch/SKILL.md`). Mirror to `~/.claude/skills/ao-worker-dispatch/SKILL.md` on machines that spawn AO workers (Cursor/Claude Code discover skills from `~/.claude/skills/`). See `docs/VERIFICATION_RULES_PLACEMENT.md` for why verification rules live here rather than only in global CLAUDE.md or per-repo CLAUDE.

## Mandatory prompt elements (add to EVERY ao spawn call)

### 1. Test runner
```
Use the target repository's documented test runner and test-layer contract.
For `testing_mcp/` in WorldArchitect, follow `testing_mcp/CLAUDE.md`: use its
direct `python3` invocation with explicit `PYTHONPATH`, never `vpython` or
pytest collection. Tests in `testing_mcp/` and `testing_ui/` require a real
running server and real services, except the explicit direct-provider schema
probe allow-list. Never infer a runner from a generic AO prompt.
```

### 2. Commit-early discipline
```
Commit a green unit after its scoped checks pass and its evidence is recorded;
do not wait for unrelated work. Follow the live task's authorization for push
and draft-PR creation. Do not use fixed context percentages as stop or push
thresholds; checkpoint before compaction and preserve the active worktree.
```

### 3. Branch verification (post-compaction)
```
After any context compaction event:
1. Run: git branch --show-current
2. Verify it matches your assigned branch: [BRANCH]
3. If wrong, do not edit or switch the current checkout blindly. Inspect status and worktree ownership, preserve unrelated work, and enter an approved isolated worktree pinned to the assigned revision.
```
```

### 4. Scope discipline
```
PR1 means PR1 ONLY. Do not add PR2 features to a PR1 branch.
If you discover out-of-scope code in the working tree, leave it untouched; isolate this task's explicit paths or report the concrete conflict. Never discard unrelated work.
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
ao send <session> "Fix the requested PR scope on its verified branch. Follow the target repository's test instructions; preserve unrelated work; commit green units and push only within the authorized task scope."
```

**Why claim-pr is mandatory for existing PRs**: Sessions on `feat/<bead>` branches with no PR get killed by AO cleanup. `claim-pr` switches the worktree to the real PR branch AND registers the PR linkage that prevents cleanup.

**Exception**: `claim-pr` fails if the PR branch is checked out in another worktree. Preserve that checkout and use `diskm worktree-new <repo-path> <local-branch> --base origin/<branch>` to create an isolated task checkout. Verify the returned path and exact base before editing.

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
- [ ] Task prompt names the target repository's documented test runner and test-layer contract
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

## Post-push review feedback (advisory)

CodeRabbit and Bugbot are optional advisory reviewers, not readiness, `/green`,
or merge gates. Read their feedback and take what is useful; do not wait for an
approval or ask a bot to approve.

After an authorized push that addresses review feedback:

1. If a new CodeRabbit review is available, inspect its scope and report it as advisory:
   ```bash
   gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews \
     --jq '[.[] | select(.user.login=="coderabbitai[bot]")] | sort_by(.submitted_at) | .[-1] | {state, submitted_at}'
   ```
2. Assess any carried review by its actual scope and commit delta under `pr-lifecycle`; a timestamp alone does not establish applicability.

Verify current-head CI and mergeability through the canonical owners; do not infer a required gate from reviewer-bot status.

## Worker follow-up

Use the full-history and two-sample protocol in `ao-session-monitor` before
deciding that a worker is stalled. A timer, short tail, or old activity
indicator alone is not a follow-up trigger. Steer only when an independent
current-state check shows a specific actionable problem and the task
authorizes steering.

Follow up only when an independent current-state check shows a specific,
actionable problem, such as a verified assigned-branch mismatch or a missing
required test/review step. Use canonical owners to classify CI and mergeability;
never use a bot state, tool timer, fixed context percentage, or short pane tail
as a gate.

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

**Mitigation**: Always invoke `br` from the intended workspace and follow the
target repository's Beads owner. If you suspect a bead was created in another
workspace, use supported `br` read-only commands from each exact workspace to
locate it. Do not inspect or edit raw `.beads` interchange files or databases;
follow `~/.claude/skills/beads-issue-tracking/SKILL.md` for recovery.

## Evidence of this skill working
- wa-57: 12 nudges required (no skill existed) → target: 0 nudges for python/commit issues
- Tracked in bead: rev-ceo5
