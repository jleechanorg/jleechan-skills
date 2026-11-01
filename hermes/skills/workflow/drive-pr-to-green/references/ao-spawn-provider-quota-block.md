# ao-spawn-provider-quota-block — third distinct dispatch failure mode

**Added 2026-07-06, jleechanorg `self-hosted-mikey` cleanup (bead `$USER-zcxt`)** — distinct from `ao-spawn-rate-limit-wedge` (GH API bucket exhaustion) and `ao-spawn-cap-zombie-recovery` (session-cap full of `[spawning]` rows). This is the **provider-side per-user subscription quota** (e.g. Claude/Gemini per-user monthly allotment), not a token-quota reset and not a GH-API rate limit.

## Symptoms (all observed in one session, jc-1957)

1. `ao spawn -p <project> "<task>"` returns shell `exit_code 124` after 120s timeout — looks identical to the documented `ao-spawn-rate-limit-wedge` false-failure.
2. The corresponding tmux session IS created (`tmux list-sessions` shows `953501c04ccc-jc-1957`).
3. But on `tmux capture-pane`, the worker shows:

   ```
   ⚠ Individual quota reached. Please upgrade your subscription to increase your
   limits. Resets in 40m1s.
   Error ID: 3fe91b44fe3540bbb9c2746f8873f937
   ```

   …then sits at the prompt with no work done. Within ~3 minutes, `ao status` shows the worker as `[exited]`.
4. **Asymmetric failure mode**: a second sibling dispatch (`ao-6918` for `agent-orchestrator`) shows in `ao session ls` as `[spawning]` but **never materializes a tmux session at all** — orchestrator eats the spawn attempt and reports `idle` indefinitely. No Error ID, no pane content.

## Distinguishing this from the other two failure modes

| Signal | rate-limit-wedge | zombie-recovery | provider-quota-block (this one) |
|---|---|---|---|
| `gh api rate_limit` GraphQL bucket | 0/5000 | full or partial | full or partial (GH API unrelated) |
| `ao session ls` shows N rows | N high | N = cap | N correct (≤ cap) |
| tmux pane shows | nothing / garbled | normal boot | "Individual quota reached" error |
| Worker exits within | never (wedged on GH API) | never (wedged on cap) | ≤ 3 min, state=`[exited]` |
| Sibling dispatch same project | often fails the same way | fails with "cap exceeded" | first worker shows quota error, second never materializes tmux |
| Recovery time | wait for `reset_graphql` epoch (~5–60 min) | kill zombies + retry immediately | wait for provider quota reset (~40 min per the error message) |

## Recovery recipe

### Step 1 — Diagnose

Before pivoting, **prove the worker hit a quota error, not a normal timeout**. The 120s shell timeout on `ao spawn` is ambiguous on its own — verify the worker is dead:

```bash
# Capture the tmux pane for the failed worker
tmux capture-pane -t <tmux-name> -p -S -50 | tail -30

# Look for one of:
#   - "Individual quota reached. Please upgrade your subscription..."
#   - "Error ID: <uuid>"
#   - empty pane with just the cursor and `? for shortcuts` footer
```

If you see "Individual quota reached" or an Error ID, you're in quota-block territory. If you see a normal Claude boot sequence that just hasn't gotten to your message yet, wait one more 30s cycle — that's a normal slow boot, not a quota block.

### Step 2 — Decide: inline vs. wait

Two paths. **Pick the inline path only when the diff qualifies for the `pr-green-dispatch` COMMIT's exception.**

**Inline path (when the diff is ≤ 20 lines across ≤ 2 files, trivially correct, no architectural judgment)** — same threshold the COMMIT defines for skipping AO dispatch entirely:

1. Do NOT retry `ao spawn` (will hit the same quota block).
2. Create fresh worktrees per repo off `origin/main`:

   ```bash
   # For each repo that needs a change
   git -C $HOME/<repo> worktree add \
     $HOME/.worktrees/<repo>/<short-slug> \
     -b fix/<descriptive-name> origin/main
   ```

