---
description: /slack — post real inline images/video/files into a Slack channel or DM (not just links)
type: skill
execution_mode: immediate
---

# /slack [--dm | --channel <id>] --file <path> [--file <path> ...] [--title <t> ...] [--comment <text>] [--thread-ts <ts>]

Read `~/.claude/skills/slack-media-upload/SKILL.md` and run
`~/.claude/skills/slack-media-upload/scripts/slack_upload.py` with `$ARGUMENTS`. Use this whenever the deliverable is media that must render inline
in Slack — pasting a raw URL into a normal Slack message tool does not do
that; see the skill for why and for known DM/token pitfalls.
