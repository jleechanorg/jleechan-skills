# PR driver decision evidence

## Purpose

PR drivers already track the current stage, next action, owner, active job, and wake condition. This proposal adds a lightweight way to connect a long-running action to the decision its result will inform. The goal is to help an operator see what is being learned, what is still underway, and what will happen when a result arrives.

This is a design proposal. It does not change the lifecycle contract or claim that the proposed wording improves completion time.

## Proposed behavior

Before starting an expensive check, review, or browser journey, the driver identifies the observation that would change its next decision. Keep this in the existing status update or handoff with the PR, current head, unmet requirement, action, expected evidence, and any running job handle. When the next action is obvious and inexpensive, start it without adding a planning step.

Use the user's priority and deadline. Continue an actionable requirement already underway when it is the highest-priority work. Keep independent PR work moving when capacity permits. When a dependency prevents progress, name the event that would unblock it and continue another authorized action.

When a result arrives, compare it with the expected observation. Link the returned artifact, identify the revision it tested, and state the next decision. Partial evidence may narrow the issue without closing a gate. If the head or base moved, retain the original receipt and determine which claims remain applicable before relying on it.

Keep the behavior within the existing lifecycle and execution record. It adds no scheduler, separate checklist, approval requirement, or evidence gate. It does not change user priority, ownership, review, merge, or safety rules.

## Examples

| Situation | Driver response |
|---|---|
| A browser job timed out while downloading Chromium before tests began. | Inspect the job output and runner's browser state. The timeout establishes that the journey did not reach assertions. Start one focused run when a compatible browser is available, and retain its actual handle. |
| A batch matching operator messages to PRs requests ten results and returns nine. | Preserve the rejected batch and identify the missing message. Do not report accepted predictions or a gain. Compare only after a complete candidate result and independent references exist for the same eligible events. |
| A PR reaches final approval with only merge authorization outstanding. | Record the exact head and the remaining human decision. Keep Stage 5 readiness distinct from merge authority. |
| Two terminals mention the same PR. | Check the live PR, branch activity, and ownership record before assigning work. A repeated mention alone does not establish a second owner or a new nudge. |

## Pilot and evaluation

Evaluate the current lifecycle on fixed scenarios using identical inputs and a pinned source. Record actions, deciding observations, expected evidence, and input/output hashes. Independently assess each decision, preserve baseline passes as regression cases, and link the receipt. If any baseline case fails, change only the relevant wording, rerun the same cases with the same model, and independently assess each changed decision. If all cases pass, leave lifecycle instructions unchanged.

For adoption, first observe current practice to identify whether a decision gap exists. If none appears, stop without an instruction change. If a gap appears, compare authorized assignments using the proposed observation in existing status updates with matched assignments using current practice. Match starting stage and unmet-work type. Give each assignment the same observation duration from its start, and freeze the enrollment cutoff before comparison. Report unmatched cases.

For each assignment, record time to the first independently verified requirement closure and whether it reached Stage 5 during the observation window. Include open assignments and observation duration. Separate time spent waiting for human approval, external services, and missing records. Count human nudges only when source records support their attribution, and count each message once across the cohort. Leave unknown attribution unknown.

Use existing PR events, check logs, and evidence receipts. Do not infer time intervals from missing events. A small cohort is a feasibility check, not strong causal evidence. Report individual outcomes alongside cohort counts.

Consider broader adoption only when comparable cases show faster verified closure without evidence shortcuts or added human intervention. Extend the observation when cohorts are small or materially different. Revisit the design if it adds status work without changing decisions or delays independent work.

## Acceptance criteria for an implementation

- The driver names an observation before expensive work when that observation can change the next action.
- The driver keeps and resumes an existing job instead of repeating work without a reason.
- The driver preserves the user's priority and continues independent authorized work when feasible.
- A partial or infrastructure result is not reported as product success or failure without supporting evidence.
- Every status claim is tied to its source artifact and tested revision.
- Existing review, evidence, stage, approval, and merge requirements remain controlling.
- Pilot results include unfinished cases, observation windows, and attribution gaps.
