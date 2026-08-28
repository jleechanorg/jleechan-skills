# Beads Issue Tracking - Your Project Reference

Beads (`bd`) is the project's git-native issue tracker. Issues live in `.beads/issues.jsonl` (version-controlled) with a SQLite cache (`beads.db`, gitignored).

## Essential Commands

```bash
bd list                              # List open issues
bd list --status in_progress         # Filter by status
bd show REV-abc123                   # Show issue detail
bd create "Fix the login bug"        # Create issue
bd update REV-abc123 --status done   # Close issue
bd search "keyword"                  # Full-text search
bd status                            # DB health summary
```

## Status Values

`open` | `in_progress` | `blocked` | `done` | `closed`

## Commit Convention

Reference beads in commit messages:

```
fix(auth): resolve JWT expiry edge case

REV-abc123
```

## Database Recovery ("no beads database found")

The SQLite DB (`beads.db`) is gitignored and ephemeral — created by the daemon, not committed. If the daemon is killed (e.g. by `integrate.sh`), the DB disappears and `bd` commands fail.

**Fix:** run `bd init` to rebuild from the committed JSONL:

```bash
bd init       # rebuilds beads.db from .beads/issues.jsonl
bd status     # verify
```

Do **not** set `no-db: true` in `.beads/config.yaml` unless you want to permanently disable SQLite. The SQLite DB gives you search, filtering, and daemon-backed performance.

## Why the Pre-Commit Hook Sometimes Warns

The `bd` pre-commit hook flushes pending changes to JSONL before every commit/stash. If the daemon is down and the DB is missing, it prints:

```
Warning: bd sync --flush-only failed (daemon may be down, run 'bd init' to restore DB)
```

This is a **warning only** — it does not block commits. Run `bd init` afterward to restore the DB.

## Integrate.sh and Beads

`integrate.sh` can kill the beads daemon as part of its cleanup. After running `integrate.sh`, if `bd status` shows the error above, just run `bd init`.

`integrate.sh --force` skips the expensive squash-merge detection for branches with >1000 commits (configurable via `FORCE_SQUASH_CHECK_MAX`).

## Config File: `.beads/config.yaml`

Key settings (uncomment to activate):

```yaml
issue-prefix: "REV"      # prefix for all issue IDs
sync-branch: "beads-sync" # git branch for beads commits
# no-db: false           # keep false to use SQLite (recommended)
# no-daemon: false       # keep false to use daemon for speed
```

## Daemon Management

```bash
bd daemon start           # start beads daemon
bd daemon stop            # graceful stop
bd daemons stop <path>    # stop daemon for specific repo path
bd doctor                 # diagnose issues
```

The daemon lives in the background and serves `bd` commands via a Unix socket (`.beads/bd.sock`). It is **not** needed for `bd` to work — just for performance.

## JSONL Sync

`.beads/issues.jsonl` is the source of truth committed to git. Always include `.beads/` changes in commits and PRs (per CLAUDE.md).

```bash
bd sync                   # sync JSONL ↔ DB
bd sync --flush-only      # write DB → JSONL only (what pre-commit hook does)
```

## Worktree Warning

Avoid staging `.worktrees/pr-*/` directories — git treats them as embedded repos and breaks `git stash`. If accidentally staged:

```bash
git rm --cached .worktrees/pr-5654
```

## Merge Conflict Prevention (union driver)

`.gitattributes` is configured with `merge=union` for `.beads/issues.jsonl`. This uses git's built-in union merge strategy which concatenates unique lines from both sides — no conflict markers ever, since each JSONL line is a self-contained record with a unique hash ID.

If you see merge conflicts in `.beads/issues.jsonl`, the union driver is not configured:

```bash
# Check
cat .gitattributes | grep beads
# Should show: .beads/issues.jsonl merge=union

# Fix if wrong
# Edit .gitattributes: change merge=beads to merge=union
# Remove the old custom driver:
git config --unset merge.beads.driver
```

## Working in Worktrees — Main Dir Drift

Each git worktree has its own `.beads/issues.jsonl`. The pre-commit hook (`/.git/hooks/pre-commit`) automatically:
1. Runs `bd sync --flush-only` (flushes Dolt DB → JSONL)
2. Runs `git add .beads/issues.jsonl` (auto-stages it)

So beads ride along with every code commit automatically — **no separate bead-only PRs needed**.

If you work primarily in worktrees and the main repo dir shows `modified: .beads/issues.jsonl`, you can safely discard it:

```bash
git checkout -- .beads/issues.jsonl
```

The beads from your worktrees will merge to main when those PRs merge (via the union driver).
