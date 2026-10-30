---
name: superpowers-quick
description: Turn an explicitly requested idea into a complete design and implementation plan using recommended defaults, without starting implementation.
---

# Superpowers quick

This is the jleechanorg wrapper inspired by Superpowers by Jesse Vincent/obra; preserve that attribution. Explicit invocation selects recommended planning defaults without routine choice/approval pauses. It does not authorize implementation, commits, pushes, destructive actions, credential access or external disclosure.

Inspect project context, explore2–3 viable approaches, choose one and record each considered question, chosen default and rationale under Assumptions and Recommended Defaults. Produce a complete architectural specification at docs/superpowers/specs/YYYY-MM-DD-topic-design.md and an executable implementation plan at docs/superpowers/plans/YYYY-MM-DD-topic.md. Include constraints, interfaces, failure behavior, concrete files, meaningful tests, commands, dependencies and acceptance criteria. Self-review both for contradictions and placeholders.

Use supported installed brainstorming/writing-plan skills when available within this wrapper's planning-only boundary; otherwise perform the same design/plan steps directly. Do not require machine-local child packages or an execution handoff.

**TDD plan step check (before advice):** Apply this self-review whether the plan came from the installed Superpowers skill or the fallback.
- For every task that changes behavior, check the Superpowers writing-plans sequence: write the failing test → run it to verify the expected failure → write the minimal implementation → run the test and relevant regressions to verify they pass → commit. Require exact test and implementation paths, runnable commands, and expected RED/GREEN outcomes tied to the intended behavior, not an unrelated setup error.
- For a task that does not change behavior, record `TDD: N/A` with a concrete reason and a specific verification check; do not silently exempt implementation tasks.
- Inspect every task, fix missing, reordered, or vague steps, and recheck the saved plan before advice. Record each task's checked sequence or justified N/A under `TDD Plan Check` in the plan. If execution needs unavailable facts, tools, or authority, record the exact precondition and make the affected steps conditional.
- This is plan inspection, not evidence that RED/GREEN tests have run: do not execute tests, edit implementation code, or commit during this planning-only check.

Run [advice](../advice/SKILL.md) over both artifacts using authorized internal reviewers. Report RAN with the exact verdict, or FAILED with the actual cause; do not claim approval on missing quorum. Retry once only for a transient failure before any reviewer launches; after partial fan-out preserve results and retry only an eligible failed lane, never duplicate the whole run.

[Web advice](../web-advice/SKILL.md) is separate and only runs with explicit external recipient/content authorization. Reuse an already attempted seat; do not submit twice. Report its state separately as RAN, SKIPPED, UNAVAILABLE or FAILED. No external attempt means SKIPPED when authorization is absent.

Finish only when the TDD plan step check is complete. Report both absolute document paths, questions/defaults/rationales and separate advice states. If implementation needs new facts/authority, record exact preconditions and conditional steps in the plan. Do not begin implementation or ask which execution mode to use.
