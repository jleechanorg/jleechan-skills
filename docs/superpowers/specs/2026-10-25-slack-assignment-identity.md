# Verified operator identity for dot-to-dot assignments

## Outcome
Authorized assignments between dots use the connected human operator's Slack account, with explicit AI attribution.

## Non-goals
No credential access, token copying, identity spoofing, additional communication authority, bot-health-check changes, or media-uploader rewrite.

## Acceptance
The /slack dispatcher reads the canonical identity policy first. The assignment route verifies the operator profile, workspace, user ID, recipient and destination before sending. Missing or mismatched identity fails closed rather than falling back to a bot. Readback verifies author and destination, and uncertain sends are reconciled before retry. Ordinary bot updates are unchanged.

## User story
An operator delegates through their dots without losing the intended human-account delivery route or hiding that the message was AI-sent.

## Proof plan
Existing thin-dispatcher and installer tests remain passing. No new test file ships with this change (artifact scope: documentation only). An isolated installer must copy the changed documents byte-for-byte. These checks do not prove a live external send or installed behavior on other hosts.

## Mock exemption
No application UI changes. Source and isolated installation evidence are sufficient for this instruction-routing claim; no synthetic Slack messages are sent as tests.

## Risk
Using a human account could imply personal authorship. Preserve the AI Terminal attribution and verify the account before sending. Exported files contain no actual operator email or account identifiers; identity comes from trusted private configuration or explicit user instruction. Policy text does not grant new authority or bypass access denials.
