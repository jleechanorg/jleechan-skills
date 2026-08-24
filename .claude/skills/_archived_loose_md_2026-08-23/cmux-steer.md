# cmux-steer — Control another cmux terminal tab via the Unix socket

**Usage**: Read and follow this skill directly; no `/cmux-steer` slash command is defined.

**Purpose**: Read and steer another agent's terminal pane (e.g. a coding agent)
from within cmux, without disrupting the user's active workspace navigation.

## ⚠️ SUPERSEDED — Use `cmux` CLI, not raw socket protocol

The raw `nc -U $SOCK` examples below still work for low-level access, but they
have a **name → surface resolution gap** that has caused repeated failures
("why do you always get confused when I name a surface"). The canonical recipe
is the `cmux` CLI, which exposes workspace/surface/tab refs directly.

**Always start here when the user names a surface, tab, or workspace:**

```bash
# 1. MY workspace = caller.workspace_ref, falling back to focused.
#    `caller` is populated only when this command runs inside cmux itself;
#    from a standalone terminal (and from most skill invocations) it is null,
#    and a naive `["caller"]["workspace_ref"]` lookup will KeyError. The
#    defensive form below silently falls back to the focused workspace.
WS=$(cmux identify --json | python3 -c '
import sys, json
d = json.load(sys.stdin)
c = d.get("caller") or {}
print(c.get("workspace_ref") or d.get("focused", {}).get("workspace_ref"))
')

# 2. Every pane + tab by name; ◀ here = caller surface, ◀ active = focus.
#    Do NOT filter the output — sibling tabs and the ◀ markers are the signal.
cmux tree --all --workspace "$WS"

# 3. Read the target surface. ⚠ Cross-workspace `cmux read-screen
#    --workspace X --surface Y` is NOT reliable in current cmux (verified
#    bug — see ~/.hermes/skills/cmux/references/surface-read-routing-bug.md):
#    it can silently return the currently-focused surface's content even
#    when the `result` echoes the requested refs. The reliable recipe for
#    reading a non-focused surface is **focus-then-read**:
#      a. `cmux focus-surface --workspace "$WS" --surface surface:N` (or the
#         JSON-RPC `surface.focus` equivalent) to make surface:N the focused
#         surface, then
#      b. `cmux read-screen --lines 80` (no --workspace / --surface args —
#         the bare invocation reads the focused surface).
#    For an already-focused surface, the bare `cmux read-screen --lines N`
#    is sufficient and matches what you see on screen.
```

### Three anti-patterns this skill now warns against

- **Global name search** — `cmux list-pane-surfaces | grep <name>` matches a
  same-named tab in another workspace and you steer the wrong agent.
- **grep-filtering the tree** — `cmux tree --all | grep <name>` hides sibling
  tabs and the `◀ here` / `◀ active` markers you need to disambiguate.
- **`list-pane-surfaces` defaults** — defaults to ONE pane and omits tabs in
  other panes; use `cmux tree --all --workspace "$WS"` for the full picture.

### What this skill still does well

The raw `nc -U $SOCK` blocks below remain useful for low-level debugging
(`system.tree`, `system.identify`, custom JSON-RPC methods) and for
environments where the `cmux` CLI binary is not on PATH. The CLI recipes
above are the **default**; fall back to the raw socket blocks only when the
CLI fails or is unavailable.

### Known cmux CLI bugs (verified)

- **`cmux read-screen --workspace <ws> --surface <surface>`** can silently
  return the focused surface's content instead of the named one (see
  `~/.hermes/skills/cmux/references/surface-read-routing-bug.md`). Use the
  focus-then-read recipe above for any non-focused surface.
- **`surface.read_text` with `workspace_ref`/`surface_ref`** ignores the ref
  params and returns the focused surface's text. Same focus-then-read fix.

---

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

## Rule 2: send_surface by UUID works cross-workspace; read_screen does not

| Command | Cross-workspace by UUID? |
|---|---|
| `read_screen <uuid>` | ❌ always fails — index only, current workspace only |
| `send_surface <uuid> <text>` | ✅ works regardless of user's focused workspace |

## Checking if a terminal is idle

```bash
result=$(printf "send_surface $CODER_UUID test\n" | nc -U $SOCK)
# "OK"                          → idle at prompt
# "ERROR: Failed to send input" → running a command, wait and retry
```

If busy, retry loop:
```bash
while true; do
  result=$(printf "send_surface $CODER_UUID test\n" | nc -U $SOCK)
  [ "$result" = "OK" ] && break
  sleep 2
done
# Clear the probe text before sending real message
printf "send_key_surface $CODER_UUID ctrl-a\n" | nc -U $SOCK
printf "send_key_surface $CODER_UUID ctrl-k\n" | nc -U $SOCK
```

## Typing a message (human simulation)

`send_surface` types text into the input box but does **not** submit.
`send_key_surface enter` submits.

```bash
# Pattern: clear → type → enter
printf "send_key_surface $CODER_UUID ctrl-a\n" | nc -U $SOCK
printf "send_key_surface $CODER_UUID ctrl-k\n" | nc -U $SOCK
printf "send_surface $CODER_UUID your instruction here\n" | nc -U $SOCK
sleep 0.2
printf "send_key_surface $CODER_UUID enter\n" | nc -U $SOCK
```

Available special keys: `ctrl-c`, `ctrl-d`, `enter`, `tab`, `escape`, `up`, `down`, `left`, `right`

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

## Full monitoring example

```bash
SOCK="/tmp/cmux-debug-appclick.sock"

# 1. Find coder surface by label (workspace-name-safe, index-safe)
WS_UUID=$(printf "list_workspaces\n" | nc -U $SOCK \
  | grep "cmux: ubuntu" | grep -oE '[A-F0-9-]{36}')
CODER_UUID=$(printf "list_surfaces $WS_UUID\n" | nc -U $SOCK \
  | grep "cmux_coder" | grep -oE '[A-F0-9-]{36}')

# 2. Check if idle
result=$(printf "send_surface $CODER_UUID test\n" | nc -U $SOCK)
if [ "$result" = "OK" ]; then
  # Clear probe, send next task
  printf "send_key_surface $CODER_UUID ctrl-a\n" | nc -U $SOCK
  printf "send_key_surface $CODER_UUID ctrl-k\n" | nc -U $SOCK
  printf "send_surface $CODER_UUID next task: run cargo build and fix errors\n" | nc -U $SOCK
  sleep 0.2
  printf "send_key_surface $CODER_UUID enter\n" | nc -U $SOCK
else
  # Still running — check git for progress
  cd /path/to/project && git log --oneline -3
fi
```

## Rules summary

1. **Never use `select_workspace`** — it switches the user's visible workspace.
2. **Find workspace by NAME** (`list_workspaces` → grep name → get UUID).
3. **Send by UUID** — cross-workspace safe; never assume surface index.
4. **Read by index only** — `read_screen` requires being in the right workspace.
5. **Clear before typing** — `ctrl-a` + `ctrl-k` before `send_surface`.
6. **Two commands to submit** — `send_surface` types, `send_key_surface enter` submits.
7. **Probe before sending** — "test" → OK means idle; clear probe then send real message.
