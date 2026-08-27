## ⚠️ Submit Discipline (MANDATORY — read this before every cmux steer)

`cmux send` does **NOT** press Enter. This is the #1 recurring cmux failure mode
(verified 2026-07-16: user explicitly flagged "you always forget to send" after the
fable iOS pivot bootstrap). The **4-step ritual** below is a hard contract for every
send to a cmux surface. Skip ANY step and the message sits in the input buffer
without ever reaching the agent.

## ⚠️ SUPERSEDED — Use `cmux` CLI, not raw socket protocol (for name → surface resolution)

The raw `nc -U $SOCK` examples further down still work for low-level access,
but they have a **name → surface resolution gap** that has caused repeated
failures ("why do you always get confused when I name a surface"). The
canonical recipe is the `cmux` CLI, which exposes workspace/surface/tab refs
directly.

**Always start here when the user names a surface, tab, or workspace:**

```bash
# 1. MY workspace = caller.workspace_ref, falling back to focused.
#    `caller` is populated only when this command runs inside cmux itself;
#    from a standalone terminal (and from most skill invocations) it is null,
#    so the defensive form below falls back to the focused workspace.
WS=$(cmux identify --json | python3 -c '
import sys, json
d = json.load(sys.stdin)
c = d.get("caller") or {}
print(c.get("workspace_ref") or d.get("focused", {}).get("workspace_ref"))
')

# 2. Every pane + tab by name; ◀ here = caller surface, ◀ active = focus.
#    Do NOT filter the output — sibling tabs and the ◀ markers are the signal.
cmux tree --all --workspace "$WS"

# 3. Read the target. ⚠ Cross-workspace `cmux read-screen --workspace X
#    --surface Y` is NOT reliable in current cmux (see
#    ~/.hermes/skills/cmux/references/surface-read-routing-bug.md): it can
#    silently return the focused surface's content. For non-focused surfaces,
#    use focus-then-read: `cmux focus-surface --workspace "$WS" --surface
#    surface:N` then `cmux read-screen --lines 80` (no --workspace/--surface).
```

### Three anti-patterns this skill now warns against

- **Global name search** — `cmux list-pane-surfaces | grep <name>` matches a
  same-named tab in another workspace and you steer the wrong agent.
- **grep-filtering the tree** — `cmux tree --all | grep <name>` hides sibling
  tabs and the `◀ here` / `◀ active` markers you need to disambiguate.
- **`list-pane-surfaces` defaults** — defaults to ONE pane and omits tabs in
  other panes; use `cmux tree --all --workspace "$WS"` for the full picture.

The raw `nc -U $SOCK` blocks below remain useful for low-level debugging
(`system.tree`, `system.identify`, custom JSON-RPC methods).

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

# cmux-steer — Control another cmux terminal tab via the Unix socket

**Usage**: Read and follow this skill directly; no `/cmux-steer` slash command is defined.

**Purpose**: Read and steer another agent's terminal pane (e.g. a coding agent)
from within cmux, without disrupting the user's active workspace navigation.

---

## Socket path

```bash
ls /tmp/cmux*.sock
# Tagged debug build: /tmp/cmux-debug-<tag>.sock
# Untagged debug:     /tmp/cmux-debug.sock
# Release:            /tmp/cmux.sock
SOCK="/tmp/cmux-debug-appclick.sock"  # update to match your build tag
```

## Rule 1: Always find workspace by NAME, not index

The user can switch workspaces at any time, shifting surface indices. **Never
hardcode an index.** Always look up by the workspace's display name:

```bash
# List all workspaces with names
printf "list_workspaces\n" | nc -U $SOCK
# Example output:
#   0: D267DC10-... cmux: ubuntu
# * 1: 9075D919-... exp: statusline   ← user is here; doesn't matter
#   2: 258EB4B4-... o: mctrl

# Find target workspace UUID by name
WS_UUID=$(printf "list_workspaces\n" | nc -U $SOCK \
  | grep "cmux: ubuntu" | grep -oE '[A-F0-9-]{36}')

# List surfaces in that workspace
printf "list_surfaces $WS_UUID\n" | nc -U $SOCK
# Output:
#   * 0: 87DB76A9-...   supervisor (cmux)
#     1: F05FCE84-...   cmux_coder

# Extract coder surface UUID by label (never by index — indices shift)
CODER_UUID=$(printf "list_surfaces $WS_UUID\n" | nc -U $SOCK \
  | grep "cmux_coder" | grep -oE '[A-F0-9-]{36}')
