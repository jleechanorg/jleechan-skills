---
name: slack-thread-token-watch
version: 0.1.0
description: |
  Recurring cron-tick loop that watches a single Slack thread for a literal
  substring (for example WORKTREE APPROVED, MERGE APPROVED, DEPLOY APPROVED,
  or a custom approval token) and executes a pre-known callback (delete
  script, merge, deploy, etc.) on first match. Otherwise silent (one
  heartbeat per cadence). Self-cancels on match or after a configurable
  timeout. Use it for non-PR, no-AO-worker approval-gate loops.

  Bug-ref 2026-07-14, thread C0AJQ5M0A0Y/1784070882.257369. The disk-
  pressure babysit 18bd680865d9 was a literal-token watch loop but auto-
  loaded a PR-babysit skill, which silently self-cancelled because there
  was no PR and no AO worker to track. That false assurance (babysit
  armed) is what this skill prevents.
trigger:
  - watch this thread for WORKTREE APPROVED
  - watch for MERGE APPROVED in thread
  - literal token watch loop
  - approval-token gate cron
  - fire X when user types Y in this thread
changelog:
  - '0.1.0 (2026-07-14): Initial authoring. Triggered by the 2026-07-14 PR-babysit carve-out. Every prior literal-token watch loop was wired through the PR-babysit skill, which assumes a PR + AO worker pair and exits immediately when neither exists. Drafted directly from the di[REDACTED_OPENAI_KEY] babysit prompt body (job 18bd680865d9), which is the reference implementation. Verified contract: tick equals conversations.replies substring scan + optional destructive callback + hermes cron remove on terminal state.'
---

# slack-thread-token-watch

A scheduled cron job ticks every N minutes on a single Slack thread. Each tick scans the thread for a literal substring (the approval token). On first match, it executes a pre-known callback script (destructive or not) and self-cancels. Otherwise it stays silent (one optional heartbeat per cadence). The loop is finite and must terminate cleanly when the work is done, or after a configurable timeout.

## When to load

- A scheduled cron job is gating a destructive action behind a literal-substring approval from the human (for example, delete these worktrees when I type WORKTREE APPROVED, merge when I type MERGE APPROVED, deploy when I type DEPLOY APPROVED).
- A user asks you to watch this thread for XYZ and run script.sh when it appears, gate the delete on my approval, stand by for APPROVE keyword, or approval-token cron.
- You are inheriting an existing literal-token cron mid-life and need to keep its cadence without re-creating its contract.

Do NOT drive a literal-token watch loop with a PR-babysit pattern. PR babysits assume a PR + AO worker pair and self-cancel on the first tick when neither exists (see `references/bug-ref-2026-07-14.md`).

Do NOT load for one-shot approval flows (use the inline session directly), PR bring-to-green interactive loops (use drive-pr-to-green or finish-the-job), or any callback that is NOT a literal-substring scan of a known Slack thread.

## The contract (each tick)

Each tick has exactly four phases. Do them in this order, every tick.

### Phase 0 - Pre-flight (early-exit; run BEFORE composing any output)

1. Self-identity check. Run echo $CRON_JOB_ID and date -u +%FT%TZ. Confirm we know our own cron job id (required for Phase 0.5 self-cancel).
2. Did the callback already fire? Check the durable executed-flag (for example, /var/tmp/<job>_executed):

```bash
[ -f "/var/tmp/<job>_executed" ] && { echo "callback already executed; exiting"; exit 0; }
```

3. Has the loop aged out? Tick counter file (for example, /tmp/<job>/.tick_counter) must be present and less than or equal to TIMEOUT_TICKS:

```bash
STATE=/tmp/<job>/.tick_counter; mkdir -p "$(dirname "$STATE")"
TICK=$(($(cat "$STATE" 2>/dev/null || echo 0) + 1)); echo "$TICK" > "$STATE"
[ "$TICK" -gt "${TIMEOUT_TICKS:-48}" ] && { echo "aged out after $TICK ticks"; exit 0; }
```

4. Are the eligibility or candidate artifacts still valid? Run ls -la /path/to/eligibility.json and check path_whitelist_ok. If absent or invalid, post a one-liner warning and exit (do not delete anything).

