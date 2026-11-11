---
name: disk-magician
description: Use when diagnosing disk capacity or growth and when previewing repository-gated cache, temp, or worktree cleanup.
---

# Disk Magician — Claude Skill

This skill teaches Claude how to use `disk_magician` to audit disk space, identify growth regressions, and perform cleanups.

## Measurement rule

All Disk Magician measurements, reports, cleanup previews, and candidate scans follow `../disk-root-cause/SKILL.md` § Mandatory 100 MiB directory descent. A large directory total or prefix bucket locates where to investigate; it cannot stand in for child measurements, leaf age, or reclaim eligibility. Candidate size filters such as `DISK_MAGICIAN_SCRATCH_MIN_KB` only prioritize already traversed candidates; they never limit descent.

## Skill Integration & Commands

* **Which procedure**: a quick capacity check runs the zero-`du` triage in `../disk-audit/SKILL.md`. A reclaimable-amount estimate, root-cause investigation, or cleanup-target decision runs the full forensic procedure in `../disk-root-cause/SKILL.md`. Do not stop at a quick check when the request needs attribution. On the quick path, escalate when precomputed data is missing or its owner reports it stale or incomplete; follow the probe result rather than a fixed interval.
* **Default forensic diagnosis (attribution only)**: For a root-cause, floor, growth, or reclaim-estimate request, follow `../disk-root-cause/SKILL.md` after the quick probes. Run the full three-lane `diskm audit` unless a current report proves complete 100 MiB leaf coverage for every requested path and period; directory-aggregate snapshots do not prove this coverage. Use resolved portions, name unfinished paths, and do not estimate reclaim from incomplete paths.
* **Cleanup previews**: Use the canonical preview interfaces before choosing a cleanup target:
  ```bash
  diskm clean --dry-run
  diskm clean-all --dry-run
  diskm worktree-hygiene
  ```
  `worktree-hygiene` is report-only by default. For a narrower preview, use the selected `diskm` cleanup command with its documented dry-run mode.

  Never report the cleanup stack exhausted while free space remains below target. If a run reports `0 B` reclaimed, inspect the per-target skip reasons (such as `kept:lease-busy`, `kept:recent-activity`, or `kept:admin-unknown` when emitted) and the current lock holder before concluding there are no eligible targets.

## Safety Constraints & Guardrails
- **Mtime Caution:** Worktrees and agent sessions with modification time < 14 days require explicit `WORKTREE APPROVED` confirmation from the user before deletion.
- **Action gates:** Deletions and WIP publication require explicit user authorization for the exact target and each command's documented gate. This includes cleanup modes such as `--clean`, `--clean-all`, and `--routine`, plus `worktree-hygiene --execute` and `--push-wip`. `WORKTREE_APPROVED=1` is required for `--execute` deletions; it is not consent. Never place approval variables in command examples.
- **Never-delete list:** Do not delete `~/.codex/sessions`, `~/.codex/sessions_archive/`, `~/.codex/state*.sqlite`, `~/.codex/log`, or `~/.claude/projects` directly. Always route cleanup through the canonical `diskm` command so its safety filters are respected.
