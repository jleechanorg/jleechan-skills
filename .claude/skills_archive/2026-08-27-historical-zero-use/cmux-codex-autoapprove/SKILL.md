---
name: cmux-codex-autoapprove
description: Run or maintain the cmux approval worker that scans cmux terminal surfaces for approval dialogs, classifies them with `codex exec`, and sends the matching approval key. Use when testing or operating the launchd-based auto-approver, debugging missed prompts, moving the worker, or tuning candidate detection and approval heuristics.
user-invocable: true
---

## ⚠️ Submit Discipline (MANDATORY — read this before every cmux steer)

`cmux send` does **NOT** press Enter. This is the #1 recurring cmux failure mode
(verified 2026-07-16: user explicitly flagged "you always forget to send" after the
fable iOS pivot bootstrap). The **4-step ritual** below is a hard contract for every
send to a cmux surface. Skip ANY step and the message sits in the input buffer
without ever reaching the agent.

### The 4-step ritual

```bash
# STEP 1 — Type the text. OK response only proves socket acceptance, NOT submission.
cmux send --workspace workspace:N --surface surface:M "your message"

# STEP 2 — Press Enter. send does NOT auto-press Enter.
cmux send-key --workspace workspace:N --surface surface:M enter

# STEP 3 — Wait 5-15 seconds for the agent to start processing.
sleep 8

# STEP 4 — Verify with churning label (THE ONLY definitive proof).
cmux capture-pane --workspace workspace:N --surface surface:M --lines 25
# Look for one of:
#   - "Working (Xs • esc to interrupt)"
#   - "Forming… (Xs · thinking)"
#   - "Precipitating… (Xs · ↓ tokens)"
#   - "Brewed / Churned / Cooked for Xm"
# If you see ANY active churning label → SUBMITTED.
# If the text is still sitting at the ❯ prompt → NOT submitted, repeat step 2.
# If "Stopped" / "Done" / nothing → no churn, investigate.
```

### Echo-back proof (MANDATORY)

Every cmux steering action MUST be followed by an **echo-back proof** in the same
turn or the immediate next turn to your operator (Slack thread, terminal reply,
or whichever channel triggered the steer):

> ◀ sent to surface:55 (LEFT/claudec) at <HH:MM:SS PT> — 4-step ritual complete;
> churning label "Forming… 9s · ↓ 4.9k tokens" confirmed via capture-pane.

**Banned** (these are the failure modes the user keeps flagging):
- "I sent the message" (no Enter proof)
- "The agent should have received it" (no churning label)
- `cmux send` with no follow-up `cmux send-key enter`
- Sending to a surface that hasn't been focused (the global focus may be on a
  different workspace; use the raw RPC `surface.focus` if needed)

### Worktree-pointer strategy for long briefs

For task briefs >200 chars (e.g. orchestrating iOS app pivot, multi-PR review),
do NOT paste the full text into the input. Write the brief to a file in the
agent's cwd (e.g. `.cmux-<task>-brief.md`) and send a 1-2 line pointer. This
avoids the autocompleter contamination pitfall where shell-style tokens inside
long text trigger tab completion mid-stream.

### Canonical reference

Full recipe + edge cases + the 2026-06-25 worked example live at:
`~/.hermes/skills/cmux/references/send-submit-proof-2026-06-25.md`

This rule was added 2026-07-16 after the fable iOS pivot bootstrap surfaced
"you always forget to send" / "make sure you press submit and the work starts
on the cmux input" (Slack ts 1784185650.528089). Apply it uniformly to every
cmux-touching skill.

# cmux Codex Autoapprove

Canonical files:
- Skill root: `$HOME/.claude/skills/cmux-codex-autoapprove`
- Worker script: `$HOME/.claude/skills/cmux-codex-autoapprove/scripts/cmux_codex_approve_launchd.py`
- LaunchAgent: `$HOME/Library/LaunchAgents/com.$USER.cmux-codex-approve.plist`
- Plist backup: `~/.claude/skills/cmux-codex-autoapprove/com.$USER.cmux-codex-approve.plist`

## Install / Restore

On a new machine, copy the plist and load it:

```bash
cp ~/.claude/skills/cmux-codex-autoapprove/com.$USER.cmux-codex-approve.plist \
   ~/Library/LaunchAgents/com.$USER.cmux-codex-approve.plist
launchctl load ~/Library/LaunchAgents/com.$USER.cmux-codex-approve.plist
```

**PATH requirement:** The plist must include `$HOME/bin` in PATH (where `cmux` lives). Current plist already has this.
- Logs: `$HOME/.claude/supervisor/cmux-codex-launchd.log`
- State: `$HOME/.claude/supervisor/cmux-codex-launchd-state.json`

Compatibility paths:
- Wrapper path used by older flows: `$HOME/.claude/bin/cmux_codex_approve_launchd.py`
- Codex skill symlink: `$HOME/.codex/skills/cmux-codex-autoapprove`

## Purpose

Use this skill for a custom cmux auto-approver that:
- enumerates terminal surfaces with `cmux --json tree --all`
- reads visible terminal content with `cmux read-screen`
- filters for approval-like prompts near the bottom of the live screen
- asks `codex exec` for a one-token decision: `ENTER`, `1`, `y`, `SKIP`, or `DENY`
- sends the chosen key back with `cmux send` or `cmux send-key`

This is the non-`snap-agent-supervisor` path.

## Normal Workflow

1. Verify the target surface with:

```bash
cmux --json tree --all
cmux read-screen --workspace <workspace> --surface <surface> --lines 24
```

2. If you need a one-shot run, execute:

```bash
/opt/homebrew/bin/python3 $HOME/.claude/skills/cmux-codex-autoapprove/scripts/cmux_codex_approve_launchd.py
```

3. For the scheduled agent, use:

```bash
launchctl kickstart -k gui/501/com.$USER.cmux-codex-approve
launchctl print gui/501/com.$USER.cmux-codex-approve
```

## Behavior Notes

- The worker intentionally focuses on the bottom active region of the screen so stale scrollback does not retrigger approvals forever.
- Approved prompt digests are cleared once the surface returns to a normal shell or idle prompt.
- Idle runs are cheap. `codex exec` is only called when the screen looks like a real approval dialog.

## When To Edit

Edit the worker script when:
- a real approval dialog is missed
- a non-approval surface is being auto-approved
- `launchd` can detect candidates but hangs or times out during classification
- prompt wording changes and the regexes need to expand

Check these first when debugging:
- `$HOME/.claude/supervisor/cmux-codex-launchd.log`
- `$HOME/.claude/supervisor/cmux-codex-launchd.stderr.log`
- `$HOME/.claude/supervisor/cmux-codex-launchd-state.json`

