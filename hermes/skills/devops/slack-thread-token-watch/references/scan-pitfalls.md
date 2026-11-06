# Seven literal-substring scan pitfalls (slack-thread-token-watch)

Every tick's Phase 1 is a literal-substring scan over `conversations.replies`.
The pitfalls below all show up in production: each one is a real failure mode
that produced a wrong-result or a missed-result tick. Treat them as required
filtering, not optional polish.

## Pitfall 1 — Case-sensitivity drift

A substring match must be **case-sensitive AND whitespace-exact**. Do not
`lower()` the candidate body and do not strip whitespace. Operators often
type `WORKTREE APPROVED` with a trailing newline, an emoji, or a code fence.
The cron prompt should specify whether trailing newlines are matched (they
are — Slack strips them from the message body field).

**Example wrong:**
```python
if approval_token.lower() in msg['text'].lower():
```
This matches `worktree approved`, `WORKTREE APPROVED`, `Worktree approved`,
and any case-mangled form. If you want case-sensitive, do not call `.lower()`.

## Pitfall 2 — bot_id filtering

The cron itself posts heartbeats into the thread (or echoes via XOX-P after
the MCP bot fails). Those rows have `bot_id != null` and `bot_id != ""`. If
the heartbeat body happens to mention the approval token (it usually does
not, but the next tick's heartbeat might quote the prior tick), the cron
would match its own previous tick and self-fire.

**Required filter:**
```python
def is_human_approval_row(m):
    if m.get('bot_id'):
        return False
    if not m.get('user', '').startswith('U'):
        return False
    return True
```

## Pitfall 3 — Code-block quoting

The user might quote the approval token inside a fenced code block to ask a
question ("is `WORKTREE APPROVED` the right magic word?") or to point at
the prior proposal. The literal substring is present but the user did NOT
approve.

**Required filter (regex on the whole message body):**
```python
import re
def has_approval_in_unquoted(body, token):
    # Strip all triple-backtick fenced blocks first
    stripped = re.sub(r'```[\s\S]*?```', '', body)
    # Strip single-backtick inline code spans too
    stripped = re.sub(r'`[^`]*`', '', stripped)
    return token in stripped
```

## Pitfall 4 — start_ts guard

Earlier messages in the thread (the proposal itself, prior heartbeats, prior
conversation context) often contain the literal approval token. The cron
should only consider rows posted AFTER `start_ts` (the moment the loop was
armed) so that pre-existing context doesn't trigger a stale match.

**Required filter:**
```python
if float(m['ts']) < float(start_ts):
    continue  # pre-existing context, not a fresh approval
```

`start_ts` is the `thread_ts` of the original proposal message — i.e. the
moment the operator armed the loop.

## Pitfall 5 — Attachment fields, not the body

Slack has THREE places a message body can live:

- `text` (top-level, always present for `chat.postMessage`)
- `attachments[].text` (legacy rich attachment, deprecated but still seen)
- `blocks[].elements[].text` (Block Kit, the modern format)

If you only scan `text`, you miss approvals posted via Block Kit buttons or
legacy attachments. Conversely, if you scan all three, you double-count
post-render artifacts.

**Recommended approach:** scan `text` ONLY. The cron prompt should require
the user to type the approval token directly in a chat-posted message body
(not via Block Kit interaction). If the user clicks a Block Kit button,
that's a different workflow (interactive components) and out of scope.

## Pitfall 6 — XOX-P fallback when MCP bot returns not_in_channel

`mcp__slack__conversations_replies` may return `not_in_channel` for some
channels when the bot identity is missing. The fallback is XOX-P curl with
`SLACK_USER_TOKEN` (sourced from `~/.profile`, NOT `~/.bashrc`).

**Verified working extraction:**
```bash
SLACK_USER_TOKEN=$(awk -F'"' '/^export SLACK_USER_TOKEN=/{print $2; exit}' ~/.profile)
```

DO NOT use the brittle `grep ... | sed 's/...//' | sed 's/"//g'` pipeline —
it leaves a trailing quote and produces a corrupt token (HTTP 401 from
chat.postMessage).

## Pitfall 7 — Block-kit `mrkdwn: true` JSON encoding

When you compose the status post via curl `chat.postMessage` with
`mrkdwn: true`, the body can contain `*bold*` and `_italic_` markers, but
NOT Markdown `**bold**` or `__italic__`. The cron prompt should use
Slack-flavored formatting consistently.

Also: backtick inside the body must be JSON-escaped as `` \` `` only when
the surrounding string is single-quoted in bash — `python3 -c` heredocs
handle backticks natively.

## Bonus — How to test your Phase 1 logic without firing the cron

Dry-run the scan against an existing thread:

```python
import json, subprocess, os

CHANNEL = 'C0AJQ5M0A0Y'
THREAD_TS = '1784070882.257369'
TOKEN = open(os.path.expanduser('~/.slack_token')).read().strip()

r = subprocess.run(
    ['curl', '-fsS',
     '-H', f'Authorization: Bearer {TOKEN}',
     f'https://slack.com/api/conversations.replies?channel={CHANNEL}&ts={THREAD_TS}&limit=20'],
    capture_output=True, text=True)
data = json.loads(r.stdout)
for m in sorted(data['messages'], key=lambda x: float(x['ts'])):
    is_bot = bool(m.get('bot_id'))
    text = (m.get('text') or '').replace('\n', ' | ')
    print(f"ts={m['ts']} bot={is_bot} user={m.get('user','?')} text={text[:100]}")
```

A test thread should show at least one bot row (the heartbeat the cron
posted) and zero human rows until the operator types the approval token.
