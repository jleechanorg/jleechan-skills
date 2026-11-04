---
name: harness
description: Analyze failures, audit drift, or optimize the instruction harness using harness-engineering
type: skill
---

# /harness

Resolve and read `../harness-engineering/SKILL.md` relative to this alias
completely, then apply that canonical skill with the caller's arguments unchanged.
On a host that exposes only a skill catalog, resolve the exact canonical name
`harness-engineering` and read the returned skill path instead. If neither route
resolves, report the missing dependency; do not substitute another harness skill.

Preserve `--audit`, `--optimize`, and `--fix`; the canonical skill owns dispatch and
all scope and authorization gates. Loading this alias or preparing its package does
not itself invoke a workflow or authorize implementation.
