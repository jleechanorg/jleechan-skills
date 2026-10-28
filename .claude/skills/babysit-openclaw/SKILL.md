---
name: babysit-openclaw
description: Monitor OpenClaw Slack tasks for stalls or fabricated progress and nudge them safely.
---

> **Terminal-reading rule (canonical):** before any classification, assessment, or steer of a
> cmux surface, read the surface's FULL available history (~10k words when possible;
> `cmux capture-pane --scrollback --lines 1500`), then the last ~15 lines for current state.
> Never decide from a short tail. Canonical: `~/.codex/AGENTS.md` section
> "Reading a cmux terminal before deciding (full-buffer rule)".

# babysit-openclaw

Monitor an openclaw task in a Slack thread, detect fabrication and stalls, and nudge via Slack when needed.

## Usage

```
/babysit-openclaw <thread_ts> [channel_id]
```

Default channel: `<slack-channel>`

## Step 1 — Read the thread

```python
# Use the authorized Slack history/replies integration
# channel_id: <slack-channel> (or provided)
# thread_ts: <from argument>
```

Read the full thread context, including the task instruction, previous status
reports, and linked artifacts. Do not assess the task from its last message alone.

## Step 2 — Assess status

Treat each completion claim as a claim to verify. Compare it with the requested
artifact or a fresh independent result from the named command, service, or
process. Message style and elapsed time are not proof of fabrication.

### Unverified claims
- A report names commands but provides no attributable output or artifact.
- A report gives a generic success summary without the requested result.
- The cited output is stale, belongs to another task, or does not establish the claim.

Report these as `UNVERIFIED` until independent evidence resolves them. Classify
a claim as fabricated only when current independent evidence contradicts it.

### Work and stall assessment
- Fresh attributable output is evidence of progress, not proof of completion.
- Do not classify a task as stalled from elapsed time or silence alone. Check the
  current agent/session state, recent transcript or job output, and requested
  artifacts. If current state cannot be verified, report `UNVERIFIED`.
- Report `WORKING` when current independent evidence shows progress.
- Report `COMPLETE` only when the requested artifact or result is verified.

## Step 3 — Nudge if needed

Use the authorized Slack identity and connector described by
`~/.claude/skills/hermes/SKILL.md` and
`~/.claude/skills/slack-identity/SKILL.md`. Do not read or add a token in a
shell profile, put a token in OpenClaw configuration, or switch identities to
bypass a delivery or access failure. If the available connector would send as
OpenClaw itself or cannot address the existing thread, report that exact
delivery limitation without creating credentials or changing membership.

### Nudge message guidelines

- Reference the specific timestamp/quote of the last commitment openclaw made
- State the drop count if > 2 ("That's 4 drops on the same task")
- List the exact outstanding deliverables (e.g., "startup logs", "MiniMax config check", "test-call result")
- End with: "Do not acknowledge this message — just execute and post the transcript."
- Prefix: `[AI Terminal: <workspace>]`

## Step 4 — Report

After each check, report:
- Last relevant message timestamp and a one-line summary
- The independently verified artifact or result, or why it remains unverified
- Assessment: WORKING / COMPLETE / UNVERIFIED / FABRICATED
- Action taken: nudged (message id) / no action needed
- Drop count if tracking

## Evidence labels

Use `WORKING`, `COMPLETE`, `UNVERIFIED`, or `FABRICATED` only with the
independent evidence described above. Formatting, elapsed time, generic prose,
or raw terminal output alone does not establish fabrication or completion.

## Key constants

- default channel: `<slack-channel>`
- AI identity prefix: `[AI Terminal: <workspace-name>]` (required by CLAUDE.md)

## Sender and delivery

The connector's sender identity determines whether a message can reach the
target. Follow the current Slack identity owner; do not infer delivery from the
connector name or work around a sender/access failure with another identity.
