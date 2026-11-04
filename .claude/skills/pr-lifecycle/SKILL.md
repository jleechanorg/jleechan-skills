---
name: pr-lifecycle
description: "Lifecycle contract for opening PRs, driving them green, and fixing CI. Triggers on: opening a PR, driving a PR to green, fixing CI on a PR, /green, /es, /er, /advice on a PR."
metadata:
  type: policy
---

# PR Lifecycle

This is the self-contained generic lifecycle contract. [PR Workflow Manager](../pr-workflow-manager/SKILL.md) is the command and branch entry point; keep its draft, stage, evidence-applicability and safety guidance in sync with this file. Before applying a generic rule, read the target repository's `AGENTS.md`, `CLAUDE.md` and scoped instructions; never infer an opt-out from a repository's name or apparent purpose. Design documents explain rationale; this workflow does not need one.

**Shared default:** unless a repository has opted out or specified a different flow, open every new PR as DRAFT (`gh pr create --draft`) and keep it draft until quality is proven. Marking it ready for review is a deliberate, gated action, not a side effect of pushing code.

## Precedence and scope

This skill owns shared defaults for lifecycle stages, generic review routing, proportional evidence, SHA applicability and receipt publication. A target repository's explicit local contract, including a declared workflow opt-out or adapter, takes precedence within its domain. Apply shared defaults only where it is silent; never use this contract to remove a local requirement or infer an exception. Domain-specific proof for the actual claim, and separate security, credential, source-ownership and merge-authority restrictions, stay in force. Current explicit user instructions govern within those permissions.

### Existing authorization and prepared plans

An existing user or standing authorization keeps covering the same action, target and outcome within its stated spending, request and retry bounds. Re-pin and review each newly prepared plan or plan SHA before execution; that is an integrity check, not a request for renewed human approval. A required validation or evidence step does not itself authorize extra paid work; obtain new authority only for paid work outside the authorized scope or beyond its bounds. Other merge, security, retry, source-integrity, budget and evidence gates can still block execution.

## Canonical lifecycle

The full state machine. Other files (`pr-green-definition`, `/green`, `CLAUDE.md`, `AGENTS.md`) point here instead of restating it:

```
DRAFT
  → /es PASS @ SHA
  → /er PASS @ SHA (unless the narrow /er documentation allowlist, explicit trivial-change exception, compact-route review coverage accepted by local policy, or another repo-exempted class applies)
  → /advice APPROVED @ SHA when required by Advice applicability below
  → /visual-verification PASS @ SHA when gate 4 applies and the one-liner fast path does not (media published, or a rendered/displayed-data claim)
  → mark ready-for-review (gh pr ready <N>)
  → /ready work: /green, comments, conflicts, and regression checks
  → final /er PASS applicable to the candidate when required
  → final /advice APPROVED applicable to the candidate when required
  → READY
  → separate merge authorization: apply `~/.codex/AGENTS.md` § Merge safety and the target repository's explicit merge contract; readiness and review receipts do not themselves grant authority
```

Each arrow is a gate. A changed SHA triggers the delta assessment in § SHA-binding rule, not automatic invalidation or a mandatory repeat review: keep the original tested/reviewed SHA and record why its evidence and verdict still apply to the candidate.

## Retained review integrations

The shared catalog keeps host-installed `/advice` and `/web-advice` integrations rather than installing them. Before invoking either, resolve and read its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package; for a remote invocation, check the corresponding skill on the target host. If a required integration is absent, report it `UNAVAILABLE` with the missing package name and never invent a replacement runner or claim an approval. Continue independent authorized work, but leave every dependent readiness or plan-approval gate unmet: a missing `/advice` leaves its applicable quorum unmet, and a missing `/dot` or requested `/wa` continues through the reviewer fallback below with dependent substantive evidence gates open until proved. Existing review quorum, external-disclosure authorization and optional-review rules still apply.

## Compact risk-based route

Apply the trivial-change and one-liner fast paths first; this route adds no review requirement to a change they cover. For a remaining bounded, low-risk change whose claim is fully proved by source inspection and focused offline checks (for example an offline sampler/analyzer, or a small error-classification branch with caller regressions, unchanged rendering and unchanged service contracts), the PR body records the outcome, acceptance, checks and limitations. A large total diff from tests, fixtures, scripts or documentation is not a reason to escalate. Require the focused regression, the applicable CI/mergeability checks, and one independent reviewer of the complete diff and its relevant correctness or operational safeguards. That reviewer confirms compact-route eligibility from the changed claims, actual diff effects and risk, not from the PR description. Reuse that review for later stages while its scope still applies. Publish a separate evidence receipt only when the claim, a repository rule or the user needs one.

The route skips the seven-element committed spec, duplicate stage reviews, and video, live-provider, native or campaign runs that prove no changed claim. Mocks still do not prove integration behavior. A probe that can mutate state or incur a charge needs explicit execution, action, account, campaign and provider authorization in its controls, and those controls are independently reviewed before use. Existing test credentials alone do not require a product journey.

The route is a shared-default exception only where repository instructions permit it. It excludes changes to: authentication or trust boundaries, tenancy, permissions or security controls; credential creation, export, rotation or revocation; deploy, signing, release, IAM or destructive operations; CI/test selection or configuration that changes execution or proof; agent behavior or policy; shared-fixture meaning; assertion, coverage or evidence weakening; production mutation, persistence, model policy, prompts, schemas, new network paths or retry budgets; and approval, merge, review, evidence or security policy. Focused caller regressions or an offline mechanically safe sampler do not by themselves disqualify a change; skipped assertions, changed shared-fixture meaning, changed CI selection or changed agent policy do. The reviewer checks these against the actual diff effects. Splitting work or relabeling the claim or risk cannot create eligibility. Named risk-specific proof, explicit user-required proof, repository-local requirements and separate merge, credential, destructive and spending authority remain in force. The route skips only intermediate stage-title/label ceremony: a compact change still passes the applicable lifecycle gates and current-candidate checks, and reaches Stage 5 closure only after its focused checks and review pass.

