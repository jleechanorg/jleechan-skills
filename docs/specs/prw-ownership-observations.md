# Measure unattended PR time and review pickup

A PR driver needs to know how long a PR had an actionable next step with nobody executing it and no verified pending wake-up. A reviewer may finish before the driver picks up the result. Measure completion, notification and substantive pickup separately where the corresponding events are observed.

## Scope and user story

A workflow operator inspecting an assigned PR can distinguish known unattended minutes, time covered by observations and time with insufficient evidence. Use the existing receipt collector and dashboard summary. A paused task, human decision or verified pending wait has its own state. Collection is observational and never blocks the workflow. This change introduces no scheduler, permission, live installation or retrospective inference from quiet time.

## Acceptance and proof

- Read the existing transition JSONL through the normal collector. Preserve legacy event behavior and accept supported versioned ownership observations. Keep projected records free of local paths.
- Bind observations to one repository-qualified PR, head, attempt and primary obligation. Count only intervals with verifiable continuity. Deduplicate mirrored observations. A gap, head change or contradictory event leaves the affected interval unknown.
- In a fifteen-minute window, five minutes unowned before work starts and three minutes after a result returns produce eight verified unattended minutes. Acknowledgment alone never starts work. A wake that fires ends the wait when the result is actionable.
- Publish a lower bound and observation coverage for partial windows. Rank only fully observed windows. An observed zero and missing data must be distinguishable.
- Exercise ingestion, aggregation and export with focused tests, then compare one actual handoff against a read-only shadow snapshot. Report the pilot population and unknown intervals before drawing conclusions about throughput.

## Presentation and risks

The existing attention summary supplies the presentation. A separate visual mock is unnecessary for the receipt format. Incorrect joins can make unobserved work appear unattended or hide genuine pickup delays. Tests cover conflicting and missing records, unmatched revisions, mirrored retries and the end of the observation window. The pilot establishes delivery and arithmetic. Demonstrating faster closure requires comparable live assignments.

## Version 1 JSONL emission contract

The optional ownership pilot writes path-free observations through the existing
`PRW_METRICS_RECEIPTS_DIR/transition-events.jsonl` feed. It adds no service,
runner, scheduled job, hook, or PR gate. Each record is one JSON object per line.
The existing scheduled collector remains the reader. A failed or unavailable
append is best effort and never blocks, delays, or rejects PR work. Report that
PR as uncovered for the affected interval.

### Version 1 record

Every ownership event has the legacy pairing identity plus the v1 ownership
identity:

```json
{
  "event_id": "evt-006",
  "event_type": "next_action_started",
  "occurred_at": "2026-11-05T10:15:00Z",
  "observed_at": "2026-11-05T10:15:02Z",
  "pr_id": "example-org/repo#20",
  "candidate_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "attempt_number": 2,
  "schema_version": 1,
  "obligation_id": "review-result-follow-up",
  "source": "driver-session-42",
  "sequence": 6,
  "preceding_event_id": "evt-005",
  "state": "executing",
  "owner_id": "driver-session-42",
  "worker_id": "worker-2",
  "result_receipt": "review-follow-up-started-42",
  "continuity_from_event_id": "evt-005",
  "continuity_receipt": {
    "receipt_id": "driver-record-42",
    "covers_from": "2026-11-05T10:13:00Z",
    "covers_to": "2026-11-05T10:15:00Z",
    "pr_id": "example-org/repo#20",
    "candidate_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "attempt_number": 2,
    "obligation_id": "review-result-follow-up",
    "owner_id": "driver-session-42"
  }
}
```

`event_id` stays stable across retries and mirrored collection. `event_type`
names the transition. `occurred_at` is when it happened and drives duration.
`observed_at` is when the owner recorded it. Timestamps are UTC RFC 3339.
`pr_id`, the full candidate SHA, positive attempt number, obligation, source
identifier and positive sequence bind the observation. Sequence increments for
each event emitted by the same source for that PR. `preceding_event_id` forms
the causal chain. `source` is a stable, path-free identifier, never a filesystem
path or transcript.

Version 1 states are `actionable_unowned`, `executing`, `verified_wait`,
`paused`, and `endpoint_reached`.

- `actionable_unowned` means an authorized next action is available and no
  worker or job is executing it. Include `result_receipt` proving the result or
  obligation is actionable. `owner_id` may name the accountable driver.
  `worker_id` and `job_id` are absent.
- `executing` means scoped substantive work actually began. Include
  `result_receipt` for the observed start and either `worker_id` for a human or
  agent action, or `job_id` for a running job. An assignment, acknowledgment or
  status message alone does not establish execution.
- `verified_wait` means a verified job or wake is the next expected change and
  no independent primary action is available. Include `wait_reason` and either
  a live `job_id` or both `wake_trigger` and `wake_due_at`. Once the wake fires,
  record a `wake_fired` event. If work is now actionable with no executing
  owner, its state is `actionable_unowned`.
- `paused` records an explicit pause or expired authorization and includes
  `wait_reason`. Paused time is outside actionable time.
- `endpoint_reached` records completion of the requested endpoint and includes
  `result_receipt`. Time after it is outside actionable time.

Use `worker_returned` when a result makes the next obligation actionable.
Record `wake_fired` separately when a notification fires. The review-return to
pickup interval ends only at `next_action_started` or `worker_started` when that
event proves substantive work began. A wake notification does not close that
interval. Record `worker_acknowledged` separately when useful. It does not start
execution or end actionable-unowned time.

### Continuity and interval rules

The event closing an observed span sets `preceding_event_id` and
`continuity_from_event_id` to the exact prior event ID. It carries a
`continuity_receipt` object referencing the continuously accountable driver or
job record. The receipt identifies its source record, exact UTC `covers_from`
and `covers_to` boundaries, PR, candidate SHA, attempt, obligation, and an
`owner_id` or `job_id`. Boundaries equal the prior and closing event times.
Every supplied identity must match both events. If `worker_id` is supplied, it
must also match both endpoints. No local path or private transcript is included.
A missing, malformed, mismatched, or unverifiable reference leaves that span
unknown.

The collector admits ownership intervals only for schema version 1. It links
causally adjacent events at the same PR, head, attempt and obligation, and
validates continuity identity, boundaries and source sequence. Same-source
sequence numbers must advance by one across adjacent events. Conflicting event
IDs, missing sequence, gaps, contradictory same-time transitions, head or
attempt changes, an expired wake, and a missing receipt interrupt coverage.
Mirrored identical event IDs count once even if `observed_at` differs. Unknown
schema versions contribute no ownership interval. Legacy seven-field records
remain available to the existing transition metrics and cannot prove v1
ownership continuity.

The collector clips proven spans to the report window and to the PR's creation
time. It reports verified actionable-unowned minutes, unknown minutes and
coverage. Only a fully observed window can enter the ranked attention list. A
partial window exposes its verified lower bound and unknown duration outside
the ranking. A measured zero requires full observed coverage. A missing feed,
lost observer, unobserved tail or incomplete handoff remains unknown. These
observations are informational and never control PR authorization or progress.
