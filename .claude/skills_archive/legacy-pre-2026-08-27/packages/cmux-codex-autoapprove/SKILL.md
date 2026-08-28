---
name: cmux-codex-autoapprove
description: Run or maintain the cmux approval worker that scans cmux terminal surfaces for approval dialogs, classifies them with `codex exec`, and sends the matching approval key. Use when testing or operating the launchd-based auto-approver, debugging missed prompts, moving the worker, or tuning candidate detection and approval heuristics.
user-invocable: true
---

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

**Pattern wiring rule (mandatory):** Detection regexes in this worker are checked at
**two call sites** — `is_approval_candidate()` (the gate) and `heuristic_decision()`
(the action). A pattern added to `heuristic_decision()` but not `is_approval_candidate()`
will silently fail because the gate drops it first. When adding a detection regex or
phrase, you MUST add test strings to **both** functions. The test file at
`scripts/test_approval_patterns.py` enforces this by running every dialog through both
functions — it will fail if a pattern is only wired into one.

Check these first when debugging:
- `$HOME/.claude/supervisor/cmux-codex-launchd.log`
- `$HOME/.claude/supervisor/cmux-codex-launchd.stderr.log`
- `$HOME/.claude/supervisor/cmux-codex-launchd-state.json`

