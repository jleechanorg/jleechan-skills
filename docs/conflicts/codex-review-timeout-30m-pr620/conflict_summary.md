# Conflict Resolution: PR #620

## File: `.claude/skills/advice/SKILL.md`

**Conflict Type**: Reviewer-attempt deadline policy and queue/cleanup requirements
**Risk Level**: Low

**Original Markers**: `<<<<<<< HEAD`, `=======`, `>>>>>>> origin/main`.

**HEAD arm (excerpt)**: One default 1800-second (30-minute) budget, explicit
shorter or longer user limits, and a named-review wait override.

**`origin/main` arm (excerpt)**: A 600-second deadline, queue-boundary
timestamps for the primary-pair runner, and cleanup and receipt-write overrun
invalidation.

**Resolution**: Kept the 1800-second default, explicit shorter and longer user
limits, and the named-review wait override. Preserved `main`'s queue-boundary
capture and same-host timestamp requirements, remaining-budget bounds, cleanup
and receipt overrun handling, and vote invalidation rules. Routine status updates
do not reset the deadline; no timer machinery was added.

**Reasoning**: This combines the requested 30-minute reviewer budget with the
newer safeguards that ensure queueing, dispatch, cleanup, and receipt outcomes
determine vote eligibility.

## Specification

- **Outcome:** Default each complete reviewer attempt to 1800 seconds and pass
  the existing runner's attempt, work, cleanup and grace limits explicitly.
- **Non-goals:** No runner implementation, active-deadline extension, new
  transport, credential, network retry, autonomy or merge-authority change.
- **Acceptance:** Preserve explicit shorter or longer limits, later named-review
  wait instructions, original queue timing, cleanup requirements and independent
  full-scope quorum. Status questions never reset the clock; partial, failed,
  late or timed-out attempts never supply approval.
- **User story:** No product UI change. A reviewer can finish a large requested
  scope within the longer default while the operator retains control of time.
- **Proof plan:** Run focused installer, lifecycle and approval checks; inspect
  before/after policy scenarios; probe explicit 300/1800/2700-second settings;
  independently review the complete source and delivered evidence. Successful
  reviewer runs do not prove actual deadline expiry or live extension support.
- **Mock exemption:** This changes Markdown instructions without product UI.
- **Risk:** Longer attempts consume more time. The existing runner cannot extend
  a running deadline; report an unavailable route and retain an open gate when
  a later user instruction requires that unsupported capability.
