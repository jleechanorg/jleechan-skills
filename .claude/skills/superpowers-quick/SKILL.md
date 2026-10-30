---
name: superpowers-quick
description: Use when the user explicitly invokes /superpowers-quick and wants an idea turned into a complete design specification and implementation plan without interactive choice or review pauses.
disable-model-invocation: false
---

# Superpowers Quick

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


## Contract

Run the full design-to-plan workflow autonomously. The invocation is the user's explicit authorization to select every recommended option and approve each recommended design and specification checkpoint for this invocation only.

This authorization covers planning decisions and the `/advice` review required below, not implementation, destructive actions, credentials, or expanded scope. The shared standing authorization covers the `/sq` plan review's `/web-advice` submission; a current request that explicitly prohibits external submissions overrides it.

## Child-Contract Overrides

For this invocation only, use the installed `superpowers:brainstorming` and `superpowers:writing-plans` skills when available; the bundled portable fallbacks are `~/.claude/skills/superpowers-brainstorming/SKILL.md` and `~/.claude/skills/superpowers-writing-plans/SKILL.md`. This wrapper takes precedence over every child instruction that would require interactive input, mutate Git, invoke implementation, create an external side effect other than the required `/advice` review or a browser review allowed under standing authorization and Step 6, write either artifact to a different path, or continue past this wrapper's terminal condition.

Do not pause for user review, approval, clarification, or checkpoint responses. Select and record recommended defaults as specified below. Do not offer the visual companion, open it, or wait for a response. Do not commit or push as an automatic planning side effect. Documents may be committed, staged, modified, or untracked: `/sq` has no commit-state prerequisite. Never ask the user to commit, uncommit, stash, or clean unrelated work merely to run planning or document review.

Complete the required architectural design, specification self-review, implementation plan, and plan self-review. For a planning-only invocation, skip its execution handoff and do not invoke implementation or execution skills; finish by reporting the two document paths, questions asked and answers auto-picked, and advice status. If implementation was already authorized by the live request or ongoing workflow, return to that caller workflow after the planning report and continue under the existing authorization without requesting it again.

## Workflow

1. **REQUIRED SUB-SKILL:** Use `superpowers:brainstorming` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-brainstorming/SKILL.md` completely and use it as the bundled portable fallback. Always use its architectural path so this command produces both required documents, even when the underlying change would normally be classified as bounded.
2. **Inspect project context & auto-pick design choices:** For every clarification, tradeoff, or design fork that would normally be presented to the user during interactive brainstorming, formulate the question and select the option you recommend based on repository evidence and best practices. For open-ended questions, infer the safest reversible answer. Record each question, the auto-picked answer, and the underlying rationale under `Assumptions and Recommended Defaults` in the design specification. Do not ask the user preference or approval questions.
3. **Explore alternatives & complete design:** Explore 2-3 architectural approaches, select the recommended path, and complete the design internally. Treat this command's invocation as approval of the recommended design sections and final specification.
   **User-visible changes:** When the proposed work changes what a user sees, hears, or does in a rendered interface, invoke `/user-story` against the target repository in audit-only mode before finalizing the plan. Read any repo-local `user-story-*` companion first and record the relevant story paths and uncovered journeys. Keep `/sq` limited to audit and planning: do not create or edit product artifacts as a side effect of this invocation. Specify in the implementation plan the required story and visual-evidence work, including updates to the relevant story and its index where applicable. After `/sq` completes, the caller's already-authorized execution workflow continues that `/user-story` artifact work before implementation, following the skill's evidence and review requirements. This conditional call does not grant implementation authority or waive the target repository's user-story gate.
4. **Write & self-review specification:** Follow the active artifact owner for durable Markdown deliverables. Under the shared policy used by this workflow, write and self-review the specification at `~/roadmap/sq-<topic>-design-YYYY-MM-DD.md`. Remove placeholders, contradictions, and ambiguous requirements.
5. **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans` when that plugin skill is available. Otherwise read `~/.claude/skills/superpowers-writing-plans/SKILL.md` completely and use it as the bundled portable fallback. Write and self-review the implementation plan at `~/roadmap/sq-<topic>-plan-YYYY-MM-DD.md` with concrete files, tests, commands, and implementation steps.
   **TDD plan step check (before advice):** Apply this self-review whether the plan came from the installed Superpowers skill or the fallback.
   - For every task that changes behavior, check the Superpowers writing-plans sequence: write the failing test → run it to verify the expected failure → write the minimal implementation → run the test and relevant regressions to verify they pass → commit. Require exact test and implementation paths, runnable commands, and expected RED/GREEN outcomes tied to the intended behavior, not an unrelated setup error.
   - For a task that does not change behavior, record `TDD: N/A` with a concrete reason and a specific verification check; do not silently exempt implementation tasks.
   - Inspect every task, fix missing, reordered, or vague steps, and recheck the saved plan before advice. Record each task's checked sequence or justified N/A under `TDD Plan Check` in the plan. If execution needs unavailable facts, tools, or authority, record the exact precondition and make the affected steps conditional.
   - This is plan inspection, not evidence that RED/GREEN tests have run: do not execute tests, edit implementation code, or commit during this planning-only check.
