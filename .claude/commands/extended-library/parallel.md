---
description: Parallelize independent work to its real resource ceiling — not an arbitrary worker count or one-at-a-time
type: skill
execution_mode: immediate
scope: user
---
# /parallel — parallelize to ceiling

Load and follow `${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md` (Skill tool: `parallelize-to-ceiling`). Apply the decision procedure, resource-bound table, isolation invariants, and diagnostics to the work described in the argument.

**Provenance:** [Slack thread](https://jleechanai.slack.com/archives/C09GRLXF9GR/p1785477543929339?thread_ts=1785477466.893429&cid=C09GRLXF9GR) (Parallelize to Ceiling principle, landed via `/up` 2026-07-30).

The canonical skill owns the coding/verifier lane routing, fallback
precedence, model order, and isolation contract; follow those sections for
implementation and review work.

## Input

$ARGUMENTS
