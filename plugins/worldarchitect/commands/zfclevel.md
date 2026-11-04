---
description: ZFC leveling alignment check — verify PR/work conforms to ZFC leveling principles, roadmap, and doc sync
type: quality
execution_mode: immediate
---

# /zfclevel

## Purpose

Verify that the current work (branch, PR, or in-progress changes) is aligned with:
1. ZFC leveling principles and architecture
2. The canonical ZFC leveling roadmap docs
3. `~/roadmap` and `roadmap/` doc sync for ZFC leveling topics

This is a **gate/check command** — run it before opening a PR, before merging, or when you are unsure whether work is ZFC-aligned.

---

## Step 1 — Load Required Skills and Roadmap Context

Load and follow this skill **first**:
- `.claude/skills/zfc-leveling-roadmap/SKILL.md`

Canonical roadmap files (read in order):
1. `~/roadmap/zfc-level-up-model-computes-2026-04-19.md`
2. `~/roadmap/zfc-pr-task-specs-2026-04-22.md`
3. `roadmap/zfc-level-up-model-computes-2026-04-19.md` (repo-local copy — compare with ~/roadmap copy)
4. `roadmap/zfc-pr-task-specs-2026-04-22.md` (repo-local copy)
5. `~/roadmap/2026-04-21-level-up-zfc-loop-postmortem.md`
6. Any other `roadmap/*zfc*` or `roadmap/*level-up*` files relevant to the current PR or work item

If `~/roadmap` and `roadmap/` copies of the same file differ, that is a **doc sync violation** — record it explicitly and prefer the `~/roadmap` version as the canonical source.

---

## Step 2 — ZFC Level-Up Principles Checklist

Verify ALL of the following for the current work:

### Core ZFC Tenets
- [ ] **Model decides, server executes** — no keyword routing or heuristic classification in application code
- [ ] Level-up decisions are made by the model, not inferred by backend threshold crossings
- [ ] XP state expressed as `previous_turn_exp` + `current_turn_exp` pair (not computed delta)
- [ ] No legacy level-up inference paths that bypass the model-owned signal
- [ ] `xp_gained`, `progress_percent`, and level-up trigger are formatted/validated server-side from explicit model output, not inferred independently

### File Boundaries (from zfc-leveling-roadmap skill)
- [ ] No modifications to files outside the PR's authorized scope per the file-responsibility table
- [ ] No changes to frozen public contracts without explicit roadmap authorization
- [ ] Level-up/rewards/XP ownership follows the centralized ownership table in the roadmap

### Pre-flight Checks
- [ ] Grep gates from the roadmap design doc pass (no ZFC violations in changed files)
- [ ] Tests required by the roadmap design are present and passing
- [ ] No deletion of legacy code that the roadmap marks as not-yet-deleted

---

## Step 3 — Doc Sync Check

Compare `~/roadmap/` and `roadmap/` for all ZFC-leveling-related files:

```
~/roadmap/zfc-level-up-model-computes-2026-04-19.md
roadmap/zfc-level-up-model-computes-2026-04-19.md

~/roadmap/zfc-pr-task-specs-2026-04-22.md
roadmap/zfc-pr-task-specs-2026-04-22.md

~/roadmap/2026-04-21-level-up-zfc-loop-postmortem.md
roadmap/2026-04-21-level-up-zfc-loop-postmortem.md
```

For any file pair where content differs:
1. Record the specific diff (which section/line changed)
2. Prefer `~/roadmap` as canonical
3. Update the `roadmap/` copy to match `~/roadmap` if the `~/roadmap` version is newer/more accurate
4. If unsure which is canonical, flag it for human review

---

## Step 4 — PR Alignment Check

If running against an open PR:

1. Check PR title and description for ZFC alignment signals
2. Verify the PR is targeting the correct merge lane (per roadmap PR sequencing)
3. Confirm no merge conflicts with `origin/main`
4. Run `./run_tests.sh` and confirm all tests pass
5. Run `./run_lint.sh` and confirm lint is clean
6. If the PR is marked `zfc_level`:
   - Confirm `/es`, `/er`, and `/advice` passed at the current head; CodeRabbit/Bugbot feedback is advisory
   - Confirm it has evidence attached (video or E2E logs as required by the evidence policy)
7. Flag any PR that has ZFC implications but is NOT labeled `zfc_level` — it needs the label

---

## Step 5 — Report

Present findings in this format:

```
## /zfclevel Report — [branch/PR name]

### ZFC Principles
✅/❌ [Principle name] — [evidence or violation detail]

### Doc Sync
✅/❌ [File pair] — [status: in sync / diverged / missing in X]

### PR Readiness
✅/❌ [Check name] — [detail]

### Blockers (must fix before merge/PR)
- [list of blocking issues]

### Non-blocking notes
- [advisory observations]
```

If all checks pass, end with: `✅ ZFC alignment verified — ready to proceed.`

If blockers exist, end with: `❌ ZFC gate failed — fix blockers before proceeding.`