```

## Rule 2: Use JSON API for headless cross-workspace sends

The plain-text `send_surface` command FAILS cross-workspace. Always use the JSON API:

| Method | Cross-workspace? | Notes |
|---|---|---|
| `surface.send_text` (JSON) | ✅ always works | Include `\n` in text for enter |
| `send_surface` (plain text) | ❌ fails cross-workspace | Only works if workspace is selected |
| `read_screen` | ❌ current workspace only | Use index, not UUID |

## Sending text (headless, cross-workspace)

```bash
# Single command: type + enter (append \n to submit)
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"your instruction here\\n"}}\n' | nc -U $SOCK
```

This works from any workspace without switching focus. The `\n` at end acts as Enter.

## Checking if idle

```bash
# Send a harmless probe — if queued=false and ok=true, surface accepted input
result=$(printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":""}}\n' | nc -U $SOCK)
# Check result.ok and result.queued
```

## Creating workspaces and surfaces

```bash
# Create workspace
printf '{"method":"workspace.create","params":{"title":"my-workspace"}}\n' | nc -U $SOCK
# Returns workspace_id

# Rename workspace
printf '{"method":"workspace.rename","params":{"workspace_id":"UUID","title":"new name"}}\n' | nc -U $SOCK

# Add a second tab/surface
printf '{"method":"surface.create","params":{"workspace_id":"UUID"}}\n' | nc -U $SOCK
# Returns surface_id
```

## Special keys (when \n in text isn't enough)

For key combos, fall back to plain text protocol (requires workspace focus):
```bash
printf "send_key_surface $CODER_UUID ctrl-c\n" | nc -U $SOCK
printf "send_key_surface $CODER_UUID ctrl-a\n" | nc -U $SOCK
printf "send_key_surface $CODER_UUID ctrl-k\n" | nc -U $SOCK
```

Available: `ctrl-c`, `ctrl-d`, `enter`, `tab`, `escape`, `up`, `down`, `left`, `right`

## Reading a pane's screen (current workspace only)

`read_screen` requires a surface **index** (not UUID) and only works when the target is in the user's currently focused workspace. Obtain the index from `list_surfaces` output (e.g. `1: F05FCE84-... cmux_coder` → index is `1`).

```bash
# IDX = index from list_surfaces for the focused workspace (replace with actual value)
IDX=1
printf "read_screen $IDX --lines 40\n" | nc -U $SOCK
printf "read_screen $IDX --lines 80 --scrollback\n" | nc -U $SOCK
```

If the user is in a different workspace, infer state from the filesystem instead:
```bash
cd /path/to/project && git log --oneline -5
ls -lt src/   # recently modified files
```

## Full headless example

```bash
SOCK="/tmp/cmux-debug-appclick.sock"

# 1. Find coder surface by workspace name
WS_UUID=$(printf "list_workspaces\n" | nc -U $SOCK \
  | grep "cmux: ubuntu" | grep -oE '[A-F0-9-]{36}')
CODER_UUID=$(printf "list_surfaces $WS_UUID\n" | nc -U $SOCK \
  | grep "cmux_coder" | grep -oE '[A-F0-9-]{36}')

# 2. Send task headlessly (no workspace switch needed)
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"cargo build && cargo test\\n"}}\n' | nc -U $SOCK

# 3. Monitor progress via filesystem (no read_screen needed)
sleep 30
cd /path/to/project && git log --oneline -3
```

## Creating a fresh workspace with two tabs

```bash
SOCK="/tmp/cmux-debug-appclick.sock"

# Create workspace
WS=$(printf '{"method":"workspace.create","params":{"title":"my-test"}}\n' | nc -U $SOCK \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['result']['workspace_id'])")

# Rename it
printf '{"method":"workspace.rename","params":{"workspace_id":"'"$WS"'","title":"test: a/b"}}\n' | nc -U $SOCK

# Add second tab
TAB2=$(printf '{"method":"surface.create","params":{"workspace_id":"'"$WS"'"}}\n' | nc -U $SOCK \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['result']['surface_id'])")

# Get first tab
TAB1=$(printf "list_surfaces $WS\n" | nc -U $SOCK | grep "0:" | grep -oE '[A-F0-9-]{36}')

# Send commands to both tabs headlessly
printf '{"method":"surface.send_text","params":{"surface_id":"'"$TAB1"'","text":"echo tab1\\n"}}\n' | nc -U $SOCK
printf '{"method":"surface.send_text","params":{"surface_id":"'"$TAB2"'","text":"echo tab2\\n"}}\n' | nc -U $SOCK
```

## Rules summary

1. **Never use `select_workspace`** — it switches the user's visible workspace.
2. **Find workspace by NAME** (`list_workspaces` → grep name → get UUID).
3. **Use JSON API for sends** — `surface.send_text` works headlessly cross-workspace.
4. **Append `\n` to text** — acts as Enter key submission.
5. **Read by index only** — `read_screen` requires being in the right workspace; use git/filesystem for cross-workspace monitoring.
6. **Create workspaces via JSON** — `workspace.create` + `surface.create` for multi-tab setups.