If any of these short-circuit, do NOT post the heartbeat, do NOT run the callback. Exit cleanly.

### Phase 1 - Scan the thread for the literal approval token

Use the Slack MCP tool when available, fall back to XOX-P curl:

```bash
# Preferred: MCP
mcp__slack__conversations_replies(channel_id="<CHANNEL>", thread_ts="<THREAD_TS>", limit=20)

# Fallback (when MCP bot returns not_in_channel or missing_scope):
SLACK_USER_TOKEN=$(awk -F'"' '/^export SLACK_USER_TOKEN=/{print $2; exit}' ~/.profile)
curl -fsS -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=<CHANNEL>&ts=<THREAD_TS>&limit=20"
```

Then scan the body of each message whose user is a real human (U-prefix, not a bot B-prefix) for the literal substring APPROVAL_TOKEN. Case-sensitive, exact substring. Never match a synonym or normalized form.

**Critical pitfalls** (see references/scan-pitfalls.md for full details):

- Match on the text field, not attachments or block-kit element text fields. Those are post-render artifacts that can drift.
- Skip the bot's own previous heartbeat rows (filter on bot_id is null OR empty).
- Skip rows where the approval token appears in a fenced code block. The user was quoting it, not approving.
- Treat a string match as a match only if the row was posted AFTER start_ts. Earlier messages in the thread are stale context, not approval.

### Phase 2 - Run the callback (only if match + flag not set)

The callback is whatever was pre-defined in the cron prompt. Common shapes:

**Destructive delete with whitelist:**

```python
python3 << 'PY'
import json, os, subprocess
d = json.load(open('/tmp/eligibility.json'))
WHITELIST_PREFIXES = ('$HOME/projects/', '$HOME/.lvl-lanes/', ...)
freed_mb = 0; deleted = 0
for r in d:
    p = r['path']
    if r.get('locked') or r.get('age_days', 0) < 14: continue
    if not p.startswith(WHITELIST_PREFIXES): continue
    if not os.path.exists(p): continue
    subprocess.run(['rm', '-rf', p], check=False)
    freed_mb += r['size_mb']; deleted += 1
print(f'deleted={deleted} freed_mb={freed_mb:.2f}')
PY
```

**GitHub merge or action trigger:**

```bash
TOKEN=$(gh auth token)
curl -fsS -X POST -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<OWNER>/<REPO>/merges" -d '{"sha":"<HEAD>","merge_method":"squash"}'
```

Always set the executed-flag FIRST before running the callback (idempotency):

```bash
touch /var/tmp/<job>_executed
```

### Phase 3 - Self-cancel + post status (always, on terminal state)

Whether the callback fired or the loop aged out:

```bash
hermes cron remove "$CRON_JOB_ID"
```

Then post ONE status message into the original thread.

**On match + success:**

```
:large_green_circle: [thread-token-watch] APPROVAL_TOKEN received - <callback result>. df: before=<before> used, after=<after> used. Self-cancelling.
```

**On match + failure (callback crashed):**

```
:red_circle: [thread-token-watch] APPROVAL_TOKEN received but callback failed - <error>. Loop NOT self-cancelled; investigate.
```

Do NOT self-cancel on failure; operator must inspect.

**On age-out (no match, TIMEOUT_TICKS reached):**

```
:hourglass_flowing_sand: [thread-token-watch] aged out after <N> ticks without APPROVAL_TOKEN. Self-cancelling.
```

**On heartbeat-only (no match, under TIMEOUT_TICKS):**

- If the last heartbeat was under 6 hours ago: emit [SILENT] (cron playbook contract).
- Otherwise post a one-liner: :yellow_circle: [thread-token-watch] still holding gate; df <X>G/<Y>G (<Z>%); proposal age <N>h. Type APPROVAL_TOKEN to fire the <X> action.

## Authoring a new cron

```bash
hermes cron create "30m" \
  --name "<job-name>" \
  --repeat 200 \
  --deliver slack:<CHANNEL> \
  "$(cat /tmp/cron_prompt.txt)"
```

The prompt body MUST include:

1. The literal substring to match (case-sensitive).
2. The callback shell/Python block (Phase 2).
3. The path whitelist (Phase 2 destructive variant).
4. The executed-flag path (idempotency).
5. The TIMEOUT_TICKS ceiling.
6. Explicit "do NOT post multi-option menus" guardrail.
7. Explicit "do NOT spawn new cron jobs from inside this babysit" guardrail.

