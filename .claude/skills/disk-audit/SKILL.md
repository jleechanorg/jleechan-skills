---
name: disk-audit
description: Use when checking local disk capacity, investigating disk growth, or reviewing safe cleanup candidates.
---

# Disk audit compatibility entrypoint

Choose the procedure by what was asked:

- **Root-cause investigation** ("why is the disk full", "what grew") — read and follow `../disk-root-cause/SKILL.md` in full before taking action. It opens with the full `disk-magician audit`, which is what an investigation needs.
- **Quick capacity check** ("how much space is left", "what can I reclaim") — skip the full `du` walk and run the `<10s` zero-`du` triage: `df -h`, `diskm check-launchd-fleet`, `diskm reclaim-ledger --read-existing`, and `diskm history growth-top10 --days 7`.

Only run the full audit for a quick check when the precomputed ledger or snapshots are missing or stale (>36h, the same freshness window `growth-top10` requires), or residual unaccounted space genuinely needs a top-down scan.

Never delete anything without explicit user approval.
