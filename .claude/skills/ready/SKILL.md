---
name: ready
description: Drive PR(s) to merge-ready — /es /er /advice approved, then /green, all comments and merge conflicts handled. Use for /ready or /r.
---

# /ready — PR merge-readiness gate

**Order matters (draft-first):** if the PR is a DRAFT, keep it draft while
driving gates 1–3 (/es, /er, /advice) to approved; only THEN undraft, then
drive gate 4 (/green) and gate 5 to done. If the PR is ALREADY non-draft,
leave it non-draft — never convert an open non-draft PR back to draft; just
run the gates in the same order.

A PR is READY when ALL of the following hold, verified at the CURRENT head SHA
(newest check-run attempt per name; REST when GraphQL quota is low):

1. **/es** — evidence bundle exists and is published (gist linked from the PR
   body as a single canonical `**Evidence**: <gist-url> (head <sha>)` marker —
   one marker only; stale markers with old head declarations make the
   Evidence Gate fail).
2. **/er** — adversarial evidence review verdict PASS at the current head
   (re-run after every head move; findings fixed RED-first).
3. **/advice** — independent external review (agy CLI or equivalent)
   APPROVE, or all REQUEST_CHANGES findings fixed and delta-verified.
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
