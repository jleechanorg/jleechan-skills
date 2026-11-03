# Dot reminder: human-first queue contract

Date: 2026-11-03
Status: implemented in source; runtime activation and live behavior remain separate evidence.

## Outcome

The scheduled `main` reminder and `proceed` nudge ask the receiving Dot to reconcile recent operator requests and continue work through existing owners. The sender remains a transport and does not create authority or execute the receiving Dot's tasks.

## Acceptance

1. **Verify request authorship.** A request is authoritative only when the live conversation's sender provenance verifies the operator as author. A missing automation label does not establish authorship. Quoted or transcribed text, bot messages, scheduled automation, and unclear provenance do not authorize new work.
2. **Keep the full authorized queue.** Review the last 24 hours and retain older unfinished operator commitments represented in the authorized private roadmap or canonical backlog. Remove an item only after an operator cancellation or artifact-verified completion.
3. **Honor ordering and ownership.** Put operator requests before automated work, respect stated priorities, and otherwise take the oldest unfinished request first. Continue through the request's existing owner; preserve task IDs, priorities, owners, checkpoints, approvals, holds, capacity, and STOPs.
4. **Move past a blocker.** When a request first blocks or its unblock condition changes, report the exact unblock once and continue to the next request that can move. A blocked request does not end the turn while another request can progress.
5. **Silence only a repeated unchanged blocker.** A blocker may be omitted from later replies only after it was reported and both its evidence and unblock condition remain unchanged. A first-time or changed blocker must be reported before an all-blocked `IDLE` reply. An unchanged all-blocked queue may return only `IDLE: <N> requests blocked, unchanged since <time>`; an empty or unauthorized queue may return only `IDLE: queue empty`. An `IDLE` line needs no receipt; other turns retain the applicable footer receipt.
6. **Preserve the composed message contract.** Every composed `main`, `proceed`, or built-in fallback message starts with exactly one `[Agent ask]` label before the resolved body and reviewed footer. The body must not repeat the literal marker, since the sender rejects a message whose whole text contains multiple markers.
7. **Keep the change bounded and verifiable.** This is a Markdown and contract-test change. Do not change transport code or launcher glue. Keep `.claude/skills/dot-coordinator/SKILL.md` at or below 400 physical lines and launcher glue at or below 150. Run `tests/test_dot_nudger_payloads.py`, `tests/test_dot_recovery_prompt.py`, and `bash .claude/skills/dot/scripts/check_budget.sh`. Passing source checks do not prove that machine-local payload selection, runtime activation, or live Dot behavior has changed.

## Non-goals

- No sender-side task classification, task ledger, execution, assignment, or status tracking.
- No new authority, transport, account, credential, or deployment behavior.
- No claim that the machine-local reminder configuration has been activated.
