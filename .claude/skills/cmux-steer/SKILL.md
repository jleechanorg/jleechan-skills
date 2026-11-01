---
name: cmux-steer
description: Resolve, inspect, and safely steer named cmux workspaces, tabs, and surfaces.
---

> **Terminal-reading rule (canonical):** before any classification, assessment, or steer of a
> cmux surface, read the surface's FULL available history (~10k words when possible;
> `cmux capture-pane --scrollback --lines 1500`), then the last ~15 lines for current state.
> Never decide from a short tail. Canonical text: `~/.codex/AGENTS.md` section
> "Reading a cmux terminal before deciding (full-buffer rule)".

> **No workspace selection (mandatory):** never run `cmux select-workspace`, `workspace.select`, `workspace-action --action focus`, or any command that selects/focuses/switches a workspace or surface — it steals the operator's active window. Read headless with `cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines <n>`; never `cmux read-screen` as this skill's targeted read (the installed build accepts `--workspace/--surface`, but cross-workspace read routing was historically unreliable — see "Headless only"). `cmux send`/`send-key --workspace <ws> --surface <sf>` is allowed and must not select.

## Headless only (operator rule 2026-10-18)

This section is the single owner of the rule; other cmux skills point here. **Measured** in `/tmp/spicy-search/cmux/focus-test.md` (selection tracked by the `[selected]` marker in `cmux workspace list`).

**Measured to NOT change the selected workspace** (selection safety only — it does not by
itself authorize creating or closing anything; see the consent rule below):
- **Reads:** `cmux capture-pane --workspace <ws> --surface <surface-uuid-or-ref> --scrollback --lines <n>`. The 2026-10-18 measurement also covered `cmux read-screen` and did not see it move the selection; the installed build (`cmux read-screen --help`, checked 2026-10-20) does accept `--workspace`/`--surface`. **This skill still reads only with `capture-pane`** — `read-screen` can return the *focused* surface rather than the one you named (the base rule, still the observed failure mode), and cross-workspace read routing was historically unreliable, so a targeted read comes from `capture-pane`, not `read-screen`.
- **Steers:** `cmux send "<text>"` + `cmux send-key enter`, and the raw socket `surface.send_text` call (type + Enter in one call; the trailing `\n` in `text` is Enter; works cross-workspace; resolve the socket from `$CMUX_SOCKET_PATH`, default below; surface UUIDs come from `cmux surface list`):

  ```bash
  SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
  printf '{"method":"surface.send_text","params":{"surface_id":"<SURFACE-UUID>","text":"<message>\\n"}}\n' | nc -U -w 3 "$SOCK"
  # -> {"ok":true,...,"queued":false|true}
  ```

- **Creates:** `cmux new-surface ... --focus false` / `cmux new-workspace ... --focus false` (**always pass `--focus false`**). Selection-safe, but still needs operator consent on the live desktop (below).
- **Closes:** `cmux close-surface` (run-2 measured: no selection change). Same consent rule applies.

**The only thing that disturbed the operator's view:** creating or closing **workspaces/surfaces** on the live desktop — the focus test's `cmux workspace close …` teardown switched the operator's selected workspace twice. **Do NOT create or close cmux workspaces/surfaces on the operator's live desktop unless the operator says yes first.**

**Never** use explicit selection/focus commands (`select-workspace`, `workspace.select`, `workspace-action --action focus`, `focus-window`, `focus-surface`, `surface.focus`) — they are never needed for a read/steer and only move the operator's view.

- **Proof of submission:** a later `capture-pane` showing the text accepted (the verdicts in § "`cmux send` newline rule": a `Press up to edit queued messages` line, a churning label, or text gone), never the socket `ok` alone. Where `capture-pane` genuinely does not exist (socket-only mode), the send is reported UNVERIFIED, not confirmed.

### `cmux send` newline rule (measured 2026-10-20 — the "you didn't submit input" incident)

This section is the single owner of the rule; `cmux-goal` and `cmux-bulk-steer` point here.

**What the installed CLI documents** (`cmux send --help`, checked 2026-10-20): `\n` and
`\r` are interpreted as Enter, `\t` as Tab, and typed keystrokes "press Enter at every
newline, which can submit each line on its own". `--paste` does **not** interpret escapes
and replaces control characters with spaces. `cmux send` also **refuses** (sends nothing)
when the target prompt already holds a draft, or a question/permission dialog is open,
unless `--force` is passed. Builds differ, so treat escape handling as build-dependent.

