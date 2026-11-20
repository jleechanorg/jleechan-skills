# Reviewer Timeout, Recovery, and Fallback Quorum

On-demand reference for [pr-lifecycle](SKILL.md): load when managing reviewer deadlines, handling timeouts, applying replacement quorums, or handling backlogged CI.

## Reviewer timeout and completion

For `/pr-workflow` and other lifecycle reviews, each reviewer attempt has a default wall-clock limit of 1800 seconds (30 minutes), starting when the request is queued or sent. Queueing and delivery wait count; progress, partial output or a new message do not reset it. An explicit user-specified limit, shorter or longer, governs that attempt, and a later specific user instruction to await a named reviewer overrides the deadline for that attempt even without a number. If the reviewer is explicitly unavailable or quota-blocked, stop the attempt and route to the fallback immediately. Do not keep waiting on the same attempt.

A timed-out `/dot`, requested `/wa` or other non-`/advice` supplementary reviewer attempt is recorded `TIMED_OUT` with request and timeout times and any partial receipt or findings, never PASS. It is discharged at timeout, and the workflow continues through the reviewer fallback: a passing `/er` on the finished evidence plus `/advice` approval from two independent reviewers at the same head. The two-vote quorum is mandatory for this substitution only; the table-selected source-review route is unchanged. A `/wa` timeout proves none of the browser-only validation it was meant to review. Required substantive safety, evidence and domain checks stay open until proved by applicable evidence or an eligible replacement review; a timeout grants neither readiness nor merge authorization. Assess late substantive findings when they arrive; they can reopen the affected gate.

If an `/er` reviewer times out, record `TIMED_OUT` and continue independent work, but keep the evidence-review gate open until an eligible replacement completes `/er` with an applicable PASS. `/advice` or another supplementary review is not proof that the evidence was reviewed.

The Markdown instruction-only route in [review-routing.md](review-routing.md#markdown-instruction-only-route) owns its one-or-two reviewer count and bypasses the generic 50-line /advice threshold. Outside that route, /advice uses one independent full-scope reviewer only for an eligible compact low-risk route under the obligation table; otherwise it keeps its two-independent-reviewer quorum. Stricter governing requirements and the mandatory two-vote supplementary-review substitution above remain in force. Apply [advice](../advice/SKILL.md)'s identity, independence, tier and reviewer-class counting caps. Replace a failed or timed-out seat with another eligible independent reviewer, and keep replacing until quorum is reached or no eligible attempt remains; record each seat and outcome. Below quorum the result is `WITHHELD`, not approval; the lifecycle then continues under § Self-review fallback instead of stopping. A late substantive `/advice` finding is still assessed after a replacement has voted.

`/wa` (`/web-advice`) is optional, never an implicit lifecycle gate: run it only when requested or separately authorized, and keep its real verdict if it runs. Existing standing authorization and any governing workflow that requires /wa still apply. Neither optional review permits ignoring a known correctness or safety blocker.

## Cold independent source substitution

Use the [audited static source fallback](final-approval.md#source-votes-when-external-lanes-are-blocked) when its conditions hold. It is an independent vote, unlike the driver's progress-only path below; it preserves route quorum and reviewer-class caps.

## Self-review fallback when independent votes cannot be obtained

A missing reviewer vote never ends the work. Use this fallback once every seat in [advice's order of attempts](../advice/reviewer-selection.md#order-of-attempts-for-a-missing-vote) has an attempt receipt or an evidenced skip reason and the independent votes countable at the head are still fewer than the selected route requires. Quota, missing login, timeout, a vendor failure, `WITHHELD` for coverage and a non-countable approval all qualify; "not attempted" does not. A competent blocking finding from any attempt still means `NOT APPROVED` and is fixed first.

Then the PR driver:

1. **Reviews its own change and records it.** Read the complete base-to-head diff, the changed code paths and their callers at the exact head. Fix or record a disposition for every finding the attempted reviewers returned. Write a `COVERAGE:` line naming what was actually read, and end with `SELF-REVIEW: NO BLOCKING FINDINGS at <40-hex SHA>` or the blocking finding to fix. Redo it after a material head change, under the [SHA-binding rule](review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain).
2. **Counts the self review for progress, and labels it.** Keep the source-review obligation `OPEN` in the review ledger with the note `SELF-REVIEW FALLBACK`, its owner and next action, and each missing seat's reset as the wake condition, beside the complete candidate report. Treat that open row as a recorded hold, not as the next gate to work: later gates proceed. `/advice` keeps its own `WITHHELD` verdict. A self review is not an independent vote; never report it as one or as `/advice` approval.
3. **Keeps going.** The fallback stands in for the source-review gate only (draft gate 2), for progress and never as an independent vote. Finish every other applicable draft gate first: the evidence bundle, visual findings and evidence review. Then undraft, drive `/green` at the current head, close comments and conflicts and finish every other obligation that does not need the missing votes. Besides the preview-deploy exception, this is the only case where undraft precedes the route's independent source approval.
4. **Withholds final approval.** Do not declare `FINAL_READY` or merge on the fallback. Report `final approval withheld — independent source votes N of M`, with each missing seat's earliest reset or missing capability, and continue other authorized work. In an opted-in six-stage repository the missing votes are the final closing approval, so once every other gate through CI and readiness is met the label is `stage:5-final-approval`; until then the earliest unmet gate still sets the label. There the title reads `[waiting][final approval withheld: N of M votes]` while a missing seat has a known reset; otherwise it reads `[blocked][final approval withheld: N of M votes]` and the human-blocker ping is sent.

The missing independent votes arriving at the applicable head clear only the source vote gate. `FINAL_READY` additionally requires a valid [cold final stamp](final-approval.md#closing-reviewer-and-stamp) and every other gate at that head. Otherwise the PR stays short of `FINAL_READY`, and merging is the user's decision under the governing merge rule: only a merge approval the user gives for this PR after the withheld report covers it, never a standing approval or an earlier one that assumed `/advice` approval. This section adds no merge path of its own. The fallback grants no merge authority and does not replace `/er`, visual approval, CI or any domain check.

## Slow CI — never block-wait

Documentation-only changes use the CI exception immediately. **CI that does not exist is not CI to wait on.** Follow `../pr-green-definition/SKILL.md` § No-CI exception, including its evidence preconditions and the `Gate 1: CI NOT APPLICABLE — <reason>` record; if that evidence cannot establish a qualifying exception, Gate 1 stays unproven. Never replace this with `sleep N` + `gh pr checks`, and never call unrun CI passed.

For checks queued/pending more than 10 minutes, follow the local-equivalent exception in `../pr-green-definition/SKILL.md` § Backlogged CI: run the workflow's actual command and post current-head proof. Failed checks, no-conflict verification and merge authorization remain separate requirements.

## CodeRabbit/Bugbot — optional advisory reviewers

Read their feedback and take what is useful. They are never a draft-phase gate, never part of `/green` and never a wait, at any phase.
