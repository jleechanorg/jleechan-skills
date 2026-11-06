---
name: linux
description: Use when the user invokes /linux or $linux to work on their Linux machine through an existing connection.
---

Read [the canonical linux-remote skill](../linux-remote/SKILL.md) completely and apply it to the request using the current runtime’s supported tools and permission boundaries. A skill alias does not grant new tool access.

When reading this alias in the source repository rather than an installed
canonical package root, resolve `../../../.claude/skills/linux-remote/SKILL.md`
instead. Use the path appropriate to the inspected package location.

For disposable build output, test scratch, and evidence bundles on Linux (`jeff-ubuntu`) and Mac, resolve paths dynamically via the canonical scratch skill [`~/.claude/skills/scratch-space/SKILL.md`](../scratch-space/SKILL.md) using `diskm scratch-new <repo-path> <purpose> --kind build|evidence` or `~/.claude/skills/scratch-space/scripts/scratch-dir.sh`; git worktrees live under `~/.worktrees/<repo>/<name>` via `diskm worktree-new`.
