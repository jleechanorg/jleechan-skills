# Bounded reviewer waits with a mandatory advice quorum

## Outcome

PR drivers move on from a reviewer attempt after 600 seconds without losing the
two independent, full-coverage reviews needed for `/advice` approval. Claude,
claudewa, Codex, AGY, and Cursor's agent are eligible transports.

## Non-goals

Do not change merge authority, evidence sufficiency, advice applicability by
diff size, credentials, runner implementations, or persistent model defaults.
Do not count a timeout, acknowledgment, research result, alias, or orchestrator
as an independent approval.

## Acceptance

- The attempt deadline includes dispatch and queue time; progress does not reset it.
- A slow supplementary reviewer is recorded as timed out, not approved. Applicable
  evidence review and two-reviewer advice remain the completion path.
- A missing advice vote starts an eligible independent replacement. One approval
  remains WITHHELD; two complete independent approvals may satisfy the gate.
- Known material findings remain actionable even if a reviewer times out or a
  late result arrives after the workflow advanced.
- Instructions pass 600 explicitly to the existing primary-pair runner and do
  not claim it supports alternate reviewer names that its parser rejects.
- Each verdict retains exact scope, reviewer identity, coverage, and source SHA
  or document hashes. Reusing a verdict never creates another vote.

## User story

No player-facing change. An operator currently waits for a busy Dot or a
quota-limited reviewer even when other reviewers are available. After this
change, the driver records the failed attempt and obtains the remaining
independent review through another eligible transport.

## Proof plan

Inspect the complete policy diff and entrypoint consistency. Run existing
focused lifecycle, approval, and runner contract checks without changing their
assertions. Have two independent reviewers evaluate timeout, replacement,
coverage, and merge-boundary scenarios at the final revision. Publish sanitized
receipts; distinguish source-policy verification from actual installed runtime
or ten-minute process-supervision proof.

## Mock

Not applicable: this changes agent instructions, with no application UI.

## Risk

An agent could mistake timeout for assent or count aliases as separate votes.
Explicit failure dispositions, independent execution identity, retained findings,
and WITHHELD below quorum prevent that interpretation. Alternate transports need
bounded execution and isolated checkouts; documentation does not add runner APIs.

## File justification

GOAL: remove unbounded reviewer waiting while retaining independent approval.
MODIFICATION: update the lifecycle owner, advice instructions and their pointers.
NECESSITY: the current Dot route permits an hour of waiting, the advice invocation
uses twenty minutes, and fallback rules cannot fill one missing primary vote.
INTEGRATION PROOF: existing aliases resolve to these owners; focused checks and
independent policy review cover the resulting route. Tracking: `bd-ospw`.
