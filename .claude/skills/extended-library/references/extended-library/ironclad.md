---
description: /ironclad — harden a goal into ironclad exit criteria (stronger than asked), set it durably, then execute
type: llm-orchestration
execution_mode: immediate
---

# /ironclad [goal text | bead-id | "current"]

Thin dispatcher. Read `~/.claude/skills/ironclad/SKILL.md` and execute the full workflow with `$ARGUMENTS`. If no argument: harden the session's active goal (or the most recent self-set goal bead).

**Usage**:
```text
/ironclad ship the demo by friday        # harden a fresh goal
/ironclad wc-w7vp                        # re-harden an existing goal bead
/ironclad current                        # harden the active /goal condition
```
