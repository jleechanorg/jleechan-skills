---
description: Start, status, or finish a soak — a timed stability test where the clock only counts if the box stays up
type: workflow
execution_mode: deferred
scope: user
---
# /soak — manage a timed stability test

A **soak** runs a configuration for a target window. The clock only counts uptime. A crash IS data — record elapsed time, do not reset.

## Subcommands

- `soak start <name> --target <hours> --config "<description>"` — begin a soak
- `soak status [name]` — show current state (default: all active soaks)
- `soak list` — list all soaks (active + completed)
- `soak watch` — check all active soaks; mark pass/fail; update beads
- `soak close <name> --reason "<why>"` — manually close a soak

## Read first

- `~/.claude/skills/soak.md` — full protocol, target-time rules, anti-patterns
- `br list --status open` — confirm the linked bead exists

## Output requirements

A soak-status report covers:
1. **Name + config** — what's being tested
2. **Elapsed / target** — exact clock with hours
3. **Bead id** — the tracked record
4. **Crash detection** — uptime vs elapsed, pstore fingerprint, AER count
5. **Verdict** — `IN PROGRESS` / `PASSED` / `FAILED (crash at Xh Ym)` / `STALE (not updated in >24h)`

Do not declare a soak `PASSED` until elapsed > `longest_known_crash_interval` for the same config.

## Input

$ARGUMENTS
