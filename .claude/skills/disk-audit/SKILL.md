---
name: disk-audit
description: Use when checking local disk capacity, investigating disk growth, or reviewing safe cleanup candidates.
---

# Disk audit compatibility entrypoint

Read and follow `../disk-root-cause/SKILL.md` in full before taking action.

Run the `<10s` zero-`du` triage before any full audit walk: `df -h`, `diskm check-launchd-fleet`, `diskm reclaim-ledger --read-existing`, and `diskm history growth-top10 --days 7`. Only launch the full `disk-magician audit` walk when the precomputed ledger or snapshots are missing or stale (>48h), or when residual unaccounted space genuinely needs a fresh top-down scan.

Never delete anything without explicit user approval.
