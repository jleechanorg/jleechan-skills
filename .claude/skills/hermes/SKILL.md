---
name: hermes
description: Send authorized coordination to Hermes through the correct Slack identity or existing gateway, and distinguish message receipt from actual execution.
---

# Hermes coordination

Retain the existing conversation and incumbent work owner. Do not start duplicate writers or operators.

## Sender and recipient

- Distinguish the assistant's Slack bot from the owner's connected Slack identity. Their private-conversation access is different.
- Resolve Hermes from a verified conversation/profile and read the connected sender profile. Never guess accounts or hardcode personal names, emails, workspace IDs or channel IDs.
- When the current task authorizes acting as the owner, use the connected owner-identity Slack connector for the existing Hermes DM. Do not ask again for clearly granted authorization covering that sender, recipient and bounded task.
- This skill itself grants no standing permission or new access. Keep private source/review packets and campaign diagnostics in authorized private destinations. Finding another channel does not silently authorize wider disclosure.

## Send and verify

1. Read the existing thread to establish task scope and ownership.
2. Use the authorized identity and supported connector. An explicit owner-identity request must not default to a bot-only tool merely because it is the usual reply tool.
3. Retain the returned message ID/permalink and read back the sent message. Distinguish send acceptance, delivery, Hermes acknowledgement, executing action and completed result.
4. A reaction or “steered into current run” is receipt/queue evidence, not a command receipt. Obtain the actual head, command/artifact or blocker when completion depends on execution.
5. For an uncertain send, inspect the destination before retrying. Do not duplicate possibly delivered requests.

## Diagnose the right boundary

- Bot `channel_not_found` or `not_in_channel` identifies that identity's destination/access problem, not necessarily a Hermes outage. Check the authorized connected identity before declaring all messaging blocked.
- After an access or approval denial, stop that action. Do not switch identities, routes or tools to evade it. Later explicit owner authorization changing sender or destination is new evidence; use the normal approval path.
- Follow supported channel-membership recovery only within current authorization. Private channels require proper invitations. No credential, grant or permission change is implied.
- A transient approval-review failure with confirmed nonexecution is not an unsafe-action verdict. Preserve it and follow the normal bounded retry policy in current instructions.
- Verify gateway health through actual inbound processing and a response. Log age, a running process or an outbound scheduled post alone proves neither health nor outage.
- Do not restart an active gateway or change model/provider/account to cure a Slack destination error.

## Existing gateway fallback

Use the gateway only when authorized and accessible in the selected execution environment. The cloud assistant's localhost is not the owner's host; use the supported remote execution route when needed.

Existing interfaces: synchronous POST `/v1/chat/completions` with model `hermes-agent` and a user-message array; asynchronous POST `/v1/runs` with model and input. Resolve the endpoint from existing configuration, without creating credentials.

Serialize payloads with a JSON encoder; never interpolate arbitrary text into shell code or hand-built JSON. Bound timeouts and distinguish HTTP/transport failures from returned model responses. Retain asynchronous run IDs for readback: started does not mean completed and does not guarantee a Slack DM.
