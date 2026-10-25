---
name: ready
description: Drive PR(s) to merge-ready — /es, plus /er and /advice where pr-lifecycle requires them, then /green, all comments and merge conflicts handled. Use for /ready or /r.
---

# /ready — PR merge-readiness gate

## Governing workflow

Use [pr-lifecycle](../pr-lifecycle/SKILL.md) for review integrations, applicability and evidence reuse. Its [opt-in review routes](../pr-lifecycle/SKILL.md#review-routes-for-opted-in-repositories) remain part of readiness, including any applicable independent /dot obligation.

Keep drafts draft until applicable draft gates pass; never convert an already non-draft PR back to draft. Follow [review sequencing](../pr-lifecycle/SKILL.md#draft-phase-final-acceptance-gates-in-order): code review and cheap checks early, expensive evidence after stabilization. Undrafting begins ready work, not completed readiness.

A PR is READY when ALL of the following are assessed against the CURRENT candidate. CI and mergeability require current-head verification; reused evidence and reviews retain their actual original SHAs with documented applicability.
Use the newest check-run attempt per name; REST when GraphQL quota is low:

1. **/es** — evidence satisfies the applicable class in `evidence-standards`
   and the repository overlay. Retain original capture provenance and record
   current applicability separately. Underlying artifacts may use authorized
   private hosting; the separate sanitized review receipt follows
   `pr-lifecycle` § Review records in the PR description, including its one
   current `**Evidence**` marker. Preserve historical receipts and capture SHAs.
2. **/er** — when `pr-lifecycle` (including repo-defined exemptions) requires
   it, adversarial evidence review verdict PASS applicable to the candidate (findings fixed RED-first), retaining its actual reviewed/tested SHA. A head move whose actual delta leaves every tested claim,
   assertion, and driver intact may instead be reaffirmed at the new SHA under
   `pr-lifecycle/SKILL.md`'s SHA-binding rule — document the delta and the
   prior verdict's provenance rather than relabeling the old capture; a
   behavioral change or a changed assertion/driver requires a fresh run.
3. **/advice** — when `pr-lifecycle` § Advice applicability
   requires it, at least two independent full-coverage approval reviewers
   from the canonical `advice/SKILL.md` approval lanes provide approvals whose coverage applies to the candidate. Resolve every REQUEST_CHANGES finding and obtain any missing affected review; a SHA change alone does not require recalling both voters. Research and the orchestrating agent do not vote. One approval
   can block but cannot approve; unavailable or partial-coverage reviewers do
   not satisfy the approval quorum. The same delta-based reaffirmation
   applies here (full original coverage plus the small reviewed delta,
   documented at the new SHA) — it never reduces the two-reviewer quorum or the
   named-reviewer requirement in `advice/SKILL.md`; changing that requirement
   needs its own separate, explicitly approved change.
4. **/green** — follow `pr-green-definition` for applicable checks, its
   documented CI exceptions, and fresh current-head mergeability. Diagnose
   real failures; a failed or missing required check is not a pass.
5. **Comments handled** — every unresolved review thread and actionable bot
   comment addressed (fix or reasoned reply); merge conflicts resolved by
   rebase.
6. **Cross-thread regression check** — inspect OPEN beads from this and concurrent investigations for shared root causes or touched files. Surface any confirmed regression to the user for a blocking-or-not decision before merging; do not bypass it by filing a separate bead.

After readiness work stabilizes, satisfy [final review obligations](../pr-lifecycle/SKILL.md#ready-phase--finish-ready-then-final-reviews): applicable final `/er`, then final `/advice`, using documented delta/phase applicability rather than automatic reruns. Fix failing lanes, refresh affected proof and current-head checks, publish reviews under the [review-record contract](../pr-lifecycle/SKILL.md#review-records-in-the-pr-description), and re-verify before reporting READY. Reviews, ledger entries and READY never supply separate live merge authorization.

## Stage evidence publication

Apply [pr-lifecycle's stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit), including PR-description URLs, applicable inline media, access verification and reasoned exemptions. That contract is the single owner; do not duplicate it here.
