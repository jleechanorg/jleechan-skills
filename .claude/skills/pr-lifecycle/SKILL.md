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
  → /es PASS @ SHA (unless the Markdown instruction-only route below applies)
  → /er PASS @ SHA (unless the narrow /er documentation allowlist, explicit trivial-change exception, compact-route review coverage accepted by local policy, Markdown instruction-only route below, or another repo-exempted class applies)
  → table-selected independent source review PASS @ SHA when required
  → /visual-verification PASS @ SHA when gate 4 applies and the one-liner fast path does not (media published, or a rendered/displayed-data claim)
  → mark ready-for-review (gh pr ready <N>)
  → /ready work: /green, comments, conflicts, and regression checks
  → final /er PASS applicable to the candidate when required
  → final table-selected source coverage applicable to the candidate
  → READY
  → separate merge authorization: apply `~/.codex/AGENTS.md` § Merge safety and the target repository's explicit merge contract; readiness and review receipts do not themselves grant authority
```

Each arrow is a gate. A changed SHA triggers the delta assessment in § SHA-binding rule, not automatic invalidation or a mandatory repeat review: keep the original tested/reviewed SHA and record why its evidence and verdict still apply to the candidate.

## Retained review integrations

The shared catalog keeps host-installed `/advice` and `/web-advice` integrations rather than installing them. Before invoking either, resolve and read its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package; for a remote invocation, check the corresponding skill on the target host. If a required integration is absent, report it `UNAVAILABLE` with the missing package name and never invent a replacement runner or claim an approval. Continue independent authorized work, but leave every dependent readiness or plan-approval gate unmet: a missing `/advice` leaves its applicable quorum unmet, and a missing `/dot` or requested `/wa` continues through the reviewer fallback below with dependent substantive evidence gates open until proved. Existing review quorum, external-disclosure authorization and optional-review rules still apply.

## Review obligations by changed claim and risk

This table is the single shared-default routing decision for both generic and opted-in lifecycles. Classify the **complete** base-to-head diff, including non-production effects. Apply explicit repository overrides first, then the highest-risk applicable row; mixed changes retain proof for every changed claim. Unknown scope or uncertain eligibility takes the ordinary route until resolved. Never split work, relabel risk or weaken assertions to qualify.

A changed boundary means the diff alters its contract, execution or claimed outcome. Merely using an existing service, shipping to a deployed environment, holding test credentials or having an unchanged downstream UI does not create a changed service/gameplay claim. Conversely, a local label or mock test cannot erase an actual boundary change. Size admits a candidate; it never proves safety.

### Markdown instruction-only route

Apply this route before the general compact route and size-based /advice default. The diff must change agent or operator guidance in Markdown; it may also include human-readable Markdown specifications, records, and conflict notes that accompany or document that work. Those supporting documents count toward size but do not defeat eligibility. No changed path may add scripts or helpers, tests, CI, configuration, machine-readable schemas, production prompts, or an actual runtime/service contract. Mixed changes and prompt/schema/runtime-contract changes use the ordinary rows below.

Count additions plus deletions across the full PR diff at its actual base and current head, including supporting Markdown. For an ordinary, low-risk instruction change at or below 150 changed lines, one cold independent AI reviewer reads the complete diff and checks the changed rules against relevant before/after scenarios. Above 150 changed lines, use two independent full-scope reviewers. Sensitive changes use two at any size, including security, permission, credential, destructive, deployment or release operations; evidence requirements or policy; and approval, review, or merge rules. A reviewer confirms route eligibility from the diff; a label or the author’s classification cannot qualify it. Reviewer identity, independence, tier and class-count caps follow [advice](../advice/SKILL.md). Each static reviewer follows [static-review](../static-review/SKILL.md) for cold input and complete base/head changed-file coverage. Do not count separate processes or subagents as separate votes; follow advice’s reviewer-class caps. Do not combine partial coverage.

For this route, the required proof is the pinned source diff, relevant link/frontmatter or Markdown-structure checks, and the reviewer’s scenario-based receipt on the PR. Do not add a seven-element spec, separate /es or /er adjudication, evidence bundle/publication, runtime test, model/provider run, browser journey, or visual capture solely because the change is a skill or exceeds a size threshold. Reuse a complete reviewer receipt at later phases when the SHA delta leaves its claims and scenarios applicable; a phase label alone does not call for another model review. Specific evidence needed to verify a changed example or runtime claim remains required. Repository-specific gates and explicit user-requested proof still apply.

For eligible Markdown instruction changes, this subsection controls reviewer count and proof in place of the generic Agent instructions/policy row, compact route, and default size-based advice rule. It does not override the high-risk row, stricter repository requirements, or explicit user-requested proof.

This route cannot exempt itself from its sensitive-review rule. Changes that modify review policy use two independent full-scope reviews and all separately required repository or user gates.

| Class / risk | Admission and exclusions | Required proof | Independent review for readiness |
|---|---|---|---|
| Editorial / minimal | Typo, link or wording only; no policy, contract, legal/security meaning, behavior or new correctness claim. | Diff, relevant link/Markdown checks; no unrelated runtime test. | Existing trivial-doc exception where eligible; otherwise one cold static reviewer of changed text. Explicitly requested reviews still run. |
| Archive or package / integrity | Preserve existing artifact bytes, meaning and approved/unverified/historical status; no executable or install effect, fresh semantic correctness claim or missing/conflicting content. | Completeness, hashes/provenance, preservation, redaction and executable/install delta; required publication/readback remains separate. | One evidence-integrity review where needed. No semantic re-review of unchanged historical claims; this is not source approval. |
| Agent instructions / policy | Changes agents' execution of production work, evidence or review; approval/security/permission/merge changes use high-risk row. Wording-only no-rule changes may be editorial. | Full diff and before/after adversarial enforcement scenarios; runtime proof only for a changed runtime claim. | At least one cold independent adversarial full-scope source reviewer; preserve any stronger repository quorum. This policy cannot exempt itself. |
| Small deterministic / low | At most 150 production added+deleted lines and 3 runtime files in one module plus tests; deterministic local proof. No user-visible, API/data/model/deploy contract, auth/permission, shared-state, prompt/schema, security, destructive or credential effect; no changed CI/proof selection, shared-fixture meaning, assertion weakening, network path or retry budget. | Fresh focused RED/GREEN and relevant regressions; applicable CI and mergeability. Offline tooling may qualify; mutating/billable probes retain explicit execution/action/account/campaign/provider controls. | One cold independent static reviewer covers the complete source diff, focused proof, safeguards and eligibility. Direct static route below. |
| UI presentation / low | Copy, color, spacing/layout or static assets only; no interaction, navigation, state, availability, accessibility, auth or displayed-data change. Legal meaning and claims about attribution/link correctness retain their specific proof. | Real before/after rendered frame for an appearance claim, focused assertion where present; source-literal-only claims may use the existing narrow fast path. | One cold independent source reviewer may also inspect the frames if its receipt explicitly covers both source and visual claims. Direct static route below. |
| UI interaction / moderate | Navigation, settings, buttons, streaming or other observable behavior. One-vote admission requires the 150-line/3-runtime-file ceiling, frontend-only journey and component-local presentation state, with no service/data/auth/permission effect. | Real browser journey, user story and visual evidence; service claims add real boundary proof. | One full-coverage source vote only for that positively qualified bounded frontend case; otherwise two. Visual inspection does not create an additional source vote. |
| Ordinary or cross-module / moderate | Remaining features, larger deterministic work or changes spanning modules that do not positively qualify above. | Outcome specification, fresh relevant regression proof, applicable integration/visual evidence and current checks. | Two independent full-coverage source votes through the stronger route below. |
| Changed service boundary / elevated | Changes API, persistence, async/provider contract, auth/session or a deployed execution boundary; unchanged use alone does not qualify. High-risk effects use next row. | Real integration across the changed boundary; mock unit tests alone cannot prove it. | Two independent full-coverage source votes, plus applicable evidence adjudication. |
| High-risk / any size | Security, permissions, destructive operations, credentials, approval/merge authority, shared-state integrity, model prompt/schema policy, signing/release or deployment/capacity controls. | All triggered domain proof, adversarial checks and current-head checks; no generic fast-path waiver. | Two independent full-coverage source votes with applicable domain lenses; separate specialist reviewers only where an explicit owner requires independence. |

### Direct static route and evidence applicability

For the positively qualified one-vote rows, dispatch directly through [static-review](../static-review/SKILL.md): one cold reviewer independent of the author/orchestrator, complete actual diff and applicable proof, exact reviewed SHA, eligibility finding and retrievable receipt. Do not start `/advice`, Dot rotation or a provider fallback ladder merely because the total diff exceeds 50 lines. A specifically requested workflow or stricter repository route still runs. A full-coverage reviewer may cover source and evidence only where the evidence owner accepts that combined coverage; preserve any explicitly separate evidence seat. Source vote count does not waive `/es`, `/er` or publication requirements.

Proof follows **changed claims**. Use the lowest sufficient layer, retaining real boundary, native and rendered proof where claimed. For example, an App Store icon/splash presentation change needs its rendered surface; a copy/attribution/link change needs literal, attribution or destination proof as claimed; reuse of an existing Apple-logo asset needs provenance and relevant presentation proof. None implies a new gameplay journey when gameplay is unchanged. Signing, release, legal meaning, interaction or trust changes reclassify the affected scope.

Visual evidence follows the changed claim: backend-only changes with no rendered, displayed-data, or interaction claim need no visual proof. Changes that do alter a rendered surface or interaction retain the applicable real visual or browser proof. This rule applies across implementation types and does not waive service-boundary proof.

Reuse valid proof and independent coverage across draft/final phases under § SHA-binding rule. A phase label alone does not demand another model call. Changed source, evidence or interpretation gets affected independent review; unchanged historical claims retain original status and SHA. An early source vote may pass source correctness while evidence/readiness remains open: a reviewer must not withhold that source vote merely because a later approval does not yet exist. Final readiness still requires every applicable gate.

### Advice applicability

Outside positively qualified direct/static or existing trivial exceptions, the table's two-source-vote rows use `/advice` with its canonical independent quorum. Agent-policy changes of at least 50 complete-diff additions+deletions also use `/advice`; under 50, their cold independent source review remains mandatory. Preserve specifically requested reviews and explicit repository routes. Count the full verified base...head additions+deletions, not net lines or the latest commit; record production totals and runtime-file/module scope separately for numeric admission. Unknown counts and uncounted binaries cannot establish a numeric exception.

Readiness and merge authority are separate. A one-vote readiness result does not authorize automatic merge: retain the governing two-eligible-vote exact-head condition and any human approval requirement. A second static vote counts toward that merge quorum only when the advice/merge owner explicitly accepts it; otherwise use a human route only where allowed. No receipt manufactures merge, spending, credential or destructive authority.

### Reviewer timeout and completion

For `/pr-workflow` and other lifecycle reviews, each reviewer attempt has a default wall-clock limit of 1800 seconds (30 minutes), starting when the request is queued or sent. Queueing and delivery wait count; progress, partial output or a new message do not reset it. An explicit user-specified limit, shorter or longer, governs that attempt, and a later specific user instruction to await a named reviewer overrides the deadline for that attempt even without a number. If the reviewer is explicitly unavailable or quota-blocked, stop the attempt and route to the fallback immediately. Do not keep waiting on the same attempt.

A timed-out `/dot`, requested `/wa` or other non-`/advice` supplementary reviewer attempt is recorded `TIMED_OUT` with request and timeout times and any partial receipt or findings, never PASS. It is discharged at timeout, and the workflow continues through the reviewer fallback: a passing `/er` on the finished evidence plus `/advice` approval from two independent reviewers at the same head. The two-vote quorum is mandatory for this substitution only; the table-selected source-review route is unchanged. A `/wa` timeout proves none of the browser-only validation it was meant to review. Required substantive safety, evidence and domain checks stay open until proved by applicable evidence or an eligible replacement review; a timeout grants neither readiness nor merge authorization. Assess late substantive findings when they arrive; they can reopen the affected gate.

If an `/er` reviewer times out, record `TIMED_OUT` and continue independent work, but keep the evidence-review gate open until an eligible replacement completes `/er` with an applicable PASS. `/advice` or another supplementary review is not proof that the evidence was reviewed.

The Markdown instruction-only route above owns its one-or-two reviewer count and bypasses this section’s generic 50-line /advice threshold. Outside that route, /advice uses one independent full-scope reviewer only for an eligible compact low-risk route under the obligation table; otherwise it keeps its two-independent-reviewer quorum. Stricter governing requirements and the mandatory two-vote supplementary-review substitution above remain in force. Apply [advice](../advice/SKILL.md)'s identity, independence, tier and reviewer-class counting caps. Replace a failed or timed-out seat with another eligible independent reviewer, and keep replacing until quorum is reached or no eligible attempt remains; record each seat and outcome. Below quorum the result is `WITHHELD`, not approval. A late substantive `/advice` finding is still assessed after a replacement has voted.

`/wa` (`/web-advice`) is optional, never an implicit lifecycle gate: run it only when requested or separately authorized, and keep its real verdict if it runs. Existing standing authorization and any governing workflow that requires /wa still apply. Neither optional review permits ignoring a known correctness or safety blocker.

## Visible six-stage workflow (repository opt-in)

Only for a repository that explicitly adopts it, load [six-stage.md](six-stage.md): specification placement,
state readback before reporting a blocker, stage titles/labels/holds, opted-in review routes (including `/dot`
and Stage-5 visual approval), regression and synchronization, and stage-exit evidence. Other repositories keep
the generic lifecycle and their local requirements, except that its § Evidence attached to every stage exit
applies to every PR (read "stage exit" as each phase exit).

## Default PR route — `/prw`

An unqualified `/prw` invocation defaults to completing all applicable Stage 5 gates unless the caller explicitly requests an earlier endpoint; merging remains separately authorized.

Drive every PR through `/prw` (`/pr-workflow`) by default, using this generic lifecycle unless the repository opted into the visible six-stage workflow. UI and other user-facing changes always use `/prw` unless a human explicitly overrides it for that PR. A lighter path is allowed only for:

- documentation-only changes;
- non-production changes (documentation, tests, fixtures, and skill/instruction updates that do not alter approval, merge, review, evidence or security policy), subject to the repository's non-production classifier;
- backup or mirror repositories;
- an explicit human instruction to skip `/prw` for that PR;
- a very small change that needs no evidence or `/es`, such as a fix to a helper script with no user-visible effect.

The non-production and small-change bullets never cover a class excluded in § Proportional exceptions and fast paths, a high-risk class in § Coding lifecycle — scale layers to risk, or a test change that weakens an assertion; those always use `/prw`. The lighter path drops the `/prw` driver and the intermediate stage title/label transitions (`Stage 0–3`), not the work those stages gate: in opted-in repositories, keep the specification in its prescribed location and synchronize `[fa]` / `stage:5-final-approval` once applicable gates pass. Every applicable gate still applies: CI or its documented exception, `/green`, the table-selected source-review route, at least one independent adversarial full-scope LLM review of any agent-instruction change regardless of size, any repository-required review, evidence or `/dot` route, and merge authorization. When unsure, use `/prw`.

## Compact risk-based route

The small deterministic row and qualifying one-vote UI rows use the direct static route in § Review obligations by changed claim and risk. Retain focused proof and complete independent review; skip the separate seven-element committed specification and duplicate intermediate stage ceremony only where the repository permits the existing compact exception. The PR body records outcome, acceptance, checks and limitations. Current-candidate checks, applicable evidence, final Stage 5 synchronization and separate merge authority remain required.

## Proportional exceptions and fast paths

These claim/risk rules apply to the generic lifecycle and to opted-in repositories. When a change may be
trivial, one-liner, Markdown-only, logging-only, alerting-only, display-copy or non-production test work, load
[exceptions.md](exceptions.md) for the trivial-change exception and its exclusions, the one-liner fast path and
claim-specific proof. A test change that weakens an assertion is never exempt.

## Coding lifecycle — scale layers to risk

Order: explore → outcome spec (no code) → code-level design when useful → TDD (fresh failing test first) → unit + relevant integration tests → coder correctness checkpoint → formal code/evidence review → narrow fixes until a genuine human dependency. Batch findings, preserve passing lanes, and recheck only the affected behavior.

Select specification, proof depth and source-review quorum from § Review obligations by changed claim and risk. A compact outcome/acceptance/checks/limitations record suffices for qualified direct static work; ordinary features retain an outcome spec and relevant regression proof. The existing trivial and one-liner paths remain lighter. In opted-in repositories, specification placement remains required except for the existing compact-route exception. Standalone plan review is needed for high-risk or user-required cases, or an unresolved material decision; no linked pipeline adds it universally. Preserve all explicit user-required and domain-specific proof.

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
3. **Table-selected source review** — independent approval on the change itself (direct static receipt for a qualified one-vote row; otherwise `/advice` where required) (`APPROVED at <SHA>` / `NOT APPROVED at <SHA>` / `WITHHELD at <SHA>` — follow static-review or advice for the selected route), bound to its actual reviewed SHA and applicable to the candidate by the delta assessment, when required by the obligation table. `WITHHELD` does not satisfy the draft gate.
4. **`/visual-verification`** — published screenshots, GIFs or video always require this inspection. Without published media, a bounded compact-route source/logic claim that claims no changed rendering, interaction or displayed data does not trigger media proof merely because a downstream UI exists; any actual rendered, interaction or displayed-data claim keeps its applicable proof, regardless of diff size. The gate does **not** apply to a source-literal-only claim (copy, log or alert text inspected in source) that publishes no media, including a one-liner fast-path PR; those keep their bounded `N/A` allowance.
   For table-qualified UI presentation or bounded frontend interaction, the source reviewer may also supply the visual seat with explicit coverage; no extra visual seat is added by this default. Otherwise a qualifying seat is independent of the author **and** of the `/er` seat that judged the bundle. It downloads each media artifact, verifies its hash, decodes it, extracts the before and after frames, and returns `VISUAL-VERDICT: PASS|FAIL` mapping what it observed to the claim, plus what the media does **not** prove. The Review Gate Ledger carries its own `/visual-verification` row; media without that row blocks undraft. Author-side frame reading, a difference score (PSNR or similar), "captions present", a published hash, or an `/er` line item calling media "VERIFIED" is **never** a substitute: that is the same recording read by the same side. Every applicable seat must PASS; missing, inaccessible or insufficient required media leaves the gate open.
   When the headline claim is user-visible and no table-qualified one-vote UI route or one-liner fast path applies, the shared default is **two** independent visual seats before undraft; a repository route that genuinely cannot supply two records a `SINGLE-SEAT` limitation naming the missing seat, never a silent waiver.
   When the consuming surface lives in another repository, the PR cites a capture of that surface for the visual seat to review, or records the visual proof as deferred debt naming the owning repository. Deferred debt does **not** discharge this gate or authorise undraft, and is allowed only when the PR publishes no media and makes no rendered or displayed-data claim for that surface; a PR whose headline claim *is* another repository's rendered output stays draft until that capture exists and an independent seat has PASSed it.
   Byte-identical prose is still user-visible when a client renders the new data or a displayed value changes, so "no web-visible change" cannot mark video `N/A` there; otherwise `N/A` needs its specific bounded reason.

Only after every applicable gate is satisfied **for the candidate**, with original SHAs and explicit applicability where they differ, flip the PR from draft to ready-for-review (`gh pr ready <N>`).

### Documentation-only exceptions

For a diff that may be documentation-only, load [exceptions.md](exceptions.md#documentation-only-ci-exception): it owns the
CI exception and the narrow `/er` allowlist. Use its existing
[canonical changed-path helper](scripts/pr-base-changed-paths.sh) rather than by eye.

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

Once ready-phase work stabilizes, perform the final `/er` when applicable, then the final source-review coverage selected by the obligation table. These are explicit closing obligations, not copies of draft approvals. Apply the same delta-and-scope decision: a prior independent verdict that covers the final obligations can stay applicable without a fresh review at HEAD. Request missing or affected review rather than an automatic full rerun, and retain the original verdict attribution. Required advice keeps its canonical independent quorum; the orchestrator cannot approve itself.

If a final review requires a fix, batch fixes, rerun affected checks/evidence, refresh `/green` at the new head, and repeat affected evidence and table-selected source review where applicable until approved. No cycle-count limit substitutes for finishing; stop only for a genuine blocker/decision or the governing autonomy deadline. Report READY only after applicable closing verdicts and current readiness checks pass. PARTIAL, FAIL, INCONCLUSIVE, WITHHELD or an unavailable required reviewer leaves its gate open. READY never supplies merge authorization (§ Merge authorization).

## Review records in the PR description

For every review that runs, record it in the PR body per [review-records.md](review-records.md): reviewed SHA,
review type/phase, verdict, receipt URL, timestamp and reviewer/coverage.

## Slow CI — never block-wait

Documentation-only changes use the CI exception immediately. **CI that does not exist is not CI to wait on.** Follow `../pr-green-definition/SKILL.md` § No-CI exception, including its evidence preconditions and the `Gate 1: CI NOT APPLICABLE — <reason>` record; if that evidence cannot establish a qualifying exception, Gate 1 stays unproven. Never replace this with `sleep N` + `gh pr checks`, and never call unrun CI passed.

For checks queued/pending more than 10 minutes, follow the local-equivalent exception in `../pr-green-definition/SKILL.md` § Backlogged CI: run the workflow's actual command and post current-head proof. Failed checks, no-conflict verification and merge authorization remain separate requirements.

## CodeRabbit/Bugbot — optional advisory reviewers

Read their feedback and take what is useful. They are never a draft-phase gate, never part of `/green` and never a wait, at any phase.

## Merge authorization

Merge authorization follows the shared size-tiered rule in `~/.codex/AGENTS.md` § Merge safety and any explicit target-repository contract. This skill neither requires nor waives a human `MERGE APPROVED` phrase where the governing rule does not; explicit local approval requirements stay in force. Earlier-SHA review applicability for readiness does not satisfy a stricter exact-head condition on a separately authorized automatic-merge route. Keep that merge condition unless the human explicitly changes it; do not infer a new automatic-merge permission from this policy.
