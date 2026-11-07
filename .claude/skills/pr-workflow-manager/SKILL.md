---
name: pr-workflow-manager
description: "PR workflow entry point: discover canonical skills, verify source ownership, publish draft PRs, and drive applicable stages."
type: usage
scope: project
---

# PR Workflow Manager

## Terminal goal and entry contract

An unqualified `/prw` (`/pr-workflow`) defaults to driving the PR to **`FINAL_READY`** across all applicable gates under one continuous session goal, unless the user explicitly requests an earlier milestone. Intermediate checkpoints (opening draft, pushes, initial approval, undrafting, stage labels) are not task completion; merge authority remains separate. For the canonical completion contract and exit conditions, follow [pr-lifecycle](../pr-lifecycle/SKILL.md#terminal-goal-and-first-screen-contract).

## One operational contract

Before selecting a branch, stage, or gate, inspect the target repository's `AGENTS.md`, `CLAUDE.md`, and scoped instructions. Local repository instructions take precedence within their domain. Where local instructions are silent, apply the canonical [pr-lifecycle](../pr-lifecycle/SKILL.md) completion loop.

## Find the skills before inventing a workflow

1. Use an already-known local checkout of the official `jleechan-skills` repository, or resolve an installed skill's source. Verify its remote and commit; preserve local edits.
2. If no checkout exists, clone the official source to an unused development directory: `git clone https://github.com/jleechanorg/jleechan-skills.git <unused-directory>`.
3. Read `.claude/skills/pr-lifecycle/SKILL.md` from that checkout.
4. If Git access is unavailable, state the exact gap; never invent uninstalled capability.

## Verify ownership and exact branch

- Verify head repository, branch, head SHA, and base from live PR metadata:
  `gh pr view <N> --json url,headRefName,headRefOid,headRepository,baseRefName`.
- Inspect remotes and status. Work in the incumbent checkout or an isolated worktree; preserve unrelated work.
- Never use hard resets, force-pushes, or discarded work as routine verification. Re-read remote head before publication.

## Autonomous execution and boundaries

Drive the PR through the [pr-lifecycle completion loop](../pr-lifecycle/SKILL.md#the-autonomous-completion-loop):
1. Default to opening PRs as DRAFT (`gh pr create --draft`).
2. Select route from [review-routing.md](../pr-lifecycle/review-routing.md).
3. Maintain the single current record in the PR description ([Review Ledger and Execution Record](../pr-lifecycle/review-records.md#unified-obligation-and-review-ledger)).
4. Own asynchronous jobs with explicit handle and verified resumption mechanism (a written wake condition alone is not resumption); retain ownership of blocking dependencies through their endpoint or accepted handoff.
5. Pass draft gates in order, undraft via `gh pr ready`, and satisfy closing obligations.
6. Creating or updating a PR does not authorize merge. Merge authority must be satisfied separately.
