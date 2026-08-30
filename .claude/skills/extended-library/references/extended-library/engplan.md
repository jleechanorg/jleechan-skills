---
description: /engplan - Generic engineering plan with stage-PR file-exclusive ownership, TDD, /4layer, beads, and 100-300 LOC commit caps
type: planning
execution_mode: immediate
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE

**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

**PRIMARY REFERENCE**: See `.claude/skills/engplan.md` for the complete protocol, 14-section template, 7 core rules, and 6-phase execution workflow.

## 🚨 EXECUTION WORKFLOW (summary)

1. **Phase 0 — Discovery**: identify scope keyword; list `~/roadmap/` and `<repo>/roadmap/` docs in scope; list open PRs in scope; list active beads; check MEMORY.md.
2. **Phase 1 — File ownership audit**: per open PR, list files; build conflict matrix; identify hot files.
3. **Phase 2 — Stage decomposition**: 2-5 stage-PRs; assign each file to exactly one stage-PR; verify exclusivity; choose sequencing.
4. **Phase 3 — Per-PR commit plan**: TDD discipline at commit level (test commit FIRST → code commit NEXT → optional refactor → evidence). Each commit 100-300 LOC delta. PRs of 3-8 commits.
5. **Phase 4 — Doc generation**: write `~/roadmap/nextsteps-<YYYY-MM-DD>-<scope>-stage-pr-plan.md` with 14 mandatory sections.
6. **Phase 5 — Sync**: copy to `<repo>/roadmap/` and any active worktrees; `git add` so CI/CR see it.
7. **Phase 6 — Memory write**: add entry to `~/.claude/projects/<project>/memory/`; update `MEMORY.md` index.

## 📋 ARGUMENTS

`/engplan <scope>` — scope keyword (e.g., `auth`, `level-up`, `checkout`).
If omitted, infer from current branch / recent commits / open PR titles.

## 📌 CORE RULES (full detail in skill)

1. File-exclusive ownership (no two open PRs touch same file)
2. Separate commits for tests and code — test commit lands BEFORE code commit
3. Per-commit LOC cap: 100-300 (generated files exempt; pure deletion exempt from minimum)
4. PRs of 3-8 commits
5. /4layer test coverage per stage-PR (Layer 1-4 by what changes)
6. Beads tracking — every PR has ≥1 governing bead, every commit references one
7. Memory linkage — read existing memory; write new entry per plan

## See Also

- `.claude/skills/engplan.md` — full skill body
- `.claude/skills/zfc-leveling-roadmap/SKILL.md` — domain-specific instance
- `.claude/skills/deletion-milestone.md` — net-LOC discipline
- `.claude/commands/4layer.md` — minimal-repro ladder
- `.claude/commands/tdd.md` — red/green/refactor
- `~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md` — canonical example
