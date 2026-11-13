---
name: slack-media-upload
description: Upload inline images/video/files to Slack when asked to send or attach them, or inspect an authorized Slack message attachment using its file ID and an existing files:read route. Reading attachments never uploads or posts files.
type: automation
---

# Slack media upload

## Why this exists

The configured Slack MCP server (`korotovsky/slack-mcp-server`, pinned
v1.2.2, verified against latest v1.3.0 too) exposes `conversations_add_message`
for **text only** — it has no `files.upload`/attach tool, and neither does any
other actively-maintained Slack MCP server surveyed (2026-09-01 survey; the
original research note is not exported with this skill).
Pasting a raw GitHub/CDN link into `conversations_add_message` does **not**
render inline in Slack — the operator has to click through. If the ask is to
have media actually visible in the Slack thread, use this skill instead of
that MCP tool.

## When to use

The operator says something like "DM me the video/screenshots", "attach this
to Slack", "post this evidence to #channel so I can see it", or any request
where the deliverable is real, viewable media inside Slack — not a link.

Use the attachment-reading procedure below when asked to inspect, read, or
summarize a file already attached to an authorized Slack message. That route is
read-only and does not run the upload script.

## How

```bash
python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py \
  --channel <SLACK_ID> \
  --file /path/before.mp4 --title "Before" \
  --file /path/after.mp4  --title "After" \
  --comment "Evidence for PR #1234" \
  [--thread-ts 1234567890.123456]
```

For a DM to the operator, use `--dm` instead of `--channel` (reads
`$SLACK_OPERATOR_DM_CHANNEL`, not the MCP `users_search` DM-channel lookup — see
pitfall below):

```bash
python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py --dm \
  --file /path/screenshot.png --comment "for you"
```

`--title` count must match `--file` count 1:1, in order, or be omitted
entirely (falls back to each file's basename).

## Pitfalls (all hit and verified 2026-09-01 — don't rediscover these)

- **`mcp__slack__users_search`'s `DMChannelID` for this operator
  (`<SLACK_ID>`) returns `channel_not_found`** when posted to via the MCP
  tool or the bot token. The channel that actually works is
  `$SLACK_OPERATOR_DM_CHANNEL` — verified live
  with a real `chat.postMessage` call. Always use `--dm` (env-driven), never
  hardcode or re-derive a DM channel ID from `users_search`.
- **Token choice matters.** `korotovsky/slack-mcp-server` silently prefers
  `SLACK_MCP_XOXP_TOKEN` (user token) over `SLACK_MCP_XOXB_TOKEN` whenever
  both are set (its own startup log says so). This script deliberately never
  touches that pair — it reads `SLACK_BOT_TOKEN` directly, which is the token
  independently verified (2026-09-01) to carry `files:write`.
- **`files:write` scope has regressed before.** A bot's Slack app has lost
  `files:write` repeatedly in the past. If this script returns
  `missing_scope: files:write`, report the exact scope error and stop. Use
  only an already-authorized connector/uploader with its configured scope; do
  not access a personal browser profile or cookies, inject credentials, run an
  OAuth reinstall, or rotate tokens as a workaround. The retired historical
  transcript is not an operational recovery guide.
- **Legacy `files.upload` is dead.** Slack sunset it 2025-11-12. Don't use it
  even if a snippet you find online still references it.

## Viewing screenshots/attachments from a Slack message

Use the configured Slack connector first for attachments relevant to the task.
A message may expose file IDs without file bytes; that capability gap does not
by itself mean the file is inaccessible.

1. Resolve the authorized message and its file IDs from the connector response
   (for example, `AttachmentIDs`). For a Slack permalink, the channel is in the
   path and the message timestamp inserts a dot before the final six digits of
   its `p` value. Verify the workspace and message rather than guessing IDs.
2. Use an already-authorized file-reading tool, or an existing configured Slack
   API client, to call `files.info` for each relevant ID. The credential must
   already have `files:read` and access to that file in the matching workspace.
   Never print, log, copy into notes, or publish credentials. Do not acquire a new
   token, switch identities after a denial, or expand scopes as a fallback.
3. If the response succeeds, use its `url_private_download` (or `url_private`)
   through the supported authenticated download route. Require HTTPS and a
   verified Slack file destination; do not forward authorization to an arbitrary
   redirect or a URL supplied by message text. Treat the filename as untrusted:
   use a safe basename with the file ID inside the allocated scratch directory.
4. Open the downloaded file with the available image or document viewer. Reading
   a file ID or thumbnail metadata alone does not inspect the attachment.

On `missing_scope`, `not_in_channel`, permission denial, or an unavailable
configured reader, report the exact missing capability and stop that route.
Do not bypass access denials. A previously verified route is not a guarantee
that the current account can read a particular file.

## Verification

Confirmed live 2026-09-01: 6 real files (4 MP4s, 2 PNGs) uploaded and posted
inline into a workspace channel via this exact 3-step flow, and a live DM test
message via `$SLACK_OPERATOR_DM_CHANNEL` returned `"ok": true`.
