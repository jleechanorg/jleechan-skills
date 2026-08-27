---
name: cmux-backup
description: Backup all cmux workspaces, surfaces, and their current working directories via the socket API. Produces a timestamped JSON snapshot at ~/.cmux-backups/.
metadata:
  type: skill
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

### ⚠️ Output Contract — typed text + terminal response (MANDATORY)

Every reply that reports a `cmux send` action MUST include, in the same reply:

1. **The exact text that was typed** — verbatim copy of the string passed to `cmux send`.
2. **The cmux terminal response** — verbatim transcript of what `cmux capture-pane` /
   `cmux read-screen` returned AFTER the `cmux send-key enter` settle window
   (typically 5-15s). Specifically, the agent's first action after absorption.
3. **Submission status** — explicit verdict: "submitted (churning label X)",
   "not submitted (text still at ❯ prompt)", or "blocked (no churn, retried N times)".

**Treat as not working until we see a response.** A reply that does NOT include
both the typed text AND a terminal response is invalid evidence that the
steer landed. The operator cannot distinguish a successful send from a failed
send that left text in the input buffer.

Canonical contract + echo-back template: `~/.hermes/skills/cmux/references/output-contract-mandatory.md`.

### ⚠️ LLM-Provenance Caveat (MANDATORY footer)

Every reply that quotes cmux output, terminal text, or agent actions produced
by another LLM (the worker agent OR the assistant's own synthesis of agent
output) MUST end with this verbatim footer:

> *This was generated from another LLM and not the actual user, so feel free
> to push back if you disagree and we can discuss.*

Full caveat rules + scope: `~/.hermes/skills/cmux/references/output-contract-mandatory.md` § "LLM-Provenance Caveat".

### Echo-back proof (MANDATORY)

Every cmux steering action MUST be followed by an **echo-back proof** in the same
turn or the immediate next turn to your operator (Slack thread, terminal reply,
or whichever channel triggered the steer). The proof MUST follow the template
in `~/.hermes/skills/cmux/references/output-contract-mandatory.md` and include
the typed text + terminal response + submission status, not just the
churning label.

> ◀ sent to surface:55 (LEFT/claudec) at <HH:MM:SS PT> — typed: "<first 80 chars>";
> response: "<first 80 chars of the churning label or first agent line>"; status:
> submitted (churning label "Forming… 9s · ↓ 4.9k tokens").

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

# cmux-backup

Snapshot all cmux workspaces + surfaces + per-workspace CWD/git state to
`~/.cmux-backups/<timestamp>.json` via the cmux Unix socket API.

## Invoke

```
/cmux-backup
```

Or manually:

```bash
~/.claude/scripts/cmux-backup.sh
```

## What it captures

| Field | Source |
|---|---|
| workspace id, title, index, selected | `workspace.list` JSON API |
| workspace current_directory | `workspace.list` `.current_directory` |
| workspace cwd (shell-reported) | `sidebar_state --tab=<ws_uuid>` → `cwd=` |
| workspace focused_cwd | `sidebar_state` → `focused_cwd=` |
| workspace git_branch | `sidebar_state` → `git_branch=` |
| workspace PR info | `sidebar_state` → `pr=`, `pr_label=` |
| surface id, title, type, pane_id | `surface.list` JSON API |

## Output format

```json
{
  "timestamp": "2026-05-18T12:34:56",
  "socket": "/Users/.../cmux.sock",
  "workspace_count": 26,
  "workspaces": [
    {
      "id": "8DAE7F5B-...",
      "title": "worktree_level_choices",
      "index": 0,
      "selected": false,
      "current_directory": "$HOME",
      "cwd": "$HOME/projects/worktree_level_choices",
      "focused_cwd": "$HOME/projects/worktree_level_choices",
      "git_branch": "feat/level-choices",
      "pr": "123",
      "surfaces": [
        {
          "id": "07A1ECD6-...",
          "title": "worktree_level_choices",
          "type": "terminal",
          "pane_id": "6FECF31A-..."
        }
      ]
    }
  ]
}
```

## Protocol used

```bash
SOCK="$CMUX_SOCKET"  # or ~/Library/Application Support/cmux/cmux.sock

# All workspaces
printf '{"method":"workspace.list","params":{}}\n' | nc -U "$SOCK"

# Surfaces per workspace
printf '{"method":"surface.list","params":{"workspace_id":"<uuid>"}}\n' | nc -U "$SOCK"

# CWD + git state per workspace
printf "sidebar_state --tab=<workspace_uuid>\n" | nc -U "$SOCK"
```

## Dev build sockets

```bash
# Find socket for a specific dev build:
cat ~/Library/Application\ Support/cmux/dev-may-18-last-socket-path
lsof -p $(pgrep -f "cmux DEV may-18") | grep -E "\.sock"

# Use CLI with dev build socket:
CMUX_SOCKET_PATH=/tmp/cmux-debug-may-18.sock cmux list-workspaces
CMUX_SOCKET_PATH=/tmp/cmux-debug-may-18.sock cmux tree
```

## Companion restore skill

`~/.claude/scripts/cmux-restore.sh [--backup <file>] [--dry-run] [--list]`

- Skips workspaces already present by title
- Creates missing ones with `workspace.create` + `surface.send_text` cd
- Headless — never calls `select_workspace`

## Rules

1. Never call `select_workspace` — read-only snapshot only.
2. Use `$CMUX_SOCKET` env var first; fall back to
   `~/Library/Application Support/cmux/cmux.sock`.
3. Write backup to `~/.cmux-backups/cmux-backup-<timestamp>.json`.
4. Print a summary table to stdout (workspace index, title, cwd, git branch).