**What the operator measured** (the failure this rule exists for): a `/goal` sent with a
**real newline** in the argument was left parked in the composer with a blank line beneath
the cursor and never submitted — operator-caught at 10:04 AM (`lvl up` notice) and again
at 12:10 PM (`world` `/goal`) on 2026-10-20.

**Therefore the only safe send is a single-line text plus one explicit Enter:**

```bash
# PREFERRED — one line, then a real key event (chained or separate, both valid).
# Route BOTH commands explicitly: --workspace/--surface on send and on send-key.
cmux send --workspace workspace:<N> --surface surface:<sf> "your single-line message" \
  && cmux send-key --workspace workspace:<N> --surface surface:<sf> enter
# EQUIVALENT on builds whose send interprets escapes (checked: cmux send --help):
# the trailing \n IS the one Enter — do not also send send-key
cmux send --workspace workspace:<N> --surface surface:<sf> "your single-line message\n"
# WRONG — a real newline anywhere in the argument forms a second line that may
# park the text unsent or submit a fragment
cmux send --surface surface:<sf> "$MSG
"
```

Verification is mandatory — capture the bottom ~14 lines afterwards:
- `❯ <your text>` still visible → **NOT submitted**; send one `cmux send-key --workspace <ws> --surface <sf> enter`
  and re-check.
- A blank line with the cursor resting beneath the text → the newline-trap signature: send one
  bare Enter, never the text again.
- `Press up to edit queued messages` → **submitted and queued** (agent busy); success.
- text gone / new spinner → **submitted**.

**Repair, never re-type.** Send one bare Enter, then re-capture. Do not re-send the text: on
builds where the composer already holds a draft `cmux send` refuses the send outright, and on
builds where it does not the second send appends a duplicate line.

Never report "sent" from `cmux send`'s `OK` alone — `OK` proves keystrokes were
accepted, not that the agent received the message.

## ⚠️ Submit Discipline (MANDATORY — read this before every cmux steer)

A send without a submit never reaches the agent: the socket `text` must carry the
Enter (`\n`), and the CLI form must submit with exactly one Enter — either the
literal `\n` at the end of the argument, or a following `cmux send-key enter`, never
both (verified 2026-07-16: user flagged "you always forget to send" after the fable
iOS pivot bootstrap; the same failure was caught again on 2026-10-20 with a `/goal`
left in the composer). The submit ritual below is a hard contract for every send to a
cmux surface.

**Why it is counted as 3 steps.** The 2026-07-16 form is labelled **4-step**
(type → `send-key enter` → wait → verify). Since 2026-10-20 the same contract is
written as **3 steps** (send-with-Enter → wait → verify) because step 1's type and
Enter are issued together — chained with `&&`, or as a socket `surface.send_text`
whose `text` ends in the literal `\n`. Issuing them together removes one decision
point; it does not change the number of keystroke operations, and a standalone
`send-key enter` remains correct. The newline rule that makes step 1 fail is owned
by § "`cmux send` newline rule" above.

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

# 3. Read the target HEADLESSLY. NEVER focus/select/activate anything to read:
#    focusing changes the user's visible workspace (operator directive, repeated).
#    Use capture-pane only (read-screen is not this skill's targeted read), and
#    verify identity by CONTENT, preferring filesystem evidence:
#      cmux capture-pane --workspace "$WS" --surface <uuid> --scrollback --lines 1500
#    If the read cannot be trusted, read the transcript/STATE.md/checkpoint files
#    (~/.claude/projects/**.jsonl, roadmap STATE files, git worktrees) instead of
#    focusing. Banned for reading: `cmux focus-surface`, `cmux select-workspace`,
#    `cmux open`, `cmux new-surface`, or any UI click that changes focus.
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

### The submit ritual — 3 steps (supersedes the 2026-07-16 4-step ritual)

