# Lifecycle policy reconciliation

## Outcome

Make remaining PR entrypoints resolve the canonical `pr-lifecycle` owner without
recreating its policy. Reconcile actual readiness conflicts while preserving
separate merge authority, review quorum, domain proof and source ownership.
Publish one draft PR from current main; do not merge or install it on a host.

## Non-goals

- No scripts, CI changes, new review transports, provider calls or deployment.
- No automatic-merge grant changes or relaxation of an exact-head merge condition.
- No rewriting already-correct readiness reuse, the under-50/at-least-50 boundary,
  or standing `/wa` authorization. No deletion of the `draft-first-pr` alias.
- No edits to another active owner's paths before explicit custody reconciliation.

## Acceptance

- Active lifecycle references in the scoped entrypoints point to `pr-lifecycle`.
- Reporting does not equate `/green` with completed readiness or require a new
  review solely because HEAD moved. Factory PR creation remains draft-first.
- Shared-policy reconciliation preserves independent `/cs` and merge restrictions.
- Existing contract assertions stay strong; focused regression tests fail before
  the fix and pass after it. Exact-head remote contract CI must pass.
- The PR records resolved, already-fixed and held items honestly. Full completion
  requires clearing held scope and the canonical independent review obligations;
  self-review and native checks do not count as `/advice` quorum votes.

## User stories

An agent following a reporting or planning entrypoint should reach the current
lifecycle owner rather than a stale copied sequence. A reviewer should see which
claims the candidate establishes and which work remains held, without treating a
green check or a reused receipt as merge authorization.

## Proof plan

Inspect exact main bytes and every open PR's changed paths before editing. Add
regressions to existing contract tests, preserve causal RED/GREEN outputs, and run
the applicable contract suites. Inspect each diff and resolve changed pointers.
Publish sanitized, SHA-bound receipts and request eligible external reviews via
the existing authorized workflow. Remote CI supplies full-checkout validation;
a partial cloud source fixture is not a full local repository test run.

## Mock exemption

No application UI or rendering changes. Source/diff inspection and policy contract
tests prove the bounded documentation claims; screenshots and video are N/A.

## Risk and initial ownership audit

These are operational review-policy instructions, not harmless prose. The existing
lifecycle's policy-review safeguards still apply. At main
`6b8888445d83b54e1cb90559660f64caaaf7d6d0`, the initial audit found:

| Item | Disposition |
|---|---|
| agento-report, auton, factory-evolve, pr-report, superpowers-quick, testing-layers, write-goal and its goal-spec template, zero-touch | Available for pointer/readiness cleanup. |
| ironclad | Held: its owner-name assertion is in the lifecycle contract test owned by #565. |
| pr-lifecycle and tests/test_coding_lifecycle_contract.py | Held by distinct Stage-0/readback PR #565; not absorbed into this task. |
| md_files/AGENTS.shared.md | Held for custody reconciliation with #518, #521 and #525. |
| advice | Inspected; quorum remains authoritative. Active #495 and #522 ownership is preserved. |
| evidence-standards | Precedence/reuse already correct; active #549 ownership is preserved. |
| fixpr | Readiness wording needs reconciliation but is held by #532. |
| pr-green-definition, evidence-review, ready, pr-workflow-manager | Already delegate relevant lifecycle scope; keep legitimate entrypoint pointers and domain proof. |

Subsequent hunk-level reconciliation cleared only evidence-standards lines 11–13
for direct lifecycle pointers; #549's domain/UI hunks stay untouched. The
evidence-review entrypoint now resolves those same canonical anchors directly.
Ready and pr-workflow-manager already link the stage-exit owner, so equivalent
pointer repetition does not justify a second policy or unrelated churn.
Shared-policy lifecycle/reuse paragraphs and old owner references were also
cleared by hunk-level reconciliation with #518/#521/#525; their unrelated
sections, production counters, `/cs` and merge safeguards are preserved.
Ironclad line 54 and the matching existing assertion at lifecycle-test line 149
were likewise cleared as disjoint from #565's added test near line 383.
No #565 branch or canonical lifecycle edit is included. Fixpr remains owned
by #532, whose Step-2 replacement already addresses the same readiness shortcut.

The direct owner instruction puts the stage bracket last. Any relayed provenance-
last request conflicts with it; retain real provenance before the stage suffix
without inventing a model identity. This specification adds no new merge grant.
