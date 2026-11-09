---
name: pr-lifecycle
description: "Lifecycle contract for opening PRs, driving them green, and fixing CI. Triggers on: opening a PR, driving a PR to green, fixing CI on a PR, /green, /es, /er, /advice on a PR."
metadata:
  type: policy
---

# PR Lifecycle

This is the self-contained generic lifecycle contract. [PR Workflow Manager](../pr-workflow-manager/SKILL.md) is the command and branch entry point; keep its draft, stage, evidence-applicability and safety guidance in sync with this file.

## Codex review dispatch

Before selecting a review route, apply [the Codex review dispatch policy](review-routing.md#codex-review-dispatch) when the originating PR driver is Codex, including its delegated runtimes. It takes precedence over shared-default AI review and approval seats throughout this lifecycle and its linked references; it limits automatic AI review dispatch, not evidence collection, self-review, explicit requests, or independent gates imposed by higher-priority instructions or the target repository. Claude and agy keep the existing routes.

## Terminal goal and first-screen contract

An unqualified `/prw` (`/pr-workflow`) defaults to driving the PR to **`FINAL_READY`** across all applicable Stage 5 gates, unless explicitly requested earlier. One session goal covers all PR work.

- **Session Goal:** Detect capability through the supported CLI interface (native goal tool/API when available, or [cmux-goal](../cmux-goal/SKILL.md) when hosted in cmux; do not build a new controller, stop hook, scheduler, or deterministic policy engine). If supported and absent, automatically activate one task-scoped native session goal covering the requested PR(s) and accepted session PR work through `FINAL_READY` (or an explicit earlier user endpoint). Reuse a matching existing goal without recreating it; preserve an unrelated active goal unless the user explicitly authorizes replacement; do not create per-PR duplicate goals. Never revive or re-install a goal the user cleared, paused, or stopped without a fresh explicit instruction. When unsupported or unavailable, fall back cleanly to the driver and PR obligation/execution record without claiming native goal activation or blocking authorized work. Verify actual persisted goal state/readback and functioning ownership/resumption separately rather than treating goal prose, a printed `/goal` line, or command delivery as activation.
- **First-screen goal line (mandatory):** print exactly one of `Goal: activated via <cmux|tmux|native> (readback ok)`, `Goal: already active (reused|preserved-different)`, `Goal: not set (<reason>)`, `Goal: unsupported (<reason>)`, or `Goal: unverified (<reason>)` before the first PR-mutating action. Under plain tmux, use [cmux-goal](../cmux-goal/SKILL.md) § tmux (`bin/self_goal.py set`), which prints that line itself; silence is a contract violation. Read-only prerequisite inspection (including condition clause probes) may precede activation; activation and its truthful `Goal:` line must precede the first PR-mutating action (push, label, comment, edit). Write a user-set earlier stop or read-only limit into the goal condition as an "or" alternative, never as an extra required conjunct, so the Stop hook cannot deadlock.
- **Checkpoints vs. Completion:** PR creation, pushes, first approval, undrafting, and stage labels are intermediate checkpoints—never completion.
- **Separation of Authorities:** `FINAL_READY` certifies required obligations, checks, and receipts are complete. Merging requires separate authority under `~/.codex/AGENTS.md` § Merge safety and repository policy. If authorized, merge executes immediately before optional reporting.
- **Exit Conditions:** Return a final response only when:
  1. `FINAL_READY` is verified (and merge executed if authorized); or
  2. No authorized action remains, and an exact blocker, owner, and wake condition are recorded.

## Continuation through the requested endpoint

Execute the PR's next unmet obligation continuously through `FINAL_READY`. Status replies do not end the request: refresh live state, answer briefly, then resume. Own started jobs and delegated lanes through results under `parallelize-to-ceiling`; integrate their artifacts. Stop only at the requested endpoint, user stop, or genuine external blocker.

## Precedence and scope

Target repository instructions (`AGENTS.md`, `CLAUDE.md`) take precedence within their domain. Apply shared defaults only where silent; never remove a local requirement or infer an ungranted exception. Bind head repository, branch, SHA, and base from live PR metadata (`gh pr view`).

### Existing authorization and prepared plans

An existing user or standing authorization keeps covering the same action, target and outcome within its stated spending, request and retry bounds. Re-pin and review each newly prepared plan or plan SHA before execution; that is an integrity check, not a request for renewed human approval. A required validation or evidence step does not itself authorize extra paid work; obtain new authority only for paid work outside the authorized scope or beyond its bounds. Other merge, security, retry, source-integrity, budget and evidence gates can still block execution.

## The autonomous completion loop

Drive the PR through this continuous cycle without stopping at intermediate checkpoints:

1. **Refresh and Choose the Next Action:** On every event or resume, first re-read live PR state (head, base, checks, comments, merged/closed, other writers); stop work already satisfied, closed or owned elsewhere. Then read the earliest unmet [Review Ledger](review-records.md#unified-obligation-and-review-ledger) gate and actual returned artifact:
   - **Missing review input:** produce or retrieve exactly that input; independent work continues. Incomplete packets never approve.
   - **Truncated read:** the same reviewer recovers unread ranges within its attempt deadline ([review-recovery.md](review-recovery.md#reviewer-timeout-and-completion), [static-review](../static-review/SKILL.md), [advice](../advice/SKILL.md)); partial votes never combine.
   - **Failed claim or supported blocking defect:** inspect its source or artifact. Fix and reverify every supported behavior blocker; batch affected proof and review. For unsupported claims, produce proof when the task needs them; otherwise narrow them honestly. Rewriting alone is not a fix. Nonblocking findings do not hold merge.
   - **Stale or ambiguous premise:** verify against current source; seek reviewer correction before dependent edits, never fabricating fixes or silently discarding findings.
   - **Candidate or base changed:** inspect the complete delta; request only affected judgment per [review-routing.md](review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain).
   - **Verdicts applicable, next action authorized:** start it now; optional polish stays off the critical path.
   - **Proven hold:** record handle, blocked action and resumption trigger; continue independent authorized work.
   While subagents, reviewers or CI run, first do every authorized step not needing their result (publish finished evidence, record received receipts, dispatch the next obligation). Only when none remains, make one longest-timeout wait or yield; never repeat short waits, sleeps or status pings. An acknowledged dispatch is not pickup: verify actual reviewer/job start, record its handle and callback or resume mechanism, and keep ownership through returned artifacts.
2. **Own Asynchronous Work & Dependencies:** Record each actual job handle and verified callback or resume mechanism in the current execution record; written wake conditions alone do not cause resumption. Retain ownership of blocking dependency PRs through their required endpoint or verified accepted handoff; delivery alone does not unblock the parent. While waiting, integrate completed artifacts and begin any authorized next obligation that does not depend on the outstanding result.
3. **Synchronize Presentation:** Synchronize title, labels, and description ledger from current obligation state.
4. **Final Readiness and Merge:** When all draft and closing obligations pass, current checks are green, and receipts are published, synchronize `FINAL_READY` (scoping readiness strictly to the PR's own applicable obligations, while keeping any additional unreviewed runtime or measurement closure claims marked `UNVERIFIED` per [review-records.md](review-records.md#unified-obligation-and-review-ledger) without holding the PR for an optional report).
   - **Headline claim-to-proof check before `FINAL_READY`:** Before synchronizing `FINAL_READY` (or closing a broader task claim alongside a PR), check each headline claim directly against its actual proof:
     - **Real caller for activation/runtime claims:** A test harness exercising a substitute helper function or synthetic state proves only that helper's logic, not the real CLI/caller entry point; runtime activation and continuation must be observed through the actual supported caller.
     - **Source events and arithmetic for metrics/reports:** Trace headline numbers to raw source timestamps/events, verify timestamp subtraction per attempt, leave unobserved intervals `UNKNOWN`/`null` rather than `0`, avoid keyword/repo heuristics for route claims, and label pre-change window cutoffs as baselines rather than post-change effect.
     - **Exact reviewed artifacts for coverage:** Approving a PR diff covers only the exact files and SHA reviewed, never separately generated audit scripts, measurements, or external closure claims outside that diff.
     Missing proof stays `UNVERIFIED`; a stage label or narrower file approval cannot fill it.
   Once `FINAL_READY` is verified and merge authority holds at the exact head, execute the merge immediately before optional post-merge reporting, telemetry snapshots, or secondary bookkeeping so optional bookkeeping cannot delay an authorized merge (while mandatory pre-merge gates, exact-head verification, and required receipt publication/readback still precede merge).

**Handoff transitions:** The active driver owns both handoffs without an unattended gap:
- **Evidence ready to review start:** When required proof is complete and readable at the candidate SHA (`evidence_ready_at`), dispatch the required review immediately (`review_requested_at`) and verify actual reviewer pickup (`actual_review_started_at`); acknowledgment alone is not review start.
- **Reviewer return to next action:** Immediately on reviewer return (`review_return_at`), start the next substantive action (`next_substantive_action_started_at`): apply supported fixes, advance the stage, or execute an authorized merge. Keep any independent authorized work moving while another result is pending.

## Canonical lifecycle

```
DRAFT
  → Route selection & exemptions (qualified Markdown instruction-only route skips separate /es and /er; documentation allowlist exempts /er but retains applicable /es)
  → When pinned source ready: Table-selected source review PASS @ SHA
      (runs concurrently with independent evidence work)
  → For routes requiring evidence:
      1. Complete evidence bundle (/es @ SHA; early preflight != final PASS)
      2. Required independent visual findings (/visual-verification PASS @ SHA, for visual claims)
      3. Closing evidence review (/er PASS @ SHA, adjudicating evidence + visual findings)
  → Mark ready-for-review (gh pr ready <N>)
  → /ready work: /green, comments, conflicts, regressions
  → Final closing /er and source review coverage applicable to candidate
  → FINAL_READY
  → Separate merge authorization
```

## Draft-phase final acceptance gates (in order)

Before undrafting (`gh pr ready <N>`), select route and satisfy applicable gates:

1. **Route selection and exemptions** — Classify the diff under [review-routing.md](review-routing.md). Positively qualified Markdown instruction-only changes do not force separate `/es` or `/er` adjudication; they satisfy draft review through route-defined scenario review(s) and Markdown structure checks. Ordinary documentation-only exceptions under [exceptions.md](exceptions.md) exempt `/er` under their exact allowlist, but retain applicable `/es` (proportionate diff/link/structure checks; no runtime proof added to ordinary docs merely by size).
2. **Concurrent source review** — Table-selected independent source review (`APPROVED at <SHA>`) can start as soon as pinned source is ready, running concurrently with independent evidence work.
3. **Evidence bundle (`/es`)** — When evidence is required, prepare the complete evidence bundle bound to tested SHA per `../evidence-standards/SKILL.md`. An early evidence preflight checks artifact completeness, but is not final PASS.
4. **Independent visual findings (`/visual-verification`)** — For published media or rendered UI claims outside the one-liner fast path, an independent visual seat decodes media, inspects frames, and confirms `VISUAL APPROVED at <40-char-sha>` before closing evidence review (requiring two independent visual seats before undraft for user-visible headline claims unless a qualified one-vote UI route, one-liner fast path, or explicit `SINGLE-SEAT` limitation applies, preserving independent author/evidence-seat rules per [review-routing.md](review-routing.md#visual-verification-and-seat-requirements)).
5. **Closing evidence review (`/er`)** — When `/er` is required, obtain closing evidence review PASS (not PARTIAL/FAIL/INCONCLUSIVE) under [review-routing.md](review-routing.md), adjudicating complete evidence and required visual findings.
6. **Undraft** — Execute `gh pr ready <N>` once all applicable draft-phase gates pass.

## Ready phase — finish `/ready`, then final reviews

Undrafting starts `/ready`; it does not establish readiness. Invoke `ready` for current-head `/green`, conflict resolution, and regression checks. Once ready-phase work stabilizes, complete final closing `/er` and source review coverage per [review-routing.md](review-routing.md). Reusing valid earlier approvals via delta assessment is permitted; duplicate reviews are not required when coverage applies. Report `READY` only when all closing obligations pass.

## Retained review integrations

Resolve and read `../advice/SKILL.md` or `../web-advice/SKILL.md`. If absent, report `UNAVAILABLE` and keep dependent gates open; never invent a replacement runner or self-certify approvals.

## Default PR route — `/prw`

Drive every PR through `/prw` by default. UI and user-facing changes always use `/prw` unless an explicit human instruction overrides it for that PR. Lighter paths (documentation-only, qualified non-production changes, backup/mirror repos, or very small changes) drop intermediate stage transitions but retain all required checks, independent reviews, and merge authorization. When unsure, use `/prw`. See [review-routing.md](review-routing.md#default-pr-route-and-lighter-paths) for full lighter-path eligibility and exclusions.

## Coding lifecycle — scale layers to risk

Explore → outcome spec → TDD (failing test first) → unit/integration tests → correctness review → targeted fixes. Collect expensive evidence only after code stabilizes.

## Merge authorization

Merge authorization follows the shared size-tiered rule in `~/.codex/AGENTS.md` § Merge safety and explicit target-repository policy. This skill neither requires nor waives a human `MERGE APPROVED` phrase where the governing rule does not; explicit local approval requirements stay in force. Earlier-SHA review applicability for readiness does not satisfy a stricter exact-head condition on a separately authorized automatic-merge route; keep that merge condition unless the human explicitly changes it. Readiness or this refactor grants no new permission.

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

### Documentation-only exceptions

For a diff that may be documentation-only, see [exceptions.md](exceptions.md#documentation-only-ci-exception): it owns the CI exception and the narrow `/er` allowlist. Use its existing [canonical changed-path helper](scripts/pr-base-changed-paths.sh) rather than by eye.
