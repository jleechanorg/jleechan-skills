---
name: pr-workflow-manager
description: "PR workflow entry point: discover canonical skills, verify source ownership, publish draft PRs, and drive applicable stages."
type: usage
scope: project
---

# PR Workflow Manager

## One operational contract

Before choosing a branch, worktree, PR stage or gate, inspect the target repository's `AGENTS.md`,
`CLAUDE.md` and scoped instructions for an explicit PR-workflow contract, adapter or opt-out, and follow it
for its domain. Never infer an opt-out from the repository's name or apparent purpose; with none declared,
use the shared defaults below.

Read [pr-lifecycle](../pr-lifecycle/SKILL.md) before creating, staging or driving a PR. Where local
instructions are silent it supplies the lifecycle, visible stages (title prefixes, suffixes, labels),
specification placement, review routes and evidence/approval applicability. Its
[reviewer timeout contract](../pr-lifecycle/SKILL.md#reviewer-timeout-and-completion) owns reviewer
deadlines, timeout dispositions, fallback routing and advice quorum recovery for `/dot`, `/wa` and other
reviewer waits; add no separate timer and never treat a timeout as approval. This entry point owns
practical discovery, branch verification and publication. Preserve repository-specific evidence, safety,
native and merge requirements and separate permissions.

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

During an authorized `/prw`, apply [the lifecycle continuation contract](../pr-lifecycle/SKILL.md#continuation-through-the-requested-endpoint) when responding to status or progress interruptions.

## Retained review integrations

Follow [pr-lifecycle's retained review integrations](../pr-lifecycle/SKILL.md#retained-review-integrations)
for skill discovery (including on a remote host), `UNAVAILABLE` reporting, quorum and disclosure boundaries.

## Useful highlighted skills

Pick a helper for the actual question; these links add no gates. pr-lifecycle and the target
repository still decide which reviews and evidence are required.

- [advice](../advice/SKILL.md): obtain independent perspectives on a design or implementation decision; preserve the applicable review quorum.
- [4layer](../4layer/SKILL.md): locate a failure at the lowest sufficient test layer before escalating to broader or live tests.
- [evidence-review](../evidence-review/SKILL.md): check that PR claims resolve to real, provenance-backed artifacts and disclose gaps.

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

Use these defaults only where the repository's explicit creation and stage instructions are silent and,
for PR creation, the shared draft default applies. They do not waive security, credential, ownership or
merge gates.

| Scenario | Safe ordinary action |
|---|---|
| First branch push | Verify target, then `git push -u <verified-remote> HEAD`. |
| Same-repository PR | Verify head and base repositories are identical, then `gh pr create --repo <verified-base-owner/repo> --draft --base <verified-base> --head <verified-branch>`. |
| User-owned fork PR | The same explicit `--repo`/`--base` with `--head <verified-head-user>:<verified-branch>`. |
| Existing PR update | Scoped commit and ordinary push through its sole writer; verify remote SHA. |
| Missing upstream | Verify remote branch, then `git branch --set-upstream-to=<remote>/<branch>`. |
| Status | Read PR head/base, all applicable check attempts, reviews and mergeability. |
| Connector publication | Use its authorized expected-head/non-forced update and exact readback; do not pretend it establishes native Git upstream tracking. |

The [GitHub CLI manual](https://cli.github.com/manual/gh_pr_create) documents owner-qualified fork heads and an organization-owner limitation. If the tool cannot express the exact head repository, use an already-authorized interface that can, or report the blocker; never guess from a same-named branch. After creation, read back both repository identities, head/base branches and head SHA before updating or claiming the intended PR.

No bundled creation script is assumed. Use an optional helper only if it exists, has been inspected and
preserves the applicable creation state, ownership and expected-head requirements; never run a missing,
unverified or incompatible helper because old guidance names one.

## Stage changes and evidence

Select class, risk, changed claims, proof and source-review count from [the lifecycle obligation table](../pr-lifecycle/SKILL.md#review-obligations-by-changed-claim-and-risk). Record the selected row and its positive eligibility evidence in the existing PR/task record. This entry point performs operational preflight; it does not add a second routing table, provider ladder or source-vote requirement.

The [compact risk-based route](../pr-lifecycle/SKILL.md#compact-risk-based-route) may skip intermediate stage-title/label ceremony and the separate seven-element committed specification only where repository instructions permit the compact exception. It does not skip required checks or Stage 5 closure. For opted-in repositories, apply [stage transitions](../pr-lifecycle/SKILL.md#stage-title-and-labels), [default PR route and lighter non-production path](../pr-lifecycle/SKILL.md#default-pr-route--prw), and [evidence applicability](../pr-lifecycle/SKILL.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain). Title/label changes are not execution proof, review approval or merge authority.

At start, after each push and on a new failure, refresh head, applicable checks and findings. Record the requested endpoint, actual blockers (required gates/P0 versus nonblocking findings), executing owner, next action and clearance evidence in the existing PR/task record.

Before expensive work, assess existing results against their recorded SHA and clear cheap relevant failures. Before review dispatch, verify required artifacts are readable and hash-bound; record measured merge-base/head scope, target-tip conflict status, selected route, prior-proof applicability and producer gaps. Resolve templates by the owner's named access mode, not file position: validate the rendered prompt as data, correct it to that mode, reject unresolved placeholders, and do not switch modes or export merely to satisfy a template error. Select an eligible available model and coverage; count a vote only when actual model, complete coverage and receipt SHA match. New conditions must trace to the user/intake contract; identify new scope instead of silently gating readiness on it.

A same-cause probe/review that clears no blocker and reduces no uncertainty calls for a changed approach while independent work continues. Continue through the requested endpoint without invented approval stops or cycle/time caps. Diagnose original logs before a targeted fix/retry, preserve assertions, and follow canonical ready/final phases. Waiting or blocked is not Working; badges, skipped tests, assignment and pending review never establish readiness.
Before promoting a user-visible change to `stage:5-final-approval`, apply the
[canonical visual-approval contract](../pr-lifecycle/SKILL.md#review-routes-for-opted-in-repositories)
and [draft-phase visual gate](../pr-lifecycle/SKILL.md#draft-phase-final-acceptance-gates-in-order).
The compact route does not itself waive an applicable visual receipt: follow the lifecycle's
claim/risk table and preserve its explicit one-liner and bounded nonvisual/source-only exceptions.
When required, record `VISUAL APPROVED at <40-char-sha>` with the required findings.
`/dot: REQUESTED, pending`, author inspection, and link checks do not satisfy that receipt.

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
Stage-exit receipts follow [pr-lifecycle's stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit); that contract is the single owner.
