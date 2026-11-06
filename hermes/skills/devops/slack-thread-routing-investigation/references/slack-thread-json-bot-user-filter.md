# Filtering `conversations.replies` JSON for user replies vs bot posts (2026-07-14)

## Why this exists

Babysit crons, dropped-thread followups, and any cron that gates execution on a literal approval token (`WORKTREE APPROVED`, `MERGE APPROVED`, etc.) routinely do a `conversations.replies` scan and need to distinguish **real user replies** from **bot posts** (which can include the bot's own earlier auto-confirmations, thinking-line leaks, and other agent-side posts that happen to mention the approval string).

The Slack `conversations.replies` JSON shape is **deceptive about authorship**: on a bot-posted message, the `user` field is the `xoxb-...` bot's authenticated user ID (which is **identical** to the human user's ID when the bot is posting as a user via a user token like `SLACK_USER_TOKEN`). The reliable disambiguators are **`bot_id`** and **`subtype`**, not `user`.

## JSON shape observed on `conversations.replies` (2026-07-14)

Thread `C0AJQ5M0A0Y / 1784070882.257369` returned 21 messages. All 21 were agent-side posts. Their JSON shapes (relevant fields only):

```jsonc
// Bot-self message posted via Slack MCP (mcp__slack__conversations_add_message) or
// curl chat.postMessage using HERMES_SLACK_BOT_TOKEN — appears under bot's user ID:
{
  "ts": "1784075301.243729",
  "user": "U09GH5BR3QU",                  // ← bot's authorized user ID, not the human
  "bot_id": "B0BGY53L8N8",                // ← ONLY present on bot posts
  "subtype": "bot_message",               // ← optional, present on some bot paths
  "thread_ts": "1784070882.257369",
  "text": "..."
}

// Same shape when posting via SLACK_USER_TOKEN (xoxp) — `user` field becomes
// the human's user ID ($USER = U09GH5BR3QU), no `bot_id`, no `subtype`.
// Looks identical to a real user reply from the JSON alone.

// User-side reply (POST via xoxp *intentionally*): SAME shape as above.
// Anthropomorphic gate like "WORKTREE APPROVED" is text-searchable, not
// authorship-differentiable from a bot alias post.
```

**Trap:** Do NOT use `user == "U<our-human-uid>"` to assume human authorship. When a bot posts via `HERMES_SLACK_BOT_TOKEN`, the `user` field is the bot's `xoxb` user ID (which the Slack app assigns at install — often named after the operating user or the human owner for clarity). When the same bot posts via `SLACK_USER_TOKEN` (xoxp), the `user` field becomes the **human's user ID**, indistinguishable from a real user reply. Both can land the approval token by accident or by prompt.

## The right filter — both signals together

```python
import json, subprocess, os
TOK = os.environ.get('SLACK_USER_TOKEN') or os.environ.get('HERMES_SLACK_BOT_TOKEN')
out = subprocess.check_output([
    'curl', '-fsS',
    '-H', f'Authorization: Bearer {TOK}',
    f'https://slack.com/api/conversations.replies?channel=CXXXXXXXX&ts=THREAD_TS&limit=20'
]).decode()
msgs = json.loads(out).get('messages', [])

def is_real_user_post(m):
    """True only if this row is plausibly authored by a human, not a bot."""
    return (
        m.get('bot_id') is None           # present iff Slack-side bot post
        and m.get('subtype') != 'bot_message'
        and m.get('user') is not None     # has a user attribute at all
    )

user_msgs = [m for m in msgs if is_real_user_post(m)]
approval_seen = any('WORKTREE APPROVED' in m.get('text', '') for m in user_msgs)
```

`bot_id` is the strongest signal — Slack sets it on every bot-posted message (via Slack app, custom bot, MCP `conversations_add_message`, or `chat.postMessage` from an app) and **never** on a user-initiated post. `subtype == "bot_message"` is a secondary signal Slack sometimes adds. Both together are robust; either alone is usually enough.

## Pitfall — text-substring search alone is insufficient