## Guardrails (NEVER VIOLATE)

- NEVER fire the callback without exact substring match (case-sensitive) on a row whose user is a real human (U-prefix, bot_id null).
- NEVER delete a row outside the path whitelist, with locked=true, or with age_days under FLOOR_DAYS.
- NEVER rm -rf without trying trash <path> first (Finder recoverable).
- NEVER post a multi-option menu (A/B/C/D forks).
- NEVER spawn new cron jobs from inside this cron (avoid recursive-cron leak).
- Pre-send gate: every Slack message must avoid MEDIA:/path text tokens (use the 3-stage files.completeUploadExternal API for any binary evidence; see evidence-attach-to-slack skill).

## Termination rules

The loop terminates when ANY of these are true:

1. Approval token matched and callback completed successfully.
2. Approval token matched but callback failed (operator must inspect; do NOT auto-cancel).
3. Loop aged out (TICK greater than TIMEOUT_TICKS).
4. Cron schedule itself has been disabled (hermes cron edit --repeat 0 or hermes cron remove).
5. Operator manually runs hermes cron remove.

On termination: self-cancel via hermes cron remove "$CRON_JOB_ID" and post the appropriate terminal status message.

## Anti-patterns (do NOT do)

- Reaching for a PR-babysit pattern because the prompt mentions watch, babysit, or tick. PR babysits assume a PR + AO worker pair and exits after one tick when neither exists. The false assurance (watch loop armed) is the failure mode this skill exists to prevent.
- Posting the callback result on every tick after the work is done. One tick owns the close; later ticks own silence.
- Posting to Slack when nothing changed and the playbook says [SILENT]. Noise is worse than silence; the human inbox is the precious resource.
- Re-implementing the path whitelist inline as a bash regex. Use Python startswith() on each whitelist tuple; bash globbing silently misses edge cases.
- Treating bot_id non-null rows as approval. Bot rows are heartbeat artifacts, not human input.
- Using mcp__slack__conversations_add_message for thread replies without first checking the channel scope (fails with not_in_channel for some channels; fall back to XOX-P curl per SOUL.md slack-cross-workspace-fallback-xoxp).
- Calling hermes cron remove from inside a Phase 1 scan (race with self). Always Phase 3.

## Tool usage notes

- Use terminal for curl, python3, and hermes cron. Fan-out parallel where possible.
- Use mcp__slack__conversations_replies for the canonical scan (preferred over curl; gets paginated thread properly).
- Fall back to XOX-P curl chat.postMessage when the MCP bot returns not_in_channel or missing_scope (per SOUL.md slack-cross-workspace-fallback-xoxp).
- Use hermes cron list for the self-cancel CLI + audit recipe.
- Use python3 -c "import json; ..." for eligibility filtering. Never inline shell JSON parsing on multi-line fields (it breaks on body field LF bytes).

## Verification

Before posting the first tick of a new loop, confirm:

- The cron is correctly delivering to the channel + thread configured by the operator.
- The literal approval token is exactly the substring the operator will type (case-sensitive; no leading/trailing whitespace in the prompt's match string).
- The callback shell/Python block is syntactically valid (bash -n or python3 -c dry-run).
- The path whitelist is correct; verify each prefix exists and is owned by the operator.
- The executed-flag path is in a writable location (for example, /var/tmp/<job>_executed, NOT inside ~/.hermes/).
- The TIMEOUT_TICKS ceiling is reasonable (for example, 48 for a 30-min cadence = 24 h; 200 for 30-min = 100 h).

## Support files

- references/scan-pitfalls.md - the seven common literal-substring scan pitfalls (case-sensitivity, bot_id filtering, code-block quoting, start_ts guard, attachment fields, block-kit elements, XOX-P fallback).
- references/prompt-template.md - drop-in prompt body template with all required fields (literal token, callback, path whitelist, executed-flag, TIMEOUT_TICKS, guardrails).
- references/bug-ref-2026-07-14.md - full transcript of the di[REDACTED_OPENAI_KEY] babysit 18bd680865d9 failure mode and the cron-output dump that diagnosed it.