## Advice applicability

Outside the compact route, under shared defaults, `/advice` is optional for a PR under 50 changed lines and required for a PR of 50 or more, at both the draft and final ready-review phases. A specifically requested review still runs. This size rule supersedes broader docs/test/non-production `/advice` exemptions outside the compact route; it does not waive independent safety/code review, security, evidence, CI or merge authorization. Initial gate applicability and later re-review depth are separate decisions.

A high-risk change keeps its required independent coverage when `/advice` is optional. Follow the repository's required independent code/safety lane; if none is named, a named independent full-diff code/safety reviewer (not the author or orchestrator) inspects the risk controls and records exact SHA, complete coverage, findings and verdict. Evidence-only review does not satisfy this code-review gate. Stricter repository lanes and quorums still apply; this fallback does not make `/advice` mandatory for an under-50 PR.

Count additions + deletions across the complete PR diff at the live head against its actual base, including every production and non-production file: not net lines, production-only lines or the latest commit. Use complete GitHub PR totals or the equivalent verified base...head Git diff, and record both refs and the count. An unknown or incomplete count, or uncounted binary changes, cannot establish the under-50 exception. Recompute after any head or base change. Examples: +25/-24 = 49, optional; +25/-25 = 50, required; +10/-0 code plus +40/-0 docs = 50, required.

### Reviewer timeout and completion

For `/pr-workflow` and other lifecycle reviews, each reviewer attempt has a default wall-clock limit of 1800 seconds (30 minutes), starting when the request is queued or sent. Queueing and delivery wait count; progress, partial output or a new message do not reset it. An explicit user-specified limit, shorter or longer, governs that attempt, and a later specific user instruction to await a named reviewer overrides the deadline for that attempt even without a number. If the reviewer is explicitly unavailable or quota-blocked, stop the attempt and route to the fallback immediately. Do not keep waiting on the same attempt.

A timed-out `/dot`, requested `/wa` or other non-`/advice` supplementary reviewer attempt is recorded `TIMED_OUT` with request and timeout times and any partial receipt or findings, never PASS. It is discharged at timeout, and the workflow continues through the reviewer fallback: a passing `/er` on the finished evidence plus `/advice` approval from two independent reviewers at the same head. The two-vote quorum is mandatory for this substitution only; the general under-50 advice threshold is unchanged. A `/wa` timeout proves none of the browser-only validation it was meant to review. Required substantive safety, evidence and domain checks stay open until proved by applicable evidence or an eligible replacement review; a timeout grants neither readiness nor merge authorization. Assess late substantive findings when they arrive; they can reopen the affected gate.

If an `/er` reviewer times out, record `TIMED_OUT` and continue independent work, but keep the evidence-review gate open until an eligible replacement completes `/er` with an applicable PASS. `/advice` or another supplementary review is not proof that the evidence was reviewed.

`/advice` keeps its applicable two-independent-reviewer quorum. Replace a failed or timed-out seat with another eligible independent reviewer, and keep replacing until quorum is reached or no eligible attempt remains; record each seat and outcome. Below quorum the result is `WITHHELD`, not approval. A late substantive `/advice` finding is still assessed after a replacement has voted.

`/wa` (`/web-advice`) is optional, never an implicit lifecycle gate: run it only when requested or separately authorized, and keep its real verdict if it runs. Existing standing authorization and any governing workflow that requires /wa still apply. Neither optional review permits ignoring a known correctness or safety blocker.

## Visible six-stage workflow (repository opt-in)

Repositories that explicitly adopt this section use these complete stage rules; others keep the generic lifecycle and their existing local requirements.

### Specification and artifact

Outside the compact risk-based route, every specification records seven elements: outcome, non-goals, acceptance, user stories (or an explicit no-user-facing-change reason), proof plan, mock (or justified exemption), and risk. Keep the specification and implementation in the same PR. For the complete actual-base...head diff, counted as in § Advice applicability:
- Under 50 total additions+deletions: use PR-body `## Specification`, including for high-risk small changes.
- 50 or more, or an incomplete, uncountable or binary diff: commit the seven-element specification in the same PR.
- Crossing that boundary without the committed specification returns to Stage 0.

Stage 0 is complete only when its artifact exists in an open PR at that location. A commit on a branch with no PR is not a Stage 0 artifact: no reviewer, `/advice` or `/dot` can bind to it. Artifact placement does not waive high-risk independent full-diff review or required real proof. Do not split coherent work to evade review thresholds.

### State readback before reporting a blocker

Before reporting work as uncommitted, unpublished, missing a PR or otherwise blocked, run and quote `git status --porcelain`, `git log --oneline -1` and `gh pr list --head <branch> --state all`. A blocker claim without those outputs is unverified; report the measured facts, not remembered ones.

### Stage, title and labels

On creation, after each push, and when scope or status changes, refresh the descriptive title to match the implemented behavior and remaining work, then read back the published title. Preserve provenance and use the earliest unmet stage; a title change never completes or advances a gate.

Use one stage label, one two-letter stage prefix and one recognized trailing stage suffix, naming the same stage, for example `[er] Improve campaign loading [evidence review]`. Preserve the substantive title, unrelated tags/labels and all holds; repository-required author/tool provenance tags go immediately before the suffix, which goes last. On transition or migration, remove only recognized stage markers at the start or end, then add exactly one current prefix and suffix. Do not strip other bracketed text or invent a tool/model identity. Suffix-only titles gain their matching prefix on synchronization.

