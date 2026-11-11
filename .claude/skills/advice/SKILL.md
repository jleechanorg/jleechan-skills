---
name: advice
description: Use when a focused second opinion is needed; collect the applicable independent, full-coverage reviewer votes on an exact change or saved-document bundle.
---

# /advice — independent second opinion

Use `/advice [question]` instead of `advisor()`. This skill owns selection, quorum, deadlines, isolation and receipts.
[static-review](../static-review/SKILL.md) owns reviewer input; [pr-lifecycle](../pr-lifecycle/SKILL.md#advice-applicability) owns phases, thresholds, applicability and publication; evidence-standards owns evidence classes.
Follow the flow below. Read the linked operational section before its action; load transport-specific details only for the selected route.

## 1. Pin the question and complete scope

Inspect existing verdicts and [resubmission/applicability](reconciliation.md#5-reconcile-and-report) before queueing: preserve eligible unchanged approvals and request only missing or affected judgment, or explicitly requested further review.
Read [scope and packet rules](review-process.md#1-pin-the-question-and-complete-scope). Pin the full 40-hex revision or identical complete document bytes and hashes; unbound documents approve only `DOCUMENTS sha256:<BUNDLE HASH>`.
Keep the user's question with the orchestrator. Every reviewer receives only static-review's channel preamble and filled template, with a complete pointer; no question, summary or framing.
Each approver covers the entire scope; recover truncation within its deadline, never combine partial readers. Source approval does not supply the separate [evidence-review](../evidence-review/SKILL.md) verdict.

## 2. Select independent reviewers

Record route/count before dispatch. Default: two independent full-scope source votes. Use one only when pr-lifecycle positively selects a one-source route and the reviewer confirms eligibility; explicit advice uses the same count.
Stricter requirements bind. Mandatory supplementary-review substitution still requires two eligible advice votes and applicable evidence review. Archive integrity is not source approval; votes never change merge authority.

### Capability profile and tier selection

Read [selection/admission](reviewer-selection.md#capability-profile-and-tier-selection), using available, authorized capabilities and the existing machine-local profile.

| Tier | Candidates | Counting |
|---|---|---|
| 1 | Authorized CLI/model seats including extras, Dot accounts, Instinct | Alternatives; no mandatory brand/pair. At most one Dot and one Instinct; never combine them into a two-vote quorum. |
| 2 | Native static reviewers; Hermes/Hermes-PC | Static reviewers collectively at most one vote; Hermes instances collectively at most one. |
| 3 | Authorized authenticated web chats via /web-advice | Only when earlier tiers cannot fill remaining quorum. |

### Candidate checks, fan-out and fallback

Before dispatch, enumerate every configured account and host, including extras and outside routes. Carry roster, authorization sources, existing attempts and remaining dispatch budget into orchestration briefs, never cold reviewer prompts.
Read [candidate checks](reviewer-selection.md#candidate-checks-fan-out-and-fallback). Check existing configuration, verified bindings and quota receipts; use supported non-message probes when needed, never chat pings to all candidates.
Launch missing eligible independent reviews concurrently within runtime/resource limits. Keep valid votes and in-flight deadlines, avoid duplicate requests, replace unavailable/failed/timed-out seats, and advance tiers when needed. Each replacement consumes an assignment; stop new dispatch at quorum unless another authorized obligation requires it.
Account for **every candidate in the receipt and user-facing report**: disclosure-safe candidate/host alias, health evidence/time, review attempted yes/no, outcome or evidenced skip reason, receipt/next action. Distinguish probes from launches; unknown stays UNKNOWN, missing attempt receipts mean UNVERIFIED.
Record AVAILABLE, UNAVAILABLE with reason, BUSY with handle, QUOTA with printed reset, or DUPLICATE with identity key. Busy/quota/duplicate seats reserve no votes. Do not claim exhaustion while an eligible unattempted candidate can fill the gap within authority/budget.

### Identity

Read [identity rules](reviewer-selection.md#identity) before admitting a seat. One actual account is one vote across aliases/hosts/retries. Author, orchestrator and /research do not vote; a Dot lifecycle-leg verdict cannot count again as advice.
CLI models require reliable runtime metadata; outside fields are `attested.` with privately verified frozen bindings and independence proof. Missing public fields differ from unverified identity. Keep private identities machine-local.

### CLI capabilities

For CLI seats, read [commands, configuration, quota cache and readback](reviewer-selection.md#cli-capabilities). Set-but-invalid overrides make the seat unavailable; never silently use defaults. Bound and receipt each attempt; no new runner, wrapper, watchdog or timer.

### Outside-route authorization and transports

Before outside dispatch, read [authorization and transport rules](reviewer-selection.md#outside-route-authorization-and-transports). Portable instructions grant no disclosure authority: use machine-local opt-in or explicit task authorization; preserve restrictions and secret protection. Instinct resolves authorization through its own skill.
Dot uses interactive transport, caller-selected account and `DOT_ROTATE_ON_LIMIT=0`; its whole route expires one budget after first send. Hermes is Slack-only; web needs actual attachments and account attestation. No forbidden transport substitution.

### Native static fallback

For native seats, read [static fallback](reviewer-selection.md#native-static-fallback) and static-review; packet-only context, never parent-history forks. Each counted seat covers the whole scope; preserve explicit outside-review obligations.

## 3. Enforce the attempt deadline

Read [deadline mechanics](review-process.md#3-enforce-the-attempt-deadline) before dispatch: 1800 seconds end to end, static 600, unless user sets a limit; explicit named-reviewer wait instructions follow the documented exception without extending an already-running native timeout.
Capture queue clocks on the launching host; reserve cleanup/readback time inside the budget, bound calls/waits, and receipt actual completion. Progress never resets the clock. Late/failed/incomplete attempts and cleanup/receipt overruns cannot approve; keep findings and use another eligible seat.

## 4. Review access modes and isolation

Read [access-mode table and checks](review-process.md#4-review-access-modes-and-isolation) before selecting cheapest complete access and dispatching. Reviewers stay read-only despite full permissions; preserve original state. Use copies only when needed, in configured Scratch; remove only owned copies after verified process exit. Unresolved cleanup is non-countable and its resources cannot be reused.

## 5. Reconcile and report

Read [counting, verdict, receipts and applicability](reconciliation.md#5-reconcile-and-report). Count only attributable full-scope COVERAGE/VERDICT with the required successful receipt and mode-specific checks. Acknowledgement is not approval.
Reconcile disagreements yourself. One competent blocking objection, including from a partial reviewer, means NOT APPROVED. P1/P2 alone are nonblocking; batch fixes/dispositions. Below eligible quorum means WITHHELD.
Report the exact target, every reviewer's verdict/coverage/reasoning/risk/findings, answer to the question, full candidate roster, and per-attempt receipts. Preserve original clocks/eligibility when repairing bookkeeping; never fabricate coverage or revive void votes.
End with exactly one target-bound `VERDICT: APPROVED at <target>`, `VERDICT: NOT APPROVED at <target>`, or `VERDICT: WITHHELD at <target> — <reason>` line, using the reference's full-SHA or document-bundle format.
