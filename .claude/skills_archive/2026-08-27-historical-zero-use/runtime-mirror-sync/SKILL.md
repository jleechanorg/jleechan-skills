---
name: runtime-mirror-sync
description: RETIRED — self-hosted-oss/install.sh and its runtime mirror sync flow no longer exist. Historical reference only; see runner-health and ezgha-watchdog for the current mechanism.
type: reference
---

# Runtime Mirror Sync (RETIRED)

**Status: retired.** `self-hosted-oss/` (including `install.sh` and the
`RUNTIME_SCRIPTS` array described below) was deleted from this repo by
PR #8057 and its cleanup follow-up completing that retirement. The live
self-hosted runner fleet is now managed by the external `ez-gh-actions`
("ezgha") daemon; in-repo support scripts live under
`self-hosted-colima/scripts/`. For current fleet health and operations,
see `.claude/skills/runner-health/SKILL.md` and the user-scope
`ezgha-watchdog` skill. The rest of this document is preserved as
historical context for why the old mirror-sync flow existed — do not
follow it for new changes, and do not resurrect
`self-hosted-oss/install.sh`.

**Known follow-up:** the user-scope PreToolUse hook
`~/.claude/hooks/block-runtime-mirror-edits.sh` referenced below still
exists outside this repo and still assumes the retired flow described
here. It needs separate manual review/removal by the repo owner — this
skill file cannot reach outside this repo's git tree to fix it.

---

## Historical content (pre-retirement)

`launchd` runs scripts out of `~/.local/share/worldarchitect-runners/`. That
directory was a **runtime mirror** populated by
`self-hosted-oss/install.sh`'s `RUNTIME_SCRIPTS` array from
`self-hosted-oss/*.sh` in this repo.

## Why this matters

Editing the mirror directly is the "I edited the wrong file" anti-pattern.
It is silently clobbered on the next `install.sh` run, and other Macs never
see the change. The fix never propagates; the bug "magically comes back" on
reboot or on a teammate's machine.

## Enforcement

A user-scope PreToolUse hook
(`~/.claude/hooks/block-runtime-mirror-edits.sh`, Edit|Write|MultiEdit
matcher) blocks direct Edit/Write on
`~/.local/share/worldarchitect-runners/*.sh` and emits a diagnostic pointing
to the correct path. The hook deliberately allows:

- Edit/Write on `self-hosted-oss/*.sh` (any worktree)
- Edit/Write on `.jsonl` / `.log` / `.bak` / `.swp` in the mirror (state files)
- Bash `cp` / `rsync` to the mirror (the explicit sync shortcut below)

## Correct flow for self-hosted-oss changes

1. Edit `self-hosted-oss/<script>.sh` in the repo (this worktree).
2. Commit + push + open a PR (infra changes need a PR; host-only edits
   drift, get clobbered, and don't propagate).
3. After commit, sync the local mirror via Bash:
   ```bash
   cp self-hosted-oss/<script>.sh \
      ~/.local/share/worldarchitect-runners/<script>.sh
   ```
4. After the PR merges, re-run `bash self-hosted-oss/install.sh` on every
   other Mac so `RUNTIME_SCRIPTS` re-populates the mirror from the merged
   source.

## Making a change — self-hosted runner change protocol

Any change to the self-hosted runner setup (Docker runtime, launchd plist,
socket path, environment variables, Colima config) **must**:

1. **Update `install.sh`** — the script is the source of truth; a host-level
   change not reflected in `install.sh` will be lost on reinstall or a new
   machine.
2. **Commit a plist template** to `self-hosted-oss/launchd/` for any launchd
   agent installed to `~/Library/LaunchAgents/`. Use
   `@HOME@`/`@INSTALL_DIR@`/`@LOG_DIR@` placeholders. The installed plist must
   be reproducible by re-running `install.sh`.
3. **No bare `sudo` or `brew services` one-liners as the fix** — wire them
   into the install script so a fresh machine gets the same result
   automatically.
4. **All changes go through a PR.** No one-off host edits outside
   `self-hosted-oss/`. PR review catches (a) cross-machine drift, (b) audit
   trail, (c) host-specific fixes that don't propagate. Create via `/newb`;
   re-run `install.sh` on each host after merge.
5. **Single-writer check before opening the PR**: run
   `./scripts/check-pr-file-collisions.sh` (or `--pr N` on an existing PR).
   Multiple open PRs silently editing the same runner-health script
   (`ubuntu-runner-health.sh`, `mac-runner-health.sh`, `runner-health-lib.sh`)
   is a recurring collision class (#8057/#8056/#8033); a COLLISION hit means
   that file needs exactly ONE owning PR — coordinate before proceeding.
   Advisory only, not a CI gate.

## When the hook blocks — what to do

If you hit the hook, you almost certainly meant to edit
`self-hosted-oss/<script>.sh`. Re-open the file in the repo path and apply
the change there. The override `RUNTIME-MIRROR EDIT APPROVED` exists for
short-lived local experiments that will be reverted before the next install,
but is intentionally awkward to type.

## Related memory

- `feedback_2026-06-18_heal_runners_sigkill_session_conflict.md` — the
  episode that surfaced the wrong-file problem; documents the SIGKILL→SIGTERM
  fix at the recycle site, not in the mirror.
- `feedback_2026-06-09_runner_supervisor_and_ops.md` — the earlier
  "Stable install path sync" rule this skill extends.