3. Apply the diff inline (sed / patch / write_file as appropriate).
4. Verify locally (yaml.safe_load, lint, actionlint).
5. Commit + push (`git push -u origin fix/<descriptive-name>`).
6. Open normal PRs with a body following `~/.codex/AGENTS.md` § PR descriptions (canonical owner) and the target repository's `AGENTS.md`/`CLAUDE.md` and PR template; retain any repo-required Evidence section and `Beads: <bd-id>` line.
7. Arm a babysit cron for the post-create /green cycle.

**Wait path (when the diff is larger or requires architectural judgment)**:

1. Do NOT inline-implement. Wait for the provider quota reset (~40 min per the error message).
2. Acknowledge the wait in Slack: *"AO dispatch quota-blocked, resets in ~40m. Will retry at <ts>. Spinning babysit at +45m to re-dispatch."*
3. Create a one-shot cron at +45m: `hermes cron create "45m" --deliver 'slack:<chan>:<thread>' --name 'mikey-cleanup-retry (45m)'`
4. The retry cron body should re-issue the same `ao spawn` and continue from there.

### Step 3 — Inline-exception thresholds (verified 2026-07-06)

The `pr-green-dispatch` COMMIT says: *"Single file, <20 lines, trivially correct — These may be done inline. If CI fails or CR requests changes, pivot to AO worker at that point."* This applies **to the entire diff, not per-file**. In the 2026-07-06 session, the inline path applied because:

- Total diff: 4 lines across 4 files (3 + 2) — well below 20.
- All changes are identical-pattern sed replacements (`["self-hosted","self-hosted-mikey"]` → `["self-hosted"]`) — zero architectural judgment.
- Behavior unchanged (the repo var routes to a different runner fleet).
- All 4 files are pure YAML with no test or business-logic surface.

If any of those criteria don't hold, take the wait path instead.

## Anti-patterns

- **Retrying `ao spawn` immediately after the quota error** — same quota, same error, wasted orchestrator cycle. The orchestrator may also take time to recover its session table after a quota-rejected spawn.
- **Spawning a third / fourth sibling worker hoping it bypasses the quota** — quota is per-account (the auth token used by AO), not per-session. Adding more workers doesn't help.
- **Switching to a different agent plugin (e.g. `codex` instead of `claude-code`)** — quota is per-account, and the user's account-level subscription is the limit. Verify the `agento` agentRules plugin allows the substitute first; don't swap agents in a hurry.
- **Pivoting to inline implementation when the diff is bigger than 20 lines** — that violates the COMMIT exception. Take the wait path.

## Reference: Why the second sibling dispatch never materialized a tmux session

Verified 2026-07-06 with `ao-6918` (agent-orchestrator sibling to `jc-1957`):

- `ao spawn` returned shell exit_code 124 (timeout).
- `ao session ls -p agent-orchestrator` showed `ao-6918 [spawning]` for ~3 min.
- `tmux list-sessions | grep ao-6918` returned **nothing** — no tmux session was created.
- `ao status` showed no row for `ao-6918` after 5 min.

Hypothesis: orchestrator's `lifecycle-worker` sub-handler swallowed the quota error before the tmux could be created. Recovery was the same as for `jc-1957`: drive inline. No retry needed.

## Detection recipe (paste into babysit prompts)

When arming a babysit cron for a multi-PR fanout after a quota block, include the detection recipe inline:

```bash
# On every cron tick, before checking PR state, verify the prior AO worker isn't silently dead
for session in jc-1957 ao-6918; do
  if ! tmux list-sessions 2>/dev/null | grep -q "$session"; then
    if [ -n "$(ao status 2>/dev/null | grep "$session.*exited")" ]; then
      echo "Worker $session exited (likely quota block). Inline pivot complete — verify PR state only."
    fi
  fi
done
```

This keeps the babysit from re-trying `ao send` to a dead tmux and producing phantom "Worker idle" messages.