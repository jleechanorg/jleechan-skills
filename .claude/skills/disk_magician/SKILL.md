---
name: disk_magician
description: Use when diagnosing disk capacity or growth and when previewing repository-gated cache, temp, or worktree cleanup.
---

# Disk Magician — Claude Skill

This skill teaches Claude how to use `disk_magician` to audit disk space, identify growth regressions, and perform cleanups.

## Skill Integration & Commands

* **Default diagnosis (Phase 0)**: Run the concurrent top-down 5 GiB accounting, coverage-validated snapshot deltas, and safe quick-win report before drilling down. Follow `../disk-magician/SKILL.md` for the full forensic procedure. Residual is not backup size or reclaimable without evidence.
  ```bash
  disk-magician audit
  ```
* **Safe cleanup preview (Phase 1)**: Preview cache and temp cleanup through the repository gates:
  ```bash
  ./disk_magician.sh clean
  ```
* **Destructive cleanup (Phase 2)**: Interactively clear Docker VM disk images, Colima VMs, and old agent session folders:
  ```bash
  ./disk_magician.sh clean-all
  ```
* **Worktree Hygiene Sweep (deep pass)**: For a dedicated triage-and-delete pass across all monitored project roots (not just the current repo), run `scripts/worktree_hygiene.sh` instead of `clean`. Dry-run by default; apply mode requires both `--execute` and `WORKTREE_HYGIENE_APPROVED=1`:
  ```bash
  ./scripts/worktree_hygiene.sh
  ```

## Safety Constraints & Guardrails
- **Mtime Caution:** Worktrees and agent sessions with modification time < 14 days require explicit `WORKTREE APPROVED` confirmation from the user before deletion.
- **Never-delete list:** Do not delete `~/.codex/sessions`, `~/.codex/sessions_archive/`, `~/.codex/state*.sqlite`, `~/.codex/log`, or `~/.claude/projects` directly. Always run cleanups through `disk_magician.sh` to ensure safety filters are respected.
