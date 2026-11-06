# Merge resolution: pr696-size-nature-20261104 (PR #696) — 2026-11-04

Merged origin/main at 67de744816af63732ab33f2f56851c27888034e into the existing PR #696 branch.

## `.claude/skills/advice/SKILL.md`

- Hunk group 1 (review quorum and reviewer tiers): **Kept current main** — retained the merged reviewer tier and identity-counting contract. Removed the stale reference to a local record-only exemption and pointed the section to the lifecycle-owned size-and-risk route.
- Hunk group 2 (verdict quorum): **Kept current main** — retained the generic two-vote default and qualified lifecycle-selected one-review routes; the new route controls only eligible Markdown instruction changes.

## `.claude/skills/pr-lifecycle/SKILL.md`

- Hunk group 1 (review obligations and advice applicability): **Combined** — retained the current risk table, compact route, reviewer deadline and Advice contract. Added one explicit Markdown instruction-only route that chooses one reviewer for low-risk changes up to 150 changed lines, two for larger low-risk changes, and two at every size for sensitive subjects. It records proof limited to the changed claims and excludes review policy from self-qualification.
- Hunk group 2 (older record-only subsection): **Dropped side** — the PR-side record-only rule counted passive Markdown records and required an outside vote plus /es, while the current main contract no longer recognizes that exemption and has newer reviewer tiers and claim-based proof. Lost: only the old standalone record-only subsection; its broad file-list heuristic and separate /es requirement. The new rule applies to instructional Markdown based on full diff size and risk, and preserves stricter independent approval rules.

## AGENTS.md

- No merge conflict. Updated the catalog-wide >50-line /cs and Ponytail rule to defer only when the canonical lifecycle affirmatively selects the Markdown instruction-only route. This review-policy PR is sensitive and is excluded from that route.

## Tests

- Before: `git diff --check` — not run on the PR-only pre-merge tree; the existing PR changed the review contract and had no code or executable test change.
- After: `git diff --check` — PASS after conflict resolution.
- After: `python3 scripts/verify_portable_skills.py portable` — PASS.
