# Merge resolution: PR #675 — 2026-11-04

Merged `origin/main` at `99db75e7f8d8feaee501062c6fa31e7ef57d49a9` into `fix/prw-blocker-driven-closure` at `8a7e10cab8b398172fd6c6bac48bffeacfaf6e55` by normal merge. Main's merged prose simplification is the resolution baseline; only this branch's classification and intake behavior is applied to it. No history rewrite or live installation.

## `.claude/skills/pr-lifecycle/SKILL.md`

- Hunk group 1 (compact eligibility versus classification): **Combined** — keep the branch's nine-class table and highest-risk/repository precedence; use main's shorter surrounding lifecycle prose.
- Hunk group 2 (direct route and advice applicability): **Combined** — retain one cold static source vote for positively qualified rows and two votes for ordinary/boundary/high-risk rows; keep main's concise integration and timeout mechanics. Replaced the incompatible generic size-only route, whose old threshold would override the approved class route.
- Hunk group 3 (count/timeout references): **Combined** — numeric admission remains in the table; supplementary-review timeout fallback remains main's version, with its reference to the table-selected route instead of the superseded under-50 default. No timeout or quorum was weakened.
- Hunk group 4 (opted-in stage routing): **Combined** — stages point to the single table, preserving main's stage title, label, readback and regression guidance. Do not duplicate line-count/Dot/provider routing.
- Hunk group 5 (visual approval): **Combined** — retain main's concise before/after findings, SHA binding and evidence-seat independence outside the table-qualified exception. Qualified one-vote UI rows may use their source reviewer for frame coverage explicitly; the visual stamp and actual frame inspection still apply.
- Hunk group 6 (proportional exceptions): **Combined** — retain main's narrow trivial/one-liner rules; compact-route heading points to table eligibility and preserves the PR-body specification/intermediate-ceremony exception, current checks, Stage 5 and repository overrides.
- Hunk group 7 (coding layers): **Combined** — keep main's shorter execution guidance; replace the duplicate class/layer table with the classification owner's pointer and the branch's unchanged specification/plan applicability.
- Hunk group 8 (draft source/visual gates): **Combined** — retain main's shortened integrity, media, deferred-proof and independence rules; select source votes and the qualifying UI visual seat through the table. Missing evidence still leaves readiness open.
- Hunk group 9 (ready closeout): **Combined** — main's concise delta/reuse/final-check prose selects table-required source coverage rather than restoring advice for every size-qualified change. Source approval and final readiness remain separate; merge authority remains unchanged.

## `.claude/skills/pr-workflow-manager/SKILL.md`

- Hunk group 1 (operational preflight): **Combined** — retain main's shortened entry point and visual/lifecycle pointers, add the table pointer, and condense the branch's measured base/head, artifact access, access-mode, actual-model/coverage, producer-gap and blocker-driven continuation checks into existing preflight. No second policy table or approval/provider ladder is introduced.

## Tests

- Before: `python3 -m unittest tests.test_coding_lifecycle_contract -q` → four tests, OK (0.027 seconds), at `8a7e10cab8b398172fd6c6bac48bffeacfaf6e55`.
- After: `python3 -m unittest tests.test_coding_lifecycle_contract -q` → four tests, OK (0.026 seconds), resolved candidate content before merge commit.
- After: `git diff --check` → PASS. Both conflicted files contain no conflict markers; structural checks resolve all lifecycle headings and backlinks.
- Semantic preservation: compact heading remains; specification section applies the seven-element placement rule only outside compact scope; compact section retains its waiver and repository precedence. Table retains nine classes, changed-boundary definition, separate source/readiness decisions, and independent merge authority. No runtime behavior is claimed.
