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
#    Both files are identical regardless of CODEX_HOME on a default install;
#    the Claude adapter only differs when CODEX_HOME is non-default (its
#    @import is rewritten). Stage the post-rewrite adapter as a temp file so
#    the backup check compares against the post-rewrite form (not the raw
#    source) and a re-run is a true no-op.
ts="$(date -u +%Y%m%dT%H%M%SZ)"

# Stage both intended payloads as temp files. Bash $() command substitution
# strips trailing newlines, so we cannot use shell variables for the
# content -- use files instead.
# Fail fast if either source template is missing or unreadable: the temp
# file below would otherwise be created empty and silently overwrite the
# destination via backup_and_write, deleting a valid policy.
for src in "md_files/AGENTS.shared.md" "md_files/CLAUDE.adapter.md"; do
  if [ ! -f "$src" ] || [ ! -r "$src" ]; then
    echo "bootstrap: ERROR -- $src is missing or unreadable; aborting before any install" >&2
    exit 1
  fi
done
intended_ag_tmp="$(mktemp -t md_bootstrap_ag.XXXXXX)"
intended_ad_tmp="$(mktemp -t md_bootstrap_ad.XXXXXX)"
trap 'rm -f "$intended_ag_tmp" "$intended_ad_tmp"' EXIT
# Capture install's exit status explicitly: a partial write that returns
# nonzero would otherwise pass the [ ! -s ] size check and be installed as
# the real policy via backup_and_write.
if ! install -m 0644 "md_files/AGENTS.shared.md" "$intended_ag_tmp"; then
  echo "bootstrap: ERROR -- install failed for md_files/AGENTS.shared.md; aborting" >&2
  exit 1
fi
if [ ! -s "$intended_ag_tmp" ]; then
  echo "bootstrap: ERROR -- staged AGENTS payload is empty ($intended_ag_tmp); aborting" >&2
  exit 1
fi

if [ "$CODEX_HOME" != "$HOME/.codex" ]; then
  target_import="@$CODEX_HOME/AGENTS.md"
  # Use Python for the @import rewrite because BSD sed and POSIX awk gsub
  # both lack a portable way to emit a literal `&` in the replacement
  # (the GNU `\&` extension is not in BSD sed). Python's str.replace()
  # is unambiguous.
  if ! python3 -c '
import sys
target = sys.argv[1]
src = open(sys.argv[2]).read()
sys.stdout.write(src.replace("@~/.codex/AGENTS.md", target))
' "$target_import" "md_files/CLAUDE.adapter.md" > "$intended_ad_tmp"; then
    echo "bootstrap: ERROR -- python rewrite failed for md_files/CLAUDE.adapter.md; aborting" >&2
    exit 1
  fi
else
  target_import="@~/.codex/AGENTS.md"
  if ! install -m 0644 "md_files/CLAUDE.adapter.md" "$intended_ad_tmp"; then
    echo "bootstrap: ERROR -- install failed for md_files/CLAUDE.adapter.md; aborting" >&2
    exit 1
  fi
fi
if [ ! -s "$intended_ad_tmp" ]; then
  echo "bootstrap: ERROR -- staged adapter payload is empty ($intended_ad_tmp); aborting" >&2
  exit 1
fi

backup_and_write() {
  # Back up `$2` if it differs from the supplied `intended` file, then copy
  # `intended` over `$2` (idempotent — preserves mtime when no change).
  local intended="$1" dst="$2" ts="$3"
  if [ -f "$dst" ] && ! cmp -s "$intended" "$dst"; then
    cp -p "$dst" "$dst.bak.$ts"
    echo "backed up $dst -> $dst.bak.$ts"
  fi
  if [ ! -f "$dst" ] || ! cmp -s "$intended" "$dst"; then
    install -m 0644 "$intended" "$dst"
  fi
}

backup_and_write "$intended_ag_tmp"  "$CODEX_HOME/AGENTS.md"  "$ts"
backup_and_write "$intended_ad_tmp" "$CLAUDE_HOME/CLAUDE.md" "$ts"

if [ "$CODEX_HOME" != "$HOME/.codex" ] && ! grep -qF "$target_import" "$CLAUDE_HOME/CLAUDE.md"; then
  echo "ERROR: rewired adapter is missing target import $target_import" >&2
  exit 1
fi
[ "$CODEX_HOME" != "$HOME/.codex" ] && echo "rewired Claude adapter import to $target_import"

# 4. Verify both files are at their expected paths.
[ -f "$CODEX_HOME/AGENTS.md"  ] && echo "shared policy: OK ($CODEX_HOME/AGENTS.md)"
[ -f "$CLAUDE_HOME/CLAUDE.md" ] && echo "Claude adapter: OK ($CLAUDE_HOME/CLAUDE.md)"

# 5. Sanity check: the SOURCE files under md_files/ must not contain
#    absolute user paths. The installed copies are intentionally
#    machine-specific when CODEX_HOME is non-default (the @import is
#    rewired to an absolute path), so we scan the source files instead --
#    the portable artifacts that ship in version control.
#    Fail loudly if any input is missing, unreadable, or non-regular
#    (directories, fifos, symlinks to nowhere, etc.) — no false-positive OK.
ok=1
for f in "md_files/AGENTS.shared.md" "md_files/CLAUDE.adapter.md"; do
  if [ ! -f "$f" ] || [ ! -r "$f" ]; then
    echo "portable: ERROR -- $f is missing, unreadable, or not a regular file" >&2
    ok=0
    continue
  fi
  # Capture grep's exit status BEFORE the if-test (otherwise rc is always 0 here).
  grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+' "$f" >/dev/null 2>&1
  rc=$?
  case "$rc" in
    0) echo "portable: ERROR -- $f contains user-specific paths" >&2; ok=0 ;;
    1) : ;;                                                    # clean no-match
    *) echo "portable: ERROR -- grep failed on $f (exit $rc)" >&2; ok=0 ;;
  esac
done
[ "$ok" = "1" ] && echo "portable: OK (no /Users/<name> or /home/<name> paths in source files)"
```

Notes on the install path:

- `backup_and_write` uses bash functions that take a path-to-intended-content
  as the first argument, so paths with embedded spaces (e.g.
  `CODEX_HOME="$HOME/codex with space"`) are handled correctly. Do not replace
  this with `set -- $pair` — that word-splits on whitespace and silently
  skips backups.
- The comparison uses the **post-rewrite** adapter form (with `@$CODEX_HOME/AGENTS.md`
  substituted in when CODEX_HOME is non-default), not the raw source file. Without
  this, `cmp` would always see a "divergence" between the on-disk adapter and the
  raw source after the @import rewrite, and the bootstrap would create spurious
  backups on every re-run.
- `awk gsub` (not sed) is used for the @import rewrite because awk's gsub takes
  the replacement as a variable — paths containing `|`, `/`, `#`, or any other
  punctuation cannot break it. The replacement is pre-escaped for `&` and `\` so
  paths containing those characters (which awk gsub treats as back-references)
  survive intact.
- `case "$rc" in 0|1|*)` correctly maps grep's three exit codes (0 = match,
  1 = no match, ≥2 = error) to the right verdict. The earlier `if grep...; then
  rc=$?` shape always captured the if-test result (0 or 1), never grep's actual
  exit ≥2.

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
