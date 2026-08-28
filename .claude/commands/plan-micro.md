---
description: Create an overall Ironclad contract, then a TDD micro-bead plan with a full Ironclad contract for every bead
type: planning
execution_mode: immediate
---

# /plan-micro [scope]

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/plan-micro/SKILL.md` and execute its
full workflow with `$ARGUMENTS`. Make recommended choices without asking questions. This command
first writes the full overall Ironclad document, then plans and creates or
updates beads, dedicated per-bead Ironclad documents, and roadmap artifacts. It
prefers cheaper parallel read-only subagents for independent discovery and
review lanes. It does not activate session state or implement the planned code.
