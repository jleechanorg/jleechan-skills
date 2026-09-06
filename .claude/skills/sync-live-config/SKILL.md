---
name: sync-live-config
description: Judge and propagate drift between this repo's .claude/.codex/hermes content and live agent-config directories (this machine's ~/.claude, ~/.codex, ~/.hermes, and optionally remote hosts over SSH). Use when a fix may have been committed to this repo but not reached the live harness, or vice versa.
---

# Sync live config

This repo is normally a downstream **export** of live agent config — usually
`~/.claude/` is the source of truth and `/exportcommands` pushes it here. But
that direction isn't guaranteed: a fix can land straight in this repo (e.g. a
subagent commits directly to GitHub) and never flow back, OR the live side
can move on independently after the last export and make the repo's snapshot
the stale one (confirmed for `hermes/skills/` on 2026-09-06 — see below).

**The script never decides direction. You do.** `scripts/sync_live_config.py`
has two subcommands:

- `report [--full] [--remote HOST]... [--json] [--remote-only]` — gathers
  evidence only, writes nothing. For every scoped file: `new` (missing live),
  `modified`, or `ok`, plus the repo's last commit touching that path, and —
  if the live path turns out to live inside its *own* distinct git repo (e.g.
  `~/.hermes` is `jleechanorg/jleechanclaw`) — that repo's last commit on the
  same path, plus a capped unified diff for small text files. It also reports
  a **`live_only`** status: files present live but absent from the repo's
  tracked scope, which a repo-only file scan would otherwise never see (this
  is the exact shape of the `hermes/skills` rename/delete drift below). Remote
  targets get the same per-file commit/diff enrichment as local, but **not**
  the `live_only` directory walk yet — see "Remote targets" below for the
  exact gap.
- `apply --direction {repo-to-live,live-to-repo} --paths PATH [PATH ...] [--remote HOST]`
  — mechanically copies exactly the paths you name, in exactly the
  direction you name. No inference, no batch-wide default. Every path is
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

## Protocol — this is where the judgment happens

1. **Gather evidence, not conclusions.**
   ```bash
   python3 scripts/sync_live_config.py report --json [--full] [--remote HOST]
   ```
   Read the JSON yourself. Do not skip straight to `apply`.

2. **Every file with status `ok` needs no action.** For every `new` or
   `modified` file, make an actual per-file (or, for `--full`, per-directory)
   judgment call — this is a model decision, not a lookup table:
   - Read the `diff_snippet` when present; understand *what* changed, not
     just *that* it changed. A pure description/typo fix reads differently
     than a behavior change.
   - Compare `repo_last_commit` vs `live_last_commit` (when the live path
     resolves into its own git repo). Whichever side has the more recent,
     more specific commit touching that exact path is the stronger — but
     not automatic — signal for which side is fresher.
   - If `live_repo_root` is set, that live path is under **independent,
     ongoing development outside this repo's export cycle** — treat repo→live
     there as suspect by default, not as the safe default direction.
   - If a file is `new` (missing on the live side) with no `live_last_commit`
     at all, that usually means live never had it — repo→live is the
     ordinary call, but still check whether the *containing feature* even
     makes sense on that target (e.g. a WorldAI-specific script has no
     business on a machine that doesn't run WorldAI).
   - When genuinely unsure, or when repo and live both show recent,
     substantive, divergent changes to the same file — **do not apply
     either direction.** Report it to the user as a real conflict instead
     of guessing.
   - A `live_only` row has no repo commit to compare against by definition —
     judge it from `live_repo_root`/`live_last_commit` alone (was this
     intentionally created/renamed live and never exported, or is it
     leftover junk?) and from context (test caches and `.pytest_cache/`
     artifacts are pre-filtered out, but skill-specific scratch files still
     show up and need a real look).

3. **`hermes/skills/` and `.claude/skills_archive/` are known inversion
   risks** (confirmed 2026-09-06: this repo's `hermes/skills/` snapshot
   traced entirely to a single stale 2026-08-01 `/exportcommands` push,
   while live `~/.hermes` — its own actively-committed repo — had moved on
   for 5+ weeks; a blind repo→live `--full` there would have resurrected
   already-renamed/deleted content). For any diff under these paths: check
   `live_repo_root`/`live_last_commit` first, and default to *recommending
   a fresh `/exportcommands` run* (live→repo) over silently pushing the old
   snapshot down, unless the evidence clearly says otherwise.

4. **Apply per decision, not per batch.** Once you've judged a file (or a
   small consistent group of files with the same, clearly-justified
   direction), apply exactly those paths:
   ```bash
   python3 scripts/sync_live_config.py apply --direction repo-to-live --paths <path> [<path> ...]
   python3 scripts/sync_live_config.py apply --direction live-to-repo --paths <path> [<path> ...] --remote jeff-ubuntu
   ```
   Never run `apply` over an entire report's file list without having
   individually judged each one.

5. **Report a decision table**, not just a summary: file, direction chosen
   (or "skipped — conflict"), one-line reason, applied y/n. The user needs
   to see the reasoning, not just the outcome.

6. **Never delete.** Applying in either direction only adds/overwrites the
   destination file; it never removes anything that exists only on one
   side.

## Remote targets

`report --remote HOST` resolves the remote `$HOME` once, then runs a single
batched script over SSH that returns, per path, its hash, enclosing-repo last
commit, and (for files under the diff-snippet size cap) base64 content so a
real unified diff can be computed locally — the per-file judgment inputs
match local. **One real gap remains:** the `live_only` directory walk (files
present live but never repo-tracked) only runs against the local machine
today; a remote target does not yet get that scan, so a remote-side rename/
delete drift (the `hermes/skills` incident shape) would currently be invisible
to `report --remote`. Treat a clean `report --remote` result as "no drift in
the tracked-file scope," not as "definitely no drift at all," until that gap
is closed. `apply --remote HOST` transfers only the files you named:
`tar`+`scp`+remote-extract for repo-to-live, or `ssh ... cat` for live-to-repo.
Destination paths are always fully resolved in Python before being sent to
the remote shell — never left for the remote side to expand a `$HOME`-style
variable itself. The remote batch script uses portable primitives
(`sha256sum` with a `shasum -a 256` fallback, a plain prefix-strip instead of
GNU-only `realpath --relative-to`) so it works against both Linux and macOS
remotes.

## Bootstrapping on a machine that has never run this before

`/sync-live-config` is a thin dispatcher pointing at
`${CLAUDE_HOME:-$HOME/.claude}/skills/sync-live-config/SKILL.md` — on a
machine where this skill has never been synced, that path doesn't exist yet
and the slash command can't resolve. The first sync on a new machine must be
done by running the script directly from a repo checkout:
`python3 scripts/sync_live_config.py report` — once this skill itself is
included in whatever scope you sync, the slash command becomes available for
every subsequent run.
