# Archived Commands

This directory holds commands moved out of the active `.claude/commands/` surface during the 2026-08-23 consolidation pass. They are **reference-only, lower priority** — not deleted, since git history alone doesn't make them discoverable to someone browsing the repo.

## Why these were archived

Each file here had **both**:
1. **Zero measured invocations** across the full mined history of Hermes SQLite, Claude Code project logs, and Codex SQLite (see `~/.claude/skills/command-research/SKILL.md` for the scanner and methodology), and
2. **Zero references** from any command that remains active in `.claude/commands/`, computed via fixed-point dependency closure (a command referencing an archive candidate pulls it back to active; repeat until no more changes).

This was deliberately **not** a top-N-by-usage cutoff. A naive "keep only the top 20-30 most-invoked commands" approach would have archived commands with real, verified nonzero usage that simply have low raw counts because they're invoked once per mission rather than repeatedly per PR cycle (e.g. orchestration primitives like `/swarm`, `/sidekick`, `/parallel` — all of which stayed active). It also would have missed near-100%-agentic automation rails like `/execute`, `/copilot`, `/fixpr` that don't show up in a casual glance at "commands humans type."

## What's still open

158 commands were found to have some measured usage but sit outside the empirical top tier. Those were **left active**, not archived here — deciding a further cutoff threshold for that set is a deliberate judgment call, not a mechanical one, and hasn't been made yet.

## Restoring a command

If you need one of these back on the active surface:

```bash
git mv archive/commands/<name>.md .claude/commands/<name>.md
```

Then re-check for any references that assumed it was archived.
