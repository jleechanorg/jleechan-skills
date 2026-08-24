---
description: "/fe — alias for /factory-evolve; analyzes cold-review vs in-pipeline reviewer gaps, opens PRs end-to-end, drives each through /green, merges with explicit MERGE APPROVED"
type: skill
execution_mode: immediate
aliases: [factory-evolve]
---

# /fe [--flags] (alias for /factory-evolve)

Analyzes cold-review vs in-pipeline reviewer gaps, opens PRs end-to-end, drives each through `/green`, and merges with explicit MERGE APPROVED.

Read `~/.claude/skills/factory-evolve/SKILL.md` and execute the full workflow with the provided flags. Single writer for the workflow is `~/.claude/commands/factory-evolve.md`; this file is a thin alias so the multi-phase orchestration (history search → subagent fanout → G1+G2 audit → proposals doc → open PRs → /green → merge) is identical for both entry points.

**Usage**:

```
/fe                                  # scan last 7 days, open + drive PRs to /green + merge
/fe --days 14                        # widen lookback window
/fe --pr 26                          # audit one specific PR (cold review vs factory wiring)
/fe --taxonomy                       # structural G1+G2 audit only (no history, no PRs)
/fe --no-pr                          # write proposals doc only; don't open PRs
```

**History search MUST use `/history`** (per `~/.claude/CLAUDE.md`
"History search" rule). Never hand-coded `rg` — the rg pattern misses
`nohup`/`tee`/multiline invocations.

**Merge is operator-gated.** "MERGE APPROVED" is the only valid merge
trigger; do not auto-merge.

Equivalent to: `/factory-evolve $ARGUMENTS`
