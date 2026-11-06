# AO spawn: silent session-record landed, no fresh worktree (added 2026-07-14, PR #8290)

**Date:** 2026-07-14
**Affected session record:** `worldarchitect-41..44` (4 zombie entries for PR #8290 spawn attempts)
**Failure mode:** distinct from `ao-spawn-cap-zombie-recovery.md` (Round-7) — the daemon returns `INTERNAL_ERROR` after a long timeout AND silently inserts a row into the session table WITHOUT spinning up a worker / worktree / prompt buffer.

## Symptom

Spawning an AO worker with `ao spawn --project <P> --name <NAME> --prompt "<brief>"` returns:

```
- Creating session
... [30-180s of silence] ...
INTERNAL_ERROR
exit code: 0 (no nonzero exit to surface the failure)
```

`ao session ls` shows NO matching entries (`{"jobs": []}` or empty array). But on disk, four rows exist:

```
~/.ao/data/worktrees/worldarchitect/worldarchitect-41/
~/.ao/data/worktrees/worldarchitect/worldarchitect-42/
~/.ao/data/worktrees/worldarchitect/worldarchitect-43/
~/.ao/data/worktrees/worldarchitect/worldarchitect-44/
```

Inspection of the worktree directory reveals the smoking gun: each contains `.agent_prompt_pr-2162-gemini-3-upgrade..txt` (or similar PRIOR-PR filename) **instead of** the prompt that was just sent. The worktrees are leftovers from a previous failed dispatch; the new spawn retried against the SAME slot numbers but did NOT actually create fresh worker state.

```bash
ls $HOME/.ao/data/worktrees/worldarchitect/worldarchitect-44/
# → AGENTS.md CLAUDE.md GEMINI.md ... (real your-project.com files)
# → .agent_prompt_pr-2162-gemini-3-upgrade..txt   <-- SMOKING GUN

cat $HOME/.ao/data/worktrees/worldarchitect/worldarchitect-44/.agent_prompt_pr-2162-gemini-3-upgrade..txt | head -5
# → (verbatim copy of the prior PR-2162 dispatch brief, NOT my PR-8290 brief)
```

## Why this happens (root cause)

When AO's `POST /api/v1/sessions` hangs in the agent-check preflight (Codex install / Claude OAuth token verification / harness health probe), the daemon:

1. **Persists the session row** in the orchestrator's session table (id + project + name) so it shows up in `ao session ls`.
2. **Does NOT create a worktree** — the worktree allocator step never runs.
3. **Times out at the gateway-level timeout** (60-180s), returning `INTERNAL_ERROR` to the CLI.

When the agent retries with the SAME `--name`, the daemon **reuses the old slot number** (e.g. `worldarchitect-41`) but does not reset the slot's on-disk state. The `worldarchitect-44/` directory is leftover from a much earlier PR-2162 spawn attempt, and the agent-check preflight timeout on retry never cleans it up.

The smoking-gun file `.agent_prompt_<PR-N>.txt` is the keystone: it's the `.agent_prompt` artifact the daemon writes WHEN IT WAS GOING TO spawn a worker — but the slot's on-disk state was from a PRIOR spawn that already wrote a different prompt.

This is distinct from the Round-7 cap-rejection path (`ao-spawn-cap-zombie-recovery.md`): Round-7 zombies are alive-but-stuck session rows; Round-8 zombies are **partial slot allocations that never became workers**.

## Verify the zombie is real

```bash
# 1. Check daemon healthz / readyz
curl -fsS -m 5 http://localhost:3001/healthz
curl -fsS -m 5 http://localhost:3001/readyz

# 2. Check disk for orphan worktrees
ls $HOME/.ao/data/worktrees/<project>/

# 3. Check the .agent_prompt_*.txt contents — confirm it's NOT your brief
for wt in $HOME/.ao/data/worktrees/<project>/<project>-*/; do
  echo "=== $wt ==="
  ls "$wt"/.agent_prompt_*.txt 2>/dev/null | head -3
  echo "  first 3 lines:"
  head -3 "$wt"/.agent_prompt_*.txt 2>/dev/null
done

# 4. Cross-check with the recent AO project session count
curl -fsS http://localhost:3001/api/v1/projects | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d.get('projects', []):
    print(f\"  {p.get('name'):30s}  sessions={p.get('session_count')}/{p.get('max_sessions')}\")
"
```

If the disk shows `worldarchitect-XX/` worktrees with `.agent_prompt_*.txt` referencing a PRIOR PR's brief, the slot is contaminated and the current spawn will never produce a worker for the new PR.

## Three-step recovery

**Step 1 — Kill the contaminated slot rows.** `ao session kill <session-id>` returns success but the worktree can persist if the slot didn't fully initialize. Run for each zombie:

```bash
for sid in 41 42 43 44; do
  timeout 5 ao session kill "worldarchitect-$sid" 2>&1 | head -3
done
```

**Step 2 — Wipe the on-disk worktree state.** The daemon doesn't auto-clean partial slot allocations; remove the directory so the slot allocator can reuse the number:

```bash
# CAREFUL — this deletes a worktree. Verify it has NO uncommitted work first.
for wt in $HOME/.ao/data/worktrees/worldarchitect/worldarchitect-{41,42,43,44}/; do
  echo "=== $wt ==="
  git -C "$wt" status --short --branch 2>&1 | head -3
  echo "(if empty above, safe to remove)"
done
# After verification:
# rm -rf $HOME/.ao/data/worktrees/worldarchitect/worldarchitect-{41,42,43,44}/
```

**Step 3 — Bounce the daemon (only if Steps 1+2 don't unstick the spawn).** `launchctl bootout gui/$(id -u)/com.<org>.ao` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.<org>.ao.plist`. This clears in-memory slot state.

After these three steps, retry `ao spawn --project <P> --name <NEW-NAME>` (use a fresh `--name` to avoid slot collision). If it still hangs at the agent-check preflight, the daemon has a deeper problem — pivot to inline.

## Pivot-to-inline fallback

When the AO daemon is healthy (`healthz` + `readyz` pass) but `POST /sessions` consistently hangs past 180s, the inline drive-to-green path is:

1. **`git worktree add <NEW-WORKTREE> <PR-HEAD-SHA>`** — create a worktree at the PR head, not on the branch yet.
2. **`git switch <branch>` from inside the worktree** — but ONLY if no other worktree holds that branch. If a stale worker holds the branch (e.g. `wa-3310`), `git switch` errors with `'<branch>' is already checked out at <path>`. **Before detaching, verify whether origin/<branch> has moved past the stale worker's recorded HEAD.** Three cases:
   - **Case A — origin/<branch> is at or behind stale-worker's HEAD:** the worker never pushed (or pushed an older commit). Safest detach: `git -C <stale-worker> switch --detach <stale-worker's base SHA from reflog>` so recoverable history is preserved.
   - **Case B — origin/<branch> is AHEAD of stale-worker's HEAD (force-push happened elsewhere):** the stale worker's branch pointer is stale. Re-attach to origin first: `git -C <stale-worker> reset --hard origin/<branch>` (no uncommitted work to lose), THEN the new worktree can simply take the branch via `git switch <branch>` from itself (no detach needed).
   - **Case C — branch is in a "Merge remote-tracking branch into ..." state (a prior agent was mid-merge when it exited):** the merge state lives in `.git/MERGE_HEAD` inside the stale worktree. Run `git -C <stale-worker> merge --abort` first to clear the mid-merge state, then apply Case A or B.
   **NEVER `git branch -D <branch>`** to forcibly release it from the stale worktree — that destroys the reflog and any unpushed commits. Detach-with-reflog or reset-to-origin preserves recovery options.
   ```bash
   # Detection helper:
   STALE_HEAD=$(git -C <stale-worker> rev-parse HEAD)
   ORIG_HEAD=$(git -C <main-repo> rev-parse origin/<branch>)
   if git -C <stale-worker> merge-base --is-ancestor $STALE_HEAD $ORIG_HEAD; then
     echo "Case B: origin ahead — safe to reset stale to origin"
     git -C <stale-worker> reset --hard origin/<branch>
   elif [ -f <stale-worker>/.git/MERGE_HEAD ]; then
     echo "Case C: mid-merge — abort then apply A or B"
     git -C <stale-worker> merge --abort
   else
     echo "Case A: stale is ahead — detach to its base SHA"
     STALE_BASE=$(git -C <stale-worker> reflog | tail -1 | awk '{print $1}')
     git -C <stale-worker> switch --detach $STALE_BASE
   fi
   ```
   Real incident (PR #8290, 2026-07-14): wa-3310 was Case B — origin/feat/daily-level-up-2026-07-08 was at `3cbbaf6b7c`, but wa-3310 was at `d41d26d4f1` (the prior agent's local merge commit). Resetting wa-3310 to origin freed the branch cleanly with no history loss.
3. **`git merge --no-ff origin/main`** — resolve conflicts inline (often just 1-2 files; for PR #8290 it was `$PROJECT_ROOT/tests/test_prompt_embedding_store.py`, resolved by taking origin/main which had a Round-8 fix from PR #8381/8394).
4. **`vpython -m pytest <prompt-tests>`** — smoke-test the merge did not regress prompts.
5. **Sync evidence gist** via `sync-evidence-metadata.sh` (use the multi-file recipe in `evidence-gate-multi-metadata-filename-trap-2026-07-14.md`).
6. **`git push --force-with-lease origin <branch>`** — the standard green-Gate-trigger path. ALWAYS use `--force-with-lease`, not `--force`.
7. **`gh workflow run <GREEN-GATE-WF> --repo <OWNER>/<REPO> --ref <branch> -f pr_number=<N> -f head_sha=<NEW-SHA>`** + **`gh workflow run <EVIDENCE-GATE-WF> -f pr_sha=<NEW-SHA>`**.
8. **Arm babysit cron** with `ao-babysit/scripts/babysit.py --cron-job-id <id>` — every 5m for 30 ticks is the canonical cadence.

This inline path takes 5-15 min of agent time for the merge + tests + push + trigger sequence; AO spawn + babysit would otherwise take the same wall-clock via the worker.

## Pitfalls (BANNED)

1. **Banned — assuming "ao session ls is empty" means the spawn didn't land.** The CLI returns the slot-allocation row even when no worker is materialized. ALWAYS check `~/.ao/data/worktrees/<project>/` for orphan directories before concluding the spawn failed completely.
2. **Banned — re-running the same `ao spawn --name <NAME>` after a 60-180s timeout.** The slot is contaminated; you need a fresh `--name` (different string) AND ideally a manual worktree cleanup. The daemon does NOT garbage-collect on retry.
3. **Banned — killing the AO daemon process directly with `kill -9`.** Use `launchctl bootout` then `launchctl bootstrap` so the launchd supervisor restarts it cleanly. `kill -9` leaves the daemon's slot allocator in an unknown state and the next spawn will be worse.
4. **Banned — deleting `$HOME/.worktrees/<org>/<stale-worker>` without first detaching it from any branch it holds.** The branch pointer is global to the repo; deleting the worktree dir without `git worktree remove` (or detaching first) leaves the branch in a dangling state until `git worktree prune` is run.

## Cross-references

- `references/ao-spawn-cap-zombie-recovery.md` — Round-7 sibling: cap-rejection zombie cleanup. The two failure modes are different but the verification recipes overlap.
- `references/evidence-gate-multi-metadata-filename-trap-2026-07-14.md` — Round-8 sibling: evidence gist filename trap. Pair this with the multi-file sync recipe when the inline pivot path lands a /green dispatch.
- `~/.hermes/skills/ao-babysit/scripts/babysit.py` — the post-spawn observe-only loop. The inline pivot path's step 8 (arm babysit) is the same regardless of whether the worker was an AO session or the inline session.
- PR #8290 thread C0AH3RY3DK6/1784030452.318509 — originating incident. Four zombie worldarchitect-4{1,2,3,4} slots persisted; pivot-to-inline landed merge commit `aff95f87e3` directly from the gateway session.