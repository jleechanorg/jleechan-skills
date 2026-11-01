---
description: Coordinate with Hermes through verified Slack, with evidence-based monitoring and safe inactive-task recovery.
---

# /hermes

Read and follow [the canonical Hermes skill](../skills/hermes/SKILL.md)
completely, applying `$ARGUMENTS` as the user's scoped request.
Installed target: `${CLAUDE_HOME:-$HOME/.claude}/skills/hermes/SKILL.md`.
Resolve the relative link from this command's directory, not the working directory.
If the skill cannot be read, report the blocker; never use gateway or CLI transport.