| Stage | Title prefix | Title suffix | Label | Work and exit proof |
|---|---|---|---|---|
| 0 Specification | [sp] | [specification] | stage:0-spec | Draft opened; outside the compact route, seven elements, stories and mock/exemption complete in the required artifact. The compact route records its outcome, acceptance, checks and limits in the PR body. |
| 1 Coding | [cd] | [coding] | stage:1-coding | Scoped implementation and applicable causal RED/GREEN, focused checks and correctness review complete. |
| 2 Evidence generation | [ev] | [evidence generation] | stage:2-evidence | Applicable /es proof generated and delivered, original tested SHA and claim map recorded, or justified exemption. |
| 3 Evidence review | [er] | [evidence review] | stage:3-evidence-review | Applicable /er and draft review route satisfied by independent verdicts whose coverage applies to the candidate. The review SHA need not equal HEAD when the delta assessment supports reuse. |
| 4 CI and undraft | [ci] | [CI and undraft] | stage:4-ci-undraft | Undraft and complete /ready's CI, comments, conflicts and cross-thread regression work with current-candidate /green using only documented exceptions. Its closing reviews belong to Stage 5, not this exit. |
| 5 Final approval | [fa] | [final approval] | stage:5-final-approval | Final-phase review obligations and (for user-visible changes outside the one-liner fast path) independent AI visual approval (`VISUAL APPROVED at <40-char-sha>`) satisfied by applicable independent approvals, with findings resolved or explicitly deferred as allowed. Earlier review SHAs may remain valid by reasoned assessment; merge authority is separate. |

A stage name describes remaining work: [final approval] does not mean approved or merged.
Orthogonal hold labels are hold:reviewer, hold:operator, hold:conflict and hold:quota; they never replace the stage. Whoever applies a hold records in the PR body who applied it, the quoted instruction it rests on with its source and date, and the concrete, checkable condition that lifts it. A hold label is a pointer, never authority. The driving agent removes a hold sourced from a handoff, coordinator or agent note when its lift condition is met or a later live user message explicitly covers the held action, and the removal note cites that evidence. A hold sourced from a live human instruction, or guarding a user-only item in shared policy (merge, destructive action, spending, credentials), is lifted only by that human or by that item's own approval; report only these as user-only gates. A hold on "deploys" does not cover PR preview deployment unless it names previews: preview deployment is a lifecycle step, not a release.

For each transition, read the actual head/base, title, labels, body, artifacts and findings; choose the earliest unmet stage; synchronize title, label and `## PR Stage`; and read back all three. Place `## PR Stage` **below** the body's opening line-delta sentence (`Line deltas: prod +X/-Y across N files; non-prod +A/-B across M files.`), which stays the first line; a stage sync never displaces, buries or restates it. If the body has no such opener, add a measured one before inserting the stage block. The body records stage/status, accountable owner, next action or exact blocker and resumption trigger, actual head/base, full diff count and review route, and original tested/reviewed SHAs with current applicability.
Verify label existence with authorized tooling and provision labels only within explicit scope. A denied, unavailable or uncertain operation is a partial state to report, not permission to bypass it. A successful title update alone is not synchronization. No bulk adoption from draft status or CI colour.

### Review routes for opted-in repositories

Eligible PRs use the compact risk-based route above. Others use § Advice applicability and its independent-coverage rules; "large" includes an incomplete or uncountable diff. Optional /advice does not make all independent review optional: this route names the alternative, and only the narrow trivial-change exception can waive that extra lane.
At Stage 3, outside the compact route, small PRs need /advice OR independent /dot approval unless the trivial-change exception applies; large PRs need both. Stage 5 applies the same route to final obligations, and large PRs attempt /wa best effort when authorized. Compact PRs reuse their one independent complete-diff review across applicable stages; that does not waive separately required policy approval or named safety gates.
An explicitly requested /wa stays an attempt in the route. Honor existing standing authorization without asking again, and apply § Reviewer timeout and completion, including its user-override clauses and its `/er` plus two-vote `/advice` substitution when /wa times out or is unavailable. Record the actual disposition and never claim browser-only validation occurred. An unavailable or timed-out best-effort /wa is disclosed, not turned into approval.
Resolve /dot through an existing authorized independent Dot reviewer, not the author or orchestrator. If the route needs /dot and the first Dot is busy, send the same request to the next configured Dot account in rotation; § Reviewer timeout and completion (including its user-override clauses) limits each account's attempt, queue and send wait included. If Dot is busy, times out or is unavailable, that section's reviewer fallback satisfies the /dot leg; record `/dot busy: /er + /advice substituted` with the accounts tried, request/timeout times and outcomes. A /dot verdict arriving after its attempt timed out neither counts toward the route nor replaces the fallback, but its substantive findings are assessed and can reopen the affected stage. Required substantive evidence gates stay open until proved. A /dot receipt names its reviewer, declared source/evidence scope, original tested/reviewed SHAs, actual inspection and actions, verdict, coverage, findings/limits and a retrievable receipt. An acknowledgment, a capability claim or another reviewer's verdict is not /dot approval, and the covered scope must satisfy the requested gate: narrow visual approval is not full source approval.
**Mandatory AI Visual Approval Gate before Stage 5 (`stage:5-final-approval`) and Merge:** outside the compact route, every user-visible change not covered by the narrow documentation-only / zero-UI-impact non-visual exemption or the one-liner fast path (§ Proportional exceptions and fast paths) needs, for Stage 3 -> Stage 5 promotion and merge readiness, an explicit `VISUAL APPROVED at <40-char-sha>` from an AI reviewer independent of the author **and** of the `/er` evidence seat, as draft gate 4 (`/visual-verification`) requires: an `/advice` visual inspection that downloads and inspects the actual rendered stills/frames, `/dot`, or an `/er` visual lane run by a seat other than the one that produced or reviewed the evidence. A reasoned delta assessment may instead preserve an earlier evidenced SHA whose rendered UI did not change. A pending request (e.g. `/dot: REQUESTED, pending`), a code-only `/advice` substitution or a link-existence check is NOT a visual approval PASS; if `/dot` is unavailable or pending, the driver MUST obtain the approval from `/advice` or such an independent `/er` visual lane before labeling `stage:5-final-approval`. For each user-visible claim the record MUST give the before (where one exists) and after artifact links, what the reviewer saw in each (changed element, state, viewport) and a matches-claim verdict, bound to the evidenced SHA (the approved head, or the earlier SHA a delta assessment preserves); a bare stamp or approver name is not a PASS. Repositories may require the findings as a PR-body table and check its presence and SHA binding in CI.
Reviewer eligibility and quorum stay owned by their review skills. The author or orchestrator cannot self-award an independent vote, a bot or orchestrator acknowledgment is not an independent review, and reusing a verdict never creates an extra voter. A technical /dot verdict is evidence of review, never human permission to merge, change policy or operate another scope.
Draft and final obligations are distinct: check whether an existing verdict's scope and phase cover the closing obligations instead of copying a draft status, and request only the missing or affected review.

