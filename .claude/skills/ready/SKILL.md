---
name: ready
description: Drive PR(s) through pr-lifecycle's selected readiness route, then current-head /green, comments, conflicts and applicable final reviews. Use for /ready or /r.
---

# /ready — PR merge-readiness gate

## Readiness contract

Use [pr-lifecycle's review obligations](../pr-lifecycle/SKILL.md#review-obligations-by-changed-claim-and-risk), selected from the complete diff and changed claims/risk, for all draft and final review applicability. Do not launch a fixed `/es`, `/er`, `/advice`, runtime, visual or bundle sequence for every PR; the lifecycle route and repository override decide which proof and review are required. Never fabricate approval or treat an unavailable required reviewer as a pass.

Keep drafts draft until the selected draft-phase gates pass; never convert an already non-draft PR back to draft. Follow [the lifecycle's review sequencing](../pr-lifecycle/SKILL.md#draft-phase-final-acceptance-gates-in-order); undrafting begins ready work, not completed readiness.

After the selected work stabilizes, finish [the lifecycle ready phase](../pr-lifecycle/SKILL.md#ready-phase--finish-ready-then-final-reviews): re-pin the current candidate for `/green`, mergeability, comments, conflicts and cross-thread regressions, then complete any selected final reviews. Preserve original tested/reviewed SHAs and record current applicability under the [SHA-binding rule](../pr-lifecycle/SKILL.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain). Readiness and review receipts never grant merge authority.

## Stage evidence publication

Apply [pr-lifecycle's stage-exit receipt contract](../pr-lifecycle/six-stage.md#evidence-attached-to-every-stage-exit), the single owner of PR-description URLs, applicable inline media, access verification and reasoned exemptions.
