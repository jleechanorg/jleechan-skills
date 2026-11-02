---
name: grokbot
description: Read or send an explicitly authorized message to an existing Grok bot conversation using verified browser controls; grokb is an alias.
---

# /grokbot

Use the existing authenticated browser and supported browser-control tools,
analogous to /dot. This skill owns conversation/identity checks and send policy;
it does not install a browser, create bots, dispatch source work by default,
call a provider API or use another model as a transport.

## Resolve the requested operation

Default to read-only unless the user requested a send. Resolve the exact existing
`https://grok.com/bot/<bot-id>` conversation from the user's request or their
private `~/.config/grokbot/config.json` route mapping. Keep actual bot IDs,
account names and private work inventory out of this public package. Do not
create a replacement bot, guess a route from a title, reuse another service's
login, or switch accounts to get around a limit. Missing mapping is a precise
blocker; continue unrelated authorized work.

Use the runtime's directly supported browser-control interface. Honor its
instructions and the user's browser preference. On a host with an installed
browser-default workflow, follow it; do not substitute browser-side inference,
shell HTTP, internal APIs or unsupported DOM/browser hooks. In an app with
computer-use browser tools, select the requested browser/tab through that API,
read its current documentation and inspect the rendered UI before each action.
Never assume a locator or selector from an old run still exists.

## Identity, destination and one writer

1. Establish the expected signed-in identity from the user's current request
   or trusted private configuration. Verify it against the rendered account UI
   before reading conversation content or composing. Login presence alone is
   not an identity match. Return identity-match booleans, not email/account data.
   If identity cannot be verified, stop without sending; do not enter credentials,
   attempt an auth repair or grant new access.
2. Verify the bot URL plus visible conversation title and relevant context.
   A redirect is neither success nor failure by itself. Ambiguity means HOLD.
   Read only the context needed for the requested task and duplicate check.
3. Keep one writer for this conversation/composer through the existing owner
   checkpoint. Preserve active peer drafts and edits; do not clear, submit or
   overwrite a peer's text. If ownership is uncertain, inspect read-only and
   return the conflicting scope. Sending requires positive evidence that the existing
   ownership mechanism establishes the sole current conversation writer, across
   request IDs and senders; an empty composer or request-scoped receipt alone
   cannot establish exclusion. If that mechanism or checkpoint is unavailable
   or unproved, HOLD without typing. Do not install another lock service or sender.
4. Do not copy cookies, browser profiles, local storage, tokens or credentials.
   Never launch a second browser against an occupied profile, delete locks or
   resync sessions. If the existing authorized browser is unavailable, name the
   transport/identity blocker without treating a new profile as logged in.

## Read or send

For a read-only request, inspect the requested existing conversation and report
the source/head and original artifact timestamps actually available. Never
type, clear a draft or send a test message merely to prove the skill works.

For an authorized send:

1. Preserve the exact requested payload and scope in the existing task checkpoint.
   For a work request include its existing ID, retained owner/scope, exact head,
   next authorized action, acceptance, checkpoint and resumption trigger. This
   skill does not grant work authority, ownership or extra execution capacity.
2. Reuse one stable logical-request marker across retries, routes and runs.
   Before typing, inspect prior delivery receipts and the rendered conversation.
   An already-delivered marker returns its prior receipt, never a second send.
   An unresolved prior attempt is UNCERTAIN: inspect read-only and do not resend.
   Preserve that state in the existing owner checkpoint across interruptions;
   a fresh invocation or new marker is not permission to duplicate the action.
3. Persist the stable marker, exact payload hash, target, writer and pending-attempt
   state in the existing durable owner checkpoint before typing. Verify that
   state can be recovered across interruption; unavailable persistence means HOLD.
   Immediately before submit persist UNCERTAIN and verify that write succeeded.
   Only positive delivery readback may transition it to DELIVERED; a crash leaves
   the uncertainty hold intact. This uses the existing checkpoint, not a new ledger.
   Revalidate identity, target, one writer and send authority. Inspect the composer
   for a peer draft. Fill through the supported UI only, read back the complete
   text and compare it to the exact payload before submitting. If a supported
   control cannot preserve the text, stop before submission.
4. Submit once using the observed enabled send control. Verify the exact outgoing
   message rendered in the intended conversation and a cleared composer. A click,
   URL, process exit or changed Working badge is not verified delivery.
5. After timeout, disconnect, mismatched readback or incomplete verification,
   report UNCERTAIN with the target/request marker and do read-only reconciliation.
   Do not automatically retry, send a correction, rotate accounts or clear drafts.
   There is no destination idempotency or exactly-once guarantee.

## Receipts and follow-through

Keep these claims separate, bound to the same request marker and target:
- DELIVERED: exact outgoing content and cleared composer were observed.
- PICKED_UP: the named incumbent explicitly accepted that bounded request.
- EXECUTING: an attributable original command/test/artifact proves actual action
  at the stated head; acceptance, generic Working and queued CI are insufficient.
- CHECKPOINT: owner/head, acceptance state, original evidence time, current action,
  next action, hold and trigger are recorded through the existing checkpoint.
- COMPLETED: acceptance was independently verified against the actual artifacts.

Use bounded observations under the current task's existing deadline; do not
create a scheduler or daemon. Polling and status refresh never change the last
execution timestamp. A claimed result must be checked at its source. Report
unverified delivery/pickup/execution honestly and keep remaining owner work
retained. Preserve the caller's shared capacity limit, one source/native operator,
privacy rules, human approvals and explicit denials. No source assignment is
created by a route label, bot reply or this skill's installation.
