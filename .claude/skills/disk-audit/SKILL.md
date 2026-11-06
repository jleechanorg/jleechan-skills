---
name: disk-audit
description: Use when checking local disk capacity or estimating a reclaimable amount. Choosing or justifying a cleanup target is a root-cause question — route it to disk-root-cause.
---

# Disk audit compatibility entrypoint

Choose the procedure by what was asked:

- **Root-cause investigation, or choosing/justifying a cleanup target** ("why is the disk full", "what grew", "which of these should I delete and why") — read and follow `../disk-root-cause/SKILL.md` in full before taking action. It opens with the full `disk-magician audit`, which is what an investigation needs.
- **Quick capacity check, or a reclaimable-amount estimate** ("how much space is left", "how much can I free") — skip the full `du` walk and run the `<10s` zero-`du` triage: `df -h`, `diskm check-launchd-fleet`, `diskm reclaim-ledger --read-existing`, and `diskm history growth-top10 --days 7`.

Only run the full audit for a quick check when the precomputed ledger or snapshots are missing or stale — check the freshness requirement the tool itself reports rather than assuming a fixed window, since different ledgers have different windows — or when residual unaccounted space genuinely needs a top-down scan.

Never delete anything without explicit user approval.
