---
name: hermes
description: Send authorized coordination to Hermes through the correct Slack identity or existing gateway, and distinguish message receipt from actual execution.

description: Coordinate authorized engineering work with Hermes through Slack, verify acknowledgment and evidence, and recover genuinely inactive ownership after 20 minutes.
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

Use the existing authorized private Slack conversation with Hermes. This skill
does not grant communication, repository, publication, merge, credential, or
machine access beyond the current user's authorization.
## Slack-only transport
- Resolve the recipient through the connected Slack directory and existing
  conversation history. Keep recipient IDs in machine-local configuration or
  the task checkpoint, never in this portable skill.
- Use a supported connected Slack send/read capability. Keep follow-ups in the
  verified task thread and retain its permalink.
- Do not invoke `hermes chat`, local HTTP gateways/proxies, SSH, terminal input,
  or another messaging platform as a fallback for contacting Hermes.
- If Slack is unavailable, denied, or its destination is ambiguous, report the
  exact blocker. Preserve the unsent request; do not bypass the restriction or
  create credentials, a gateway, or a new recipient.
- Before retrying an uncertain send, read the intended thread to determine
  whether it arrived. Never duplicate an already delivered or queued request.
## Request, acknowledgment, execution
Send a bounded handoff: task/goal, existing owner, repository and branch/head,
acceptance checks, evidence already available, permitted next step, holds, and
a unique task marker, and the originating Dot account/conversation reference
when Dot is the caller. Bind that origin to the verified calling account and exact
conversation URL, obtained from the current caller or a trusted tool result;
do not infer it from a display name, default account, or a similar chat title.
Ask Hermes to acknowledge the task and bound origin, review, monitor, and report
a concrete next action. Include takeover permission only when the user has
authorized it.
Track these states separately:
1. SENT: the transport returned a message reference.
2. ACKNOWLEDGED: a fresh Hermes-authored reply names the task and disposition.
3. EXECUTING: a current command/run or source artifact substantiates work.
4. COMPLETE: the acceptance checks are verified at the evidenced head.
5. BLOCKED: the exact missing capability, approval, or artifact is recorded.
For a requested monitor, record MONITORING only after its first evidenced check
and a supported continuation are established, including the next check or wake.
An acknowledgment or promise to watch is not a running monitor. For a Dot nudge,
record DELIVERED only with evidence that the exact message reached the bound
conversation; track its attributable reply separately from delivery. A transport
receipt alone does not prove either monitoring coverage or nudge delivery.
A reaction, echoed input, queue entry, process age, spinner, assignment, or
status claim alone is not an acknowledgment or proof of execution. Verify
results against source: head SHA, true test exit, raw log, capture, deployment
revision, or applicable operation receipt. Request a partial result promptly
rather than waiting for every lane to finish.
## Monitor and review
When the user asks to "cc Hermes" or have Hermes review a task, include
monitoring and authorized Dot nudges for that same task in the handoff. Do not
require a second request just to follow up. This does not authorize monitoring
unrelated work, new schedules, a second writer, or broader communication.
Explicit review-only/no-follow-up instructions override this default.
For work the user asked Hermes to oversee, agree on the monitored tasks and
reuse their existing checkpoints. Record owner, current operation, last
meaningful progress time with timezone, artifact, next action, and resumption
trigger. Check original sources and later cancellations before acting. Preserve
an explicit STOP or hold until the user clearly lifts it for that action and
target; a generic "continue," a review request, or this skill's recovery rule
does not release an unrelated or still-applicable hold.
Meaningful progress changes the acceptance evidence: a relevant commit,
advancing test/build output, a captured result, or a verified unblock.
A repeated status message, poll, acknowledgment, or changed timestamp does not
reset the inactivity clock. A long-running operation with fresh advancing
output remains active even without a commit. An unchanged remote head alone
cannot establish inactivity: inspect the owner's actual task activity, local
worktree when available, and command/test/build output. If that activity cannot
be verified, record UNVERIFIED and request evidence rather than starting a
second writer.
Use the current runtime's supported waits or existing authorized monitoring.
Do not install daemons, create competing monitors, or change schedules merely
by loading this skill. If the runtime cannot maintain checks, report the last
observation and arrange an authorized existing owner; do not promise coverage.
Hermes reviews exact-head evidence and reports findings to the current writer.
Review ownership does not itself transfer the writer role or grant merges.
## 20-minute inactivity recovery
At 20 minutes without meaningful progress, investigate rather than
automatically stealing the branch:
1. Re-read the original task, latest owner messages, PR/worktree changes, and
   actual run status. Missing or failed reads mean UNVERIFIED, not inactive.
2. Nudge the current owner with the last artifact and ask for its present
   action, blocker, or explicit handoff. Inspect delivery and response before
   retrying. Preserve peer drafts and any uncertain in-flight operation.
3. If a process is advancing, retain its owner. If approval, quota, access,
   device availability, or another real dependency blocks it, keep that lane
   BLOCKED and continue independent authorized work.
4. Take over only when the user authorized continuation/takeover, the task is
   still wanted, and source evidence establishes no competing live writer.
   Require an explicit handoff or independently verified ended/stopped owner;
   silence or an expired timer alone is insufficient.
