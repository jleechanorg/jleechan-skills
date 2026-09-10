# Shared `CLAUDE.md` / `AGENTS.md` setup

Portable templates for the shared Codex/Claude policy layout. These files are **machine-portable** — they contain no user-specific paths, so a fresh machine can install them and have the same two-runtime setup the author uses.

If you fork or refresh these files, run the path-scan in the "Refreshing" section before committing.

## Files in this directory

| File | Install destination | What it is |
|------|---------------------|------------|
| `AGENTS.shared.md` | `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) | The **canonical shared global policy** loaded by every Codex/Claude session. Edit shared rules here once. |
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

`@~/.codex/AGENTS.md` is a literal text import — it does not expand environment variables, so the file must be installed at the default `~/.codex/AGENTS.md` (or you must edit the adapter to point at `$CODEX_HOME` if your `CODEX_HOME` is non-default).

### Why the indirection exists

- **Single source of truth.** Universal rules live in `~/.codex/AGENTS.md`. Both
  Codex (native load) and Claude Code (via `@` import) read it. No drift.
- **Adapter pattern.** Runtime-specific behavior lives in the adapter
  (`~/.claude/CLAUDE.md` adds Claude-only subagent rules, model routing,
  voice/calibration). Edit the adapter; the shared rules stay untouched.

## Reproducing this layout on a fresh machine

```bash
# 0. From the root of this repo, after `git clone` of jleechan-skills.

# 1. Install the shared policy to the Codex home (default ~/.codex).
mkdir -p ~/.codex
cp md_files/AGENTS.shared.md ~/.codex/AGENTS.md

# 2. Install the Claude adapter.
mkdir -p ~/.claude
cp md_files/CLAUDE.adapter.md ~/.claude/CLAUDE.md

# 3. Verify both files are at their expected paths.
test -f ~/.codex/AGENTS.md   && echo "shared policy: OK"
test -f ~/.claude/CLAUDE.md  && echo "Claude adapter: OK"

# 4. Sanity check: no absolute user paths leaked into the installed files.
! grep -E '/Users/[A-Za-z]+' ~/.codex/AGENTS.md ~/.claude/CLAUDE.md \
  && echo "portable: OK (no /Users/<name> paths)"
```

If your `CODEX_HOME` is not `~/.codex`, also update the `@` import in
`~/.claude/CLAUDE.md` to point at the actual Codex home.

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
! grep -nE '/Users/[A-Za-z]+|/home/[A-Za-z]+|@[A-Za-z0-9.-]+\.example\.(com|org|net)' \
    md_files/AGENTS.shared.md md_files/CLAUDE.adapter.md \
  && echo "portable: clean"
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