### Regression and synchronization

Use the earliest unmet gate: changed or missing requirements or specification -> Stage 0; implementation defect or material change -> Stage 1, then affected proof; missing or invalid evidence -> Stage 2; missing draft review coverage -> Stage 3; only CI, conflict or readiness work -> Stage 4; only final approval -> Stage 5.
A head or base move alone needs delta assessment and current-candidate /green, not a full evidence/review restart. After Stage 4, a harmless change can reuse applicable reviews but still refreshes /green before final completion. Material policy, assertion, fixture, driver, configuration, prompt or schema changes reopen the gates they affect. Keep original receipts and timestamps; never rename historical evidence as a new run.

When changing stage names, title suffixes, labels, review routes or applicability rules, keep this contract, the pr-workflow-manager entry point and repository adapters in sync. Repo adapters reference this skill instead of copying its tables. Check affected references and report any stale or unavailable installed copy; a source push does not install or synchronize another computer.

### Evidence attached to every stage exit

Outside the compact route, attach evidence to the PR description as retrievable artifact URLs plus a sanitized gist receipt URL; under the one-liner fast path the PR-body before/after quote plus current-head CI is the receipt and no gist is needed. Proof only in a comment, local path, chat or promised upload is insufficient. Every completed stage 0–5 has an appropriate receipt; specification proof does not need future runtime evidence. Stage 2 produces the acceptance-evidence package, not the first evidence of any kind: earlier stages publish their own specification or focused-check receipts. One version-pinned gist may hold distinct stage/event anchors without ceremonial duplicate uploads.

Compact PRs record the outcome, focused commands and results, tested or reviewed SHA, limitations and independent reviewer in the PR body, adding artifact links only when needed to substantiate the claim. Other PRs use the full evidence index: stage, disposition (`COMPLETE`, `NOT REQUIRED`, `REUSED` or `BLOCKED`), candidate head/base, full diff classification, original tested/reviewed SHAs and execution timestamps, applicable commands/environment/results, artifact hashes, reviewer and coverage, limitations, and exemption or reuse rationale. Keep original receipts and append superseding events instead of restamping evidence.

Embed applicable screenshots and playable video inline in the PR description next to direct original-media URLs, and verify the URLs resolve and intended reviewers can view the media. A gist link alone does not satisfy applicable visual proof, and inline embedding is not visual *review*: draft gate 4 (`/visual-verification`) is a separate, independent reading of the frames. Docs, logs and source-only trivial-copy claims may record a specific media `N/A` reason; never manufacture media to fill a field. Apply every applicable `/es` integrity, provenance, sanitization and claim-sufficiency requirement before declaring the stage passed.

Missing, inaccessible or unauthorized publication is `PUBLICATION BLOCKED`: continue independent work, but do not claim that stage exit complete. Missing or failed required checks are not exemptions. Read back the description, and keep evidence history and title/stage-label consistency.

## Default PR route — `/prw`

Drive every PR through `/prw` (`/pr-workflow`) by default, using this generic lifecycle unless the repository opted into the visible six-stage workflow. UI and other user-facing changes always use `/prw` unless a human explicitly overrides it for that PR. A lighter path is allowed only for:

- documentation-only changes;
- non-production changes (documentation, tests, fixtures, and skill/instruction updates that do not alter approval, merge, review, evidence or security policy), subject to the repository's non-production classifier;
- backup or mirror repositories;
- an explicit human instruction to skip `/prw` for that PR;
- a very small change that needs no evidence or `/es`, such as a fix to a helper script with no user-visible effect.

The non-production and small-change bullets never cover a class excluded in § Proportional exceptions and fast paths, a high-risk class in § Coding lifecycle — scale layers to risk, or a test change that weakens an assertion; those always use `/prw`. The lighter path drops the `/prw` driver and the intermediate stage title/label transitions (`Stage 0–3`), not the work those stages gate: in opted-in repositories, keep the specification in its prescribed location and synchronize `[fa]` / `stage:5-final-approval` once applicable gates pass. Every applicable gate still applies: CI or its documented exception, `/green`, the `/advice` threshold, at least one independent adversarial full-scope LLM review of any agent-instruction change regardless of size, any repository-required review, evidence or `/dot` route, and merge authorization. When unsure, use `/prw`.

## Proportional exceptions and fast paths

These claim/risk rules apply to the generic lifecycle and to opted-in repositories; only the stage/title/label machinery is opt-in.

Classify the complete diff by effects and claimed outcomes, not file extension, a non-production label or the latest commit size. For an entirely harmless documentation/mechanical change, or an obvious display-copy-only change, under 50 total additions+deletions, a compact `/es` receipt with source before/after inspection and proportionate checks can suffice. Record `/er` and the extra independent `/dot` lane as `NOT REQUIRED — trivial-change exception`, never a fabricated PASS or reviewer vote. This exception applies at both review phases; explicitly requested reviews remain required. In opted-in repositories the seven-element specification may be concise but stays required in its prescribed location. The >=50 advice boundary is unchanged.