5. Record the ownership change in the existing task/PR thread, preserving the
   branch, dirty files, evidence and all holds. Re-pin the head immediately
   before editing and stop if another writer has advanced it.
6. Resume the smallest authorized reversible step. Report the actual command
   and result. Never re-run a cancelled action, publish, merge, alter access,
   restart a service, or incur new provider usage merely to clear inactivity.
For a newly dispatched task with no progress yet, start the clock at its first
verified dispatch timestamp. Missing send confirmation leaves the task
UNVERIFIED rather than inventing a start time. The 20-minute threshold is then
measured from the last verified progress, not from the latest reminder. A resumed task resets it only after new meaningful
progress. Keep one writer and one monitoring record per task.
## Dot nudges
For a Dot-originated monitor authorized for both channels, at 20 minutes without
meaningful progress send a targeted nudge to the original calling Dot conversation
and cc that same Dot in the original corresponding Slack coordination thread.
Bind the Slack workspace, channel, thread, and Dot identity alongside the caller's
account and conversation URL in the handoff. Reverify that Slack identity and its
relationship to the calling Dot through the connected directory and original
thread before mentioning or routing; a display name or previously observed ID
alone is insufficient. Never substitute another Dot or broadcast to other chats.
Track the conversation nudge and Slack cc separately, with exact-message readback
and a message reference/permalink for each. If one route is blocked or ambiguous,
report that route's blocker and retain its message unsent; a successful route does
not establish delivery on the other. Preserve drafts, explicit holds, and STOP.
Hermes may nudge only the original calling Dot for the same engineering task.
Use the originating account, exact verified conversation URL, and stable
conversation/room reference recorded in the handoff; do not substitute the
default Dot, a different chat, or another
account. If the original destination is missing or cannot be verified, ask the
caller in the existing Slack task thread and keep the nudge unsent.
Read the installed [Dot skill](../dot/SKILL.md) and resolve that recorded origin
to its existing verified account and conversation. Recheck the active target
against that binding before submission. Set `DOT_ROTATE_ON_LIMIT=0` on every
Dot transport invocation
and pass the verified account/chat explicitly; the transport otherwise rotates
by default. A quota limit remains a blocker for that same target. Preserve peer
drafts: do not submit, clear, or modify another draft unless the user's
authorization covers that exact action and content. If a peer draft blocks the
nudge, retain it unsent and report the blocker. Verify that the exact nudge
appears in the bound conversation, then obtain an attributable Dot response;
record delivery and acknowledgment separately. A staged composer or queued send
is not delivery or acknowledgment.
Include the task marker, last progress artifact/time, current owner, blocker
and requested next action. Do not rotate accounts, bypass a denied route, or
share credentials. Keep this Hermes monitor's 20-minute evidence rule rather
than restarting its clock because a nudge was sent. No new recurring sender
is authorized by this section.
## Canonical installation and Linux sync
This repository copy is the source of truth. Do not maintain divergent local
Hermes instructions. After review and applicable approval, inspect the current
installer's scope before using it: a whole-catalog or `--merge` overwrite is not
a narrow Hermes install. Read the installed
[Linux workflow](../linux-remote/SKILL.md) for a requested Linux sync.
For this scoped change, reconcile exactly these three paths, relative to the
repository's `.claude/` and the destination `${CLAUDE_HOME:-$HOME/.claude}/`:
- `skills/hermes/SKILL.md`
- `commands/hermes.md` (flat `/hermes` pointer)
- `commands/extended-library/hermes.md` (legacy namespaced pointer)
Do not flatten the nested command into the flat destination: their relative
skill links have different depths. Copy each reviewed source to its matching
destination. The whole-catalog installer preserves this layout, but is not a
selective installer and must not be used for this narrow update.
Inspect all three destinations before writing, including symlinks and divergent
content. Reconcile differences first; retain recoverable originals outside the
discoverable command tree. Use an existing supported selective installer or a
permitted file-copy operation limited to these three approved files. Replace
the stale namespaced gateway entry with its reviewed pointer as part of the
same scoped update; updating only the flat command leaves an unsafe entry.
Do not overwrite Dot, Linux, or other installed packages to deploy Hermes.
If any destination cannot be safely reconciled or copied, report installation
blocked rather than claiming a complete install or broadening its scope.
Verify both `/hermes` and `/extended-library:hermes` resolve to the installed
canonical skill, and neither discoverable entry retains gateway instructions.
Check command discovery after reloading the runtime; file hashes alone do not
prove runtime discovery. Do not send a live message merely to test discovery.
Use only a connection permitted by the active runtime. An SSH example in a
skill does not override a requirement to use a registered remote executor.
If the Linux environment is disconnected or unauthorized, keep sync pending
with the exact blocker; do not use a different route to evade it.
Compare source and installed hashes on each host, preserve unrelated local
changes, and report canonical SHA, installed paths, validation exits and sync
result. Never sync credentials, browser profiles, account IDs, or secrets.
Installation alone does not establish Slack access or a running monitor.
