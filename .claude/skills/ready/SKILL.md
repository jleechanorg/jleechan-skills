---
name: ready
description: Drive PR(s) to merge-ready — /es, plus /er and /advice where draft-first-pr requires them, then /green, all comments and merge conflicts handled. Use for /ready or /r.
---

# /ready — PR merge-readiness gate

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


**Order matters (draft-first):** if the PR is a DRAFT, keep it draft while
driving the applicable gates 1–3 (/es, and /er and /advice where `draft-first-pr`
requires them (including its Advice applicability rule)) to approved; only THEN undraft, then
drive the remaining ready work and the final reviews below to done. If the PR is ALREADY non-draft,
leave it non-draft — never convert an open non-draft PR back to draft; just
apply the same final gate requirements.

These are final acceptance gates, not a serial work schedule. Follow
`draft-first-pr/SKILL.md`: run independent code reviews and cheap focused checks
early in parallel, resolve or explicitly defer findings, then freeze the change
before expensive evidence. Apply its Advice applicability and change-impact rules;
do not postpone the first code review until after evidence. Undrafting begins
ready work, not completed readiness.

A PR is READY when ALL of the following hold, verified at the CURRENT head SHA
(newest check-run attempt per name; REST when GraphQL quota is low):

1. **/es** — evidence satisfies the applicable class in `evidence-standards`
   and the repository overlay. Retain original capture provenance and record
   current applicability separately. Underlying artifacts may use authorized
   private hosting; the separate sanitized review receipt follows
   `draft-first-pr` § Review records in the PR description, including its one
   current `**Evidence**` marker. Preserve historical receipts and capture SHAs.
2. **/er** — when `draft-first-pr` (including repo-defined exemptions) requires
   it, adversarial evidence review verdict PASS applicable to the candidate (findings fixed RED-first), retaining its actual reviewed/tested SHA. A head move whose actual delta leaves every tested claim,
   assertion, and driver intact may instead be reaffirmed at the new SHA under
   `draft-first-pr/SKILL.md`'s SHA-binding rule — document the delta and the
   prior verdict's provenance rather than relabeling the old capture; a
   behavioral change or a changed assertion/driver requires a fresh run.
3. **/advice** — when `draft-first-pr` § Advice applicability
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
6. **Cross-thread regression check** — before treating gate 5 as satisfied,
   check whether any OPEN bead — filed by this session, a sidekick, or any
   OTHER concurrent investigation running in parallel (e.g. a live-bug
   `/repro` thread) — shares root cause or a touched file with this PR's
   diff. A confirmed regression discovered elsewhere is not automatically
   non-blocking just because it came from a different task. If one exists,
   explicitly surface it to the user as a blocking-or-not decision before
   merging — never silently file it as a separate parallel-track bead and
   proceed. (Added 2026-08-16 after PR #8951: a confirmed regression bead
   found via a parallel `/repro` thread sat un-triaged while the PR merged
   anyway.)

After this work stabilizes, complete final `/er` then final `/advice` as required
by `draft-first-pr` § Ready phase. Apply that owner's reasoned delta and phase assessment to final approvals, including approvals earned at an earlier SHA; record applicability without relabeling the original review. Request only missing or affected coverage; do not rerun unchanged expensive evidence. A fix
reopens affected proof and current-head readiness checks. Record every review's
gist URL and reviewed SHA under that owner's Review records contract, preserving
history and honest blocked states. Do not report READY before this closure.

If a PR does not satisfy these, MAKE it satisfy them (fix lanes, evidence
publication, gate reruns), then re-verify. Merges remain human-authorized:
report READY state separately from the live merge authorization required by
`draft-first-pr` and the repository. The separate live merge authorization is
never supplied by a review, ledger entry, or READY verdict.

## Stage evidence publication

Follow [draft-first-pr](../draft-first-pr/SKILL.md) for proportional exceptions and every stage exit receipt. Always put retrievable artifact/gist URLs and applicable viewable inline media in the PR description, with explicit media N/A only where justified. Verify access and read back the description; comment-only or local-only proof does not complete publication. Do not duplicate the canonical exception matrix here.
