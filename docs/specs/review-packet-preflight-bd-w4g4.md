# Review-packet and merge-tree preflight validator (`bd-w4g4`)

## Outcome
Prevent wasted cold reviewer turns (`/advice`, `/cs`, `/er`, `static-review`) caused by base-branch merge conflicts, stale `HEAD` SHA pins, or corrupted non-git exported review packets.

## Non-goals
Do not automatically rebase/merge branches inside the validator, alter reviewer quorum or counting rules, or introduce third-party Python dependencies.

## Acceptance
- `scripts/verify_review_packet.py --repo <git-dir> --base <base> --head <head> [--expected-head <40-char-sha>]` runs `git merge-tree --write-tree` and full-SHA verification, exiting non-zero with `CONFLICT_WITH_BASE` or `HEAD_DRIFT` on conflict or mismatch.
- `scripts/verify_review_packet.py --packet-dir <export-dir>` verifies `.git` is absent, `base.diff` exists, and every file listed in `manifest.json`, `SHA256SUMS`, or `SHA256SUMS.txt` matches its SHA-256 hash on disk without symlink or path traversal escapes.
- `.claude/skills/static-review/SKILL.md`, `.claude/skills/pr-lifecycle/SKILL.md`, and `.claude/skills/pr-lifecycle/six-stage.md` require clean base mergeability and `verify_review_packet.py` preflight before spawning cold `/cs`, `/er`, or `/advice` seats.

## User stories
No user-facing product UI changes; an operator or PR driver receives immediate preflight failure codes (`CONFLICT_WITH_BASE`, `HEAD_DRIFT`, `HASH_MISMATCH`) before spending cold reviewer rounds on conflicted branches or broken packet exports.

## Proof plan
Unit tests in `tests/test_verify_review_packet.py` covering clean diverged merges, conflicts, short/stale `HEAD` SHAs, missing/invalid refs, `.git` metadata rejection, `base.diff` presence, `manifest.json`/`SHA256SUMS` digest verification, and symlink/traversal rejection, plus repository portability and contract test suites.

## Mock
Not applicable: no rendered UI or visual interface changes.

## Risk
Low deterministic tooling and review-preflight guidance change; callers on fresh hosts without the script installed retain an explicit `git merge-tree --write-tree` and SHA-256 fallback in `static-review`.
