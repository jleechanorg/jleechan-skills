---
name: superpowers-quick
description: Use when the user explicitly invokes /superpowers-quick and wants an idea turned into a complete design specification and implementation plan without interactive choice or review pauses.
disable-model-invocation: false
---

# Superpowers Quick

## Contract

Run the full design-to-plan workflow autonomously. For this invocation, select recommended choices and approve each recommended design and specification checkpoint. Do not pause for routine questions or review; resolve ordinary ambiguity from available evidence and record assumptions and recommended defaults.

This authorization covers planning decisions and the `/advice` review below, not implementation, destructive actions, credentials, or expanded scope. The caller's existing authorization for implementation or execution continues after this planning report; `/sq` does not grant it. Standing authorization covers the required `/web-advice` plan submission unless the current request explicitly prohibits external submissions.

## Owners and boundaries

- Use the installed `superpowers:brainstorming` and `superpowers:writing-plans` skills when available; otherwise follow `../superpowers-brainstorming/SKILL.md` and `../superpowers-writing-plans/SKILL.md`. Those skills own their detailed design and plan-writing methods. Always produce both architectural documents, including for work otherwise classified as bounded.
- Use the active `/advice` and `/web-advice` skills for reviewer selection, transport, quorum, and recovery. Read their definitions before invocation. This wrapper owns the required `/sq` review scope and artifacts below; it does not duplicate their procedures.
- Follow the active artifact owner for durable Markdown. Under the shared policy, save both documents in `~/roadmap/` as `sq-<topic>-design-YYYY-MM-DD.md` and `sq-<topic>-plan-YYYY-MM-DD.md`.

Do not commit, push, or mutate Git as a planning side effect. Documents may be committed, staged, modified, or untracked; `/sq` has no commit-state prerequisite. Do not ask the user to clean unrelated work. Do not create product artifacts during planning. For a user-visible change, run `/user-story` in audit-only mode and include required story/index work in the plan. Do not offer or wait for the visual companion.

## Workflow

1. Inspect project context and existing decisions. Resolve routine uncertainties from evidence; explore useful alternatives, select the recommended design, and record considered questions, selected answers, and reasons under `Assumptions and Recommended Defaults` in the specification. Do not ask preference or approval questions.
2. Complete and self-review the architectural design. Save it to the roadmap path above; remove placeholders, contradictions, and ambiguous requirements.
3. Complete and self-review the implementation plan at its roadmap path. Include concrete files, tests, commands, and implementation steps.
4. **TDD plan check, before advice:** inspect every plan task. For each behavior change, require the writing-plans sequence: failing test, run to verify the expected failure, minimal implementation, passing test and relevant regressions, then commit. Name exact test and implementation paths, runnable commands, and behavior-specific RED/GREEN outcomes. For tasks that do not change behavior, record `TDD: N/A`, a concrete reason, and a specific verification check. Record each task's check under `TDD Plan Check`; make unavailable facts, tools, or authority explicit preconditions and affected steps conditional. This is plan inspection only: do not run tests, edit implementation code, or commit during this check.
5. **Review the exact saved documents:** resolve `SPEC_PATH` and `PLAN_PATH`. Resolve and validate the roadmap repository before deriving repository-relative names:
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
   Both paths must exist there as non-ignored, non-symlink Markdown files. Use `/advice` document-review mode on both relative paths, with normal reviewer selection and authorization constraints. Record each file's SHA256 and the bundle hash; reviewers must assess the exact current bytes regardless of Git status. The checkout HEAD is context only. A document verdict never approves code, HEAD, or dirty state. Do not use revision mode or a bundled runner.
6. Run `/web-advice` for the `/sq` plan review under standing authorization unless the current request explicitly prohibits external submission. It is separate from `/advice` lanes. Reuse a `/advice` browser submission only when it covers both exact document hashes; otherwise submit through `/web-advice`. Bind any review after a document edit to its new hash. Follow both review owners for failures and recovery, preserve completed valid votes, and record every attempt and exact verdict. Do not impose wrapper attempt caps or duplicate completed verdicts. If all supported browser routes and owner-defined recovery are unavailable, report `/web-advice: UNAVAILABLE` and continue independent caller work. Use `SKIPPED` only when the current request prohibits submission or the workflow does not call for it. Report `/advice` and `/web-advice` states separately.
7. Report both actual absolute document paths, the considered questions and auto-picked answers with rationale, and separate review states: `/advice: RAN | FAILED` with verdict or reason; `/web-advice: RAN | SKIPPED | UNAVAILABLE | FAILED` with verdict or reason and whether it came from `/advice` submission or standalone review. Do not ask which execution mode to use.

## Terminal condition

Finish this planning workflow when both complete documents exist, pass their self-reviews, the TDD plan check is recorded, contain no `TBD`, `TODO`, or deferred decision, and required advice attempts and status records are complete. For planning-only requests, stop without implementation or execution handoff. If implementation was already authorized by the live request or ongoing caller workflow, return to that workflow after the report and continue under its existing authorization without requesting it again. If a new authority or user-specific fact is needed, still finish both documents, record the exact precondition under `Implementation Preconditions`, and make affected steps conditional.
