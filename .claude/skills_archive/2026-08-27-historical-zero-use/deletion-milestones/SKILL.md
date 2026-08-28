---
name: deletion-milestones
description: "Use for PRs scoped to deletion. Net production LOC must be ≤0; PR lifecycle time-boxed at 30 min; document, do not substitute, the deletion."
---

# Milestone scope alignment — deletion PRs must delete


**Skill:** `deletion-milestone.md` — net LOC protocol, PR lifecycle time budget, anti-substitution rules.

- Read governing bead/roadmap before starting. If plan is "add behavior instead of delete," re-assert scope.
- Net production LOC must be ≤ 0. If net > 0, state "net positive — deletion work remaining."
- PR lifecycle (conflict resolution, CR, CI) is not deletion progress — time-box at 30 min.
- Proposed CI gates from RCA must be tracked as explicit deliverables (file + gate), not memory entries.
