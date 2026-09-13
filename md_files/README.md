# Shared `CLAUDE.md` / `AGENTS.md` setup

Portable templates for the shared Codex/Claude policy layout. These files are **machine-portable** — they contain no user-specific paths, so a fresh machine can install them and have the same two-runtime setup the author uses.

If you fork or refresh these files, run the path-scan in the "Refreshing" section before committing.

## Files in this directory

| File | Install destination | What it is |
|------|---------------------|------------|
| `AGENTS.shared.md` | `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` | The **canonical shared global policy** loaded by every Codex/Claude session. Edit shared rules here once. |
| `CLAUDE.adapter.md` | `~/.claude/CLAUDE.md` | The thin Claude adapter that imports the shared policy via `@~/.codex/AGENTS.md`. |

## How the "shared file setup" wires together

Two runtimes, one source of truth:

```text
~/.codex/AGENTS.md      ← canonical shared policy (Codex reads natively)
        │
        │ imported via
        ▼
~/.claude/CLAUDE.md     ← Claude Code adapter: "@~/.codex/AGENTS.md"
                         + Claude-specific additions only
```

`@~/.codex/AGENTS.md` is a literal text import — it does not expand environment variables, so the file must be installed at the default `~/.codex/AGENTS.md`. If your `CODEX_HOME` is non-default, edit the `@` line in `~/.claude/CLAUDE.md` after installation so it points at the actual Codex home (the bootstrap shows you how below).

### Why the indirection exists

- **Single source of truth.** Universal rules live in `~/.codex/AGENTS.md`. Both
  Codex (native load) and Claude Code (via `@` import) read it. No drift.
- **Adapter pattern.** Runtime-specific behavior lives in the adapter
  (`~/.claude/CLAUDE.md` adds Claude-only subagent rules, model routing,
  voice/calibration). Edit the adapter; the shared rules stay untouched.

## Reproducing this layout on a fresh machine

```bash
# 0. From the root of this repo, after `git clone` of jleechan-skills.

# 1. Resolve the Codex home. Defaults to ~/.codex if CODEX_HOME is unset.
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$CODEX_HOME" "$CLAUDE_HOME"

# 2. Back up any existing policy files so a re-run can never silently overwrite them.
ts="$(date -u +%Y%m%dT%H%M%SZ)"
for pair in \
    "md_files/AGENTS.shared.md $CODEX_HOME/AGENTS.md" \
    "md_files/CLAUDE.adapter.md $CLAUDE_HOME/CLAUDE.md" ; do
  set -- $pair
  if [ -f "$2" ] && ! cmp -s "$1" "$2"; then
    cp -p "$2" "$2.bak.$ts"
    echo "backed up $2 -> $2.bak.$ts"
  fi
done

# 3. Install the shared policy and the Claude adapter.
cp md_files/AGENTS.shared.md  "$CODEX_HOME/AGENTS.md"
cp md_files/CLAUDE.adapter.md "$CLAUDE_HOME/CLAUDE.md"

# 4. If CODEX_HOME is non-default, point the adapter's @import at the real path.
if [ "$CODEX_HOME" != "$HOME/.codex" ]; then
  sed -i.bak "s|@~/.codex/AGENTS.md|@$CODEX_HOME/AGENTS.md|" "$CLAUDE_HOME/CLAUDE.md"
  echo "rewired Claude adapter import to @$CODEX_HOME/AGENTS.md"
fi

# 5. Verify both files are at their expected paths.
[ -f "$CODEX_HOME/AGENTS.md"  ] && echo "shared policy: OK ($CODEX_HOME/AGENTS.md)"
[ -f "$CLAUDE_HOME/CLAUDE.md" ] && echo "Claude adapter: OK ($CLAUDE_HOME/CLAUDE.md)"

# 6. Sanity check: no absolute user paths leaked into the installed files.
#    Fail loudly if any input is missing or unreadable (no false-positive OK).
ok=1
for f in "$CODEX_HOME/AGENTS.md" "$CLAUDE_HOME/CLAUDE.md"; do
  if [ ! -r "$f" ]; then
    echo "portable: ERROR — $f is missing or unreadable" >&2
    ok=0
    continue
  fi
  if grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+' "$f" >/dev/null 2>&1; then
    rc=$?
    # grep exit 1 (no match) is the only clean result; 2+ means scan error.
    if [ "$rc" -ge 2 ]; then
      echo "portable: ERROR — grep failed on $f (exit $rc)" >&2
      ok=0
    else
      echo "portable: ERROR — $f contains user-specific paths" >&2
      ok=0
    fi
  fi
done
[ "$ok" = "1" ] && echo "portable: OK (no /Users/<name> or /home/<name> paths)"
```

The `cmp -s` before each `cp` means the bootstrap is idempotent: re-running it on a machine whose policy already matches the template is a no-op (no backup, no overwrite). Re-running it on a machine with local edits produces a `.bak.<UTC-timestamp>` file next to the old policy.

## Editing guidance (per `AGENTS.shared.md`)

> Edit shared policy or runtime adapters — semantic signoff + behavioral gate (mandatory)
> Structural checks are necessary but not sufficient. For edits that shorten, move,
> or restructure a rule, ask whether an agent reading only the new text would still
> take the enforcement action; if unsure, do not ship. Keep high-salience autonomy
> and safety headings standalone. Before and after edits, run canaries: with an
> obviously implied next step and no blocker, does the agent proceed without
> asking, and does it cite the source before asserting a status claim?

Treat that gate as live for any edit to any file in this directory.

## Refreshing

If you copy a fresh policy file from your `~` into this directory, run the path-scan before committing — it fails the change if any user-specific path leaked in:

```bash
# Reject any input that is missing or unreadable (no silent OK).
files=(md_files/AGENTS.shared.md md_files/CLAUDE.adapter.md)
ok=1
for f in "${files[@]}"; do
  if [ ! -r "$f" ]; then
    echo "scan: ERROR — $f is missing or unreadable" >&2
    ok=0
    continue
  fi
  if grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+|@[A-Za-z0-9.-]+\.example\.(com|org|net)' \
       "$f" >/dev/null 2>&1; then
    rc=$?
    if [ "$rc" -ge 2 ]; then
      echo "scan: ERROR — grep failed on $f (exit $rc)" >&2
      ok=0
    else
      echo "scan: HIT — $f contains user-specific paths:" >&2
      grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+|@[A-Za-z0-9.-]+\.example\.(com|org|net)' "$f" >&2
      ok=0
    fi
  fi
done
[ "$ok" = "1" ] && echo "portable: clean"
```

Sanitize any hit before commit. Common substitutions:

- `/Users/<name>/.nvm/...` → `~/.nvm/...` (or `$NVM_DIR/...`)
- `/Users/<name>/.claude/...` → `~/.claude/...`
- `/Users/<name>/.local/bin/...` → `~/.local/bin/...`
- `/Users/<name>/.config/...` → `$HOME/.config/...` or `~/.config/...`

## Maintenance

- **These are portable templates, not verbatim snapshots.** `AGENTS.shared.md`
  and `CLAUDE.adapter.md` are sanitized for cross-user use.
- **To refresh from your home directory:** copy the file, run the path-scan,
  fix any hits, then commit. Do not `cp` a home file directly into this
  directory without the scan — it will reintroduce user-specific paths.
- **Absolute user paths (e.g. `/Users/<name>/...` or `/home/<name>/...`) in PR diffs is a regression.** Treat the path-scan
  as a pre-commit gate.
