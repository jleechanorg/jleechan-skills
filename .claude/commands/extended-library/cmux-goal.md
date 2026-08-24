---
description: /cmux-goal — set the builtin /goal for yourself via the cmux socket CLI (Stop hook + purple indicator)
type: llm-orchestration
execution_mode: immediate
---

# /cmux-goal [condition text | "from-bead <id>" | "harden first: <goal>"]

Thin dispatcher. Read `~/.claude/skills/cmux-goal/SKILL.md` and execute the full workflow with `$ARGUMENTS`.

**Usage**:
```text
/cmux-goal PR #271 merge-ready per bead wc-w7vp     # set literal condition now
/cmux-goal from-bead wc-w7vp                        # derive short condition from a goal bead
/cmux-goal harden first: ship the demo              # run /ironclad, then set the builtin
```