```bash
# STEP 1 — Type the message, then submit it with EXACTLY ONE Enter. `&&` chain is the
#          preferred CLI form; the socket form needs the LITERAL escape \n in `text`.
#          Never add a second Enter (no `\n` AND `send-key` in the same steer).
cmux send --workspace workspace:N --surface surface:M "your message" \
  && cmux send-key --workspace workspace:N --surface surface:M enter
# Socket equivalent (low-level / CLI unavailable):
#   printf '{"method":"surface.send_text","params":{"surface_id":"<SURFACE-UUID>","text":"your message\\n"}}\n' | nc -U -w 3 "${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
# `OK surface:M` / `ok:true` only prove socket acceptance, NOT submission.

# STEP 2 — Wait 5-15 seconds for the agent to start processing.
sleep 8

# STEP 3 — Verify by re-capture; a churning label is the strongest proof.
cmux capture-pane --workspace workspace:N --surface surface:M --lines 25
# Look for one of:
#   - "Working (Xs • esc to interrupt)"
#   - "Forming… (Xs · thinking)"
#   - "Precipitating… (Xs · ↓ tokens)"
#   - "Brewed / Churned / Cooked for Xm"
# If you see ANY active churning label → SUBMITTED.
# If the text is still sitting at the ❯ prompt → NOT submitted. Repair with ONE bare
#   Enter (`cmux send-key --workspace <ws> --surface <sf> enter`, or a socket send whose `text` is just
#   "\n"), then re-capture. Never re-send the message.
# If "Stopped" / "Done" / nothing → no churn: the steer may still have been accepted
#   (see the newline rule's verdict list) — check for a queued-message line before
#   concluding it failed.
```

### ⚠️ Output Contract — typed text + terminal response (MANDATORY)

Every reply that reports a `cmux send` action MUST include, in the same reply:

1. **The exact text that was typed** — verbatim copy of the string passed to `cmux send` (or the `text` sent via `surface.send_text`).
2. **The cmux terminal response** — verbatim transcript of what `cmux capture-pane` returned AFTER the submit settle window
   (typically 5-15s, counted from the Enter). Specifically, the agent's first action after
   absorption — for a **queued** submission the agent has not acted yet, so report the
   queued line itself as the observed response and do not claim an action.
3. **Submission status** — explicit verdict: "submitted (churning label X)",
   "not submitted (text still at ❯ prompt)", "queued (Press up to edit queued
   messages — accepted, agent busy)", or "blocked (no Enter accepted, retried N times)".

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
- A send with no Enter at all: neither a following `cmux send-key enter` nor a trailing literal `\n` (exactly one of the two, never both)
- A real newline character in the send argument (2026-10-20 — parks the text unsent)
- Re-sending text after a non-submit instead of one bare Enter
- Focusing or selecting a surface to send; always target with explicit `--workspace`/`--surface`

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
echo "${CMUX_SOCKET_PATH:-<unset>}"   # preferred: the app exports this per session
ls /tmp/cmux*.sock                    # older/debug builds keep sockets in /tmp
# Tagged debug build: /tmp/cmux-debug-<tag>.sock
# Untagged debug:     /tmp/cmux-debug.sock
# Release default used by this skill when the env var is unset:
SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
# Debug builds: SOCK="/tmp/cmux-debug-appclick.sock"  # update to match your build tag
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

The plain-text `send_surface` command FAILS cross-workspace. Always use the JSON API
(or the `cmux send` + `cmux send-key enter` CLI form, which is preferred):

| Method | Cross-workspace? | Notes |
|---|---|---|
| `surface.send_text` (JSON) | ✅ always works | Include the literal `\n` in text for enter |
| `cmux send` + `cmux send-key enter` | ✅ always works | Preferred CLI form; one `&&` chain |
| `cmux capture-pane` | ✅ always works | Headless read; the only targeted read method this skill uses |
| `send_surface` (plain text) | ❌ fails cross-workspace | Only works if workspace is selected |
| `read_screen` (plain text) | ❌ do not use | Not this skill's read path (the 2026-10-18 selection measurement covered `cmux read-screen`; the installed build also accepts `--workspace/--surface`, but cross-workspace read routing was historically unreliable); read with `cmux capture-pane --workspace … --surface …` |

## Sending text (headless, cross-workspace)

```bash
# Preferred: CLI, type + Enter in one chain (literal \n never involved)
cmux send --workspace "$WS_UUID" --surface "$CODER_UUID" "your instruction here" \
  && cmux send-key --workspace "$WS_UUID" --surface "$CODER_UUID" enter

# Low-level: single JSON call, type + enter (append the literal escape \n to submit)
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"your instruction here\\n"}}\n' | nc -U $SOCK
```

This works from any workspace without switching focus. The literal `\n` at the end acts
as Enter; a *real* newline splits the text and has left it parked unsent in both 2026-10-20
operator incidents (§ "`cmux send` newline rule"). Send one line and submit explicitly.

## Checking if idle

```bash
# Send a harmless probe — if queued=false and ok=true, surface accepted input
result=$(printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":""}}\n' | nc -U $SOCK)
# Check result.ok and result.queued
```

## Creating workspaces and surfaces

