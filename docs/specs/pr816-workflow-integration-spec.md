# Workflow integration contract

## Outcome
Keep review commands, Slack attachment routing, portable redgreen guidance, and installer aliases consistent with their existing owners.

## Non-goals
Do not activate live Slack, mem0, model, or service integrations, change profile exclusions, or infer application intent in code.

## Acceptance
- The active auto workflow uses available advice; reviewdeep handles APPROVED, NOT APPROVED, and WITHHELD.
- Redgreen distinguishes source approval from recorded RED/GREEN execution evidence.
- Slack attachment reads select the existing reading procedure rather than the upload runner.
- Selecting slack-identity installs the Slack command; selecting both Slack skills installs both dependencies.
- The dispatcher validator retains mechanical checks without an editorial prose-length cap.
- Recall tests exercise positive query transport, field priority, and blank-field handling without a live memory request.

## User story
An operator can install the selected command aliases, find attachment-reading guidance, and follow review outcomes without mistaking source approval for execution proof.

## Proof plan
Use pinned source review, portable-manifest checks, causal installer RED/GREEN, focused contract tests, and current-candidate CI. Preserve original tested and reviewed revisions.

## Mock exemption
No rendered product interface changes, so no UI mock is required. Deterministic fixtures support local contract claims only; they do not prove live integrations.

## Risk
The installer retains a legacy alias-length fallback. Media operations in minimal profiles require explicit selection of the media skill; this change does not widen dependency closure.
