---
name: superpowers-quick
description: Use when the user explicitly invokes /superpowers-quick and wants an idea turned into a complete design specification and implementation plan without interactive choice or review pauses.
disable-model-invocation: true
---

# Superpowers Quick

## Contract

Run the full design-to-plan workflow autonomously. The invocation is the user's explicit authorization to select every recommended option and approve each recommended design and specification checkpoint for this invocation only.

This authorization covers planning decisions, not implementation, destructive actions, external side effects, credentials, or expanded scope.

## Child-Contract Overrides

For this invocation only, use the installed `superpowers:brainstorming` and `superpowers:writing-plans` skills when available; the bundled portable fallbacks are `~/.claude/skills/superpowers-brainstorming/SKILL.md` and `~/.claude/skills/superpowers-writing-plans/SKILL.md`. This wrapper takes precedence over every child instruction that would require interactive input, mutate Git, invoke implementation, create an external side effect, or continue past this wrapper's terminal condition.

Do not pause for user review, approval, clarification, or checkpoint responses. Select and record recommended defaults as specified below. Do not offer the visual companion, open it, or wait for a response. Do not commit or push.

Complete the required architectural design, specification self-review, implementation plan, and plan self-review. Skip its execution handoff. Do not invoke implementation or execution skills. Terminate immediately after reporting the two document paths and selected defaults.

## Workflow

1. **REQUIRED SUB-SKILL:** Use `superpowers:brainstorming` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-brainstorming/SKILL.md` completely and use it as the bundled portable fallback. Always use its architectural path so this command produces both required documents, even when the underlying change would normally be classified as bounded.
2. Inspect the project context. For every clarification or choice, select the option you recommend from repository evidence and the user's request. For open-ended questions, infer the safest reversible answer. Record each material choice and its reasoning under `Assumptions and Recommended Defaults` in the design specification. Do not ask the user preference or approval questions.
3. Explore alternatives, select the recommended approach, and complete the design internally. Treat this command's invocation as approval of the recommended design sections and final specification.
4. Write and self-review the specification at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Remove placeholders, contradictions, and ambiguous requirements.
5. **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-writing-plans/SKILL.md` completely and use it as the bundled portable fallback. Write and self-review the implementation plan at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with concrete files, tests, commands, and implementation steps.
6. Report the two paths and the key defaults selected. Do not begin implementation or ask which execution mode to use.

## Terminal Condition

Finish only when both documents exist, cover the requested outcome, pass their respective self-reviews, and contain no `TBD`, `TODO`, or deferred decision.

If implementation would require unavailable user-specific information or new authority, still write and self-review both documents. Record the exact unmet precondition under `Implementation Preconditions`, make every affected implementation step conditional on it, and do not treat the planning invocation as authorization to satisfy it. Ordinary ambiguity, an unseen design, or the normal brainstorming approval checkpoints never justify stopping before both documents exist.