The exception excludes application prompts, schemas, selectors, URLs, interpolation, format/control strings, authentication, permissions, consent, payments, legal meaning, and approval, merge, review, evidence or security policy. Agent instructions that change these rules are not harmless documentation: this workflow policy cannot exempt its own review. A one-line change can be high risk. Mixed diffs follow the requirements of their affected claims.

**One-liner fast path.** A PR qualifies when the trivial-change exception applies and its production change is at most 10 added+deleted lines of display copy, comments, or removal of unused or unreachable text. Eligibility comes from the diff, not the PR's stated claim: the production diff changes only literal text, with no layout, style, component, condition, interpolation, data or control-flow change, and its only non-production changes are the pinning-assertion edits this path requires and literal-text updates in existing tests. The changed text necessarily renders differently and is the claim; any rendered, layout, interaction or displayed-data effect beyond it puts the diff off this path. It is complete when it has:
- current-head CI green, or the documentation-only CI exception;
- a clean merge-tree;
- a PR body that quotes the before/after source lines;
- where a test already covers the text, an assertion that pins the new literal (or, for a pure removal, asserts the removed text is absent) and that fails when run against the old text.

Its claim is source-literal and it publishes no media, so draft gate 4 (`/visual-verification`) and visual review do not apply, and it needs no gist, inline media, committed capture drivers, `/er`, visual-findings table or stamp, or `/dot`; record each as `NOT REQUIRED — one-liner fast path`. A later delta that changes the quoted text, the pinning assertion, or anything that renders the text re-runs these checks; other deltas reuse them under § SHA-binding rule, except that current-head CI is never reused. The compact `/es` receipt and the Stage 2–3 receipts are the PR-body before/after source quote, the pinning assertion's failing output against the old text (an excerpt in the PR body, where a test covers the text), and the current-head CI result; the `**Evidence**:` marker may point to that PR-body section or the PR diff URL with the head SHA instead of a gist. In opted-in repositories the specification may be one line per element and these checks satisfy Stages 2–3; Stage 4 (undraft, comment resolution, conflicts and current-candidate `/green`) still applies before Stage 5. Precedence follows § Precedence and scope: this path overrides a repository's generic "user-visible changes need media, gists or visual approval" wording only where that repository delegates proportional exceptions to this contract (for example a "Shared proportional-evidence applicability" pointer); otherwise the repository's explicit requirement governs. Reviewers must not raise P0/P1 findings for proof this path waives; such notes are P2 at most. Merge authority and the separate merge gates are unchanged, and an explicit user request for proof still applies.

For Markdown-only instruction changes, focused proof may use the complete base-to-head source diff, link/heading/structure checks, and scenarios against both text versions. Application runtime, browser/media and real-provider proof are `N/A` only when no changed claim depends on them. Markdown containing automation, prompts, schemas or machine-consumed contracts still needs its applicable proof. Changed agent instructions still need at least one independent adversarial full-scope LLM review, plus any applicable `/advice` quorum and repository-required `/dot` route. Reuse one version-pinned receipt across applicable stages, keeping original SHAs and recording candidate applicability; rerun only proof the delta affects.

For logging-only changes, use bounded execution showing the actual emitted log, level and fields, with original source SHA, command, timestamps and sanitized output; focused `/er` may approve that emission claim without unrelated browser or provider runs. Check privacy and side effects: new sensitive data, destinations, machine-consumed contracts, alerts, expensive expressions, exceptions, mutation or retries need their affected proof. Emission alone does not prove downstream ingestion or alert delivery.

For alerting-only changes, focused `/es` and `/er` may prove the alerting claim with a controlled real trigger through the changed emission or dispatch path and receipt of the actual alert at each claimed destination. Keep the source SHA, environment, timestamp, correlation and delivery IDs when available, sanitized alert text, and logs plus provider or destination receipts. Video, screenshots, browser or native gameplay journeys and paid LLM runs are not required merely to prove an alert fired. Direct sink sends prove transport only; mock, unit and source inspection cannot prove live delivery. Mixed diffs keep the affected proof for non-alert changes; privacy and security checks, CI, code-review, quorum and merge permissions are unchanged. A PR merely named for alerts gets no broad exemption, and an alert-only claim carries no universal mandate for native or player journeys.

Non-production tests, fixtures, drivers and CI changes need proportionate checks of changed assertions and affected contracts, not automatic runtime capture and not automatic exemption. Never weaken assertions or mock away a claimed boundary to qualify.

Source-only display-copy inspection proves the literal change, not rendering, accessibility or localization; media may be explicitly `N/A` for that bounded claim. A claimed static appearance needs real rendered proof and an inline screenshot; interaction or streaming claims keep their applicable video requirements. These narrow exceptions govern generic all-UI-media wording in linked skills; named risk-specific requirements, explicit user-required proof and safety controls still apply.

## Coding lifecycle — scale layers to risk

Order: explore → outcome spec (no code) → code-level design when useful → TDD (fresh failing test first) → unit + relevant integration tests → coder correctness checkpoint → formal code/evidence review → narrow fixes until a genuine human dependency. Batch findings, preserve passing lanes, and recheck only the affected behavior.

| Change class | Layers |
|---|---|
| Wording-only / small low-risk (including a small code fix) | Apply the trivial and one-liner fast paths first. Skip the standalone spec, plan and plan-review cycle: compact-route changes use the PR-body outcome/acceptance/checks/limits, and other opted-in repository changes keep the required same-PR specification placement without extra design/plan review ceremony. Use focused tests and applicable gates. A runtime change or file count alone does not make a change non-small. |
| Ordinary feature | Outcome spec, TDD, unit + relevant tests, correctness checkpoint, then formal review. |
| Cross-service boundary | Add an integration-layer test; a mocked unit test cannot prove it. |
| Large change | May pause at the correctness checkpoint for human direction before expensive review (optional, never a gate). |
| High-risk (security, data-integrity, permission, deployment, approval, merge, destructive, credential) | No layer skipping except the explicit Advice applicability rule; independent final coverage and all other required gates still apply. |

