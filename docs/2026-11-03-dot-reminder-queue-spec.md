# Dot reminder: human-first queue contract

Date: 2026-11-03
Status: implemented in source; runtime activation and live behavior remain separate evidence.

## Outcome

The scheduled `main` reminder and `proceed` nudge ask the receiving Dot to reconcile recent operator requests and continue work through existing owners. The sender remains transport-only and does not create authority or execute the receiving Dot's tasks.

## User story

Before: a first blocker can hide the exact unblock, or each reminder can repeat an unchanged blocker while another operator request waits. After: the Dot reports a new blocker and its unblock, continues with another request that can move, emits one IDLE summary after all remaining blockers are already reported unchanged, then stays silent until the queue or evidence changes.

## Acceptance

1. **Verify authorship.** A request is authoritative only when live conversation sender provenance verifies the operator as author. Missing automation labels do not establish authorship. Quoted or transcribed text, bot messages, scheduled automation, and unclear provenance do not authorize work.
2. **Keep the full authorized queue.** Review the last 24 hours and retain older unfinished operator commitments represented in the authorized private roadmap or canonical backlog. Remove an item only after operator cancellation or artifact-verified completion.
3. **Honor ordering and ownership.** Put operator requests before automated work, respect stated priorities, and otherwise take the oldest unfinished request first. Continue through the request's existing owner; preserve IDs, priorities, owners, checkpoints, approvals, holds, capacity, and STOPs.
4. **Move past blockers.** Report a first-time or changed blocker once with its exact unblock, then continue to the next request that can move. A blocker does not end the turn while another request can progress. Omit details about unchanged blockers in progress replies but keep those requests in the queue.
5. **Make IDLE one-shot.** A new or changed blocker is reported before any IDLE. When every remaining request is complete, unauthorized, or blocked by a previously reported unchanged condition, send the applicable IDLE line once. An unchanged all-blocked queue may use `IDLE: <N> requests blocked, unchanged since <time>`; an empty or unauthorized queue may use `IDLE: queue empty`. After that IDLE, stay silent until the queue, evidence, or unblock condition changes. IDLE needs no receipt; every other turn retains the full Turn Receipt: Mode, Target, Artifact proof, Blocker, and in-flight handle/checkpoint when applicable.
6. **Preserve composed-message labeling.** Every composed `main`, `proceed`, or built-in fallback message starts with exactly one `[Agent ask]` label before the resolved body and reviewed footer. The body must not repeat the literal marker, which makes the sender reject the message.
7. **Keep the change bounded and verifiable.** This is a Markdown and contract-test change. Do not change transport code or launcher glue. Keep the coordinator skill at or below 400 physical lines and launcher glue at or below 150. Run `tests/test_dot_nudger_payloads.py`, `tests/test_dot_recovery_prompt.py`, `tests/test_dot_never_stalls_contract.py`, `tests/test_coordinator_cli.py`, and `bash .claude/skills/dot/scripts/check_budget.sh`. Passing source checks do not prove machine-local payload selection, runtime activation, or live Dot behavior has changed.

## Proof plan

- Run the four focused contract suites and the budget script at the exact candidate SHA.
- Run the Dark Factory controller review against the exact base/head and this spec.
- Verify payload resolution, activation, and live Dot behavior separately before claiming the installed schedule changed.

## Mock

No mock applies: the deliverable changes written instructions and contract tests, with no visual or interactive UI. Tests inspect composed message text and source rules; they do not simulate a live Dot response.

## Risk

- More requests may be reported because the Dot continues after a blocker; existing owners, priorities, approvals, holds, capacity limits, and STOP still control work.
- Unclear sender provenance is deliberately excluded from operator authority.
- Source changes do not activate machine-local reminder files or prove live behavior.

## Non-goals

- No sender-side task classification, task ledger, execution, assignment, or status tracking.
- No new authority, transport, account, credential, or deployment behavior.
- No claim that machine-local reminder configuration has been activated.
