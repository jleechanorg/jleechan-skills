---
name: pr-workflow-manager
description: "PR workflow entry point: discover canonical skills, verify source ownership, publish draft PRs, and drive applicable stages."
type: usage
scope: project
---

# PR Workflow Manager

## One operational contract

Before taking any workflow action, inspect the target repository's `AGENTS.md`, `CLAUDE.md`, and scoped
instructions for an explicit PR-workflow contract, adapter, or opt-out. Do this before choosing a branch,
worktree, PR stage, or gate. Follow an explicit local contract for its domain; do not infer an opt-out from
the repository's name or apparent purpose. If no local opt-out or conflicting requirement is declared,
use the shared defaults below.

Reviewer attempt deadlines, timeout dispositions, fallback routing and advice
quorum recovery are owned by [pr-lifecycle's reviewer timeout contract](../pr-lifecycle/SKILL.md#reviewer-timeout-and-completion).
Apply it to `/dot`, `/wa` and other reviewer waits; do not add a separate timer
or treat a timeout as approval.

Read [pr-lifecycle](../pr-lifecycle/SKILL.md) before creating, staging or driving a PR. It supplies shared
defaults for lifecycle, visible stages/title prefixes and suffixes/labels, specification placement, review
routes and reasoned evidence/approval applicability wherever local instructions are silent. This entry point
owns practical discovery, branch verification and publication steps. No dated design document is required.

Keep these two skills in sync: a lifecycle or stage change updates the shared default contract and checks this
entry point and repository adapters for conflicting commands or summaries. Reference the contract rather
than copying its tables. Preserve repository-specific evidence, safety, native and merge requirements. When
local instructions and shared defaults differ, follow the explicit local instruction in its domain and use
the shared default only for unresolved details. Neither contract changes separate permissions.

## Find the skills before inventing a workflow

1. Use an already-known local checkout of the official jleechan-skills repository, or resolve an installed
   skill's source. Verify its remote and record its commit; preserve local edits.
2. If no checkout exists, clone the official source to an unused local development directory:
   `git clone https://github.com/jleechanorg/jleechan-skills.git <unused-directory>`.
   Never clone over an existing directory, reset a dirty checkout or copy somebody else's credentials.
3. Read `.claude/skills/pr-lifecycle/SKILL.md` and this skill from that checkout. Read relevant sibling
   skills for actual review/test execution. Cloning is not installation, host synchronization or permission
   to run an installer.
4. If Git access is unavailable or denied, state the exact gap; use an already-authorized read connector
   only where permitted, preserving the source ref. Do not bypass a denial or invent installed capability.
5. Existing checkouts are not silently overwritten or auto-updated. Fetch/inspect safely when authorized;
   report drift and preserve unrelated work before any requested sync.

The repository's AGENTS.md should reference this entry point and the canonical lifecycle. User-level
agent guidance should provide the same discovery path, not maintain a third lifecycle definition.
A command named /pr-workflow, if installed, must resolve to this entry point; absence is not permission
to invent an alias or claim one exists.

## Activation cues

Use for opening or driving PRs, post-push follow-through, branch/upstream problems, stage changes,
CI/conflict diagnosis, and review/readiness coordination.

## Verify ownership and the exact branch

- Read repository AGENTS.md/CLAUDE.md, current user scope, existing PR and source-owner/hold records.
- Verify actual head repository, head branch, head SHA and base from live PR metadata:
  `gh pr view <N> --json url,headRefName,headRefOid,headRepository,baseRefName`.
- Inspect local status, remotes and upstream. A similarly named branch or a log grep is not source binding.
- Fetch the verified branch using the existing authorized remote. Work in the incumbent checkout or an
  explicitly coordinated isolated worktree; preserve dirty and unrelated changes.
- Never use a hard reset, force-push, deleted branch or discarded work as routine branch verification.
  This skill grants none of those actions and no new writer/operator.
- Re-read the remote head before publication. Unexpected movement requires reconciliation, not overwrite.

## Shared-default publication

The actions below are shared defaults only. After inspecting the target repository's instructions, use these
creation and stage choices only where those instructions are silent; follow any explicit local creation state
or workflow instead. Local instructions do not waive separate security, credential, ownership or merge gates.

| Scenario | Safe ordinary action |
|---|---|
| First branch push | Verify target, then `git push -u <verified-remote> HEAD`. |
| Same-repository PR | When local instructions are silent and the shared draft default applies, use `gh pr create --repo <verified-base-owner/repo> --draft --base <verified-base> --head <verified-branch>`; verify head and base repositories are identical first. |
| User-owned fork PR | When local instructions are silent and the shared draft default applies, use the same explicit `--repo`/`--base` with `--head <verified-head-user>:<verified-branch>`. |
| Existing PR update | Scoped commit and ordinary push through its sole writer; verify remote SHA. |
| Missing upstream | Verify remote branch, then `git branch --set-upstream-to=<remote>/<branch>`. |
| Status | Read PR head/base, all applicable check attempts, reviews and mergeability. |
| Connector publication | Use its authorized expected-head/non-forced update and exact readback; do not pretend it establishes native Git upstream tracking. |

The [GitHub CLI manual](https://cli.github.com/manual/gh_pr_create) documents owner-qualified fork heads and an organization-owner limitation. If the tool cannot express the exact head repository, use an already-authorized interface that can, or report the blocker; never guess from a same-named branch. After creation, read back both repository identities, head/base branches and head SHA before updating or claiming the intended PR.

An optional helper is usable only if it actually exists, has been inspected and preserves the applicable
local or shared creation state, ownership and expected-head requirements. No bundled creation script is
assumed by this skill.
Do not execute a missing, unverified or incompatible helper just because old guidance names one.

## Stage changes and evidence

For opted-in repositories, apply [stage transitions](../pr-lifecycle/SKILL.md#stage-title-and-labels), [default PR route and lighter non-production path](../pr-lifecycle/SKILL.md#default-pr-route--prw), and [evidence applicability](../pr-lifecycle/SKILL.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain). Title/label changes are not execution proof, review approval or merge authority.

After each push, inspect applicable latest checks and review findings. Diagnose original logs before a
targeted fix/retry, preserve assertions, and follow the canonical ready/final phases. Waiting/blocked is not
Working. Do not call a PR ready from badges, skipped tests, an assignment or a pending review.
For any user-visible change (anything not covered by the narrow documentation-only / zero-UI-impact non-visual exemption), Stage 3 -> Stage 5 (`stage:5-final-approval`) promotion and merge readiness MUST include an explicit `VISUAL APPROVED at <40-char-sha>` (or a reasoned delta assessment preserving an earlier evidenced SHA whose rendered UI did not change) from an independent AI reviewer (`/er` visual lane inspecting actual rendered image/video frames, advice visual inspection, or `/dot`). A pending request (e.g., `/dot: REQUESTED, pending`) or link-existence check alone is NOT a visual approval PASS; if `/dot` is unavailable or pending, run an independent AI visual reviewer (advice or `/er` visual lane that downloads and inspects the rendered stills/frames) and record `VISUAL APPROVED at <40-char-sha>` before labeling `stage:5-final-approval`. The approval record MUST include, per user-visible claim, the before (where a before state exists) and after artifact links, a concrete description of what the reviewer saw in each (the changed element, its state, and the viewport), and a matches-claim verdict, all bound to the evidenced SHA (the approved head, or the earlier SHA a reasoned delta assessment preserves); a bare stamp or approver name without those findings is not a visual approval PASS. Repositories may require the findings as a PR-body table and check its presence and SHA binding in CI.

## PR description and reporting

Use the repository's actual template and authoritative description requirements.
Record scope and non-goals, full production/non-production deltas, original execution evidence,
review coverage/applicability, current stage, owner, blockers and next action.
Keep receipts and prior verdict attribution; verify the rendered body and reviewer access.
Report partial publication or an uncertain result before retrying. No private source, credentials or
personal communications may be published outside their authorized destination.

## Boundaries

Creating or updating a PR does not authorize merge, deployment, credential changes, new quota,
native/account operations, schedule changes or another owner's source work.
Merge authority remains repository/user-specific and must be satisfied separately.

## Stage evidence publication

Apply [pr-lifecycle's stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit), including PR-description URLs, applicable inline media, access verification and reasoned exemptions. That contract is the single owner; do not duplicate it here.
