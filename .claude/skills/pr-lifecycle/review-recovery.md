# Reviewer Timeout, Recovery, and Fallback Quorum

On-demand reference for [pr-lifecycle](SKILL.md): load when managing reviewer deadlines, handling timeouts, applying replacement quorums, or handling backlogged CI.

## Reviewer timeout and completion

For `/pr-workflow` and other lifecycle reviews, each reviewer attempt has a default wall-clock limit of 1800 seconds (30 minutes), starting when the request is queued or sent. Queueing and delivery wait count; progress, partial output or a new message do not reset it. An explicit user-specified limit, shorter or longer, governs that attempt, and a later specific user instruction to await a named reviewer overrides the deadline for that attempt even without a number. If the reviewer is explicitly unavailable or quota-blocked, stop the attempt and route to the fallback immediately. Do not keep waiting on the same attempt.

A timed-out `/dot`, requested `/wa` or other non-`/advice` supplementary reviewer attempt is recorded `TIMED_OUT` with request and timeout times and any partial receipt or findings, never PASS. It is discharged at timeout, and the workflow continues through the reviewer fallback: a passing `/er` on the finished evidence plus `/advice` approval from two independent reviewers at the same head. The two-vote quorum is mandatory for this substitution only; the table-selected source-review route is unchanged. A `/wa` timeout proves none of the browser-only validation it was meant to review. Required substantive safety, evidence and domain checks stay open until proved by applicable evidence or an eligible replacement review; a timeout grants neither readiness nor merge authorization. Assess late substantive findings when they arrive; they can reopen the affected gate.

If an `/er` reviewer times out, record `TIMED_OUT` and continue independent work, but keep the evidence-review gate open until an eligible replacement completes `/er` with an applicable PASS. `/advice` or another supplementary review is not proof that the evidence was reviewed.

The Markdown instruction-only route in [review-routing.md](review-routing.md#markdown-instruction-only-route) owns its one-or-two reviewer count and bypasses the generic 50-line /advice threshold. Outside that route, /advice uses one independent full-scope reviewer only for an eligible compact low-risk route under the obligation table; otherwise it keeps its two-independent-reviewer quorum. Stricter governing requirements and the mandatory two-vote supplementary-review substitution above remain in force. Apply [advice](../advice/SKILL.md)'s identity, independence, tier and reviewer-class counting caps. Replace a failed or timed-out seat with another eligible independent reviewer, and keep replacing until quorum is reached or no eligible attempt remains; record each seat and outcome. Below quorum the result is `WITHHELD`, not approval. A late substantive `/advice` finding is still assessed after a replacement has voted.

`/wa` (`/web-advice`) is optional, never an implicit lifecycle gate: run it only when requested or separately authorized, and keep its real verdict if it runs. Existing standing authorization and any governing workflow that requires /wa still apply. Neither optional review permits ignoring a known correctness or safety blocker.

## Slow CI — never block-wait

Documentation-only changes use the CI exception immediately. **CI that does not exist is not CI to wait on.** Follow `../pr-green-definition/SKILL.md` § No-CI exception, including its evidence preconditions and the `Gate 1: CI NOT APPLICABLE — <reason>` record; if that evidence cannot establish a qualifying exception, Gate 1 stays unproven. Never replace this with `sleep N` + `gh pr checks`, and never call unrun CI passed.

For checks queued/pending more than 10 minutes, follow the local-equivalent exception in `../pr-green-definition/SKILL.md` § Backlogged CI: run the workflow's actual command and post current-head proof. Failed checks, no-conflict verification and merge authorization remain separate requirements.

## CodeRabbit/Bugbot — optional advisory reviewers

Read their feedback and take what is useful. They are never a draft-phase gate, never part of `/green` and never a wait, at any phase.
