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

For this invocation only, use the installed `superpowers:brainstorming` and `superpowers:writing-plans` skills when available; the bundled portable fallbacks are `~/.claude/skills/superpowers-brainstorming/SKILL.md` and `~/.claude/skills/superpowers-writing-plans/SKILL.md`. This wrapper takes precedence over every child instruction that would require interactive input, mutate Git, invoke implementation, create an external side effect, write either artifact to a different path, or continue past this wrapper's terminal condition.

Do not pause for user review, approval, clarification, or checkpoint responses. Select and record recommended defaults as specified below. Do not offer the visual companion, open it, or wait for a response. Do not commit or push.

Complete the required architectural design, specification self-review, implementation plan, and plan self-review. Skip its execution handoff. Do not invoke implementation or execution skills. Terminate immediately after reporting the two document paths, questions asked and answers auto-picked, and the advice status.

## Workflow

1. **REQUIRED SUB-SKILL:** Use `superpowers:brainstorming` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-brainstorming/SKILL.md` completely and use it as the bundled portable fallback. Always use its architectural path so this command produces both required documents, even when the underlying change would normally be classified as bounded.
2. **Inspect project context & auto-pick design choices:** For every clarification, tradeoff, or design fork that would normally be presented to the user during interactive brainstorming, formulate the question and select the option you recommend based on repository evidence and best practices. For open-ended questions, infer the safest reversible answer. Record each question, the auto-picked answer, and the underlying rationale under `Assumptions and Recommended Defaults` in the design specification. Do not ask the user preference or approval questions.
3. **Explore alternatives & complete design:** Explore 2-3 architectural approaches, select the recommended path, and complete the design internally. Treat this command's invocation as approval of the recommended design sections and final specification.
4. **Write & self-review specification:** Write and self-review the specification at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Remove placeholders, contradictions, and ambiguous requirements.
5. **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-writing-plans/SKILL.md` completely and use it as the bundled portable fallback. Write and self-review the implementation plan at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with concrete files, tests, commands, and implementation steps.
6. **Execute advice reviews (`/advice` & `/web-advice`):** Run `/advice` (and `/web-advice` where web/browser context is relevant) on the generated specification and implementation plan. Record the execution state and verdicts returned by the review lanes.
7. **Report to user:** In the final response, you MUST always include:
   - **Document paths:** Full absolute paths to the generated specification (`docs/superpowers/specs/...`) and implementation plan (`docs/superpowers/plans/...`).
   - **Questions asked & answers auto-picked:** A structured list or table detailing all questions considered, the specific choices auto-picked, and their rationale.
   - **Advice status:** Explicit statement of whether `/advice` and `/web-advice` were run and their resulting status/verdict (e.g. `RAN (APPROVED: Codex + Opus)` / `RAN (WITHHELD: ...)` / `SKIPPED (reason: ...)`).
   Do not begin implementation or ask which execution mode to use.

## Terminal Condition

Finish only when both documents exist, cover the requested outcome, pass their respective self-reviews, and contain no `TBD`, `TODO`, or deferred decision.

If implementation would require unavailable user-specific information or new authority, still write and self-review both documents. Record the exact unmet precondition under `Implementation Preconditions`, make every affected implementation step conditional on it, and do not treat the planning invocation as authorization to satisfy it. Ordinary ambiguity, an unseen design, or the normal brainstorming approval checkpoints never justify stopping before both documents exist.
