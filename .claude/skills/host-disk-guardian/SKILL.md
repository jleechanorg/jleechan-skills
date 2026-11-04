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
  - "Disk Magician is the operational owner. Route by request: quick capacity or plain reclaim (including 'check host free space') -> the zero-du triage in ~/.claude/skills/disk-audit/SKILL.md; root-cause investigation, cleanup decisions, and scheduled maintenance -> ~/.claude/skills/disk-root-cause/SKILL.md and, when a Disk Magician checkout is available, its CLAUDE.md (locate the CLI with `command -v diskm`). Use the CLI named there."
  - "Scripts are implementation helpers, not separate operator entry points. This skill does not authorize direct cleanup or launchd installation."
---

# /host-disk-guardian — Disk Magician routing pointer

## Current owner

Route by what was asked, so one request never selects two procedures:

- **Quick capacity or a reclaimable amount** ("check host free space", "how much can I
free") -> the zero-`du` triage in `~/.claude/skills/disk-audit/SKILL.md`. Do not start a
full audit walk for these. If the precomputed ledger or snapshots are missing or stale, escalate to the full audit rather than trusting the quick numbers.
- **Root-cause investigation, choosing a cleanup target, and scheduled maintenance**
("why is the host full", "what grew", "what should I clean up", "which of these should I
delete") -> follow
`~/.claude/skills/disk-root-cause/SKILL.md` and, when a Disk Magician checkout is available, its `CLAUDE.md`
(locate the CLI with `command -v diskm`; if it is absent, report the missing prerequisite).

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