**Mandatory regardless of class:** gates the user explicitly required, and high-risk, security, data-integrity, permission, deployment, approval, merge, destructive and credential gates. Outside the compact route, real proof stays mandatory for every production-behavior claim. For compact bounded logic, focused tests prove only the affected branch, not an end-to-end production or service-boundary claim, which keeps its real integration evidence. **Skippable by class:** standalone spec/plan, plan-review cycle, history mining, and extra review lanes for small low-risk changes, including small code fixes. A standalone plan review applies only to high-risk or user-required cases, or an unresolved material decision. Skill pipelines (`write-goal`, `ironclad`, `ready`) delegate applicability and review timing here; none may apply universally.

Run a direct causal reproducer early; cheap real smoke may catch a wrong target. Collect expensive final evidence once relevant code and checks have stabilized. Do not wait for green to diagnose a failed test, and diagnose existing failures first. Apply the documented local-equivalent exception for backlogged checks; never label a failed or unproven check as passed.

Freeze means a coordinated candidate SHA with the executing owners, not a branch lock. It does not authorize resets, history rewrites or discarded work. After a necessary fix, agree the new candidate and revalidate the affected claims.

**Execution handoff invariant.** An accepted next step needs an executing owner or started tool before reporting `Working`. With only an exact blocker plus resumption trigger, report `Blocked` or `Waiting`, never `Working`. Creating a goal or checklist is not execution. Do not stop at a completed design when implementation was authorized.

### Continuation through the requested endpoint

During an authorized `/prw`, a status or progress response does not end the request: refresh live state, answer briefly, then resume the next authorized action toward the requested endpoint. Own each started job or delegated lane through its result under the async-handle, handback and independent-work rules in `parallelize-to-ceiling`, then integrate and verify the returned artifact. Stop only at the requested endpoint, a user scope change or stop, or a genuine scoped blocker or user-only decision under the applicable authority rules. Batch findings and fixes per § Draft-phase final acceptance gates; assess the actual delta and rerun only affected proof and review.

## Draft-phase final acceptance gates (in order)

Before this final sequence, run independent code-correctness reviews (including /advice reviewers) and cheap focused checks in parallel when resources permit. Resolve or explicitly defer their findings, batch fixes, and freeze the code before expensive evidence; do not run expensive evidence while known code-correctness work remains. Reviewers may finish code inspection early, but final approval accounts for the finished evidence and candidate, including documented applicability of any earlier reviewed SHA.

When several reviews are requested, use one frozen candidate/base and one shared factual scope and defect inventory; shared inputs do not replace each review's independent judgment. Run independent review groups concurrently where transport and resource rules permit. Each review covers the entire declared change; focus lanes supplement approval, never replace it. Collect current findings in one batch, and after repeated same-cause findings inspect the shared representation before another local patch. Do not invent extra approval gates; existing approvals stay workflow-specific. Final evidence stays last, and evidence in the declared review scope must actually be inspected by an eligible independent reviewer. Reuse that verdict while its evidence and claim coverage remain applicable after the documented delta assessment. New or changed evidence needs the affected independent review; unchanged material does not need another full reading or model call merely to restamp a SHA. The orchestrator cannot invent missing coverage or self-award approval.

While a PR is draft, pass these final gates in order where applicable; do not skip any applicable gate.

A repository's own instructions (for example its `AGENTS.md` coding lifecycle) may exempt defined low-risk classes, such as docs-only, test-only or small non-production changes, from `/er`; follow that classification and its exclusions. Where the repository defines none, the default is the narrow documentation allowlist below plus the explicit trivial-change exception above. No `/er` exemption covers changes to approval, merge, review, evidence or security rules, or to security, permission, credential or merge-path code.

1. **`/es`** — evidence bundle passes (real evidence per `../evidence-standards/SKILL.md` + repo-specific extensions), bound to its original tested SHA and shown applicable to the candidate by the delta assessment below.
2. **`/er`** — evidence review verdict PASS (not PARTIAL/FAIL/INCONCLUSIVE), with its original reviewed/tested SHAs and a reasoned applicability assessment for the candidate. Not required for the documentation-only class below, a repo-exempted class, the explicit trivial-change class, or a compact-route PR whose single independent reviewer covers both source and focused proof where local policy accepts that coverage. An older `/es` SHA alone does not require a rerun.
3. **`/advice`** — second-opinion approval on the change itself (`APPROVED at <SHA>` / `NOT APPROVED at <SHA>` / `WITHHELD at <SHA>` — see `../advice/SKILL.md`), bound to its actual reviewed SHA and applicable to the candidate by the delta assessment, when required by Advice applicability. `WITHHELD` does not satisfy the draft gate.
4. **`/visual-verification`** — published screenshots, GIFs or video always require this inspection. Without published media, a bounded compact-route source/logic claim that claims no changed rendering, interaction or displayed data does not trigger media proof merely because a downstream UI exists; any actual rendered, interaction or displayed-data claim keeps its applicable proof, regardless of diff size. The gate does **not** apply to a source-literal-only claim (copy, log or alert text inspected in source) that publishes no media, including a one-liner fast-path PR; those keep their bounded `N/A` allowance.
   A qualifying seat is independent of the author **and** of the `/er` seat that judged the bundle. It downloads each media artifact, verifies its hash, decodes it, extracts the before and after frames, and returns `VISUAL-VERDICT: PASS|FAIL` mapping what it observed to the claim, plus what the media does **not** prove. The Review Gate Ledger carries its own `/visual-verification` row; media without that row blocks undraft. Author-side frame reading, a difference score (PSNR or similar), "captions present", a published hash, or an `/er` line item calling media "VERIFIED" is **never** a substitute: that is the same recording read by the same side. Every applicable seat must PASS; missing, inaccessible or insufficient required media leaves the gate open.
   When the headline claim is user-visible and neither the compact route nor the one-liner fast path applies, the shared default is **two** independent visual seats before undraft; a repository route that genuinely cannot supply two records a `SINGLE-SEAT` limitation naming the missing seat, never a silent waiver.
   When the consuming surface lives in another repository, the PR cites a capture of that surface for the visual seat to review, or records the visual proof as deferred debt naming the owning repository. Deferred debt does **not** discharge this gate or authorise undraft, and is allowed only when the PR publishes no media and makes no rendered or displayed-data claim for that surface; a PR whose headline claim *is* another repository's rendered output stays draft until that capture exists and an independent seat has PASSed it.
   Byte-identical prose is still user-visible when a client renders the new data or a displayed value changes, so "no web-visible change" cannot mark video `N/A` there; otherwise `N/A` needs its specific bounded reason.

