---
name: superpowers-quick
description: Use when the user explicitly invokes /superpowers-quick and wants an idea turned into a complete design specification and implementation plan without interactive choice or review pauses.
disable-model-invocation: true
---

# Superpowers Quick

## Contract

Run the full design-to-plan workflow autonomously. The invocation is the user's explicit authorization to select every recommended option and approve each recommended design and specification checkpoint for this invocation only.

This authorization covers planning decisions, not implementation, destructive actions, external side effects, credentials, or expanded scope.

## Workflow

1. **REQUIRED SUB-SKILL:** Use `superpowers:brainstorming`. Always use its architectural path so this command produces both required documents, even when the underlying change would normally be classified as bounded.
2. Inspect the project context. For every clarification or choice, select the option you recommend from repository evidence and the user's request. For open-ended questions, infer the safest reversible answer. Record each material choice and its reasoning under `Assumptions and Recommended Defaults` in the design specification. Do not ask the user preference or approval questions.
3. Explore alternatives, select the recommended approach, and complete the design internally. Treat this command's invocation as approval of the recommended design sections and final specification.
4. Write and self-review the specification at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Remove placeholders, contradictions, and ambiguous requirements.
5. **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans`. Write and self-review the implementation plan at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with concrete files, tests, commands, and implementation steps.
6. Report the two paths and the key defaults selected. Do not begin implementation or ask which execution mode to use.

## Terminal Condition

Finish only when both documents exist, cover the requested outcome, pass their respective self-reviews, and contain no `TBD`, `TODO`, or deferred decision.

If a valid plan requires unavailable user-specific information or new authority, stop with the exact blocker. Ordinary ambiguity, an unseen design, or the normal brainstorming approval checkpoints are not blockers under this explicitly invoked wrapper.
