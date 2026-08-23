---
name: host-disk-guardian
description: Alert when the Mac runner host's free disk drops below 50GB, auto-clean safe targets (evidence bundles, scratchpads, merged-PR worktrees) below 20GB. Closes the gap where mac-runner-disk-cleanup.sh (retired) and ezgha's own docker-daemon-view disk floor only ever saw CONTAINER-side disk, never true HOST free space. Use when user says "check host disk", "disk guardian stuck", or after a low-disk incident on the MacBook runner host.
type: skill
scope: repo
owner: $USER
version: 1.0.0
triggers:
  - "host disk low"
  - "check host free space"
  - "clean up evidence bundles"
allowed-tools:
  - Bash
  - Read
context:
  - "Provenance: 2026-07-03 incident (bead rev-g5bwl) — host disk hit 100% (285MB free/926GB) mid runner-fleet recovery, corrupting colima's containerd content store (blob I/O errors) and nearly re-crashing the fleet."
  - "This is independent of ezgha's own disk floor check (ez-gh-actions src/docker_backend.rs, min_free_disk_gb): that check measures disk 'as seen by the docker daemon' and only gates new container spawns. It does not see or clean host-side, non-docker files — the actual root cause of the 2026-07-03 incident."
  - "Two tiers: WARN (<50GB) and CRITICAL (<20GB, auto-clean runs). Both tiers post a Slack alert by reading ezgha's already-configured webhook from ~/.config/ezgha/config.toml at runtime (rev-a6pww) -- never hardcoded, degrades to a log-only line if the config/field/curl call is missing or fails. Auto-clean targets, safest-first: evidence bundles under /tmp/your-project.com/* older than 2 days, scratchpads under /private/tmp/claude-501/* older than 3 days, then merged-PR agent worktrees under /private/tmp/wa-*."
  - "Worktree cleanup is the highest-risk target and has four independent safety gates: (1) the worktree's own `origin` remote must actually be $GITHUB_REPOSITORY, never trusted by branch-name alone; (2) the branch must have a CONFIRMED merged PR via `gh pr list --state merged` whose headRefOid matches the worktree's current HEAD exactly, never inferred from name/age or a reused/rebased branch; (3) zero uncommitted changes (git status --porcelain empty); (4) `git worktree remove` is called WITHOUT --force, so git's own refusal is the real backstop."
  - "Mac-host-scoped only (uses macOS-specific `df -g`). The Linux fleet (jeff-ubuntu) has its own separate hardening tracked under bead rev-runn001, not this skill."
---

# /host-disk-guardian — Mac runner host free-space alert + auto-clean

## The problem it solves

`mac-runner-disk-cleanup.sh` (retired along with self-hosted-oss) and ezgha's
own disk floor check (`docker_backend.rs`, `min_free_disk_gb`) both only ever
see disk space from inside the container/docker-daemon view. Neither one sees
or cleans host-side files that don't belong to a container: evidence bundles
under `/tmp/your-project.com/*`, Claude scratchpads under
`/private/tmp/claude-501/*`, and stray git worktrees left behind after a PR
merges. On 2026-07-03, exactly this kind of host-side accumulation drove free
disk to 285MB/926GB, corrupting colima's containerd content store mid-recovery.

## Usage

```bash
bash .claude/skills/host-disk-guardian/scripts/host-disk-guardian                # check + clean if critical
bash .claude/skills/host-disk-guardian/scripts/host-disk-guardian --dry-run       # report only, never delete
```

## Thresholds

| Tier | Free disk | Action |
|------|-----------|--------|
| Healthy | >= 50GB | log only, exit 0 |
| Warn | 20-50GB | log ALERT + Slack alert, exit 1, no cleanup |
| Critical | < 20GB | log CRITICAL + Slack alert, run auto-clean, exit 2 |

Override via `HOST_DISK_GUARDIAN_WARN_GB` / `HOST_DISK_GUARDIAN_CRITICAL_GB`. Slack alert reads
`slack_webhook_url` from `~/.config/ezgha/config.toml` at runtime (override via
`HOST_DISK_GUARDIAN_EZGHA_CONFIG`) -- never hardcoded, never git-tracked. Missing config, missing
field, or a failed `curl` all degrade to a log line; the host-disk-guardian/auto-clean logic never
depends on the alert channel succeeding.

## Auto-clean targets (critical tier only), in order

1. Evidence bundles: `/tmp/your-project.com/*` older than 2 days.
2. Scratchpads: `/private/tmp/claude-501/*` older than 3 days.
3. Merged-PR worktrees: `/private/tmp/wa-*` whose branch has a confirmed
   merged PR **and** zero uncommitted changes. Anything ambiguous (dirty
   worktree, unmerged branch, unreadable branch) is skipped and logged, never
   force-deleted.

All three directory roots and the worktree glob are overridable via
`HOST_DISK_GUARDIAN_EVIDENCE_DIR` / `HOST_DISK_GUARDIAN_SCRATCHPAD_DIR` /
`HOST_DISK_GUARDIAN_WORKTREE_GLOB` (used by the test suite for isolation).

## Install (launchd, macOS)

```bash
sed -e "s|@HOME@|$HOME|g" \
    -e "s|@INSTALL_DIR@|<absolute-path-to-repo>|g" \
    -e "s|@LOG_DIR@|$HOME/Library/Logs|g" \
  .claude/skills/host-disk-guardian/install/org.jleechanorg.host-disk-guardian \
  > ~/Library/LaunchAgents/org.jleechanorg.host-disk-guardian
launchctl load ~/Library/LaunchAgents/org.jleechanorg.host-disk-guardian
```

Remove:
```bash
launchctl unload ~/Library/LaunchAgents/org.jleechanorg.host-disk-guardian
rm ~/Library/LaunchAgents/org.jleechanorg.host-disk-guardian
```

## Tests

`scripts/tests/test_host_disk_guardian.sh` — mocks `df` (forces each disk
tier deterministically) and `gh` (forces merged/unmerged PR lookups), uses
real `git worktree add`-linked fixtures (not standalone `git init` repos) so
the actual `git worktree remove` safety path is exercised, not bypassed.
