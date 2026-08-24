---
description: /slack-audit — audit Slack threads for untracked work items; --fix to redrive dropped threads with replies to channel
type: orchestration
execution_mode: immediate
---

# /slack-audit

Read **`~/.claude/skills/slack-audit/SKILL.md`** and execute it according to `$ARGUMENTS`.

All channel selection, dry-run vs. --fix mode, GH tracking checks, and Slack posting logic live **only** in that skill — not in this file.

Default: `--channel worldai --hours 24 --dry-run`

## Example

```
/slack-audit --channel worldai --hours 48 --fix
```
