---
name: pr-workflow-manager
description: "PR workflow entry point: discover canonical skills, verify source ownership, publish draft PRs, and drive applicable stages."
type: usage
scope: project
---

# PR Workflow Manager

## One operational contract

Read [draft-first-pr](../draft-first-pr/SKILL.md) before creating, staging or driving a PR.
It is the self-contained owner of lifecycle, visible stages/title prefixes/labels, specification placement,
review routes and reasoned evidence/approval applicability. This entry point owns practical discovery,
branch verification and publication steps. No dated design document is required.

Keep these two skills in sync: a lifecycle or stage change updates the canonical contract and checks this
entry point and repository adapters for conflicting commands or summaries. Reference the contract rather
than copying its tables. Preserve repository-specific evidence, safety, native and merge requirements.
An apparent conflict is resolved from current user direction and the applicable authoritative rule,
not by silently choosing the weakest gate.

## Find the skills before inventing a workflow

1. Use an already-known local checkout of the official jleechan-skills repository, or resolve an installed
   skill's source. Verify its remote and record its commit; preserve local edits.
2. If no checkout exists, clone the official source to an unused local development directory:
   `git clone https://github.com/jleechanorg/jleechan-skills.git <unused-directory>`.
   Never clone over an existing directory, reset a dirty checkout or copy somebody else's credentials.
3. Read `.claude/skills/draft-first-pr/SKILL.md` and this skill from that checkout. Read relevant sibling
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

## Draft-first publication

| Scenario | Safe ordinary action |
|---|---|
| First branch push | Verify target, then `git push -u <verified-remote> HEAD`. |
| Open the PR | `gh pr create --draft --base <verified-base> --head <verified-branch>`. |
| Existing PR update | Scoped commit and ordinary push through its sole writer; verify remote SHA. |
| Missing upstream | Verify remote branch, then `git branch --set-upstream-to=<remote>/<branch>`. |
| Status | Read PR head/base, all applicable check attempts, reviews and mergeability. |
| Connector publication | Use its authorized expected-head/non-forced update and exact readback; do not pretend it establishes native Git upstream tracking. |

An optional helper is usable only if it actually exists, has been inspected and preserves the draft,
ownership and expected-head requirements. No bundled creation script is assumed by this skill.
Do not execute a missing, unverified or incompatible helper just because old guidance names one.

## Stage changes and evidence

For an opted-in repository, follow the complete stage mapping in draft-first-pr:
choose the earliest unmet gate, update the recognized title prefix, single stage label and PR-body stage,
then read them back. Preserve unrelated tags/labels and holds; report partial or denied updates honestly.
Title/label publication is not execution proof, review approval or merge authority.

Keep the original tested and reviewed SHAs. Inspect the actual intervening head/base delta and record
why an earlier independent verdict remains applicable, is partially applicable, or needs affected new proof.
A new SHA alone does not force a fresh evidence run or review. No blanket file-category carry-forward,
invented voter or self-approval is permitted. Current-candidate CI/mergeability checks remain separate.

After each push, inspect applicable latest checks and review findings. Diagnose original logs before a
targeted fix/retry, preserve assertions, and follow the canonical ready/final phases. Waiting/blocked is not
Working. Do not call a PR ready from badges, skipped tests, an assignment or a pending review.

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

Follow [draft-first-pr](../draft-first-pr/SKILL.md) for proportional exceptions and every stage exit receipt. Always put retrievable artifact/gist URLs and applicable viewable inline media in the PR description, with explicit media N/A only where justified. Verify access and read back the description; comment-only or local-only proof does not complete publication. Do not duplicate the canonical exception matrix here.
