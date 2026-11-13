## 5. Reconcile and report

**Counting a vote.** A counted reviewer returns full-scope `COVERAGE:` and a nonempty `VERDICT:`. Its receipt shows
a zero exit, a present and parseable receipt, no mutation of the original checkout, no surviving reviewer process,
and no cleanup failure (receipt timing, archive handling, and non-mandatory bookkeeping follow §3).
A static-review receipt replaces only the exit field; an outside-route receipt (`remote` or
`packet`) replaces the exit, process and cleanup fields with that row's evidence. When a seat returns nonzero, ignore its
whole receipt, since a failed late rewrite can leave an older success-looking one. If clone setup timed out,
directory removal does not prove its descendants exited: record that and do not count the attempt.

**Verdict.** Reconcile disagreements within the declared scope yourself; do not ask the user to pick between
reviewers. A competent blocking objection, even from a partial-coverage reviewer, means `NOT APPROVED`; partial
coverage never supplies an approval. P1/P2 findings are nonblocking and alone neither withhold approval nor require
another round; the author batches them and records each fix or disposition in the report. Without the required
independent full-coverage approvals under §2's tier caps, the result is
`WITHHELD`.

**Report.** Give the full 40-hex reviewed SHA for revision-bound review or `DOCUMENTS sha256:<bundle hash>` for a
complete bundle-only review; never use an abbreviated SHA or mutable `HEAD`. Each reviewer's verdict,
coverage, reasoning, risk and findings, the question's answer, and the complete
[candidate report](reviewer-selection.md#candidate-checks-fan-out-and-fallback). Keep a receipt per
attempt: identity, actual CLI, account and model, start and completion times, exit or timeout, the exact prompt
(any deviation voids the vote, per static-review), complete output, coverage and cleanup result. End with exactly
one line: `VERDICT: APPROVED at `<SHA>``, `VERDICT: NOT APPROVED at `<SHA>``, or `VERDICT: WITHHELD at `<SHA>` — <reason>`;
for bundle-only saved-content review, `DOCUMENTS sha256:<bundle hash>` takes the place of ``<SHA>``.

**Resubmission and applicability.** Keep original reviewers, SHAs and findings; reliance at a later head follows
[review-routing's SHA-binding rule](../pr-lifecycle/review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain)
and is not a new vote. Before any re-dispatch, the author fixes every blocking finding in one batch, then (a) searches
all reviewed artifacts for each restatement of a corrected requirement and fixes every one, not only the cited line;
(b) verifies every cited path, line, link and artifact exists at the new pin. Inspect the complete delta, claims,
evidence and phase; applicability is not a new vote, and material uncovered changes need affected independent
review. When that rule's record is partially applicable with named gaps, send the affected review to the same seat
as static-review §4's addendum; otherwise request the complete review. Classify instruction changes by behaviour
and contract effect, never by path.
Never claim approval, applicability or publication without its receipt.

For visual follow-up, use [visual-verification's reuse and scoped follow-up](../visual-verification/SKILL.md#reuse-and-scoped-follow-up).
Repair mechanically verifiable receipt fields yourself rather than dispatching a
reviewer for bookkeeping; preserve §3 eligibility and original clocks. Such a
repair cannot supply missing coverage, alter a verdict or revive a void vote.
For human-judgment prose in a PR body, follow [document-standards' review and
publication owner](../document-standards/SKILL.md#pr-body-prose-review-and-publication).
