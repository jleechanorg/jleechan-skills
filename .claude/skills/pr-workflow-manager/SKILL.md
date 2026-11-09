---
name: pr-workflow-manager
description: "PR workflow entry point: discover canonical skills, verify source ownership, publish draft PRs, and drive applicable stages."
type: usage
scope: project
---

# PR Workflow Manager

## Terminal goal and entry contract

An unqualified `/prw` (`/pr-workflow`) defaults to driving the PR to **`FINAL_READY`** across all applicable gates under one continuous session goal, unless the user explicitly requests an earlier milestone. Intermediate checkpoints (opening draft, pushes, initial approval, undrafting, stage labels) are not task completion; merge authority remains separate. For the canonical completion contract, exit conditions, and canonical `[status][short detail]` title presentation (e.g. `[ready][needs approval] Substantive change [cli][model]`), follow [pr-lifecycle](../pr-lifecycle/SKILL.md#terminal-goal-and-first-screen-contract) and [six-stage.md](../pr-lifecycle/six-stage.md#stage-title-and-labels).

- **Automatic native goal activation:** When `/prw` starts, detect capability through the supported CLI interface (native goal tool/API when available, or [cmux-goal](../cmux-goal/SKILL.md) when hosted in cmux) and activate or reuse one task-scoped native session goal through `FINAL_READY`; never revive a goal the user cleared, paused, or stopped. Detailed activation rules (supported/absent, already-active, user-cleared/stopped protection, unsupported fallback, and verified persistence) are canonically owned by [pr-lifecycle's terminal goal contract](../pr-lifecycle/SKILL.md#terminal-goal-and-first-screen-contract). The `/prw` alias already ran cmux-goal's `bin/self_goal.py set` (tmux and cmux hosts); print its `Goal:` line verbatim before the first PR-mutating action, or run it now if it was skipped.

## One operational contract

Before selecting a branch, stage, or gate, inspect the target repository's `AGENTS.md`, `CLAUDE.md`, and scoped instructions. Local repository instructions take precedence within their domain. Where local instructions are silent, apply the canonical [pr-lifecycle](../pr-lifecycle/SKILL.md) completion loop.

## Find the skills before inventing a workflow

1. Use an already-known local checkout of the official `jleechan-skills` repository, or resolve an installed skill's source. Verify its remote and commit; preserve local edits.
2. If no checkout exists, clone the official source to an unused development directory: `git clone https://github.com/jleechanorg/jleechan-skills.git <unused-directory>`.
3. Read `.claude/skills/pr-lifecycle/SKILL.md` from that checkout.
4. If Git access is unavailable, state the exact gap; never invent uninstalled capability.

## Verify ownership and exact branch

- Read target repository `AGENTS.md`/`CLAUDE.md`, current user scope, existing PR, and source-owner/hold records. Reconcile with any sole writer before writing to prevent competing updates.
- Verify actual head repository, head branch, head SHA, and base from live PR metadata:
  `gh pr view <N> --json url,headRefName,headRefOid,headRepository,baseRefName`. Inspect remotes, local status, and upstream; a similarly named branch or a log grep is not source binding.
- Fetch the verified branch using the existing authorized remote. Work in the incumbent checkout or an explicitly coordinated isolated worktree; preserve dirty state and unrelated changes.
- Never use hard resets, force-pushes, deleted branches, or discarded work as routine verification; this skill grants none of those actions and no new writer. Re-read remote head before publication; unexpected remote movement requires reconciliation, not overwrite.
- For upstream mechanics and branch tracking verification, follow [git-branch-tracking](../git-branch-tracking/SKILL.md).

## Practical publication guidance

Apply these compact defaults where explicit repository instructions are silent; existing global merge/push safety remains canonical:
- **First branch push:** Verify target and upstream tracking (`git push -u <verified-remote> HEAD`), following [git-branch-tracking](../git-branch-tracking/SKILL.md).
- **Same-repository PR creation:** Verify head and base repositories are identical, then bind explicitly:
  `gh pr create --repo <verified-base-owner/repo> --draft --base <verified-base> --head <verified-branch>`.
- **User-owned fork PR creation:** Use the same explicit `--repo` and `--base` with `--head <verified-head-user>:<verified-branch>`. If a tool cannot express the exact head repository (such as GitHub CLI fork or organization limitations), use an already-authorized capable interface or report the precise blocker; never guess from a same-name branch.
- **After-create readback:** Read back both repository identities, head/base branches, and head SHA before updating or claiming the intended PR.
- **Existing PR updates:** Scoped commit and ordinary push only through the PR's sole writer; re-read remote head SHA immediately afterward to verify publication.
- **Missing upstream repair:** Verify the remote branch, then configure tracking: `git branch --set-upstream-to=<remote>/<branch>`.
- **Connector updates:** Connector authorized expected-head non-forced updates and exact readback are distinct from native Git upstream; do not treat connector publication as establishing native Git upstream tracking.

## Autonomous execution and boundaries

Drive the PR through the [pr-lifecycle completion loop](../pr-lifecycle/SKILL.md#the-autonomous-completion-loop), which owns route selection, gate order, obligation records, asynchronous work, evidence applicability and final claim-to-proof checks. Load [six-stage.md](../pr-lifecycle/six-stage.md) only when the target repository opts into that workflow, and the relevant [on-demand routing/recovery references](../pr-lifecycle/SKILL.md#review-obligations-by-changed-claim-and-risk) when their decisions are needed. Open new PRs as drafts; undraft only after its applicable draft gates pass.

## Boundaries

Creating or updating a PR does not authorize merge, deployment, credential changes, new quota, native/account operations, schedule changes or another owner's source work. Merge authority remains repository/user-specific and must be satisfied separately. Operational title presentation follows [six-stage.md](../pr-lifecycle/six-stage.md#stage-title-and-labels), and stage-exit receipts follow [pr-lifecycle's stage-exit receipt contract](../pr-lifecycle/six-stage.md#evidence-attached-to-every-stage-exit); those contracts are the single owners.