Only after every applicable gate is satisfied **for the candidate**, with original SHAs and explicit applicability where they differ, flip the PR from draft to ready-for-review (`gh pr ready <N>`).

### Documentation-only CI exception

Documentation-only changes, including instruction/skill documentation, need no CI or runner wait. Apply `../pr-green-definition/SKILL.md` § Documentation-only CI exception for scope, proportionate local validation and SHA-bound reporting. That exception is independent of the narrower `/er` allowlist below and does not remove applicable draft-phase gates, conflict checks or merge authorization.

### Documentation-only `/er` exception (narrow allowlist)

After `/es`, classify the complete changed-path set against the PR's true base. An owner/repository suffix is ambiguous across hosts, so resolve the base through the API, not from a remote name.

With the PR checkout as the working directory, run this skill's `scripts/pr-base-changed-paths.sh <N>` by its path in the loaded skill directory: `"${CLAUDE_HOME:-$HOME/.claude}/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh"` for an installed skill, or `.claude/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh` under a repository checkout. It resolves the base through `gh api` on the pulls endpoint (`clone_url` and `ssh_url`), requires exactly one local remote matching the full host and repository path, and prints `git diff --name-only ${BASE_REMOTE}/${BASE_BRANCH}...HEAD`. Inspect its output; a resolution error leaves the exemption unproven.

