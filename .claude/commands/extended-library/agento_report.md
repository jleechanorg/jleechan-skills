---
name: agento_report
aliases:
  - agentor
description: Get a status report of all PRs agento is handling — merged vs not merged, green status breakdown
type: skill
execution_mode: immediate
---

# /agento_report

Get a status report of all PRs agento is handling.

Read `~/.claude/skills/agento-report/SKILL.md` and execute it.

## What it does

| Step | Action |
|------|--------|
| 1 | Collect open + recently-merged PRs via GitHub API |
| 2 | Apply 6-point green check per PR |
| 3 | Check AO session status |
| 4 | Display the full report inline (table format with per-PR status) |
| 5 | Post Slack summary to `#ai-slack-test` (C0AKALZ4CKW) via `mcp__slack__conversations_add_message` |
