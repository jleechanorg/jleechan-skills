---
description: Alias for slack-identity — apply Slack identity policy; send assignments or inline images/video/files
type: skill
execution_mode: immediate
---

# /slack [--dm | --channel <id>] --file <path> [--file <path> ...] [--title <t> ...] [--comment <text>] [--thread-ts <ts>]

First read `~/.claude/skills/slack-identity/SKILL.md` with `$ARGUMENTS`; follow its authorized dot-to-dot assignment route when assigning work.
For a request to inspect or read an existing Slack attachment, read
`~/.claude/skills/slack-media-upload/SKILL.md` and follow its attachment-reading
procedure. Do not run the upload script for a read request.

For a request to send or attach media in Slack, read the same skill and run
`~/.claude/skills/slack-media-upload/scripts/slack_upload.py` with `$ARGUMENTS`.
Use it when the deliverable must render inline in Slack; a raw URL in a normal
message does not do that. Follow the skill's identity, scope, and token guidance.