6. **Execute advice reviews (`/advice` and conditional `/web-advice`):**
   - Resolve the actual absolute `SPEC_PATH` and `PLAN_PATH` after saving both documents under the active artifact owner. Resolve and validate the roadmap repository before deriving repository-relative names:
     ```bash
     if ! ROADMAP_REPO="$(git -C "$HOME/roadmap" rev-parse --show-toplevel)" ||
         [ -z "$ROADMAP_REPO" ]; then
       echo "The roadmap directory is unavailable or is not a Git repository." >&2
       exit 1
     fi
     case "$SPEC_PATH" in
       "$ROADMAP_REPO"/*) SPEC_DOCUMENT="${SPEC_PATH#"$ROADMAP_REPO"/}" ;;
       *) echo "Specification is outside the roadmap repository" >&2; exit 1 ;;
     esac
     case "$PLAN_PATH" in
       "$ROADMAP_REPO"/*) PLAN_DOCUMENT="${PLAN_PATH#"$ROADMAP_REPO"/}" ;;
       *) echo "Plan is outside the roadmap repository" >&2; exit 1 ;;
     esac
     ```
     Use `/advice` document-review mode against `ROADMAP_REPO`, passing `--repo "$ROADMAP_REPO" --document "$SPEC_DOCUMENT" --document "$PLAN_DOCUMENT"` to its primary-pair runner with the normal reviewer selection and parent authorization constraints. The runner requires existing, non-ignored, non-symlink Markdown paths relative to the repository; do not pass the absolute `SPEC_PATH` or `PLAN_PATH` as `--document`. It reviews their exact current bytes regardless of Git status, without committing or pushing. The checkout HEAD supplies context only; bind the document verdict to the recorded document hashes, never claim PR/code approval from it. Do not invoke the revision-only clean-checkout mode for this handoff.
   - Run `/advice` on both the design specification and implementation plan. Run `/web-advice` for the `/sq` plan review under standing authorization unless the current request explicitly prohibits external submissions. (`/web-advice` is not an `/advice` lane; A1/A2/B/C are the lanes.) If `/advice` already submitted these exact document hashes and returned a verdict covering both, reuse it rather than submitting the same bytes again. When a document changes, bind any required new review to its new hash. Record `/web-advice` execution and verdict separately.
   - Follow the active `/advice` owner for reviewer failures and recovery. Preserve completed votes and receipts; use another eligible independent reviewer when required, and do not count failed, late, incomplete, or partial-coverage results as approvals. Do not impose a wrapper attempt cap or restart completed reviews. Record every attempt and exact verdict. Continue authorized remediation and review until the required outcome or a genuine authority, capability, user-stop, or time-box gate applies.
   - Follow the active `/web-advice` owner for browser-seat retries, transport fallbacks, and unavailable results. Preserve completed seat results; retry or route only failed or unavailable seats as that owner allows, and never duplicate a completed verdict for the same exact document hashes. When a document changes, bind any required new review to its new hash. The `/sq` plan review requires its applicable `/web-advice` result under standing authorization unless the current request explicitly prohibits that external submission. If `/advice` already made a browser submission whose verdict covers both exact hashes, reuse it; otherwise run `/web-advice`. Do not impose a wrapper-wide one-attempt limit.
   - If all applicable browser routes and owner-defined recovery are unavailable, record `/web-advice` as `UNAVAILABLE` and continue independent caller work. Do not pause or ask the user to log in. Record `SKIPPED` only when the current request explicitly prohibits the external submission or the workflow does not call for `/web-advice`.
   - Record `/advice` and `/web-advice` execution states and verdicts separately.
7. **Report to user:** In the final response, you MUST always include:
   - **Document paths:** Report the actual full absolute filesystem paths to the saved specification and implementation plan under the active artifact owner (under this shared policy, `~/roadmap/`). Never infer paths from the repository root or a naming template.
   - **Questions asked & answers auto-picked:** A structured list or table detailing all questions considered, the specific choices auto-picked, and their rationale.
   - **Advice status:** Two separate entries using these exact state sets:
     - `/advice`: `RAN | FAILED` — exact verdict or failure reason.
     - `/web-advice`: `RAN | SKIPPED | UNAVAILABLE | FAILED` — exact verdict or reason, and whether the result came from a submission during `/advice` or a standalone review.
Do not begin implementation from a planning-only invocation or ask which execution mode to use. If implementation was already authorized, continue in the calling workflow as stated under `Terminal Condition`.

## Terminal Condition

This skill is planning-only: it never starts implementation. If implementation was already authorized by the user, the calling workflow must continue explicitly after this report (per `pr-lifecycle` § Coding lifecycle); do not treat the report as the end of that work.

Finish only when both documents exist, cover the requested outcome, pass their respective self-reviews, the TDD plan step check is complete, contain no `TBD`, `TODO`, or deferred decision, and the advice attempts and required status records are complete. The final response must include both absolute document paths, the questions and auto-picked answers with rationale, and the two separate advice status entries.

If implementation would require unavailable user-specific information or new authority, still write and self-review both documents. Record the exact unmet precondition under `Implementation Preconditions`, make every affected implementation step conditional on it, and do not treat the planning invocation as authorization to satisfy it. Ordinary ambiguity, an unseen design, or the normal brainstorming approval checkpoints never justify stopping before both documents exist.
