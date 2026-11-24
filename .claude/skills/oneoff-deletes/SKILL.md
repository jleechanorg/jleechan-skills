---
name: oneoff-deletes
description: "Use for a one-off bulk delete of old files in explicitly named temp, scratch or cache roots (\"delete everything older than 6h in X\", \"reclaim space now\") when no sanctioned cleaner covers the job or its preview deferred everything. Qualifies each entry by age, open handles and unpushed git work, deletes only inside the authorized roots, and records a receipt."
---

# One-off deletes

Delete old data from named roots safely, in parallel, with a receipt. Use the project's own cleaner first
when it works. This skill is for the case where the cleaner is missing, broken, or reports "nothing
eligible, all deferred" while old data plainly exists. A deferred or incomplete preview does not prove
nothing is deletable; qualify independently.

## 1. Pin the scope before touching anything

- Write down the exact roots the user authorized (for example `/private/tmp` and one scratch volume).
  Every other root a report mentions (user temp, caches, home subdirectories) is out of scope until the
  user names it. When unsure, leave it out and say so.
- Pin the age rule (default 6 hours = 360 minutes) and the deletion method the user chose.
- One deletion owner at a time: confirm no other cleaner is running against the roots (`pgrep -f -- '<anchored name>'`).
- Record `df -k` for every root before starting.

## 2. Qualify (read-only)

`scripts/qualify.sh` prints candidates and writes the open-file list:

```bash
ROOTS="/private/tmp:/path/to/scratch" OPEN_LIST="$WORK/open.txt" DEPTH=1 \
  bash scripts/qualify.sh > "$WORK/candidates.txt"
```

It keeps an entry only if nothing beneath it was modified or status-changed within the window, no open
file lies beneath it, and its name is not state-like (sockets, pids, locks, per-session dirs). Use
`DEPTH=2` in a second pass to catch old children of directories that are partly active.

Then check what the script cannot know:

- **Unpushed work.** For every candidate containing `.git`, run `git status --porcelain`,
  `git log --branches --not --remotes`, and `git stash list`. Keep any clone with unpublished commits or
  stashes (publish them first if the user wants).
- **Live state.** Keep anything a running process or tool treats as configuration: pointer files, watcher
  state, auth directories, the session's own temp directory, registered lease or infrastructure dirs.
  Hidden entries are skipped by default.
- **Size and shape.** `du -sk` the candidates in parallel and look at the top ten before deleting.

## 3. Delete

Write the candidate list NUL-separated, then fan out one entry per process. Each call re-validates the
path prefix, re-checks age and open handles, and prints one status line:

```bash
tr '\n' '\0' < "$WORK/candidates.txt" > "$WORK/candidates.nul"
ROOTS="..." OPEN_LIST="$WORK/open.txt" EXCLUDE="*/keep-me/*" \
  xargs -0 -n1 -P8 bash scripts/delete_entry.sh < "$WORK/candidates.nul" > "$WORK/delete_log.tsv" &
```

Run it in the background with a captured log and poll the log; for multi-minute runs never block the
foreground. To stop, kill the `xargs` process, then confirm no `delete_entry.sh` children remain.

Rules that keep this safe:

- Write helper scripts with the editor/Write tool, not a shell heredoc; command-safety hooks reject
  heredocs containing `rm -rf`. Do not rephrase around a hook block.
- Never run a "test" delete on an arbitrary smallest item; pick a throwaway you created.
- Order work so any doubtful root runs last, and stop before it if scope is unclear.
- Refresh the open-file list immediately before each run; roots change while you work.
- `lsof <dir>` does not list files beneath `<dir>`. Use the full `lsof -F n` list and match by prefix
  (this is what `qualify.sh` does).

## 4. Receipt

Report, with numbers taken from the log files rather than memory: entries deleted per root, partial and
skipped counts by reason (`SKIP-new`, `SKIP-open`, `SKIP-excluded`, `PARTIAL`), `df -k` before and after
per root, what was kept and why (unpushed clones, open handles, live dirs), and any scope you declined.
Keep the deleted-path list somewhere durable (not inside a root you just cleaned) and update the tracking
bead or ticket, if one exists, with the same numbers.

## Scripts

- `scripts/qualify.sh` — read-only candidate finder (`ROOTS`, `OPEN_LIST`, `MIN`, `DEPTH`, `P`).
- `scripts/delete_entry.sh` — delete one entry after re-validation (`ROOTS`, `OPEN_LIST`, `MIN`, `EXCLUDE`).
