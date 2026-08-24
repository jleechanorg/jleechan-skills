---
description: /disk_magician - Run disk diagnostics, audit space, identify regressions, and perform safe cleanups using disk_magician
type: utility
execution_mode: immediate
---
# /disk_magician - Disk Magician Utility

**Usage**: `/disk_magician <command> [options]`

## Purpose

Analyze disk usage, scan for blind spots, and run safe cleanups using the `disk-magician` tool.

## Skill Reference

Full integration guide and guidelines:
- `~/.claude/skills/disk_magician/SKILL.md`

## Quick Commands:
- **Audit**: `disk-magician audit`
- **Discover**: `disk-magician discover`
- **Clean (Safe)**: `disk-magician clean`
- **Clean All (Aggressive)**: `disk-magician clean-all`
- **History**: `disk-magician history`
- **Snapshot**: `disk-magician snapshot`

## Safety Constraints & Guardrails
- **Mtime Caution:** Worktrees and agent sessions with modification time < 14 days require explicit `WORKTREE APPROVED` confirmation from the user before deletion.
- **Never-delete list:** Do not delete `~/.codex/sessions`, `~/.codex/sessions_archive/`, `~/.codex/state*.sqlite`, `~/.codex/log`, or `~/.claude/projects` directly.
- **Dry-run First:** Always run with `--dry-run` or preview the action before running destructive cleanups.

## Execution

When invoked with `$ARGUMENTS`, read `~/.claude/skills/disk_magician/SKILL.md` and execute the appropriate `disk-magician` commands.
