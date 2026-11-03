# Static-review access contract — PR #657 specification

## Outcome

Define static review as a fixed, cold reviewer prompt with authority to approve a fully reviewed exact change, PR, or head. Complete base/head coverage applies to every revision-bound access mode: read-only, export, clone, and revision-bound saved content. A complete unbound saved-content packet is bundle-scoped and does not require a fictitious diff or base/head binding.

## Non-goals

- No new reviewer runner, wrapper, or production/runtime code.
- No new network request, retry, or model call.
- No change to reviewer quorum, identity rules, receipt requirements, P0-only merge-blocking policy, or human merge authority.
- No application behavior or player-facing product change.

## Acceptance criteria

- Reviewers receive the fixed cold preamble and template; question, summary, or framing remains excluded.
- Read-only GitHub/API or an existing checkout is the default when it provides the complete pinned scope; a clone, export, or Scratch allocation is not required for that route.
- For every revision-bound review, reviewers read the complete base-to-head diff and full changed-path content at both revisions, or verify absence on one side. Coverage includes deleted/base-only files, renames, binary bytes, file modes, symlink targets, and actual LFS/submodule content on both sides where applicable. Bundle-only reviews read all complete declared files and evidence without inventing base/head revisions.
- A missing required object or payload makes coverage incomplete and the vote `WITHHELD`; missing content is never treated as `N/A`, inferred, or accepted from pointer hashes alone.
- Unpushed SHAs require local access: an existing checkout, verified saved-content packet, or local donor-backed copy route may supply the exact commit; GitHub/API-only review requires remotely retrievable objects.
- `REVIEW TARGET` is exactly a full 40-hex head SHA for a verified complete PR/base/head packet, or `DOCUMENTS sha256:<bundle hash>` for a bundle-only packet. Abbreviated SHAs and mutable `HEAD` are not targets.
- Complete unbound packets may approve only their named bundle. Incomplete packets or packets missing required content are `WITHHELD`.
- Existing contract tests assert these access, coverage, prompt, receipt, and lifecycle semantics without weakening quorum or merge-authorization checks.

## User story

No player-facing change. Reviewers can approve a pinned change without a local copy when they can read all required base/head content, and authors can tell exactly which revision or saved bundle a verdict covers.

## Proof plan

- Run `git diff --check` on the candidate.
- Run the existing focused advice-machine-local-clis, approval-contracts, and coding-lifecycle-contract tests in the Linux validation lane, then verify the required current-head `contract-tests` workflow.
- Perform independent full-scope review through the read-only route and require exact-head coverage; withhold if any required object or payload is unavailable.

## Mock or justified exemption

No application mock applies: this change alters Markdown reviewer and lifecycle instructions, not product runtime behavior. Existing deterministic contract tests inspect the instruction text; they do not replace the independent review or content-coverage proof.

## Risk

A remote API or saved packet may omit a base-side blob, LFS payload, submodule target, or binary content. The reviewer must mark coverage incomplete and withhold that vote; another access mode may supply it. This can reduce available votes when content is inaccessible, but it prevents approval of unseen revision content.
