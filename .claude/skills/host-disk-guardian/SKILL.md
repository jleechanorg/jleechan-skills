---
name: host-disk-guardian
description: Route host disk diagnosis, status, cleanup decisions, and scheduler maintenance to Disk Magician's current owner instructions. This skill does not authorize cleanup or install host automation.
type: skill
scope: repo
owner: disk_magician
version: 1.0.0
triggers:
  - "host disk low"
  - "check host free space"
  - "review host disk cleanup candidates"
allowed-tools:
  - Bash
  - Read
context:
  - "Disk Magician is the operational owner for measurements, status, cleanup, and scheduling. Follow ~/.claude/skills/disk-root-cause/SKILL.md and ~/projects_other/disk_magician/CLAUDE.md; use the CLI named there."
  - "Scripts are implementation helpers, not separate operator entry points. This skill does not authorize direct cleanup or launchd installation."
---

# /host-disk-guardian — Disk Magician routing pointer

## Current owner

For disk measurements, status, cleanup decisions, and scheduled maintenance,
follow `~/.claude/skills/disk-root-cause/SKILL.md` and
`~/projects_other/disk_magician/CLAUDE.md`.
Use the current CLI entry point named there; Disk Magician scripts are internal
helpers, not additional operator interfaces.

## Legacy helper status

This source tree contains the legacy helper at
`.claude/skills/host-disk-guardian/scripts/host-disk-guardian.sh`; it can delete
files on its default critical path. Do not invoke it directly from this skill.
Use the owner CLI and its current cleanup safety gates instead.

The old launchd template referenced by earlier instructions is absent from this
package. This skill provides no install, unload, removal, threshold, or cleanup
procedure. Do not infer authority to clean from a disk threshold or candidate
list.
