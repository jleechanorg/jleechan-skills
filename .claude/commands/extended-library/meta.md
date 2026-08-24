---
description: "Harness-fix meta-skill (slash: /meta) — analyze an agent behavior failure (autonomy violation, refusal, premature stopping) and run /harness to fix the agent, NOT the underlying task. Input: Slack thread URL, pasted conversation, or freeform description."
type: quality
execution_mode: deferred
scope: user
---

# /meta — Fix the agent, not the task

Read `~/.claude/skills/harness-postmortem/SKILL.md` and execute the full workflow with the provided `$ARGUMENTS` (Slack thread URL, pasted conversation, or freeform description).

**Internal skill name:** `harness-postmortem` (canonical: `~/.hermes/skills/harness-postmortem/SKILL.md`). **Collision rule:** a workspace-local `.claude/commands/meta.md` takes precedence over this file.

## Quick reference

| Flag | Effect |
|------|--------|
| (none) | Analyze and output findings, wait for approval |
| `--fix` | Analyze AND apply the harness fix without confirmation |

## Examples

```
/meta
/meta hermes stopped halfway again
/meta https://jleechanai.slack.com/archives/C0AH3RY3DK6/p1782941155305869
/meta --fix <description>
```
