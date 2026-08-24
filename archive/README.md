# Archived Commands

> **Two different archival mechanisms exist in this repo. This file documents only the first one.**
> `archive/commands/` (51 files, described below) and `.claude/commands/extended-library/` (211 files) were created at different times, by different criteria, with different consequences. They are not the same thing and neither supersedes the other. See [Second tier: `.claude/commands/extended-library/`](#second-tier-claudecommandsextended-library-2026-08-24) at the bottom.

This directory holds commands moved out of the active `.claude/commands/` surface during the 2026-08-23 consolidation pass. They are **reference-only, lower priority** — not deleted, since git history alone doesn't make them discoverable to someone browsing the repo.

## Why these were archived

Each file here had **both**:
1. **Zero measured invocations** across the full mined history of Hermes SQLite, Claude Code project logs, and Codex SQLite (see `~/.claude/skills/command-research/SKILL.md` for the scanner and methodology), and
2. **Zero references** from any command that remains active in `.claude/commands/`, computed via fixed-point dependency closure (a command referencing an archive candidate pulls it back to active; repeat until no more changes).

This was deliberately **not** a top-N-by-usage cutoff. A naive "keep only the top 20-30 most-invoked commands" approach would have archived commands with real, verified nonzero usage that simply have low raw counts because they're invoked once per mission rather than repeatedly per PR cycle (e.g. orchestration primitives like `/swarm`, `/sidekick`, `/parallel` — all of which stayed active). It also would have missed near-100%-agentic automation rails like `/execute`, `/copilot`, `/fixpr` that don't show up in a casual glance at "commands humans type."

## What's still open

158 commands were found to have some measured usage but sit outside the empirical top tier. Those were **left active**, not archived here — deciding a further cutoff threshold for that set is a deliberate judgment call, not a mechanical one.

**Resolved 2026-08-24**, but by a different mechanism and into a different directory — see the next section. Nothing was added to `archive/commands/` as a result.

## Restoring a command

If you need one of these back on the active surface:

```bash
git mv archive/commands/<name>.md .claude/commands/<name>.md
```

Then re-check for any references that assumed it was archived.

---

## Second tier: `.claude/commands/extended-library/` (2026-08-24)

A **separate, newer, unrelated** mechanism. It did not touch `archive/commands/` and did not use this directory's criterion.

| | `archive/commands/` (this dir) | `.claude/commands/extended-library/` |
|---|---|---|
| Created | 2026-08-23 (PR #358) | 2026-08-24 |
| Count | 51 | 211 |
| Criterion | zero measured invocations **AND** zero references from any active command (fixed-point dependency closure) | hard top-20-human ∪ top-20-agent cutoff (27) + 1 forced include (`/innov`) = 28 kept active; everything else moved |
| Explicitly **not** a usage cutoff? | Yes — closure-preserving by design | No — it **is** a usage cutoff, chosen over closure preservation |
| Still invocable? | **No.** Reference-only; must be `git mv`'d back to be used. | **Yes.** Invocable as `/extended-library:<name>` — a rename, not a retirement. |
| Restore | `git mv archive/commands/<n>.md .claude/commands/<n>.md` | Nothing to restore; use the namespaced name, or `git mv` back to drop the prefix |

The key asymmetry: files in **this** directory are inert. Files in `extended-library/` are live commands whose invocation name changed from `/<name>` to `/extended-library:<name>`.

The 2026-08-24 pass deliberately reversed an earlier 94-command dependency-closure recommendation made in the same session. Both versions, the reasoning, the disclosed trade-off, and the empirical verification that namespaced subdirectory commands really do stay invocable are recorded in [ARCHIVE-DECISION-2026-08-23.md](ARCHIVE-DECISION-2026-08-23.md). Directory-level detail and the full 28/211 lists: [extended-library-README.md](extended-library-README.md).
