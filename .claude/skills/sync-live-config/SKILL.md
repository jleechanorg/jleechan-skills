---
name: sync-live-config
description: Propagate this repo's .claude/.codex/hermes fixes to live agent-config directories (this machine's ~/.claude, ~/.codex, ~/.hermes, and optionally remote hosts over SSH). Use when a fix was committed to this repo but hasn't reached the live harness.
---

# Sync live config

This repo is a portable **export** of live agent config — normally
`~/.claude/` is the source of truth and `/exportcommands` pushes it here. When
fixes instead land straight in this repo (e.g. a subagent commits directly to
GitHub), they never flow back to the live directories automatically. This
skill closes that gap in the other direction: repo → live.

It is strictly one-directional and additive — it never deletes a live-only
file and never reads live state back into the repo.

## Default vs full scope

- **Default**: only the "top 6" highlighted skills from the README's
  `### Highlighted skills · left/right shift strategy` table (currently:
  `superpowers-quick`, `advice`, `web-advice`, `redgreen`, `4layer`,
  `evidence-review`, `harness-engineering`), plus any command dispatcher
  `.md` files that reference them. The script derives this list by parsing
  README.md directly — it is not a hardcoded, driftable copy.
- **`--full`**: every tracked file under `.claude/`, `.codex/hooks/`, and
  `hermes/skills/`.

## Usage

```bash
python3 scripts/sync_live_config.py                    # dry-run, local machine, top-6 only
python3 scripts/sync_live_config.py --full              # dry-run, local machine, everything
python3 scripts/sync_live_config.py --remote jeff-ubuntu # dry-run, local + a remote host
python3 scripts/sync_live_config.py --apply              # actually write the top-6 diffs locally
python3 scripts/sync_live_config.py --full --remote jeff-ubuntu --apply  # full sync, both machines
```

Run this from anywhere inside the repo — it resolves the repo root itself via
`git rev-parse --show-toplevel`.

## Protocol

1. **Always dry-run first.** Without `--apply` the script only reports
   `NEW` (missing on the target) and `MODIFIED` (content differs) files —
   it writes nothing. Read the report before deciding whether `--full` is
   actually warranted; default to top-6 unless the user explicitly asks for
   a full sync.
2. **Remote targets** are compared via a single batched `ssh ... sha256sum`
   round trip (no full file transfer for the dry run) and, on `--apply`,
   synced via a `tar` + `scp` + remote-extract round trip — mirrors the
   manual recipe this skill replaces.
3. **Report the diff plainly**: file counts per target, and the literal
   list of `NEW`/`MODIFIED` live paths. Do not summarize away specifics —
   the user needs the exact paths to spot-check.
4. **Never delete.** A file that exists live but not in the repo's scope is
   left alone; this skill only adds/updates.

## `hermes/skills/` is a special case — verify direction before `--full`

`.claude/` and `.codex/hooks/` reliably flow repo → live (this repo is the
freshest source when a fix was committed straight to GitHub). `hermes/skills/`
is different: it is populated by a *separate*, manually-invoked, one-shot
`/exportcommands` push from `~/.hermes/skills` (itself its own actively
maintained git repo, e.g. `jleechanorg/jleechanclaw`) into this repo. If that
export hasn't run recently, this repo's `hermes/skills/` snapshot goes stale
— and a `--full --apply` would then **resurrect content already renamed or
deleted on live**, not fix drift (confirmed 2026-09-06: 713 "missing" files
under `~/.hermes/skills/` traced entirely to a single 2026-08-01 export
commit, while live had moved on for 5+ weeks).

Before running `--full --apply` against `hermes/skills/`: check
`git log --oneline -- hermes/skills | head -3` in this repo for staleness,
and prefer re-running `/exportcommands` (live → repo) to refresh the
snapshot first, rather than pushing the stale snapshot back down to live.
`.claude/skills_archive/` carries the same caution — diffs there may reflect
a deliberate archival pass (e.g. the 2026-08-27 zero-use archive), not
accidental drift.
