# 2026-06-10 — Instance #4 (wa-2289 godmode-l6 dispatch ack, C09GRLXF9GR)

**Thread:** `C09GRLXF9GR/1781139255.231799` (Hermes/user channel, WorldArchitect context).
**Trigger:** `ao spawn wa-2289` for godmode-l6 twin-copy repro investigation required posting a dispatch ack to the thread per the `dispatched-task-acks` commitment in SOUL.md.
**Form attempted:** `send_message` with `target=slack:C09GRLXF9GR:1781139255.231799`
**Where it landed:** `C0AJQ5M0A0Y` (home) as top-level. Tool response: `{"success": true, "platform": "slack", "chat_id": "C0AJQ5M0A0Y", "message_id": "1781145611.547459", "note": "Sent to slack home channel (chat_id: C0AJQ5M0A0Y)", "mirrored": true}`.
**Recovery:** Path B (curl `chat.postMessage` with explicit `channel=C09GRLXF9GR, thread_ts=1781139255.231799`) → `{"ok": true, "ts": "1781145623.237729", "thread_ts": "1781139255.231799", ...}`. Verified via `mcp__slack__conversations_replies` — the new message appeared in the source thread with `ThreadTs=1781139255.231799` (correctly threaded, NOT self-rooted). Then `chat.delete` on the C0AJQ5M0A0Y duplicate (`ts=1781145611.547459`) → `ok:true`.

**This is the 4th confirmed instance** of the `target=slack:CHAN:THREAD_TS` 3-part form falling back to home channel. Prior instances: 2026-06-06 C0AH3RY3DK6, 2026-06-08 C0AH3RY3DK6, 2026-06-10 C0AH3RY3DK6 (twice in 60s), 2026-06-10 C09GRLXF9GR (this one). Across two distinct user channels plus the home channel itself. The strip is universal, not channel-specific — the gateway is rewriting `target=slack:CHAN:THREAD_TS` to `target=slack:C0AJQ5M0A0Y` at the dispatch layer, dropping the channel + thread_ts arguments entirely. Not yet fixed at the gateway.

## Differences from prior instances

| Aspect | worldai-claw (23:33 UTC) | jleechanclaw (23:34 UTC) | wa-2289 godmode-l6 (19:44 PT) |
|---|---|---|---|
| Original channel | C0AH3RY3DK6 | C0AH3RY3DK6 | C09GRLXF9GR |
| Work context | dropped-thread followup | dropped-thread followup | AO dispatch ack |
| Scratch-leak before recovery | yes (6 internal-monologue messages) | no | no |
| Recovery path | top-level channel post | in-thread curl + 2 deletes | in-thread curl + 1 delete |
| Reasoning-leak trigger | `execute_code` stdout | none | none (used `terminal`/`send_message` only) |

The cleaner handling here (no scratch-leak, no reasoning-leak) is because: (a) this was a `send_message` attempt, not a multi-call probe; (b) the agent used `send_message` (which returns the `chat_id` clearly) rather than `execute_code` (which leaks stdout); (c) the agent followed the "verify post landed" guidance from this skill immediately on the first mis-route.

## What was right vs what could be improved

**Right:**
- Caught the mis-route on the FIRST `send_message` call (response said `chat_id: C0AJQ5M0A0Y` not the expected channel).
- Used Path B (curl `chat.postMessage`) for the in-thread fallback — clean threaded reply, not a noisy top-level channel post.
- Verified with `mcp__slack__conversations_replies` before declaring success.
- Deleted the home-channel duplicate promptly so the user wouldn't see noise.

**Could be improved:**
- Should have used `mcp__slack__conversations_replies` BEFORE attempting the post to check the thread exists (cheap preflight). Future agents: preflight first if the channel/thread is unfamiliar.
- Could have used the skill's `scripts/slack_mcp_post.py` helper (Path A, MCP HTTP-direct) instead of raw curl, which would be more robust to MCP server availability. Curl is fine as a Path B escape hatch but the helper is preferred for first-attempt.

## What to do if this exact pattern recurs (5th instance, 6th, ...)

The recovery is fully recipe-ified. The recipe hasn't changed across 4 instances. New instances should NOT add new sections to this reference file unless they reveal a genuinely new failure surface (e.g. token expiry mid-recovery, MCP server down forcing Path B, etc.). Append a one-line entry to the SKILL.md "Patches / known followups" log instead — the existing reference file is the worked-example archive, not a session-log.

## Cross-references (additive to the prior 3 instances)

- `slack-thread-routing-investigation/SKILL.md` — Path B recipe used verbatim
- `slack-messaging` skill — "send_message 3-part form" pitfall, now with 4 confirmed instances
- `dispatch-task` skill — Step 4a "posting the in-thread ack" guidance, which this instance followed
- `~/.hermes_prod/SOUL.md` — `## COMMIT: slack-reply-inherit-thread-ts` (the rule that triggered the failed 3-part attempt)
- `~/.hermes_prod/SOUL.md` — `## COMMIT: dispatched-task-acks` (the rule that required the dispatch ack in the first place)
