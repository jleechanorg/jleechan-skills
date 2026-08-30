---
name: superpowers-quick
description: Use when the user explicitly invokes /superpowers-quick and wants an idea turned into a complete design specification and implementation plan without interactive choice or review pauses.
disable-model-invocation: true
---

# Superpowers Quick

## Contract

Run the full design-to-plan workflow autonomously. The invocation is the user's explicit authorization to select every recommended option and approve each recommended design and specification checkpoint for this invocation only.

This authorization covers planning decisions and the `/advice` review required below, not implementation, destructive actions, credentials, expanded scope, or disclosure to external browser reviewers. A bare `/superpowers-quick` invocation does not authorize external browser review; Step 6 defines the only opt-in path for `/web-advice`.

## Child-Contract Overrides

For this invocation only, use the installed `superpowers:brainstorming` and `superpowers:writing-plans` skills when available; the bundled portable fallbacks are `~/.claude/skills/superpowers-brainstorming/SKILL.md` and `~/.claude/skills/superpowers-writing-plans/SKILL.md`. This wrapper takes precedence over every child instruction that would require interactive input, mutate Git, invoke implementation, create an external side effect other than the required `/advice` review or a browser review explicitly authorized under Step 6, write either artifact to a different path, or continue past this wrapper's terminal condition.

Do not pause for user review, approval, clarification, or checkpoint responses. Select and record recommended defaults as specified below. Do not offer the visual companion, open it, or wait for a response. Do not commit or push.

Complete the required architectural design, specification self-review, implementation plan, and plan self-review. Skip its execution handoff. Do not invoke implementation or execution skills. Terminate immediately after reporting the two document paths, questions asked and answers auto-picked, and the advice status.

## Workflow

1. **REQUIRED SUB-SKILL:** Use `superpowers:brainstorming` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-brainstorming/SKILL.md` completely and use it as the bundled portable fallback. Always use its architectural path so this command produces both required documents, even when the underlying change would normally be classified as bounded.
2. **Inspect project context & auto-pick design choices:** For every clarification, tradeoff, or design fork that would normally be presented to the user during interactive brainstorming, formulate the question and select the option you recommend based on repository evidence and best practices. For open-ended questions, infer the safest reversible answer. Record each question, the auto-picked answer, and the underlying rationale under `Assumptions and Recommended Defaults` in the design specification. Do not ask the user preference or approval questions.
3. **Explore alternatives & complete design:** Explore 2-3 architectural approaches, select the recommended path, and complete the design internally. Treat this command's invocation as approval of the recommended design sections and final specification.
4. **Write & self-review specification:** Write and self-review the specification at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Remove placeholders, contradictions, and ambiguous requirements.
5. **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-writing-plans/SKILL.md` completely and use it as the bundled portable fallback. Write and self-review the implementation plan at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` with concrete files, tests, commands, and implementation steps.
6. **Execute advice reviews (`/advice` and conditional `/web-advice`):**
   - Determine whether the user's current request separately and explicitly authorizes submitting both documents to external browser reviewers before invoking `/advice`.
   - Run `/advice` on both the design specification and implementation plan. Without that separate authorization, pass this explicit parent constraint in the `/advice` request: `Reviewer D /web-advice is disabled; do not invoke it or any external browser transport.` Verify that the synthesis lists Reviewer D as `unavailable (disabled by parent authorization boundary)`. Treat an omitted row or an attempted Reviewer D/browser submission as an incomplete `/advice` run and record it as `FAILED`. If `/advice` attempts Reviewer D or any external browser submission without authorization, record `/web-advice` as `FAILED` with the attempted-submission reason; never label that path `SKIPPED`.
   - Retry `/advice` once only for a transient transport or reviewer-launch failure. Retry the whole `/advice` invocation only when it failed before any reviewer launched; the preceding retry permission never permits rerunning a partial fan-out. If any reviewer launched, do not rerun `/advice`; preserve completed lane results, record the incomplete run as `FAILED` with its failure reason, and continue to the terminal report. If the pre-launch retry also fails, record `/advice` as `FAILED` with both failure reasons. A `FAILED` state permits the terminal report but prohibits claiming that advice passed or approved the documents. A returned `APPROVED`, `NOT APPROVED`, or `WITHHELD` synthesis counts as `RAN`; report that exact verdict without rewriting it.
   - `/web-advice` is applicable only when the user's current request separately and explicitly authorizes submitting the documents to external browser reviewers. Any Reviewer D attempt consumes the single `/web-advice` run. If Reviewer D returned a verdict covering both documents, reuse it. If its attempt was unavailable or failed, record `/web-advice` as `UNAVAILABLE` or `FAILED` with that reason and do not submit the documents again. Do not run a second standalone `/web-advice`. Only when `/advice` did not attempt Reviewer D may you run one standalone `/web-advice` review.
   - If browser authentication or transport is unavailable, record `/web-advice` as `UNAVAILABLE` and continue. Do not pause or ask the user to log in. When no external attempt occurred and explicit authorization is absent, record `/web-advice` as `SKIPPED` and continue.
   - Record `/advice` and `/web-advice` execution states and verdicts separately.
7. **Report to user:** In the final response, you MUST always include:
   - **Document paths:** Resolve the repository root and report full absolute filesystem paths to the generated specification (`<repo-root>/docs/superpowers/specs/...`) and implementation plan (`<repo-root>/docs/superpowers/plans/...`).
   - **Questions asked & answers auto-picked:** A structured list or table detailing all questions considered, the specific choices auto-picked, and their rationale.
   - **Advice status:** Two separate entries using these exact state sets:
     - `/advice`: `RAN | FAILED` — exact verdict or failure reason.
     - `/web-advice`: `RAN | SKIPPED | UNAVAILABLE | FAILED` — exact verdict or reason, and whether the result came from `/advice` Reviewer D or a standalone review.
   Do not begin implementation or ask which execution mode to use.

## Terminal Condition

Finish only when both documents exist, cover the requested outcome, pass their respective self-reviews, contain no `TBD`, `TODO`, or deferred decision, and the advice attempts and required status records are complete. The final response must include both absolute document paths, the questions and auto-picked answers with rationale, and the two separate advice status entries.

If implementation would require unavailable user-specific information or new authority, still write and self-review both documents. Record the exact unmet precondition under `Implementation Preconditions`, make every affected implementation step conditional on it, and do not treat the planning invocation as authorization to satisfy it. Ordinary ambiguity, an unseen design, or the normal brainstorming approval checkpoints never justify stopping before both documents exist.