Searching for `'WORKTREE APPROVED'` (or any approval token) **across all messages** returns false positives: an agent's earlier "**`WORKTREE APPROVED`** would clear ~29.91 GB" nudge contains the substring, so a naïve `any('WORKTREE APPROVED' in m['text'] for m in msgs)` returns True even when the user has not replied. Verified 2026-07-14 in the di[REDACTED_OPENAI_KEY] babysit: 21/21 messages contained the substring because the proposal kept re-stating it; only after applying `is_real_user_post` did the scan correctly return 0 matches.

The combined predicate that avoids the false positive:

```python
def user_approved(msgs, token):
    """True iff a real human posted `token` somewhere in the thread."""
    return any(
        is_real_user_post(m) and token in m.get('text', '')
        for m in msgs
    )
```

## Where this gets used

- PR babysit crons — "did anything change since last tick" → "did a human reply with `MERGE APPROVED` / `WORKTREE APPROVED` / etc.". The substring-only scan is the trap; the combined predicate is the durable recipe.
- `dropped-messages` skill — same substring gate, same author-discriminator needed.
- Any cron whose prompt contains "if the user replies with X, then Y" — every such prompt should gate Y on `is_real_user_post(m) AND token in m['text']`, not on substring alone.
- Direct `mcp__slack__conversations_replies` invocations — same JSON shape (CSV-flavored, but the fields are the same) — apply the same Python filter.

## Companion — home-channel `not_in_channel` xoxp fallback

When `mcp__slack__conversations_add_message` returns `{"error": "not_in_channel"}` on the **home channel** (`C0AJQ5M0A0Y` / `#ai-general`) — or any channel the bot's `xoxb` token is not invited to, even within the same workspace — fall back to `SLACK_USER_TOKEN` (xoxp) via curl `chat.postMessage`:

```bash
TOK=$(awk -F'"' '/^export SLACK_USER_TOKEN=/{print $2; exit}' ~/.profile)
curl -fsS -X POST 'https://slack.com/api/chat.postMessage' \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"channel":"C0AJQ5M0A0Y","thread_ts":"<thread>","text":"<reply>"}'
```

The reply will appear as posted by the human (`$USER`, `UserID=U09GH5BR3QU`) — **not the hermes bot**. Include a one-line identity-disclosure in the post body when the user might be confused: `"(posted via $USER identity; bot token blocked from this channel)"`.

⚠️ **Read `~/.profile`, not `~/.bashrc`** for `SLACK_USER_TOKEN`. The `bashrc-profile-xapp-drift-blocks-launchd` memory (2026-06-18) documents why rotating `.bashrc`-only exports don't reach subshells sourced from `.profile` first.

This is the same xoxp fallback as Failure 5f in the parent skill, restated here for proximity to the JSON-filter technique — both are commonly used in the same babysit cron tick.

## Provenance (2026-07-14)

Verified in `di[REDACTED_OPENAI_KEY]` cron (id `fb6959bf3ba5`, self-cancelled after this tick), thread `C0AJQ5M0A0Y / 1784070882.257369` (parent message), tick posts ts range `1784070882 → 1784075378`. The babysit prompt's naïve `WORKTREE APPROVED` substring scan would have returned True on its own re-posted proposal at ts `1784075301.243729` (which mentions the token to motivate the gate) — instead, applying `is_real_user_post` returned 0. After applying the filter, the cron correctly issued one nudge + the final status paragraph and self-cancelled, deferring gate execution to the 30-min recurring companion babysit `babysit-di[REDACTED_OPENAI_KEY]` (job id `18bd680865d9`), which carries the same filter logic in its prompt body.

Also verified on the home-channel `not_in_channel` fallback path: bot `xoxb` token returned `not_in_channel` on `C0AJQ5M0A0Y`; xoxp `SLACK_USER_TOKEN` fallback succeeded at ts `1784076634.909909` (nudge) + `1784076648.131479` (status).

## Bug-ref

Without this filter, three classes of false-positive have shipped:
1. Auto-arm messages from a cron that just announced its own armed state, quoting the approval token in its own text.
2. Meta-reasoning narration posts from the gateway that leak the approval token in passing.
3. Earlier-tick confirmations of "the gate is set, no `X` yet" that name `X` in negation.

All three pass a substring-only scan. The combined `is_real_user_post AND token in text` predicate is the durable cure.