```bash
cmux new-workspace --focus false --name "my-workspace"   # prints the new workspace ref
cmux new-surface --focus false --workspace <ws> --type terminal   # add a second tab
# Low-level JSON equivalents (debugging only; assert the workspace is not the operator's):
#   printf '{"method":"workspace.create","params":{"title":"my-workspace"}}\n' | nc -U "$SOCK"
#   printf '{"method":"workspace.rename","params":{"workspace_id":"UUID","title":"new name"}}\n' | nc -U "$SOCK"
#   printf '{"method":"surface.create","params":{"workspace_id":"UUID"}}\n' | nc -U "$SOCK"
```

Never create or close workspaces/surfaces on the operator's live desktop without asking
first — that is the one operation that disturbed the operator's view (§ "Headless only").

## Special keys (when Enter in text isn't enough)

For key combos, prefer `cmux send-key` with the installed spelling (`ctrl+c`, `ctrl+d`,
`tab`, `escape`, `enter` — check `cmux send-key --help`). Sending a control character
through `surface.send_text` (JSON escapes `\u0003` ctrl-c, `\u0004` ctrl-d, `\t` tab,
`\u001b` escape, `\n` enter) stays headless and cross-workspace, but the 2026-10-18
measurement covered ordinary text only — **control-character sends through the socket are
unmeasured**, so use them as a fallback and verify the effect on the target:

```bash
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"\\u0003"}}\n' | nc -U -w 3 "$SOCK"
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"\\u0001"}}\n' | nc -U -w 3 "$SOCK"   # ctrl-a
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"\\u000b"}}\n' | nc -U -w 3 "$SOCK"   # ctrl-k
```

The plain-text `send_key_surface $CODER_UUID ctrl-c` form still works but only against
the focused workspace — do not focus it yourself; prefer
`cmux send-key --workspace <ws> --surface <sf>`. Available keys: `ctrl-c`, `ctrl-d`,
`enter`, `tab`, `escape`, `up`, `down`, `left`, `right`.

## Reading a pane's screen

Read any workspace headlessly with `capture-pane`:

```bash
cmux capture-pane --workspace "$WS_UUID" --surface "$CODER_UUID" --scrollback --lines 1500
```

Do not use `read_screen` as a targeted read: the installed build accepts
`--workspace`/`--surface`, but cross-workspace read routing was historically
unreliable, so `capture-pane` is this skill's only targeted read (§ "Headless only").

To infer state from the filesystem instead:
```bash
cd /path/to/project && git log --oneline -5
ls -lt src/   # recently modified files
```

## Full headless example

```bash
SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"

# 1. Find coder surface by workspace name
WS_UUID=$(printf "list_workspaces\n" | nc -U $SOCK \
  | grep "cmux: ubuntu" | grep -oE '[A-F0-9-]{36}')
CODER_UUID=$(printf "list_surfaces $WS_UUID\n" | nc -U $SOCK \
  | grep "cmux_coder" | grep -oE '[A-F0-9-]{36}')

# 2. Send task headlessly (no workspace switch needed)
printf '{"method":"surface.send_text","params":{"surface_id":"'"$CODER_UUID"'","text":"cargo build && cargo test\\n"}}\n' | nc -U $SOCK

# 3. Monitor progress via capture-pane
sleep 30
cmux capture-pane --workspace "$WS_UUID" --surface "$CODER_UUID" --lines 25
```

## Creating a fresh workspace with two tabs

```bash
cmux new-workspace --focus false --name "test: a/b"
cmux new-surface --focus false --workspace <ws> --type terminal
# Resolve both surface UUIDs with `cmux surface list`, then send to each via
# `cmux send` + `cmux send-key enter` (or surface.send_text).
```

Raw-JSON walkthrough (kept from the pre-CLI recipe; only for a non-operator/debug
instance, since creating workspaces on the live desktop needs the operator's OK):

```bash
SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"

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

1. **Never select or focus anything** — see "Headless only".
2. **Find workspace by NAME** (`list_workspaces` → grep name → get UUID).
3. **Use the CLI or JSON API for sends** — `cmux send` + `cmux send-key enter`, or `surface.send_text`; both work headlessly cross-workspace.
4. **Submit explicitly** — one single-line message plus a following `send-key enter` (or the literal `\n` escape on builds whose `send` interprets escapes); never rely on a real newline to submit.
5. **Read with `cmux capture-pane`** — headless, any workspace; never `read_screen` as a targeted read; use git/filesystem for monitoring that needs no screen read.
6. **Create with `--focus false`** — `cmux new-workspace` / `cmux new-surface` for multi-tab setups, and never create/close on the live desktop without asking.
