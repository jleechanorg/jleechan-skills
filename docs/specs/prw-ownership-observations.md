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
