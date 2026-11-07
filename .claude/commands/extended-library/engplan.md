---
description: /engplan - Generic engineering plan with stage-PR file-exclusive ownership (1 unified PR or 2-5 coarse vertical stage-PRs max), TDD, /4layer, and beads
type: planning
execution_mode: immediate
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE

**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

**PRIMARY REFERENCE**: See `.claude/skills/engplan/SKILL.md` in the repository, or `${CLAUDE_HOME:-$HOME/.claude}/skills/engplan/SKILL.md` after installation, for the complete protocol, 14-section template, 7 core rules, and 6-phase execution workflow.

## 🚨 EXECUTION WORKFLOW (summary)

1. **Phase 0 — Discovery**: identify scope keyword; list `~/roadmap/` and `<repo>/roadmap/` docs in scope; list open PRs in scope; list active beads; check MEMORY.md.
2. **Phase 1 — File ownership audit**: per open PR, list files; build conflict matrix; identify hot files.
3. **Phase 2 — Stage decomposition**: Group target work into **1 unified PR by default, or at most 2–5 coarse vertical stage-PRs; never exceed 5 PRs for one feature** (see `pr-quantity-control`); assign each file and its tests to one stage-PR; verify exclusivity; choose sequencing.
4. **Phase 3 — Per-PR commit plan**: TDD discipline (RED check before GREEN implementation → optional refactor → evidence). Choose coherent commit/PR boundaries from dependencies and risk rather than arbitrary LOC targets; keep tests inside the same PR as the code they verify.
5. **Phase 4 — Doc generation**: write `~/roadmap/nextsteps-<YYYY-MM-DD>-<scope>-stage-pr-plan.md` with 14 mandatory sections.
6. **Phase 5 — Sync**: copy to `<repo>/roadmap/` and any active worktrees; `git add` so CI/CR see it.
7. **Phase 6 — Memory write**: add entry to `~/.claude/projects/<project>/memory/`; update `MEMORY.md` index.

## 📋 ARGUMENTS

`/engplan <scope>` — scope keyword (e.g., `auth`, `level-up`, `checkout`).
If omitted, infer from current branch / recent commits / open PR titles.

## 📌 CORE RULES (full detail in skill)

1. File-exclusive ownership (no two open PRs touch same file)
2. Preserve RED → GREEN test/fix verification sequence; keep unit/integration tests in the same stage-PR as the production code they verify (no separate test-only stage-PRs)
3. Coherent commit boundaries (no artificial 100–300 LOC commit caps or padding)
4. Hard stage-PR cap: group into 1 cohesive PR by default, or at most 2–5 coarse vertical subsystem PRs (see `pr-quantity-control`; never exceed 5 PRs for one feature)
5. /4layer test coverage per stage-PR (Layer 1-4 by what changes)
6. Beads tracking — every PR has ≥1 governing bead, every commit references one
7. Memory linkage — read existing memory; write new entry per plan

## See Also

- `.claude/skills/engplan/SKILL.md` — full skill body
- `${CLAUDE_HOME:-$HOME/.claude}/skills/pr-quantity-control/SKILL.md` — hard PR count and split ceilings
- a product plugin's `zfc-leveling-roadmap` skill, if installed — domain-specific instance
- `.claude/skills/deletion-milestone/SKILL.md` — net-LOC discipline
- `.claude/commands/extended-library/4layer.md` — minimal-repro ladder
- `.claude/commands/tdd.md` — red/green/refactor
- `~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md` — canonical example
