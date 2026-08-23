---
description: Investigate the latest Jeff-Ubuntu crash (silent-stop, kernel panic, hard reset) using the canonical triage recipe
type: workflow
execution_mode: deferred
scope: user
---
# /crash — Jeff-Ubuntu crash investigation

Run the canonical crash investigation recipe end-to-end. Use this when:
- The box just rebooted unexpectedly
- The user says "crashed again" / "we crashed"
- A boot entry in `journalctl --list-boots` shows a much shorter uptime than the previous one
- pstore has new dumps that haven't been read yet

## Read first

- `~/.claude/skills/crash.md` — the full triage recipe
- `~/.claude/projects/-home-$USER-projects-other-user-scope/memory/MEMORY.md` — the live incident cluster
- `br list --status open` — confirm the active bead is `bd-12v` (Jeff-Ubuntu workload trigger)

## Required output

A short report covering:
1. **When** (timestamps, uptime) — which boot crashed and how long it ran
2. **What** (panic signature) — pstore dmesg summary, nvidia/MCE/Oops names
3. **Why it might have happened** (top 2-3 hypotheses ranked by current evidence)
4. **Next action** (concrete step the user should take — kernel rollback, disable service, memtest, etc.)

If you cannot read pstore (root-only), surface that as a `! sudo cat ...` block for the user to run — do not silently substitute heuristics.

## Input

$ARGUMENTS
