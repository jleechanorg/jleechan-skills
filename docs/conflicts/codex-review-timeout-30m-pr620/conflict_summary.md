# Conflict Resolution: PR #620

### File: `.claude/skills/advice/SKILL.md`

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
