# Plan: skill-distribution consolidation (reconciliation-first, staged)

Spec: `docs/superpowers/specs/2026-10-13-skill-distribution-consolidation-design.md`
Run `python3 -m unittest discover -s tests -p "test_*.py"` after every stage.

## S1 (this PR) - make the divergence visible, non-destructively
1. **Add the report tool** `scripts/report_skill_inventory_divergence.py`: **whole-package** comparison (every file per skill dir, build junk excluded) with `--write-ledger`.
   Verify: `python3 scripts/report_skill_inventory_divergence.py` → `29 / 7 missing / 2 identical / 20 differing`.
2. **Add the disposition ledger** `docs/superpowers/skill-inventory-dispositions.json` (evidence-derived, 29 rows, unresolved) and the fail-closed contract test `tests/test_skill_inventory_dispositions_contract.py`: every portable skill needs a disposition; `portable/**` may only be deleted once every row is resolved.
   RED/GREEN: passes now (one test skipped pre-collapse); prove the deletion gate by temporarily hiding `portable/manifest.json` with unresolved rows and confirming a failure.
3. **Correct the spec/plan** to the verified premise (done in this commit) and record the target architecture decision.
4. **Decision record** in `SHARED-SKILLS.md`: target = one bundle (`shared-skills.json`), one verifier, one marketplace manifest, one live tree; migration gated on S2 reconciliation and S4 consumer validation. No "retired" claims until the gating stages land.
5. **No deletions, no symlinks** in S1. Verify: `git diff --stat origin/main` shows only docs + 2 new non-production files.

## S2 - per-skill reconciliation (follow-up PR)
1. For each of the 7 portable-only skills: decide whether it should enter `.claude/skills/**` (with provenance) or be dropped; record the decision.
2. For each of the 19 divergent skills: diff `portable/skills/<n>/SKILL.md` vs `.claude/skills/<n>/SKILL.md`, choose the surviving body, and record why (the `.claude` copy is usually newer; confirm per file).
3. Add reconciled skills to `shared-skills.json` with sha256.
   TDD: each reconciliation that changes a skill body gets its contract test updated first (RED), then the body change (GREEN).

## S3 - collapse bundle + verifier (follow-up PR, blocked on S2)
1. RED: add `tests/test_shared_manifest_verifier.py` for `scripts/verify_shared_skills.py`; expect FAIL (script absent).
2. Implement the verifier over `shared-skills.json`; delete `scripts/verify_portable_skills.py` and `portable/**` only when the test proves nothing is lost.
3. Migrate `tests/test_portable_install.py` and the `portable/skills` fixtures in `tests/test_cross_host_catalog.py`.

## S4 - marketplace single-source (follow-up PR, blocked on consumer validation)
1. Identify the consumer of `.agents/plugins/marketplace.json` and its required schema (github source vs local).
2. Single-source with a format mapping that preserves both schemas, or document the two-schema split with a consistency test on shared fields.

## S5 - retire the dead installer (conditional)
1. Precondition check: `grep -rn install-claude-commands.sh ~/Library/LaunchAgents launchd/ crontab -l 2>/dev/null`. If any live invocation exists, reduce to a wrapper instead of deleting.
2. Otherwise remove it and repoint README/INSTALL.md at `scripts/install_shared_catalog.py`.

## TDD Plan Check
| Task | Sequence | Notes |
|---|---|---|
| S1.1/S1.2 | tool + ledger + fail-closed test; negative check on the deletion gate | guard is the ledger, not frozen counts (reviewer-required) |
| S1.3/S1.4 | docs only | `TDD: N/A` - documentation; verification is `git diff --stat` scoping |
| S2 | per-skill test update (RED) -> body reconcile (GREEN) | each body change is behavior and gets its test first |
| S3 | verifier test (RED) -> implement -> delete portable (GREEN) | deletion guarded by the verifier test |
| S4 | consumer schema test (RED) -> mapping (GREEN) | blocked on identifying the consumer |
| S5 | precondition grep; `TDD: N/A` for file removal with a documented precondition | guard is the precondition check |
