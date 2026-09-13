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

# 2. Install each policy: back up any divergent existing file, then copy.
#    Re-running on identical files is a no-op (no backup, no overwrite, mtime preserved).
ts="$(date -u +%Y%m%dT%H%M%SZ)"
backup_and_copy() {
  local src="$1" dst="$2" ts="$3"
  if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp -p "$dst" "$dst.bak.$ts"
    echo "backed up $dst -> $dst.bak.$ts"
  fi
  # Skip the copy when contents already match (preserves mtime).
  if [ ! -f "$dst" ] || ! cmp -s "$src" "$dst"; then
    install -m 0644 "$src" "$dst"
  fi
}
backup_and_copy "md_files/AGENTS.shared.md"  "$CODEX_HOME/AGENTS.md"  "$ts"
backup_and_copy "md_files/CLAUDE.adapter.md" "$CLAUDE_HOME/CLAUDE.md" "$ts"

# 3. If CODEX_HOME is non-default, point the adapter's @import at the real path.
if [ "$CODEX_HOME" != "$HOME/.codex" ]; then
  sed -i.bak "s|@~/.codex/AGENTS.md|@$CODEX_HOME/AGENTS.md|" "$CLAUDE_HOME/CLAUDE.md"
  echo "rewired Claude adapter import to @$CODEX_HOME/AGENTS.md"
fi

# 4. Verify both files are at their expected paths.
[ -f "$CODEX_HOME/AGENTS.md"  ] && echo "shared policy: OK ($CODEX_HOME/AGENTS.md)"
[ -f "$CLAUDE_HOME/CLAUDE.md" ] && echo "Claude adapter: OK ($CLAUDE_HOME/CLAUDE.md)"

# 5. Sanity check: no absolute user paths leaked into the installed files.
#    Fail loudly if any input is missing, unreadable, or non-regular
#    (directories, fifos, symlinks to nowhere, etc.) — no false-positive OK.
ok=1
for f in "$CODEX_HOME/AGENTS.md" "$CLAUDE_HOME/CLAUDE.md"; do
  if [ ! -f "$f" ] || [ ! -r "$f" ]; then
    echo "portable: ERROR — $f is missing, unreadable, or not a regular file" >&2
    ok=0
    continue
  fi
  # Capture grep's exit status BEFORE the if-test (otherwise rc is always 0 here).
  grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+' "$f" >/dev/null 2>&1
  rc=$?
  case "$rc" in
    0) echo "portable: ERROR — $f contains user-specific paths" >&2; ok=0 ;;
    1) : ;;                                                    # clean no-match
    *) echo "portable: ERROR — grep failed on $f (exit $rc)" >&2; ok=0 ;;
  esac
done
[ "$ok" = "1" ] && echo "portable: OK (no /Users/<name> or /home/<name> paths)"
```

Notes on the install path:

- `backup_and_copy` uses bash functions that take `"$src" "$dst"` as separate arguments, so paths with embedded spaces (e.g. `CODEX_HOME="$HOME/codex with space"`) are handled correctly. Do not replace the function with `set -- $pair` — that word-splits on whitespace and silently skips backups.
- `install -m 0644` is a no-op when the destination contents match the source, preserving the file's mtime. Re-running the bootstrap on an already-up-to-date machine is truly idempotent.
- `case "$rc" in 0|1|*)` correctly maps grep's three exit codes (0 = match, 1 = no match, ≥2 = error) to the right verdict. The earlier `if grep...; then rc=$?` shape always captured the if-test result (0 or 1), never grep's actual exit ≥2.

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
# Reject any missing/unreadable/non-regular input; map grep exit codes
# (0=match, 1=no-match, >=2=error) to the right verdict.
files=(md_files/AGENTS.shared.md md_files/CLAUDE.adapter.md)
ok=1
for f in "${files[@]}"; do
  if [ ! -f "$f" ] || [ ! -r "$f" ]; then
    echo "scan: ERROR — $f is missing, unreadable, or not a regular file" >&2
    ok=0
    continue
  fi
  grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+|@[A-Za-z0-9.-]+\.example\.(com|org|net)' \
       "$f" >/dev/null 2>&1
  rc=$?
  case "$rc" in
    0) echo "scan: HIT — $f contains user-specific paths:" >&2
       grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+|@[A-Za-z0-9.-]+\.example\.(com|org|net)' "$f" >&2
       ok=0 ;;
    1) : ;;  # clean
    *) echo "scan: ERROR — grep failed on $f (exit $rc)" >&2; ok=0 ;;
  esac
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
