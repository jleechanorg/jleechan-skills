---
name: disk-magician
description: Use when diagnosing disk capacity or growth and when previewing repository-gated cache, temp, or worktree cleanup.
---

# Disk Magician — Claude Skill

This skill teaches Claude how to use `disk_magician` to audit disk space, identify growth regressions, and perform cleanups.

## Skill Integration & Commands

* **Which procedure**: a quick capacity check or plain reclaim question runs the zero-`du` triage in `../disk-audit/SKILL.md`. A root-cause investigation or cleanup-target decision runs the full forensic procedure in `../disk-root-cause/SKILL.md`. Do not start a full audit for a quick check. On the quick path, escalate when a precomputed ledger or snapshot is missing, or its own freshness probe reports `STALE`; use `diskm ledger-freshness` for the ledger and follow the probe result rather than a fixed interval.
* **Default forensic diagnosis (attribution only)**: For a root-cause request, run the full three-lane `diskm audit` before drilling down. The residual is not backup size or reclaimable without evidence.
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
