---
name: disk-audit
description: Use for a quick local disk-capacity check. Reclaimable-amount estimates and cleanup-target decisions require disk-root-cause leaf itemization.
---

# Disk audit compatibility entrypoint

Choose the procedure by what was asked:

- **Root-cause investigation or choosing/justifying a cleanup target** ("why is the disk full", "what grew", "which of these should I delete and why") — read `../disk-root-cause/SKILL.md` in full and follow its audit prerequisites. Do not make an independent full-audit decision from snapshot freshness alone.
- **Quick capacity check** ("how much space is left") — run the `<10s` zero-`du` triage: `df -h`, `diskm check-launchd-fleet`, `diskm reclaim-ledger --read-existing`, and `diskm history growth-top10 --days 7`.
- **Reclaimable-amount estimate** ("how much can I free") — do not infer an amount from top-level sizes, history buckets, or a quick triage. Follow `disk-root-cause` and itemize each directory at or above 100 MiB to files and smaller directories; report incomplete coverage and no definitive reclaim estimate when traversal is unfinished.

For a quick capacity check, escalate to the full audit when precomputed data is missing, stale according to its owner, or does not establish the requested answer. Never present an aggregate parent total as itemized attribution.

Never delete anything without explicit user approval.
