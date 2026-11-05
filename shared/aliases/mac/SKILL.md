---
name: mac
description: Use when the user invokes /mac or $mac to work on their Mac through an existing connection.
---

Read [the canonical mac-remote skill](../mac-remote/SKILL.md) completely and apply it to the request using the current runtime’s supported tools and permission boundaries. A skill alias does not grant new tool access.

When reading this alias in the source repository rather than an installed
canonical package root, resolve `../../../.claude/skills/mac-remote/SKILL.md`
instead. Use the path appropriate to the inspected package location.

For Dot operations on the target Mac, use that machine's `DOT_ACCOUNT`
environment variable for account selection; it overrides the default in
`~/.config/dot/config.json`. Pass `--account` only when intentionally
overriding the machine preference for one invocation. Keep account values in
machine configuration rather than this portable alias.
