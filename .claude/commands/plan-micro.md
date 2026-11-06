---
description: Create an overall Ironclad contract, then a TDD micro-bead plan with a full Ironclad contract for every bead
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/plan-micro/SKILL.md` completely, then execute it with `$ARGUMENTS`.

**CRITICAL PR-MAPPING INVARIANT (`1 Bead != 1 PR`)**: Micro-beads (`TEST` and `IMPL`, ~100 lines each) are task/commit checkpoints on **ONE shared feature branch and ONE PR** (or at most `≤ 3` coarse stage PRs per `pr-quantity-control`). **NEVER open 1 GitHub PR per micro-bead**, and **NEVER open a `TEST` bead as a standalone PR separate from its `IMPL` bead**.