For this `/er` exemption, every changed path must be one of:

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/**`

For that class, do not run `/er`: record `/er: NOT REQUIRED — documentation-only (<changed paths>)` on the PR, then continue to `/advice` where Advice applicability requires it. These PRs still need applicable `/es` and verdict coverage for the candidate, then the ready phase under the documentation-only CI exception and separate merge authorization.

The exemption is an exact allowlist, not a file-extension heuristic: changes under `.claude/**`, `.codex/**`, `.github/**`, prompts, tests, scripts, configuration, schemas or source code do not qualify even in Markdown. A mixed diff uses the normal `/er` gate unless the entire diff independently qualifies for the explicit trivial-change exception above.

## Change-impact review and test depth

Initial gate applicability follows the rules above. For a later delta, read the full change and identify which claims, contracts, assertions or drivers it can invalidate before choosing full re-review or focused reaffirmation. Use `../4layer/SKILL.md` (`/4layer`), `../testing-layers/SKILL.md` and the repository testing-layers overlay to select the lowest sufficient layer. Evidence classification (`/es`) does not by itself require a paid model call or browser run.

| Actual change or claim | Proof and review depth |
|---|---|
| Unrelated prose delta | Read the delta, run relevant checks, and reaffirm unchanged claims; no automatic expensive replay. |
| Small single-file deterministic fix | Fresh causal unit RED/GREEN plus affected regressions can prove the deterministic claim when no external boundary is implicated; focused delta review may suffice. |
| A service boundary, auth, or persistence race | Integration proof crossing the implicated boundary; isolated unit mocks cannot establish the claim. |
| A prompt/schema or model-behavior change | Check assembled inputs deterministically first; run real LLM evidence when lower layers cannot prove the claim or an applicable risk-specific rule requires it. |
| New browser/UI behavior | Real browser proof for browser/UI claims, with required visual evidence, plus the `/visual-verification` gate: an independent seat must decode the media and read the frames. |
| CI config, agent policy, security, shared fixture, or weakened assertion | Review actual effects and rerun dependent proof; non-production labels and small file counts do not establish safety. |

Unit proof does not prove model compliance, auth, persistence races or browser behavior. Do not manufacture live proof from mocks or replays. Keep the strict real-service-only rules inside `testing_mcp/` and `testing_ui/`; use deterministic layers outside those directories. File count, path category and line count alone never decide evidence sufficiency or independent safety-review depth.

## SHA-binding rule (critical — applies to every gate in this chain)

Evidence and independent reviews are earned at their actual tested/reviewed commit SHAs. Those original SHAs and timestamps never change; never relabel an old capture as a new run. A different candidate SHA is not, by itself, a defect in the evidence or a reason to repeat the review.

Before relying on earlier /es, /er, /advice, /dot, /wa or /cs results, read the complete intervening head and base delta against the precise claims and scope of the original receipt. Record:
- original tested SHA, original reviewed SHA, candidate head/base and the inspected delta;
- covered claims, execution paths, environment/build/config and evidence dependencies;
- relevant tests and results, remaining findings/limitations, assessor and rationale;
- one disposition: applicable unchanged, partially applicable with named gaps, or invalidated.

Reuse an actual independent verdict when the assessment shows its coverage and phase still satisfy the candidate's obligations. The applicability record is not a new reviewer vote and must not claim the reviewer inspected a SHA they did not. The assessor records why existing coverage remains valid but cannot extend it to unreviewed changes, change the original verdict, dismiss its findings or grant a missing approval. Uncovered relevant changes, changed evidence in scope, unresolved material findings or uncertain applicability need affected independent review, including when the assessor is the author/driver; a new hash alone does not.

Classify by the actual delta and claim, never by path category. A production behavior change still needs fresh evidence for affected claims and appropriate independent review of that change. A changed assertion, driver or behavioral instruction invalidates the evidence that depends on it, while unrelated claims can stay valid; tests, prompts, schemas, CI, configuration and skill instructions can invalidate proof even when classified non-production. There is no blanket category carry-forward. For affected proof, use the lowest sufficient layer while keeping stricter real-service and native requirements. If the diff or provenance cannot be inspected, applicability stays unverified.

Current-candidate /green, mergeability and head-matching merge protection always need fresh verification, and a base-only move also needs assessment of the changed context and complete-diff size. Do not infer readiness from a stale CI result or unresolved conflict. Never weaken assertions or waive quorum to make an old approval appear valid.

Behavior-blocking findings must be fixed and reverified; style, nit and documentation feedback may be tracked as follow-ups.

## Ready phase — finish `/ready`, then final reviews

Undrafting starts `/ready`; it does not establish readiness. Invoke the `ready` skill for current-head `/green`, comments, conflicts and cross-thread regression checks, and follow `pr-green-definition` for applicable CI, documented exceptions and fresh mergeability; do not duplicate those mechanics here. Keep an already non-draft PR non-draft while finishing its open gates.

Once ready-phase work stabilizes, perform the final `/er` when applicable, then one final `/advice` when Advice applicability requires it. These are explicit closing obligations, not copies of draft approvals. Apply the same delta-and-scope decision: a prior independent verdict that covers the final obligations can stay applicable without a fresh review at HEAD. Request missing or affected review rather than an automatic full rerun, and retain the original verdict attribution. Required advice keeps its canonical independent quorum; the orchestrator cannot approve itself.

If a final review requires a fix, batch fixes, rerun affected checks/evidence, refresh `/green` at the new head, and repeat final `/er` then final `/advice` where applicable until approved. No cycle-count limit substitutes for finishing; stop only for a genuine blocker/decision or the governing autonomy deadline. Report READY only after applicable closing verdicts and current readiness checks pass. PARTIAL, FAIL, INCONCLUSIVE, WITHHELD or an unavailable required reviewer leaves its gate open. READY never supplies merge authorization (§ Merge authorization).

## Review records in the PR description

For every review type that runs, including `/es`, `/er`, `/advice`, `/wa`, `/cs`, other named lanes and native reviews, record in the PR body the exact reviewed SHA, review type/phase, verdict or status, timestamp, and reviewer/coverage. Document reviews also retain document hashes; their context SHA does not turn document approval into code approval.

Outside the compact route and the one-liner fast path (§ Proportional exceptions and fast paths), publish each completed review's sanitized receipt as a gist within the approved disclosure scope, and keep one current marker in the PR body for evidence-gate compatibility: `**Evidence**: <gist-url> (head <sha>)`, pointing to the authorized sanitized evidence-review receipt for current applicability. Compact PRs use the outcome/checks/SHA/limitations/reviewer summary described above, linking an artifact only when needed to substantiate the claim; the one-liner fast-path `/es` record uses its before/after section. Update only that index; keep the historical ledger, receipt URLs and original capture SHAs. Underlying raw artifacts may stay private. Missing publication authority or an inaccessible required receipt leaves the marker incomplete; never fabricate its URL.

A gist is link-accessible, not private storage: omit credentials, private source, personal communications and sensitive artifacts unless separately authorized. Verify the gist URL and intended reviewer access before calling publication complete. If tools or permissions prevent publishing a required receipt, record `PUBLICATION BLOCKED` with the exact reason and local receipt location; never invent a gist URL or passing verdict, and do not claim the record complete.
When the session has no authorized gist-creation tool (for example a cloud
session whose GitHub access excludes gists), and the PR's audience is within
the approved disclosure scope, publish the same sanitized receipt as a dated,
SHA-bound section of the PR body and cite that section's anchor where a gist
URL is required, recording `receipt: PR body (no gist tool)`; the anchor is not
a gist URL. Otherwise record `PUBLICATION BLOCKED`.

Keep `PENDING`, `UNAVAILABLE`, `FAILED` and `SUPERSEDED` results visible alongside approvals. Read the current body before updating it. The idempotency key is review type + phase + reviewed SHA + receipt identity: append a record only when the key or status is new, and treat a retry with unchanged key and status as a no-op. A status transition (including PENDING to PASS with the same receipt) or an applicability change appends a dated superseding event identifying its prior record, without erasing history. Preserve prior rounds and visual tables. For a moved head, add a current-applicability review and keep the original tested SHA and capture link instead of rewriting historical receipts. Read back the PR body after each update; an uncertain write needs readback before retrying. Record optional or skipped reviews honestly, without fabricated gists.

## Slow CI — never block-wait

Documentation-only changes use the CI exception immediately. **CI that does not exist is not CI to wait on.** Follow `../pr-green-definition/SKILL.md` § No-CI exception, including its evidence preconditions and the `Gate 1: CI NOT APPLICABLE — <reason>` record; if that evidence cannot establish a qualifying exception, Gate 1 stays unproven. Never replace this with `sleep N` + `gh pr checks`, and never call unrun CI passed.

For checks queued/pending more than 10 minutes, follow the local-equivalent exception in `../pr-green-definition/SKILL.md` § Backlogged CI: run the workflow's actual command and post current-head proof. Failed checks, no-conflict verification and merge authorization remain separate requirements.

## CodeRabbit/Bugbot — optional advisory reviewers

Read their feedback and take what is useful. They are never a draft-phase gate, never part of `/green` and never a wait, at any phase.

## Merge authorization

Merge authorization follows the shared size-tiered rule in `~/.codex/AGENTS.md` § Merge safety and any explicit target-repository contract. This skill neither requires nor waives a human `MERGE APPROVED` phrase where the governing rule does not; explicit local approval requirements stay in force. Earlier-SHA review applicability for readiness does not satisfy a stricter exact-head condition on a separately authorized automatic-merge route. Keep that merge condition unless the human explicitly changes it; do not infer a new automatic-merge permission from this policy.
