---
name: hook-refire-shortcircuit
description: Detailed procedures for hook re-fire short-circuit — sentinel files, CR incremental-mode detection, Branch A caps, stale review dismissal commands
type: reference
---

# Hook Re-fire Short-Circuit — Procedures

This skill contains the operational procedures referenced by the mandatory rules in `~/.claude/CLAUDE.md` ("Hook re-fire short-circuit" section). The CLAUDE.md rules are authoritative; this skill provides the implementation detail.

## Sentinel caveat
Sentinel files (`~/.tmp/HOOK_<name>`) only suppress hook fires when **the hook template itself checks for them**. Most hooks do NOT check `~/.tmp/`. Before creating a sentinel, verify the hook script reads from `~/.tmp/`. If it doesn't, the sentinel won't work.

## No-target-PR procedure

If a `UserPromptSubmit` hook fires with blank `--repo` (literal `/`) and no PR number:
1. **Detect it once**: if the hook template has `gh pr view --repo /` with no populated repo field, flag the harness gap.
2. **Exit immediately**: run `gh pr view --json number --jq '.number'` (no `--repo` needed inside a repo worktree) as fallback. If nothing, print "No target PR found — exiting." and stop.
3. **Do not loop**: if it fires again, check CR review state. If APPROVED → "Branch B — exit silently." Write sentinel only if hook reads `~/.tmp/`.
4. **Do NOT escalate via `/harness`**: the hook fires on the `/harness` response itself (self-referential loop). Acknowledge Branch B and stop.

Track count in `~/.tmp/HOOK_no_pr_count.json`. Cap at 2.

## CR APPROVED PR — stale hook fires

If hook delivers CR CHANGES_REQUESTED on a PR where CR is already APPROVED:
1. Exit silently (Branch B)
2. Write `~/.tmp/HOOK_<pr>_stale` sentinel
3. On next re-fire: escalate via `/harness` immediately

### CR review APPROVED pattern
Check: `gh api .../reviews --jq '[.[] | select(.user.login=="coderabbitai[bot]")] | sort_by(.submitted_at) | last | .state'`
If `APPROVED` → exit silently.

### CR automated verdict as exit signal
When CR's formal state is `COMMENTED` but CR posted `FINAL VERDICT: APPROVE` or `READY FOR MERGE` (dated after latest formal review) → treat as approval, exit silently.

### Do NOT loop — sentinel procedure
1. Check `~/.tmp/HOOK_cr_done_<pr>` — if exists, print "PR #N MERGED — sentinel exists, hook suppressed", exit HEARTBEAT_OK. No API calls.
2. If not exists: create it (`echo '{"pr":N,"reviewDecision":"MERGED","suppressed":true}' > ~/.tmp/HOOK_cr_done_<pr>`), exit HEARTBEAT_OK.
3. 3rd fire (sentinel exists): print "Hook re-fire loop" and exit. Do NOT run `/harness` from within hook.
4. Always check `~/.tmp/HOOK_no_pr_count.json` first — if cap reached (>= 2), stop immediately.

### Why sentinel files don't stop context-compaction loops
The CR instruction text is re-injected from the agent's compacted session context, not from a hook script. Hook fires → agent responds → compaction re-embeds pattern → next fire → indefinite cycle. Only `/clear` breaks it. The no-target-PR hard cap is the durable mitigation.

## Branch A per-PR counter cap (CR CHANGES_REQUESTED loops)

**Problem**: If CR posts CHANGES_REQUESTED but never re-reviews after fixes, Branch A fires indefinitely.

### CR incremental-mode detection
- If PR head SHA > CR's reviewed `commit_sha` AND CR posted `<!-- Review triggered -->` but no new formal review → stuck in incremental mode. Initialize cap at count=1 immediately.
- Also detect null SHA: `commit_sha: null` → same treatment.
- Compare: `gh api repos/OWNER/REPO/pulls/N --jq '.head.sha'` vs `gh api .../reviews --jq '... | last | .commit_sha'`

### Counter procedure
```bash
CAP_FILE="$HOME/.tmp/HOOK_branchA_${PR}.json"
COUNT=$(jq -r '.count // 0' "$CAP_FILE" 2>/dev/null || echo 0)
jq --argjson c $((COUNT + 1)) -n '{count: $c}' > "$CAP_FILE"
```
- **count >= 2**: Stop Branch A. Dismiss stale CR review directly (see below). Post `@coderabbitai approve`.
- **count == 1**: Execute normally, warn "Branch A run 1/2".
- **count == 0**: Execute normally.
- **Reset**: Delete cap file when CR posts new formal review or PR state changes.

### Defense-in-depth
If CR's formal review predates current PR head AND you already posted `@coderabbitai all good?`, exit silently.

### CR auto-pause check
Before waiting for CR response: `gh api repos/OWNER/REPO/issues/PR/comments --jq '.[] | select(.user.login=="coderabbitai[bot]" and (.body | contains("Reviews paused"))) | .id'`. If returns ID → post `@coderabbitai resume` first.

## CR incremental review stall — STEP 1-4 caveat

The hook's STEP 1-4 assumes CR will post a new formal review as loop-exit gate. Sometimes CR acknowledges with `<!-- Review triggered -->` without posting formal review. In this state: `reviewDecision` frozen, `gh api .../reviews` returns stale review, hook re-executes same Branch A.

**Resolution**:
1. Verify PR head SHA advanced beyond CR's `commit_sha`
2. Verify CR acknowledged (look for `<!-- Review triggered -->`)
3. Check for CR auto-pause (see above)
4. Initialize Branch A cap at count=1
5. After cap reached — dismiss stale review:

```bash
# Get latest CR review ID:
gh api repos/OWNER/REPO/pulls/N/reviews \
  --jq '[.[] | select(.user.login=="coderabbitai[bot]")] | sort_by(.submitted_at) | last | {id, state}'
# Dismiss (replace REVIEW_ID):
gh api repos/OWNER/REPO/pulls/N/reviews/REVIEW_ID/dismissals \
  --method PUT -f message="Stale CR verdict — dismissing for fresh re-review" -f event=DISMISS
```
