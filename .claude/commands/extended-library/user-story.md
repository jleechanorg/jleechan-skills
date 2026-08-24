---
description: /user-story — produce zero-code, zero-tech product specs and VISUAL user stories (what the user sees/hears/does) for any project, at the "rewritable without reading code" bar. Thin pointer to the user-story skill.
---

# /user-story — zero-code specs & visual user stories

Invoke the **`user-story` skill** (`~/.claude/skills/user-story/SKILL.md`) and follow it exactly.

- `$ARGUMENTS` = the target product/repo/scope (and optionally `audit` for assess-only mode). If empty, ask what product to spec.
- The skill defines the law: Rewritability Test verdict bar, observable-criteria-only stories (INVEST, Given/When/Then for stateful flows), zero-code/zero-tech banned list, mandatory visual companion (screen-flow map + mock per screen/moment incl. failure states), 8-step process with three adversarial review lenses (purity / observability / coverage+dedup), and the user review gate.
- Deliverables land as `USER_STORIES.md` + `UI_MOCKS.md` (or screenshots dir) in the target's docs, verdict in the header.
