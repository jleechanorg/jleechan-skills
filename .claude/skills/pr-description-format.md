---
name: pr-description-format
description: Required PR description sections — Background, Goals, Tenets, High-level, Testing, Low-level details
type: policy
---

# PR Description Format

Every PR description must include the following sections in order:

## Background

What context led to this change? What problem or opportunity is being addressed? Include relevant links, tickets, or prior decisions.

## Goals

What outcomes should this PR achieve? State them as concrete, verifiable objectives.

## Tenets

Guiding principles that constrained design decisions (e.g., "prefer real tests over mocks", "no breaking API changes", "minimize scope").

## High-level description of changes

Summarize what was changed and how it accomplishes the goals. Focus on the "why" behind architectural choices, not just the "what".

## Governing design doc and bead (prod / CI / ZFC)

Before filing or finalizing a PR, add a short block (see repo `.github/pull_request_template.md`):

- **Design doc:** Full `https://github.com/$GITHUB_REPOSITORY/blob/main/roadmap/...` (or `docs/design/...`) URL, or `N/A` with justification for true no-op doc-only changes.
- **Bead:** `br` issue ID (e.g. `rev-xxxxx`) or `N/A`.
- **ZFC / level-up:** If the branch touches `world_logic.py`, `rewards_engine.py`, level-up harness, or `design-doc-gate.yml`, cite the canonical [zfc-level-up-model-computes-2026-04-19.md](https://github.com/$GITHUB_REPOSITORY/blob/main/roadmap/zfc-level-up-model-computes-2026-04-19.md) and [zfc-pr-task-specs-2026-04-22.md](https://github.com/$GITHUB_REPOSITORY/blob/main/roadmap/zfc-pr-task-specs-2026-04-22.md).

CI enforces **code** invariants in `design-doc-gate.yml`; it does **not** fail PRs missing these links—this section is process enforcement.

## Scope reconciliation

Before creating, updating, or marking a PR ready, reconcile the stated PR scope
against the actual branch contents:

1. Run `git diff --stat origin/main...HEAD` (or the PR's actual base branch).
2. Run `git log --oneline origin/main..HEAD` (or the PR's actual base branch).
3. Classify each changed file as one of: implementation, test, CI/gate,
   evidence, docs, beads, or unrelated.
4. If the title or goals say "gate", "test", "docs", or another narrow scope
   but implementation files changed, stop and either reframe the title/body,
   split the PR, or explicitly justify the implementation changes.
5. If any changed file is unrelated to the stated goals, drop it or split it
   before pushing.
6. If `.beads/` changes are present, describe whether they are a new tracker,
   issue update, or migration/repair; never summarize bead deletions as cleanup.

## Testing

How was this tested? Include:
- Unit tests added/modified
- Integration or E2E tests run
- Manual verification steps performed
- Any CI results or evidence bundles

## Low-level details (up to 20 files)

For each changed file (pick top 20 most important if more than 20):
- **File path**: Justification for changing this file, what changed, why it was changed this way.
