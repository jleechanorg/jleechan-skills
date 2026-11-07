---
name: pr-lifecycle
description: "Lifecycle contract for opening PRs, driving them green, and fixing CI. Triggers on: opening a PR, driving a PR to green, fixing CI on a PR, /green, /es, /er, /advice on a PR."
metadata:
  type: policy
---

# PR Lifecycle

This is the self-contained generic lifecycle contract. [PR Workflow Manager](../pr-workflow-manager/SKILL.md) is the command and branch entry point; keep its draft, stage, evidence-applicability and safety guidance in sync with this file.

## Terminal goal and first-screen contract

An unqualified `/prw` (`/pr-workflow`) defaults to driving the PR to **`FINAL_READY`** across all applicable Stage 5 gates, unless explicitly requested earlier. One session goal covers all PR work.

- **Checkpoints vs. Completion:** PR creation, pushes, first approval, undrafting, and stage labels are intermediate checkpoints—never completion.
- **Separation of Authorities:** `FINAL_READY` certifies required obligations, checks, and receipts are complete. Merging requires separate authority under `~/.codex/AGENTS.md` § Merge safety and repository policy. If authorized, merge executes immediately before optional reporting.
- **Exit Conditions:** Return a final response only when:
  1. `FINAL_READY` is verified (and merge executed if authorized); or
  2. No authorized action remains, and an exact blocker, owner, and wake condition are recorded.

## Continuation through the requested endpoint

Execute the PR's next unmet obligation continuously through `FINAL_READY`. Status replies do not end the request: refresh live state, answer briefly, then resume. Own started jobs and delegated lanes through results under `parallelize-to-ceiling`; integrate artifacts. Stop only at the requested endpoint, user stop, or genuine external blocker.

## Precedence and scope

Target repository instructions (`AGENTS.md`, `CLAUDE.md`) take precedence within their domain. Apply shared defaults only where silent; never remove a local requirement or infer an ungranted exception. Bind head repository, branch, SHA, and base from live PR metadata (`gh pr view`).

## The autonomous completion loop

Drive the PR through this continuous cycle without stopping at intermediate checkpoints:

1. **Refresh Live State:** Fetch latest head SHA, check runs, and comments after each push or event.
2. **Select Unmet Obligation:** Read the PR description's [Review Ledger](review-records.md#unified-obligation-and-review-ledger) for the earliest unmet required gate.
3. **Batch Code Fixes:** Batch accepted review fixes into a single commit; rerun only affected proof and review.
4. **Clarify Unsupported Findings:** For contradictory or disproven findings, pin counterevidence and seek reviewer clarification before editing code.
5. **Delta Assessment & Reuse:** A changed commit SHA does not automatically invalidate evidence. Evaluate delta per [review-routing.md](review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain) and reuse valid verdicts. Never blanket auto-carry assertion, driver, prompt, schema, or config changes.
6. **Own Asynchronous Work:** Record actual job handle and wake condition in the [execution record](review-records.md#execution-record). Never exit at "review requested" without an active wake path.
7. **Synchronize Presentation:** Synchronize title, labels, and description ledger from current obligation state.
8. **Final Readiness and Merge:** When all draft and closing obligations pass, current checks are green, and receipts are published, synchronize `FINAL_READY`. If merge is authorized, execute merge before reporting.

## Canonical lifecycle

```
DRAFT
  → /es PASS @ SHA (or route exemption)
  → /er PASS @ SHA (or route exemption)
  → Table-selected source review PASS @ SHA
  → /visual-verification PASS @ SHA (when visual claims or media exist)
  → Mark ready-for-review (gh pr ready <N>)
  → /ready work: /green, comments, conflicts, regressions
  → Final closing /er and source review coverage applicable to candidate
  → FINAL_READY
  → Separate merge authorization
```

## Draft-phase final acceptance gates (in order)

While a PR is draft, satisfy these gates in order before undrafting (`gh pr ready <N>`):

1. **`/es`** — Evidence bundle passes per `../evidence-standards/SKILL.md` bound to tested SHA and verified applicable to candidate.
2. **`/er`** — Evidence review PASS (not PARTIAL/FAIL/INCONCLUSIVE) under [review-routing.md](review-routing.md) or justified exemption under [exceptions.md](exceptions.md).
3. **Table-selected source review** — Independent approval (`APPROVED at <SHA>`) per [review-routing.md](review-routing.md). `WITHHELD` does not satisfy the gate.
4. **`/visual-verification`** — Required for published media or rendered UI claims outside the one-liner fast path. An independent visual seat decodes media, inspects frames, and confirms `VISUAL APPROVED at <40-char-sha>`.

## Ready phase — finish `/ready`, then final reviews

Undrafting starts `/ready`; it does not establish readiness. Invoke `ready` for current-head `/green`, conflict resolution, and regression checks. Once ready-phase work stabilizes, complete final closing `/er` and source review coverage per [review-routing.md](review-routing.md). Reusing valid earlier approvals via delta assessment is permitted; duplicate reviews are not required when coverage applies. Report `READY` only when all closing obligations pass.

## Retained review integrations

Resolve and read `../advice/SKILL.md` or `../web-advice/SKILL.md`. If absent, report `UNAVAILABLE` and keep dependent gates open; never invent a replacement runner or self-certify approvals.

## Default PR route — `/prw`

Drive every PR through `/prw` by default. UI and user-facing changes always use `/prw`. Lighter non-production or doc-only paths drop intermediate stage transitions but retain all required checks, independent reviews, and merge authorization.

## Coding lifecycle — scale layers to risk

Explore → outcome spec → TDD (failing test first) → unit/integration tests → correctness review → targeted fixes. Collect expensive evidence only after code stabilizes.

## Merge authorization

Merge authorization follows `~/.codex/AGENTS.md` § Merge safety and explicit target-repository policy. Readiness does not confer merge authority.

## Review obligations by changed claim and risk

See [review-routing.md](review-routing.md#review-obligations-by-changed-claim-and-risk) for the 9-class risk and claim matrix.

### Markdown instruction-only route

See [review-routing.md](review-routing.md#markdown-instruction-only-route).

### Direct static route and evidence applicability

See [review-routing.md](review-routing.md#direct-static-route-and-evidence-applicability).

### Advice applicability

See [review-routing.md](review-routing.md#advice-applicability).

### Reviewer timeout and completion

See [review-recovery.md](review-recovery.md#reviewer-timeout-and-completion).

## Compact risk-based route

See [review-routing.md](review-routing.md#compact-risk-based-route).

## Change-impact review and test depth

See [review-routing.md](review-routing.md#change-impact-review-and-test-depth).

## SHA-binding rule (critical — applies to every gate in this chain)

See [review-routing.md](review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain).

## Slow CI — never block-wait

See [review-recovery.md](review-recovery.md#slow-ci--never-block-wait).

## CodeRabbit/Bugbot — optional advisory reviewers

See [review-recovery.md](review-recovery.md#coderabbitbugbot--optional-advisory-reviewers).

## Visible six-stage workflow (repository opt-in)

Only for a repository that explicitly adopts it, load [six-stage.md](six-stage.md): specification placement, stage titles/labels (`stage:0-spec` to `stage:5-final-approval`), and Stage 5 closing validation.

## Review records in the PR description

See [review-records.md](review-records.md) for PR description review ledgers and observational Scratch telemetry.

## Proportional exceptions and fast paths

See [exceptions.md](exceptions.md) for trivial-change, one-liner fast path, and documentation allowlist rules.
