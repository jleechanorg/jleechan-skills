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
