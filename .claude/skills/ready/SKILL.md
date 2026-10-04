---
name: ready
description: Drive PR(s) to merge-ready — /es /er /advice approved, then /green, all comments and merge conflicts handled. Use for /ready or /r.
---

# /ready — PR merge-readiness gate

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


**Order matters (draft-first):** if the PR is a DRAFT, keep it draft while
driving gates 1–3 (/es, /er, /advice) to approved; only THEN undraft, then
drive gate 4 (/green) and gate 5 to done. If the PR is ALREADY non-draft,
leave it non-draft — never convert an open non-draft PR back to draft; just
apply the same final gate requirements.

These are final acceptance gates, not a serial work schedule. Follow
`draft-first-pr/SKILL.md`: run independent code reviews and cheap focused checks
early in parallel, resolve or explicitly defer findings, then freeze the change
before expensive evidence. Final acceptance remains /es → /er → /advice at
the current SHA; do not postpone the first code review until after evidence.

A PR is READY when ALL of the following hold, verified at the CURRENT head SHA
(newest check-run attempt per name; REST when GraphQL quota is low):

1. **/es** — evidence bundle exists and is published (gist linked from the PR
   body as a single canonical `**Evidence**: <gist-url> (head <sha>)` marker —
   one marker only; stale markers with old head declarations make the
   Evidence Gate fail).
2. **/er** — adversarial evidence review verdict PASS at the current head
   (re-run after every head move; findings fixed RED-first). A test-only or
   otherwise non-behavioral head move may instead be reaffirmed at the new SHA
   under `draft-first-pr/SKILL.md`'s SHA-binding/staleness-tolerance rule —
   document the diff and the prior verdict's provenance rather than relabeling
   the old capture; a production/behavioral change still requires a fresh run.
3. **/advice** — at least two independent full-coverage approval reviewers
   from the canonical `advice/SKILL.md` approval lanes approve the exact head, or
   every REQUEST_CHANGES finding is fixed and the two-reviewer quorum is rerun
   and approves. Research and the orchestrating agent do not vote. One approval
   can block but cannot approve; unavailable or partial-coverage reviewers do
   not satisfy the approval quorum. The same non-behavioral-delta reaffirmation
   applies here (full original coverage plus the small reviewed delta,
   documented at the new SHA) — it never reduces the two-reviewer quorum or the
   named-reviewer requirement in `advice/SKILL.md`; changing that requirement
   needs its own separate, explicitly approved change.
4. **/green** — every current-head CI check green (rerun infra-signature
   failures: SIGKILL-during-rustc, Set-up-Python, sqlite3-amalgamation;
   diagnose real failures instead of rerunning) AND mergeable with no
   conflicts.
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

If a PR does not satisfy these, MAKE it satisfy them (fix lanes, evidence
publication, gate reruns), then re-verify. Merges remain human-authorized:
report READY state and merge only under an explicit or standing conditional
approval that names these gates.
