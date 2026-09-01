---
name: slack-media-upload
description: Post real inline images/video/files into Slack (DM or channel) when the operator asks to "send", "DM", or "attach" evidence/media to Slack. No configured Slack MCP tool can upload files — this wraps Slack's own recommended files.getUploadURLExternal -> files.completeUploadExternal flow directly.
type: automation
---

# Slack media upload

## Why this exists

The configured Slack MCP server (`korotovsky/slack-mcp-server`, pinned
v1.2.2, verified against latest v1.3.0 too) exposes `conversations_add_message`
for **text only** — it has no `files.upload`/attach tool, and neither does any
other actively-maintained Slack MCP server surveyed. Full findings, citations,
and the alternative-server survey:
`worldarchitect.ai/docs/research/2026-09-01-slack-mcp-file-upload-support.md`.
Pasting a raw GitHub/CDN link into `conversations_add_message` does **not**
render inline in Slack — the operator has to click through. If the ask is to
have media actually visible in the Slack thread, use this skill instead of
that MCP tool.

## When to use

The operator says something like "DM me the video/screenshots", "attach this
to Slack", "post this evidence to #channel so I can see it", or any request
where the deliverable is real, viewable media inside Slack — not a link.

## How

```bash
python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py \
  --channel C09GRLXF9GR \
  --file /path/before.mp4 --title "Before" \
  --file /path/after.mp4  --title "After" \
  --comment "Evidence for PR #1234" \
  [--thread-ts 1234567890.123456]
```

For a DM to the operator, use `--dm` instead of `--channel` (reads
`$JLEECHAN_DM_CHANNEL`, not the MCP `users_search` DM-channel lookup — see
pitfall below):

```bash
python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py --dm \
  --file /path/screenshot.png --comment "for you"
```

`--title` count must match `--file` count 1:1, in order, or be omitted
entirely (falls back to each file's basename).

## Pitfalls (all hit and verified 2026-09-01 — don't rediscover these)

- **`mcp__slack__users_search`'s `DMChannelID` for this operator
  (`D0A418NEHHC`) returns `channel_not_found`** when posted to via the MCP
  tool or the bot token. The channel that actually works is
  `$JLEECHAN_DM_CHANNEL` (`D0AFTLEJGJU` at time of writing) — verified live
  with a real `chat.postMessage` call. Always use `--dm` (env-driven), never
  hardcode or re-derive a DM channel ID from `users_search`.
- **Token choice matters.** `korotovsky/slack-mcp-server` silently prefers
  `SLACK_MCP_XOXP_TOKEN` (user token) over `SLACK_MCP_XOXB_TOKEN` whenever
  both are set (its own startup log says so). This script deliberately never
  touches that pair — it reads `SLACK_BOT_TOKEN` directly, which is the token
  independently verified (2026-09-01) to carry `files:write`.
- **`files:write` scope has regressed before.** The `mcp_agent_mail` Slack
  app lost `files:write` at least 4 times between 2026-07-13 and 2026-07-19
  (PRs #7953, #8139, #8337, #8455), always via an OAuth reinstall that
  rotated the bot token without updating all 3 places it lives
  (`~/.bashrc: HERMES_SLACK_BOT_TOKEN`, `~/.bashrc: SLACK_MCP_XOXB_TOKEN`,
  `~/.mcp_mail/credentials.json: SLACK_BOT_TOKEN`). If this script starts
  failing with `missing_scope: files:write`, that's the first thing to check
  — full recovery transcript in
  `~/.claude/plugins/marketplaces/claude-commands-marketplace/hermes/skills/devops/slack-mcp-mail-bot-reinstall/references/files-write-scope-reinstall-2026-07-19.md`.
- **Legacy `files.upload` is dead.** Slack sunset it 2025-11-12. Don't use it
  even if a snippet you find online still references it.

## Verification

Confirmed live 2026-09-01: 6 real files (4 MP4s, 2 PNGs) uploaded and posted
inline into `#all-jleechan-ai` via this exact 3-step flow, and a live DM test
message via `$JLEECHAN_DM_CHANNEL` returned `"ok": true`.
