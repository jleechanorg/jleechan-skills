---
description: /factory-evolve — analyze conversation + git history to find where cold reviews (codex, Bugbot, CodeRabbit, /reviewdeep) caught issues the factory reviewer nodes missed. Fans out subagents, opens PRs end-to-end, drives each through /green, merges with explicit MERGE APPROVED. Proposes targeted .dot and runner improvements.
type: llm-orchestration
execution_mode: immediate
aliases: [fe]
---

# /factory-evolve

Read `~/.claude/skills/factory-evolve/SKILL.md` and execute the full workflow with any flags passed.

Flags:
- `--days N` — lookback window (default 7)
- `--pr N` — audit one specific PR (cold review vs factory wiring)
- `--taxonomy` — structural G1+G2 audit only (no history search, no PRs)
- `--no-pr` — write proposals doc only; don't open PRs

After completing, always end with: top-3 proposals, gap category breakdown, PR/merge state, and a one-line "wiring health" verdict (e.g. "5 of 5 code-producing paths have a reviewer node; 3 PRs opened, 2 merged, 1 awaiting MERGE APPROVED").

**History search MUST use `/history`** (per `~/.claude/CLAUDE.md` "History search" rule). Never hand-coded `rg` — the rg pattern misses `nohup`/`tee`/multiline invocations.

**Merge is operator-gated.** "MERGE APPROVED" is the only valid merge trigger; do not auto-merge.
