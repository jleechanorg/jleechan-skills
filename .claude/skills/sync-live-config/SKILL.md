---
name: sync-live-config
description: Judge and propagate drift between this repo's .claude/.codex/hermes content and live agent-config directories (this machine's ~/.claude, ~/.codex, ~/.hermes, and optionally remote hosts over SSH). Use when a fix may have been committed to this repo but not reached the live harness, or vice versa.
---

# Sync live config

This repo is normally a downstream **export** of live agent config — usually
`~/.claude/` is the source of truth and `/exportcommands` pushes it here. But
that direction isn't guaranteed: a fix can land straight in this repo and
never flow back, or the live side can move on independently after the last
export. When both contain useful work, reconcile semantics in the canonical
source before choosing a propagation direction.

**The script never decides direction. You do.** `scripts/sync_live_config.py`
has two subcommands:

- `report [--full] [--remote HOST]... [--json] [--remote-only]` — gathers
  evidence only, writes nothing. For every scoped file: `new` (missing live),
  `modified`, or `ok`, plus the repo's last commit touching that path, and —
  if the live path turns out to live inside its *own* distinct git repo (e.g.
  `~/.hermes` is its own checkout of a separate harness repository) — that repo's last commit on the
  same path, plus a capped unified diff for small text files. The snippet is a
  discovery aid, not complete review evidence: read both full files and create
  a complete diff before deciding. It also reports
  a **`live_only`** status: files present live but absent from the repo's
  tracked scope, which a repo-only file scan would otherwise never see (this
  is the exact shape of the `hermes/skills` rename/delete drift below). Remote
  targets get the same per-file commit/diff enrichment as local **and** the
  same `live_only` directory walk. A remote path with a symlinked component anywhere in it (leaf
  or parent directory) reports status **`symlink`** instead, with hash/size/
  commit/diff all withheld — see "Remote targets" for why.
- `apply --direction {repo-to-live,live-to-repo} --paths PATH [PATH ...] [--remote HOST] [--dry-run]`
  — mechanically copies exactly the paths you name, in exactly the
  direction you name. **`--dry-run` previews the whole decision without writing
  anything**: per path it prints the exact source and destination absolutes,
  whether the destination would be `CREATE`d, `OVERWRITE`n, is already `SAME`,
  or why it would `FAIL`, with full hashes when available (`dst=missing` for
  creates) — and exits non-zero if any path would fail
  validation, so it doubles as a preflight. Reach for it before
  every `apply`, especially a multi-path one. It refuses `--remote` rather than
  silently previewing only the local half. No inference, no batch-wide default. Every path is
  validated to resolve inside one of the allowed roots (`.claude/`,
  `.codex/hooks/`, `hermes/skills/` and their live counterparts) before
  anything is touched — traversal, absolute paths, and symlink escapes are
  rejected, since the paths applied here come from your own judgment calls
  and should be checked like any other trust boundary.

## Default vs full scope

