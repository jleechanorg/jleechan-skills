---
name: superpowers-quick
description: Turn an explicitly requested idea into a complete design and implementation plan using recommended defaults, without starting implementation.
---

# Superpowers quick

This is the jleechanorg wrapper inspired by Superpowers by Jesse Vincent/obra; preserve that attribution. Explicit invocation selects recommended planning defaults without routine choice/approval pauses. It does not authorize implementation, commits, pushes, destructive actions, credential access or external disclosure.

Inspect project context, explore2–3 viable approaches, choose one and record each considered question, chosen default and rationale under Assumptions and Recommended Defaults. Produce a complete architectural specification at docs/superpowers/specs/YYYY-MM-DD-topic-design.md and an executable implementation plan at docs/superpowers/plans/YYYY-MM-DD-topic.md. Include constraints, interfaces, failure behavior, concrete files, meaningful tests, commands, dependencies and acceptance criteria. Self-review both for contradictions and placeholders.

Use supported installed brainstorming/writing-plan skills when available within this wrapper's planning-only boundary; otherwise perform the same design/plan steps directly. Do not require machine-local child packages or an execution handoff.

Run [advice](../advice/SKILL.md) over both artifacts using authorized internal reviewers. Report RAN with the exact verdict, or FAILED with the actual cause; do not claim approval on missing quorum. Retry once only for a transient failure before any reviewer launches; after partial fan-out preserve results and retry only an eligible failed lane, never duplicate the whole run.

[Web advice](../web-advice/SKILL.md) is separate and only runs with explicit external recipient/content authorization. Reuse an already attempted seat; do not submit twice. Report its state separately as RAN, SKIPPED, UNAVAILABLE or FAILED. No external attempt means SKIPPED when authorization is absent.

Finish with both absolute document paths, questions/defaults/rationales and separate advice states. If implementation needs new facts/authority, record exact preconditions and conditional steps in the plan. Do not begin implementation or ask which execution mode to use.
