# Merge resolution: prw-merge-pr697-20261105 (PR #697) — 2026-11-05
Merged `origin/main` (`1ff232d9fd08ac9fd8a60a1114fb78deda90a3f8`) into PR head `bc3fe1387058d3388ba088f9e6a043b603d55160`.

## `.claude/skills/evidence-standards/SKILL.md`
- Bundle and UI/media guidance: **Kept current main** — PR #696 had already compacted these rules into the canonical bundle and UI/media sections. Dropped the duplicate older examples and expanded visual-policy block from the PR branch; the current paragraph retains inline-media, frame inspection, independent review, and access requirements.

## `INSTALL.md`
- Profile table: **Kept current main** — #696 removed the measured-count column, so the branch's older scratch-install totals were stale and were not restored.

## `README.md`
- Profile table and wish catalog: **Combined** — kept the current count-free profile table from main and restored PR #697's `/wish` catalog row and detailed wish entry, which are unique feature documentation.

## Tests
- Before: `git merge-tree --write-tree origin/main HEAD` → reported conflicts in the three files above; no checks ran before resolution.
- After: `python3 -m unittest tests.test_installer` → PASS, 86 tests in 82.508s, 3 skipped; `git diff --check` and unresolved-marker scan → PASS.