- **Default**: the README's `### Highlighted skills · left/right shift
  strategy` table (currently `superpowers-quick`, `advice`, `web-advice`,
  `redgreen`, `4layer`, `evidence-review`, `harness-engineering`), parsed
  live from README.md — not a hardcoded, driftable list — plus any command
  dispatcher `.md` that references one of those skills.
- **`--full`**: every tracked file under `.claude/`, `.codex/hooks/`,
  `hermes/skills/`. Expect this to surface a lot more — go per-directory
  first (see below), don't try to judge thousands of individual files.
  Runtime/state subtrees (`projects/`, `state/`, `venvs/`, `node_modules/`,
  `plugins/`, session and history dirs — see `RUNTIME_DIRS`) are pruned during
  the walk: they are not syncable config, and `~/.claude/projects` alone is
  ~72k files. Commit lookups are batched once per enclosing repo, so a full
  report is minutes, not a hang. A run over ~3.5k tracked files yields ~5k
  `live_only` rows; judge those per-directory, never row by row.

## Protocol — this is where the judgment happens

1. **Gather evidence, not conclusions.**
   ```bash
   python3 scripts/sync_live_config.py report --json [--full] [--remote HOST]
   ```
   Read the JSON yourself. Do not skip straight to `apply`.

2. **Read the complete scoped source before judging drift.** `diff_snippet` is
   capped and cannot establish that omitted parts agree. Re-pin the repository
   commit and live target, read the full contents of each changed file, compare
   complete diffs, and inspect linked companion files and live-only files in the
   same scope. Use hashes as well as text; report filters and greps are only
   prefilters.

3. **Reconcile meaning before choosing direction.** For each file or tightly
   related group, record which semantic units to keep, adapt or reject and why.
   Preserve useful valid requirements from both copies. Do not default to the
   repository or live copy, concatenate conflicting prose, or infer authority
   from mtime or commit recency. Resolve conflicts through the active instruction hierarchy and each
   rule’s declared scope and owner; preserve repository-specific requirements
   within their domain. A canonical location establishes edit ownership, not
   that useful installed changes are obsolete. Commit history and `live_repo_root` are
   freshness evidence, never authority by themselves. Inspect scoped live-only files before deciding
   whether they are intentional, renamed or disposable. When the hierarchy
   resolves a conflict, make the smallest coherent best-of-both edit in the
   canonical repository source before propagating it. Escalate only a genuine
   unresolved owner, access or scope decision; state the exact conflict and
   attempted routes. A `symlink` row is not a direction decision: inspect its
   target owner, bytes and history read-only, retaining the automatic apply
   refusal unless a separately verified canonical target is handled through an
   authorized diff-first decision.

4. **Account for report states per path.** `ok` needs no action. For `new` or
   `modified`, inspect the full contents and relevant history. A missing live
   path usually favors repo→live only after checking that the feature belongs
   on that host. An independent `live_repo_root` calls for particular care but
   does not decide direction. A `live_only` file has no repository history;
   determine whether it is intentional, a rename or residue from its contents
   and owner. Test caches and `.pytest_cache/` artifacts are prefiltered, but
   inspect other scoped files.

5. **`hermes/skills/` and `.claude/skills_archive/` are known inversion
   risks** (confirmed 2026-09-06: this repo's `hermes/skills/` snapshot
   traced entirely to a single stale 2026-08-01 `/exportcommands` push,
   while live `~/.hermes` — its own actively-committed repo — had moved on
   for 5+ weeks; a blind repo→live `--full` there would have resurrected
   already-renamed/deleted content). For any diff under these paths: check
   `live_repo_root`/`live_last_commit` first, and default to *recommending
   a fresh `/exportcommands` run* (live→repo) over silently pushing the old
   snapshot down, unless the evidence clearly says otherwise.

6. **Re-pin and prepare before every write.** Refresh the source commit and
   hashes, destination hashes and working-tree state immediately before
   applying. If any input changed, repeat the full comparison and judgment.
   For each overwrite, preserve the exact destination bytes in configured
   Scratch and record the backup path/hash; record an explicit missing
   destination for a create. Run `apply --dry-run` for local writes and resolve
   every result. For remote writes, where dry-run is refused, verify the
   destination and reviewed backup through an authorized read-only route first.

7. **Apply per decision, not per batch.** Once you've judged a file (or a
   small consistent group of files with the same, clearly-justified
   direction), apply exactly those paths:
   ```bash
   python3 scripts/sync_live_config.py apply --direction repo-to-live --paths <path> [<path> ...]
   python3 scripts/sync_live_config.py apply --direction live-to-repo --paths <path> [<path> ...] --remote <ssh-host>
   ```
   Never run `apply` over an entire report's file list without having
   individually judged each one.

8. **Verify and report.** Read every destination back from its target host,
   compute its SHA256 and compare it with the reconciled source bytes. Report
   each path's keep/adapt/reject decisions, source and destination hashes,
   direction (or "skipped — unresolved conflict"), reason and whether it was
   applied. A successful copy command alone does not prove synchronization.

9. **Never delete.** Applying in either direction only adds/overwrites the
   destination file; it never removes anything that exists only on one
   side.

## Remote targets

`report --remote HOST` resolves the remote `$HOME` once, then runs a single
batched script over SSH that returns, per path, its hash, enclosing-repo last
commit, and (for files under the diff-snippet size cap) base64 content so a
real unified diff can be computed locally — the per-file judgment inputs
match local, including the `live_only` directory walk (files present live but
never repo-tracked), which now runs against the remote host too — so a
remote-side rename/delete drift (the `hermes/skills` incident shape) is
visible on a remote target, not just locally. The remote walk honours the same
noise filters and reports a symlinked path as `symlink` with all metadata
withheld, exactly like the tracked-file pass.

If that walk fails on a host, `report` prints a `warning: remote live_only scan
incomplete on <host>` line to stderr and still returns the tracked-file
results. A bare clean remote result therefore means "no drift in the
tracked-file scope"; check for that warning before reading it as "no drift at
all." `apply --remote HOST` transfers only the files you named:
`tar`+`scp`+remote-extract for repo-to-live, or a guard-checked remote `cat`
for live-to-repo (see below — this is not a bare `ssh ... cat`).
Destination paths are always fully resolved in Python before being sent to
the remote shell — never left for the remote side to expand a `$HOME`-style
variable itself. The remote batch script uses portable primitives: a
`sha256sum`-with-`shasum -a 256`-fallback for hashing, and `git -C "$dir" log
-- "$p"` (letting git resolve the pathspec itself against the absolute path)
for the commit lookup instead of manually reconstructing a relative path —
both an earlier `realpath --relative-to` version (GNU-only) and its
replacement prefix-strip silently dropped commit metadata whenever `$HOME` or
any path component was a symlink.

**Symlink handling is asymmetric between local and remote, by design and
verified in review, not accidentally uniform:**
- **Remote** (both `report`'s evidence gathering and both `apply`
  directions) walks every path component between the mapped root and the
  target through a shared bash function and refuses the operation entirely
  if *any* component is a symlink — including the leaf. A symlinked remote
  path shows up in `report` as status `symlink`, with hash/size/commit/diff
  all withheld (an earlier version withheld only file content, which still
  let a symlinked path's exact hash and size leak as a confirmation oracle
  for an arbitrary file elsewhere on the host).
- **Local** (`live_abs_for`/`repo_abs_for`) resolves the full path and checks
  that the result stays within the *specific* mapped root (e.g.
  `home/.claude`), which blocks escaping that root but does **not** walk
  component-by-component — a symlink whose target is still inside the same
  mapped root (e.g. `.claude/skills/foo/SKILL.md -> .claude/settings.json`)
  is allowed through. This is intentionally less strict locally than
  remotely; see "Accepted residual risks" below.

## Bootstrapping on a machine that has never run this before

`/sync-live-config` is a thin dispatcher pointing at
`${CLAUDE_HOME:-$HOME/.claude}/skills/sync-live-config/SKILL.md` — on a
machine where this skill has never been synced, that path doesn't exist yet
and the slash command can't resolve. The first sync on a new machine must be
done by running the script directly from a repo checkout:
`python3 scripts/sync_live_config.py report` — once this skill itself is
included in whatever scope you sync, the slash command becomes available for
every subsequent run.

## Accepted residual risks

This tool operates on the caller's own `$HOME` under their own account — it
is not designed to defend against an adversary who already has local write
access to that account. Two known gaps are accepted rather than chased
further, both discussed and agreed in review:

- **A symlinked check-then-write TOCTOU window.** Every containment check
  resolves symlinks and then performs a normal `open`/`cp`; a symlink
  swapped in between the check and the write would be followed. Closing this
  properly needs `O_NOFOLLOW`/`dir_fd`-relative opens, which is disproportionate
  for a single-user tool that only ever targets its own account.
- **The top-level mapped root itself being a symlink.** Containment is
  checked against `home/.claude` (etc.) *as resolved* — if `~/.claude` itself
  is a symlink to some other location (a real, common dotfiles pattern),
  everything computed relative to it is still "relative to" that resolved
  root, so operations transparently follow it. This is indistinguishable
  from the legitimate case without asking the operator, and this repo
  explicitly wants to support "my `~/.claude` is symlinked to my dotfiles
  repo" as normal, not broken.
