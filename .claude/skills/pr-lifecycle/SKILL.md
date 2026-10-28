---
name: pr-lifecycle
description: "Lifecycle contract for opening PRs, driving them green, and fixing CI. Triggers on: opening a PR, driving a PR to green, fixing CI on a PR, /green, /es, /er, /advice on a PR."
metadata:
  type: policy
---

# PR Lifecycle

This is the self-contained generic operational lifecycle contract. [PR Workflow Manager](../pr-workflow-manager/SKILL.md) is the command/branch entry point; keep its draft, stage, evidence-applicability and safety guidance synchronized with this file. Before applying a generic rule, inspect the target repository's `AGENTS.md`, `CLAUDE.md`, and scoped instructions. Explicit repository requirements govern their domain; this contract supplies defaults only where local instructions are silent. Do not infer an opt-out from a repository's name or apparent purpose. Design documents explain rationale; they are not required to execute this workflow.

**Shared default:** For repositories that have not explicitly opted out or specified a different local flow, every new PR is opened as DRAFT (`gh pr create --draft`) and stays draft until quality is proven. Inspect the target repository's instructions first; an explicit local contract governs its workflow. Flipping to ready-for-review is a deliberate, gated action — not a side effect of pushing code.

## Precedence and scope

This skill owns shared defaults for PR lifecycle stages, generic review routing, proportional evidence, SHA applicability and receipt publication. A target repository's explicit local contract takes precedence within its domain, including a declared workflow opt-out or adapter. Apply shared defaults only to details the local contract does not address; never use this contract to remove a local requirement or infer an exception. Preserve domain-specific proof for the actual claim and separate security, credential, source-ownership and merge-authority restrictions. Current explicit user instructions govern within those permissions.

## Canonical lifecycle

This is the full state machine — every other file (`pr-green-definition`, `/green`, `CLAUDE.md`, `AGENTS.md`) points here rather than restating it:

```
DRAFT
  → /es PASS @ SHA
  → /er PASS @ SHA (unless the narrow /er documentation allowlist, explicit trivial-change exception or a repo-exempted class applies)
  → /advice APPROVED @ SHA when required by Advice applicability below
  → /visual-verification PASS @ SHA when gate 4 applies (media published, or a rendered/displayed-data claim)
  → mark ready-for-review (gh pr ready <N>)
  → /ready work: /green, comments, conflicts, and regression checks
  → final /er PASS applicable to the candidate when required
  → final /advice APPROVED applicable to the candidate when required
  → READY
  → separate merge authorization: apply `~/.codex/AGENTS.md` § Merge safety and the target repository's explicit merge contract; readiness and review receipts do not themselves grant authority
```

Each arrow is a gate, not a formality. Do not skip ahead. A changed SHA triggers the reasoned delta assessment below, not automatic invalidation or a mandatory repeat review. Preserve the original tested/reviewed SHA and record why its evidence and verdict still apply to the candidate.

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner or claim an approval. For missing `/dot` or requested `/wa`, continue through the reviewer fallback below and keep dependent substantive evidence gates open until proved. If `/advice` is absent, its applicable quorum remains unmet; leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.

## Advice applicability

Within shared defaults, `/advice` is optional for every PR under 50 changed lines, at both the draft and
final ready-review phases. A PR with 50 or more changed lines requires `/advice`
at both phases. A specifically requested review still runs. Within shared defaults,
this size rule supersedes broader docs/test/non-production `/advice` exemptions; it does not
waive independent safety/code review, security, evidence, CI, or merge authorization.
High-risk changes retain their required independent coverage even when `/advice`
itself is optional. Initial gate applicability and later re-review depth are
separate decisions.

For a high-risk change with optional `/advice`, follow the repository's required
independent code/safety lane. If none is named, require a named independent
full-diff code/safety reviewer (not the author or orchestrator) to inspect the
risk controls and record exact SHA, complete coverage, findings, and verdict.
Evidence-only review does not satisfy this code-review gate. Preserve stricter
repository lanes and quorums; this fallback does not make `/advice` mandatory
for an under-50 PR.

### Reviewer timeout and completion

For `/pr-workflow` and other lifecycle reviews, each reviewer attempt has one
600-second wall-clock limit, starting when the request is queued or sent. The
limit includes queueing and delivery wait; progress, partial output, or a new
message does not reset it. If the reviewer is explicitly unavailable or quota
blocked, stop that attempt and route to the applicable fallback immediately.
Do not repeatedly wait on the same attempt. A later specific user instruction
to await a named reviewer overrides this deadline for that requested attempt.

A timed-out `/dot`, requested `/wa` or other non-`/advice` supplementary reviewer
attempt is recorded as `TIMED_OUT`, with request and timeout times and any
partial receipt or findings; it is never recorded as PASS. The attempt is
discharged at timeout so the workflow continues through the reviewer fallback:
a passing `/er` on the finished evidence plus `/advice` approval from two
independent reviewers at the same head. This makes the two-vote advice quorum
mandatory for this substitution only; it does not change the general under-50
advice threshold. The fallback advances reviewer coverage without claiming the
timed-out review happened. In particular, a requested `/wa` timeout does not
prove any browser-only validation it was meant to review. Required substantive
safety, evidence and domain checks remain open until proved by applicable
evidence or an eligible replacement review. A timeout does not grant readiness
or merge authorization. Preserve and assess late substantive findings when
they arrive; they can reopen the affected gate.

If an `/er` reviewer times out, record `TIMED_OUT` and continue independent
work, but leave the evidence-review gate open until an eligible replacement
completes `/er` with an applicable PASS. Do not count `/advice` or another
supplementary review as proof that the evidence was reviewed.

`/advice` retains its applicable two-independent-reviewer quorum. A failed or
timed-out reviewer seat must be replaced with another eligible independent
reviewer; continue replacements until quorum is reached or no eligible attempt
remains. Record each seat and outcome. Below quorum, the result is `WITHHELD`,
not approval. A late substantive `/advice` finding is retained and assessed even
after a replacement has supplied a vote.

Count additions + deletions in the complete PR diff at the live head against its
actual base, including all production and non-production files, not net lines or
production-only lines. Use complete GitHub PR totals or the equivalent verified
base...head Git diff; record both refs and the count. An unknown or incomplete
count does not qualify, nor may uncounted binary changes establish the exception.
Recompute after a head or base change; do not use only the latest commit's size.
Examples: +25/-24 = 49: optional; +25/-25 = 50: required;
+10/-0 code and +40/-0 docs = 50: required.

`/wa` (`/web-advice`) is optional, never an implicit lifecycle gate. Run it only
when requested or separately authorized; preserve its real verdict if it runs.
Honor existing standing authorization and any governing workflow that requires /wa; this generic optional default does not override such a requirement. Neither optional review permits ignoring a known correctness or safety blocker.

## Visible six-stage workflow (repository opt-in)

Repositories that explicitly adopt this section use the following complete stage rules.
No dated design document is needed. Other repositories keep the generic lifecycle and their existing local requirements.

### Specification and artifact

Every specification records seven elements: outcome, non-goals, acceptance, user stories
(or an explicit no-user-facing-change reason), proof plan, mock (or justified exemption), and risk.
Keep the specification and implementation in the same PR. For the complete actual-base...head diff:
- Under 50 total additions+deletions: use PR-body `## Specification`, including for high-risk small changes.
- At least 50, or an incomplete/uncountable/binary diff: commit the seven-element specification in the same PR.
- Crossing that boundary without the committed specification returns to Stage 0.
Stage 0 is complete only when its artifact exists in an open PR at the prescribed location: the
seven-element specification in the PR body for small changes, or the committed spec inside the PR diff
for larger ones. A commit on a branch with no PR is not a Stage 0 artifact - no reviewer, `/advice` or
`/dot` can bind to it.
Artifact placement does not waive high-risk independent full-diff review or required real proof.
Do not split coherent work merely to evade review thresholds.

### State readback before reporting a blocker

Before reporting that work is uncommitted, unpublished, missing a PR, or otherwise blocked, run and
quote all three: `git status --porcelain`, `git log --oneline -1`, and
`gh pr list --head <branch> --state all`. A blocker assertion without those outputs is unverified. A lane
that reports work as uncommitted when the tree is clean, or as missing a PR when one is open, sends the
next reader to fix the wrong thing; state the measured facts instead of the remembered ones.

### Stage, title and labels

On creation, after each push, and when scope or status changes, refresh the descriptive title to match
the implemented behavior and remaining work. Read back the published title. Preserve provenance and
use the earliest unmet stage; changing the title never completes or advances a gate.

Use one stage label, one two-letter stage prefix and one recognized trailing stage suffix.
The prefix and suffix must name the same stage, for example
`[er] Improve campaign loading [evidence review]`. Preserve the substantive title, unrelated tags/labels
and all holds, including repository-required author/tool provenance tags immediately before the suffix;
the stage suffix goes last. On transition or migration, remove only recognized stage markers from the
beginning or end, then add exactly one current prefix and suffix. Do not strip arbitrary bracketed text
or invent a tool/model identity. Existing suffix-only titles gain their matching prefix on synchronization.

| Stage | Title prefix | Title suffix | Label | Work and exit proof |
|---|---|---|---|---|
| 0 Specification | [sp] | [specification] | stage:0-spec | Draft opened; seven elements, stories and mock/exemption complete in the required artifact. |
| 1 Coding | [cd] | [coding] | stage:1-coding | Scoped implementation and applicable causal RED/GREEN, focused checks and correctness review complete. |
| 2 Evidence generation | [ev] | [evidence generation] | stage:2-evidence | Applicable /es proof generated and delivered, original tested SHA and claim map recorded, or justified exemption. |
| 3 Evidence review | [er] | [evidence review] | stage:3-evidence-review | Applicable /er and draft review route satisfied by independent verdicts whose coverage applies to the candidate. The review SHA need not equal HEAD when the delta assessment supports reuse. |
| 4 CI and undraft | [ci] | [CI and undraft] | stage:4-ci-undraft | Undraft and complete /ready's CI, comments, conflicts and cross-thread regression work with current-candidate /green using only documented exceptions. Its closing reviews belong to Stage 5, not this exit. |
| 5 Final approval | [fa] | [final approval] | stage:5-final-approval | Final-phase review obligations satisfied by applicable independent approvals, with findings resolved or explicitly deferred as allowed. Earlier review SHAs may remain valid by reasoned assessment; merge authority is separate. |

A stage name describes work remaining. [final approval] does not mean approved or merged.
Orthogonal hold labels are hold:reviewer, hold:operator, hold:conflict and hold:quota; they never replace the stage.
Whoever applies a hold records in the PR body who applied it, the quoted instruction it rests on with its source
and date, and the concrete, checkable condition that lifts it. A hold label is a pointer, never authority. A
hold sourced from a handoff, coordinator or agent note is removed by the driving agent when its lift condition is
met or a later live user message explicitly covers the held action; the removal note cites that evidence. A hold
whose source is a live human instruction, or that guards a user-only item in shared policy (merge, destructive
action, spending, credentials), is lifted only by that human or by that item's own approval; report only these
as user-only gates. A hold on "deploys" does not cover PR preview deployment unless it names
previews: preview deployment is a lifecycle step, not a release.
For each transition, read the actual head/base, title, labels, body, artifacts and findings; choose the earliest
unmet stage, synchronize title/label/`## PR Stage`, and read back all three.
Place `## PR Stage` **below** the description's opening line-delta sentence
(`Line deltas: prod +X/-Y across N files; non-prod +A/-B across M files.`): that sentence stays the body's first
line, and a stage sync must never displace, bury, or restate it. If the body has no such opener, add a measured
one before inserting the stage block.
The body records stage/status, accountable owner, next action or exact blocker/resumption trigger, actual
head/base, full diff count/review route and original tested/reviewed SHAs with current applicability.
Verify label existence using authorized tooling; provision only within explicit scope.
A denied, unavailable or uncertain operation is a partial state to report, not permission to bypass it.
Never claim synchronization from a successful title update alone. No bulk adoption from draft status or CI colour.

### Review routes for opted-in repositories

Use the Advice applicability boundary and independent coverage rules in this skill. Here, small means under 50 complete-diff additions+deletions; large means at least 50 (or an incomplete/uncountable diff). Optional /advice does not mean all independent review is optional: the opted-in route below names its alternative, while the narrow trivial-change exception can waive that extra lane.
At Stage 3: small PRs need /advice OR independent /dot approval unless the narrow trivial-change exception below applies; large PRs need both.
At Stage 5: the same route applies to final obligations; large PRs attempt /wa best effort when authorized.
Explicitly requested /wa remains an attempt in the route. Honor existing standing authorization without asking again; apply the 600-second timeout contract above and use its `/er` plus two-vote `/advice` substitution if it times out or is unavailable. Record the actual disposition. Do not claim browser-only validation occurred, and keep any required domain evidence gate open until that evidence is proved. Otherwise unavailable or timed-out best-effort /wa is disclosed, not invented approval.
Resolve /dot through an existing authorized independent Dot reviewer, not the author/orchestrator. When /dot is necessary to satisfy the applicable route and the first Dot is busy, send the same request to the next configured Dot account in rotation. Apply the 600-second attempt limit above to each account, including queue and send wait. If Dot is busy, times out or is unavailable, the reviewer fallback above—a passing /er on the finished evidence plus two independent /advice votes at the same head—satisfies the /dot review leg; record `/dot busy: /er + /advice substituted` with the accounts tried, request/timeout times, and outcomes. A /dot verdict arriving after its attempt timed out does not count toward the completed review route or replace the fallback; retain any late substantive finding and assess whether it reopens the affected stage. Required substantive evidence gates remain open until proved. An independent /dot receipt names its reviewer, declared source/evidence scope, original tested/reviewed SHAs, actual inspection/actions, verdict, coverage, findings/limits and retrievable receipt. An acknowledgment, capability claim or another reviewer's verdict is not /dot approval. Its covered scope must satisfy the requested gate; narrow visual approval is not full source approval.
Reviewer eligibility and quorum remain owned by their review skills; the author/orchestrator cannot self-award
an independent vote, and reusing a verdict never creates an extra voter. A technical /dot verdict is evidence of review, never human permission to merge, change policy or operate another scope. A bot or orchestrator acknowledgment does not qualify as an independent review.
Draft and final obligations are distinct: evaluate whether the existing verdict's scope and phase cover the
closing obligations, rather than copying a draft status blindly. Request only the missing or affected review.

### Regression and synchronization

Use the earliest unmet gate: changed/missing requirements or specification -> Stage 0; implementation defect
or material change -> Stage 1 then affected proof; missing/invalid evidence -> Stage 2; missing draft review
coverage -> Stage 3; only CI/conflict/readiness work -> Stage 4; only final approval -> Stage 5.
A head/base move alone requires delta assessment and current-candidate /green, not a full evidence/review restart.
After Stage 4, a harmless change can reuse applicable reviews but still refresh /green before final completion.
Material policy, assertion, fixture, driver, configuration, prompt or schema changes reopen the gates they affect.
Keep original receipts and timestamps. Never rename historical evidence as a new run.

Keep this contract, the pr-workflow-manager entry point and repository adapters in sync when changing stage
names, title suffixes, labels, review routes or applicability rules. Repo adapters must reference this skill,
not copy its tables. Check affected references and report any installed copy that is stale or unavailable;
a source push does not install or synchronize another computer.

### Evidence attached to every stage exit

Always attach evidence to the PR description using retrievable artifact URLs and a sanitized gist receipt URL. Proof only in a comment, local path, chat or promised upload is insufficient. Every completed stage 0–5 has an appropriate receipt; specification proof does not require future runtime evidence. Stage 2 produces the acceptance-evidence package, not the first evidence of any kind: earlier stages publish their own specification or focused-check receipts. One version-pinned gist may contain distinct stage/event anchors without ceremonial duplicate uploads.

The description's evidence index records stage, disposition (`COMPLETE`, `NOT REQUIRED`, `REUSED` or `BLOCKED`), candidate head/base, full diff classification, original tested/reviewed SHAs and execution timestamps, applicable commands/environment/results, artifact hashes, reviewer and coverage, limitations, and exemption or reuse rationale. Preserve original receipts and append superseding events instead of restamping evidence.

Embed applicable screenshots and playable video inline in the PR description alongside direct original-media URLs. Verify URLs resolve and intended reviewers can view the media. A gist link alone does not satisfy applicable visual proof, and inline embedding is not visual *review*: the `/visual-verification` gate above is a separate, independent reading of the frames. Docs, logs and source-only trivial-copy claims may record a specific media `N/A` reason; never manufacture media to fill a field. Apply all applicable `/es` integrity, provenance, sanitization and claim-sufficiency requirements before declaring the stage passed.

Missing, inaccessible or unauthorized publication is `PUBLICATION BLOCKED`: continue independent work, but do not claim that stage exit complete. Missing or failed required checks are not exemptions. Read back the description; preserve evidence history and title/stage-label consistency.

## Default PR route — `/prw`

Drive every PR through `/prw` (`/pr-workflow`) by default, using this generic lifecycle unless the repository opted into the visible six-stage workflow. UI changes and any user-facing change always use `/prw` unless a human explicitly overrides it for that PR. A lighter path is allowed only for:

- documentation-only changes;
- non-production changes (including documentation, tests, fixtures, and ordinary skill/instruction updates, subject to the repository's non-production classifier and the high-risk exclusions below);
- backup or mirror repositories;
- an explicit human instruction to skip `/prw` for that PR;
- a very small change that needs no evidence or `/es`, such as a fix to a helper script with no user-visible effect.

Neither the non-production nor the small-change bullet covers application prompts/schemas or any class listed as high-risk in § Coding lifecycle — scale layers to risk (security, data-integrity, permission, deployment, approval, merge, destructive, or credential gates), or any test/instruction change that weakens an assertion or security/merge rule; those always use full `/prw`. The lighter path skips intermediate stage-by-stage ceremony (`Stage 0–3` transitions, separate committed seven-element specification files, `/er`, `/dot`, and `/wa`): record a concise PR-body `## Specification` / summary, attach a compact `/es` receipt for proportionate checks, satisfy applicable review (`< 50` lines: one independent review or repo-defined low-risk inline check; `>= 50` lines: `/advice`, plus at least one independent adversarial review for agent-instruction changes), synchronize `[fa]` / `stage:5-final-approval` in opted-in repositories once applicable CI `/green` (or its documented exception) passes, and stop at explicit merge authorization. When unsure, use full `/prw`.

## Proportional exceptions and fast paths

These claim/risk rules apply to the generic lifecycle as well as opted-in repositories; the visible stage/title/label machinery remains opt-in.

Classify the complete diff by effects and claimed outcomes, not its extension, a non-production label, or the latest commit size. For an entirely harmless documentation/mechanical change or obvious display-copy-only change under 50 total additions+deletions, a compact `/es` receipt with source before/after inspection and proportionate checks can suffice. Record `/er` and the extra independent `/dot` lane as `NOT REQUIRED — trivial-change exception`, never a fabricated PASS or reviewer vote. This exception applies at both review phases; explicitly requested reviews remain required. In opted-in repositories, the seven-element specification may be concise but remains required in its prescribed location. The >=50 advice boundary is unchanged.

This exception excludes application prompts, schemas, selectors, URLs, interpolation, format/control strings, authentication, permissions, consent, payments, legal meaning, and approval, merge, review, evidence or security policy. Agent instructions changing these rules are not harmless documentation: this workflow policy cannot exempt its own review. A one-line change can be high risk. Mixed diffs follow the requirements of their affected claims.

For Markdown-only instruction changes, focused proof may use the complete base-to-head source diff, link/heading/structure checks, and scenarios against both text versions. Application runtime, browser/media, and real-provider proof are `N/A` only when no changed claim depends on them. Markdown containing automation, prompts, schemas, or machine-consumed contracts still requires its applicable proof. Changed agent instructions still require at least one independent adversarial full-scope LLM review, plus any applicable `/advice` quorum and repository-required `/dot` route. Reuse one version-pinned receipt across applicable stages, preserving original SHAs and recording candidate applicability; rerun only proof affected by the delta.

For logging-only changes, use bounded execution showing the actual emitted log, level and fields, with original source SHA, command, timestamps and sanitized output. Focused `/er` may approve that emission claim without unrelated browser or provider runs. Check privacy and side effects; new sensitive data, destinations, machine-consumed contracts, alerts, expensive expressions, exceptions, mutation or retries require their affected proof. Emission alone does not prove downstream ingestion or alert delivery.

For alerting-only changes, focused `/es` and `/er` may prove the alerting claim with a controlled real trigger through the changed emission or dispatch path and receipt of the actual alert at each claimed destination. Retain the source SHA, environment, timestamp, correlation and delivery IDs when available, sanitized alert text, and logs plus provider or destination receipts. Video, screenshots, browser or native gameplay journeys, and paid LLM runs are not required merely to prove alert firing. Direct sink sends prove transport only; mock, unit, and source inspection cannot prove live delivery. Mixed diffs retain the affected proof for non-alert changes. Privacy and security checks, CI, code-review, quorum, and merge permissions remain unchanged. This does not create a broad exemption for a PR merely named for alerts, and there is no universal mandate to run native or player journeys for an alert-only claim.

Non-production tests, fixtures, drivers and CI changes need proportionate checks of changed assertions and affected contracts, not automatic runtime capture and not automatic exemption. Never weaken assertions or mock away a claimed boundary to qualify.

Source-only display-copy inspection proves the literal change, not rendering, accessibility or localization. Media may be explicitly `N/A` for that bounded claim. A claimed static appearance needs real rendered proof and an inline screenshot; interaction or streaming claims retain applicable video requirements. These explicit narrow exceptions govern generic all-UI-media wording in linked skills; named risk-specific requirements, explicit user-required proof and safety controls remain applicable.

## Coding lifecycle — scale layers to risk

Order: explore → outcome spec (no code) → code-level design when useful → TDD
(fresh failing test first) → unit + relevant integration tests → coder
correctness checkpoint → formal code/evidence review → narrow fixes until a
genuine human dependency. Batch findings, preserve passing lanes, and recheck
only the affected behavior.

| Change class | Layers |
|---|---|
| Wording-only / small low-risk (including a small code fix) | For an opted-in repository, retain the required same-PR specification placement; skip additional standalone design/plan review ceremony. Otherwise: Skip standalone spec, plan, and plan-review cycle. Use focused tests and applicable gates. Runtime change or file count alone does not make a change non-small. |
| Ordinary feature | Outcome spec, TDD, unit + relevant tests, correctness checkpoint, then formal review. |
| Cross-service boundary | Add an integration-layer test; a mocked unit test cannot prove it. |
| Large change | May pause at the correctness checkpoint for human direction before expensive review (optional, never a gate). |
| High-risk (security, data-integrity, permission, deployment, approval, merge, destructive, credential) | No layer skipping except the explicit Advice applicability rule; independent final coverage and all other required gates still apply. |

**Mandatory regardless of class:** gates the user explicitly required;
high-risk, security, data-integrity, permission, deployment, approval, merge,
destructive, and credential gates; and real proof for any production-behavior claim. **Skippable by class:**
standalone spec/plan, plan-review cycle, history mining, and extra review lanes
for small low-risk changes, including small code fixes. A standalone plan review
applies only to high-risk or user-required cases, or an unresolved material
decision. Skill pipelines (`write-goal`, `ironclad`, `ready`) delegate
applicability and review timing here; none may apply universally.

Run a direct causal reproducer early; cheap real smoke may catch a wrong target.
Collect expensive final evidence once relevant code and checks have stabilized.
Do not wait for green to diagnose a failed test. Diagnose existing failures and
batch fixes before paid capture; apply the documented local-equivalent exception
for backlogged checks, never label a failed or unproven check as passed.

Freeze means a coordinated candidate SHA with the executing owners, not a branch
lock. It does not authorize resets, history rewrites, or discarded work. After a
necessary fix, agree the new candidate and revalidate the affected claims.

**Execution handoff invariant.** An accepted next step must have an executing
owner or started tool before reporting `Working`. With only an exact blocker plus
resumption trigger, report `Blocked` or `Waiting` — a blocker never makes it
`Working`. Creating a goal or checklist is not execution. Do not stop
at a completed design when implementation was authorized.

## Draft-phase final acceptance gates (in order)

Before this final sequence, run independent code-correctness reviews (including
/advice reviewers) and cheap focused checks in parallel when resources permit.
Resolve or explicitly defer their findings, batch fixes, and freeze the code
before expensive evidence. Reviewers may finish code inspection early; final
approval must account for the finished evidence and candidate, including documented applicability of any earlier reviewed SHA. Do not
run expensive evidence while known code-correctness work remains unfinished.

When multiple reviews are requested, use one frozen candidate/base and one
shared factual scope and defect inventory; shared inputs do not replace each
review's independent judgment. Run independent review groups concurrently
where transport and resource rules permit; each review covers the entire
declared change, while focus lanes supplement rather than replace approval.
Collect current findings in one batch. After repeated same-cause
findings, inspect the shared representation before another local patch. Do not
invent additional approval gates; existing approvals remain workflow-specific.
Final evidence stays last; evidence in the declared review scope must actually have been inspected by an eligible independent reviewer. Reuse that verdict when its evidence and claim coverage remain applicable after the documented delta assessment. New or changed evidence needs the affected independent review; unchanged material does not need another full reading or model call merely to restamp a SHA. The orchestrator cannot invent missing coverage or self-award approval.

While a PR is draft, accept these final gates, where applicable, in sequence — do not skip any applicable gate:

A repository's own instructions (for example its `AGENTS.md` coding lifecycle)
may exempt defined low-risk classes, such as docs-only, test-only, or small
non-production changes, from `/er`; when they do, follow that
classification and its exclusions. The narrow documentation allowlist below is
the default when the repo defines none, alongside the explicit trivial-change exception above. No `/er` exemption covers changes to approval,
merge, review, evidence, or security rules, or to security, permission,
credential, or merge-path code.

1. **`/es`** — evidence bundle passes (real evidence per `../evidence-standards/SKILL.md` + repo-specific extensions), bound to its original tested SHA and supported as applicable to the candidate by the delta assessment below.
2. **`/er`** — for every PR except the documentation-only class below or a repo-exempted class, and except the explicit trivial-change class above, evidence review verdict is PASS (not PARTIAL/FAIL/INCONCLUSIVE), with its original reviewed/tested SHAs and a reasoned applicability assessment for the candidate; an older `/es` SHA alone does not require a rerun.
3. **`/advice`** — second-opinion approval on the change itself (`APPROVED at <SHA>` / `NOT APPROVED at <SHA>` / `WITHHELD at <SHA>` — see `../advice/SKILL.md`), bound to its actual reviewed SHA and applicable to the candidate by the delta assessment, when required by Advice applicability. `WITHHELD` does not satisfy the draft gate.
4. **`/visual-verification`** — applies when the PR **publishes** any screenshot, GIF or video, or when the PR
   **claims** a rendered, interaction or displayed-data effect that media would evidence. It does **not** apply to a
   source-literal-only claim (copy, log or alert text inspected in source) that publishes no media: those keep the
   bounded `N/A` allowance they already have. A qualifying seat is independent of the author **and** of the `/er` seat
   that judged the bundle: it downloads each media artifact itself, verifies its hash, decodes the file, extracts the
   before and after frames, and returns `VISUAL-VERDICT: PASS|FAIL` mapping what it observed to the claim, plus what
   the media does **not** prove. The Review Gate Ledger carries its own `/visual-verification` row, and media that
   exists with no such row blocks undraft. Author-side frame reading, a difference score (PSNR or similar),
   "captions present", a published hash, and an `/er` line item saying media "VERIFIED" are **never** a substitute;
   that is the same recording read by the same side. Every applicable seat must PASS, and required media that is
   missing, inaccessible or insufficient leaves the gate open. When the PR's headline claim is user-visible, require
   **two** independent visual seats before undraft; where a repository's review route genuinely cannot supply two,
   require a recorded `SINGLE-SEAT` limitation naming the missing seat rather than a silent waiver. When the consuming
   surface lives in another repository, this PR either cites a capture of that surface, which the visual seat then
   reviews, or it records the visual proof as deferred debt naming the owning repository. Deferred debt does **not**
   discharge this gate and never authorises undraft: it may be recorded only when this PR publishes no media and makes
   no rendered or displayed-data claim for that surface. A PR whose headline claim *is* another repository's rendered
   output keeps the gate open, and therefore stays draft, until that capture exists and an independent seat has
   PASSed it. A change whose prose is byte-identical is still
   user-visible when a client renders the new data or a value that surface displays changes, so "no web-visible
   change" may not be used to mark video `N/A` in that case; `N/A` otherwise needs the specific bounded reason.

Only after every applicable gate is satisfied **for the candidate**, with original SHAs and explicit applicability where they differ: flip the PR from draft to ready-for-review (`gh pr ready <N>`).

### Documentation-only CI exception

Documentation-only changes, including instruction/skill documentation, do not require CI or waiting for runners. Apply `../pr-green-definition/SKILL.md` § Documentation-only CI exception for scope, proportionate local validation, and SHA-bound reporting. That exception is independent of the narrower `/er` allowlist below; it does not remove applicable draft-phase gates, conflict checks, or merge authorization.

### Documentation-only `/er` exception (narrow allowlist)

After `/es`, resolve the PR number (safe fallback `PR_NUMBER=$(gh pr view --json number --jq '.number')` if `<N>` is not known), query the supported pull-request API for the base branch and canonical repository URLs, require exactly one matching Git remote, fetch it, and classify the complete changed-path set against that base. Match the full host and repository path; an owner/repository suffix alone is ambiguous across hosts.

```bash
PR_NUMBER=${1:-$(gh pr view --json number --jq '.number')}
if ! BASE_DATA=$(gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}" \
  --jq '[.base.ref, .base.repo.clone_url, .base.repo.ssh_url] | @tsv'); then
  echo "Error: could not resolve PR base through the GitHub API" >&2
  exit 1
fi
IFS=$'\t' read -r BASE_BRANCH BASE_CLONE_URL BASE_SSH_URL <<<"$BASE_DATA"
EXPECTED_BASE_DATA="${BASE_BRANCH}"$'\t'"${BASE_CLONE_URL}"$'\t'"${BASE_SSH_URL}"
if [[ "$BASE_DATA" != "$EXPECTED_BASE_DATA" ||
      -z "$BASE_BRANCH" || -z "$BASE_CLONE_URL" || -z "$BASE_SSH_URL" ||
      "$BASE_CLONE_URL" == "null" || "$BASE_SSH_URL" == "null" ]]; then
  echo "Error: GitHub API returned an incomplete PR base" >&2
  exit 1
fi

normalize_repo_url() {
  python3 - "$1" <<'PY'
import re
import sys
from urllib.parse import urlsplit

raw = sys.argv[1].strip().rstrip("/")
scp = re.fullmatch(r"(?:[^@/]+@)?([^:]+):(.+)", raw)
if scp and "://" not in raw:
    normalized = f"{scp.group(1).lower()}/{scp.group(2)}"
elif "://" in raw:
    parsed = urlsplit(raw)
    if parsed.scheme == "file":
        normalized = parsed.path
    elif not parsed.hostname:
        raise SystemExit(1)
    else:
        normalized = f"{parsed.hostname.lower()}/{parsed.path.lstrip('/')}"
else:
    normalized = raw
print(re.sub(r"\.git$", "", normalized.rstrip("/")))
PY
}

if ! BASE_CLONE_ID=$(normalize_repo_url "$BASE_CLONE_URL") ||
   ! BASE_SSH_ID=$(normalize_repo_url "$BASE_SSH_URL"); then
  echo "Error: could not normalize canonical base repository URLs" >&2
  exit 1
fi

MATCHING_REMOTES=()
while IFS= read -r remote; do
  url=$(git config --get "remote.${remote}.url") || continue
  remote_id=$(normalize_repo_url "$url") || continue
  if [[ "$remote_id" == "$BASE_CLONE_ID" || "$remote_id" == "$BASE_SSH_ID" ]]; then
    MATCHING_REMOTES+=("$remote")
  fi
done < <(git remote)

if [[ ${#MATCHING_REMOTES[@]} -ne 1 ]]; then
  echo "Error: expected exactly one remote for '$BASE_CLONE_URL'; found ${#MATCHING_REMOTES[@]}" >&2
  exit 1
fi
BASE_REMOTE=${MATCHING_REMOTES[0]}

git fetch "$BASE_REMOTE" "$BASE_BRANCH"
git diff --name-only "${BASE_REMOTE}/${BASE_BRANCH}...HEAD"
```

For this `/er` exemption, every changed path must be one of:

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/**`

For that class, do not run `/er`. Record
`/er: NOT REQUIRED — documentation-only (<changed paths>)` on the PR, then
continue to `/advice` where Advice applicability requires it. Documentation-only
PRs still require applicable `/es` and verdict coverage for the candidate, followed by the ready
phase using the documentation-only CI exception and separate merge authorization.

This `/er` exemption is an exact allowlist, not a file-extension heuristic. Changes under
`.claude/**`, `.codex/**`, `.github/**`, prompts, tests, scripts, configuration,
schemas, or source code do not qualify even when the file is Markdown. Any
mixed diff uses the normal `/er` gate unless the entire diff independently qualifies for the explicit trivial-change exception above.

## Change-impact review and test depth

Initial gate applicability follows the rules above. For a later delta, read the
full change and identify which claims, contracts, assertions, or drivers it can
invalidate before choosing full re-review versus focused reaffirmation. Use
`../4layer/SKILL.md` (`/4layer`) and
`../testing-layers/SKILL.md`, plus the repository testing-layers
overlay, to select the lowest sufficient layer. Evidence classification (`/es`)
does not by itself require a paid model call or browser run.

| Actual change or claim | Proof and review depth |
|---|---|
| Unrelated prose delta | Read the delta, run relevant checks, and reaffirm unchanged claims; no automatic expensive replay. |
| Small single-file deterministic fix | Fresh causal unit RED/GREEN plus affected regressions can prove the deterministic claim when no external boundary is implicated; focused delta review may suffice. |
| A service boundary, auth, or persistence race | Integration proof crossing the implicated boundary; isolated unit mocks cannot establish the claim. |
| A prompt/schema or model-behavior change | Check assembled inputs deterministically first; run real LLM evidence when lower layers cannot prove the claim or an applicable risk-specific rule requires it. |
| New browser/UI behavior | Real browser proof for browser/UI claims, with required visual evidence, plus the `/visual-verification` gate: an independent seat must decode the media and read the frames. |
| CI config, agent policy, security, shared fixture, or weakened assertion | Review actual effects and rerun dependent proof; non-production labels and small file counts do not establish safety. |

Unit proof does not prove model compliance, auth, persistence races, or browser
behavior. Do not manufacture live proof from mocks or replays. Preserve strict
real-service-only rules inside `testing_mcp/` and `testing_ui/`; use deterministic
layers outside those directories. File count, path category, and line count
alone never decide evidence sufficiency or independent safety-review depth.

## SHA-binding rule (critical — applies to every gate in this chain)

Evidence and independent reviews are earned at their actual tested/reviewed commit SHAs.
Those original SHAs and timestamps never change; never relabel an old capture as a new run. A different candidate SHA is not, by itself,
a defect in the evidence or a requirement to run the same review again.

Before relying on earlier /es, /er, /advice, /dot, /wa or /cs results, read the complete intervening
head and base delta against the precise claims and scope of the original receipt. Record:
- original tested SHA, original reviewed SHA, candidate head/base and the inspected delta;
- covered claims, execution paths, environment/build/config and evidence dependencies;
- relevant tests and results, remaining findings/limitations, assessor and rationale;
- one disposition: applicable unchanged, partially applicable with named gaps, or invalidated.

Reuse an actual independent verdict when the assessment demonstrates that its coverage and
applicable phase still satisfy the candidate's obligations. This applicability record is not a new
reviewer vote and must not claim the reviewer inspected a SHA they did not inspect. The assessor records why existing coverage remains valid; the assessor cannot extend its scope to unreviewed changes, change the original verdict, dismiss its findings or grant a missing approval. Material or uncertain changes require affected independent review, including when the assessor is the author/driver.
A new independent review is needed for uncovered relevant changes, changed evidence in its scope,
unresolved material findings or uncertain applicability, not merely for a new hash.

Classify by the actual delta and claim, never by path category. A production behavior change still
requires fresh evidence for affected claims and appropriate independent review of that change.
In particular, a changed assertion, driver, or behavioral instruction invalidates the evidence that depends on it;
unrelated claims can remain valid. Tests, prompts, schemas, CI, configuration and skill instructions
can invalidate proof even when classified non-production. There is no blanket category carry-forward.

For affected proof, use the lowest sufficient layer while preserving stricter real-service and native requirements. If the diff or provenance cannot be inspected, leave applicability unverified.

Current-candidate /green, mergeability and head-matching merge protection still require fresh verification.
A base-only move also requires assessing the changed context and complete-diff size.
Do not infer readiness from a stale CI result or unresolved conflict. Batch related fixes before
expensive proof, and never weaken assertions or waive quorum to make an old approval appear valid.

Behavior-blocking findings must be fixed and reverified; style, nit and documentation feedback may be tracked as follow-ups.

## Ready phase — finish `/ready`, then final reviews

Undrafting starts `/ready`; it does not establish completed readiness. Invoke the
`ready` skill for current-head `/green`, comments, conflicts, and cross-thread
regression checks. Follow `pr-green-definition` for applicable CI, documented
exceptions, and fresh mergeability; do not duplicate those mechanics here.
Keep an already non-draft PR non-draft while completing its open gates.

After ready-phase work stabilizes, perform the final `/er` when applicable, then
one final `/advice` when Advice applicability requires it. These are explicit closing obligations, not an automatic copy of draft approvals. Apply the same reasoned delta-and-scope decision to final approvals: a prior independent verdict can remain applicable without a fresh review at HEAD when it covers the final obligations. Request missing or affected review rather than an automatic full rerun; retain original verdict attribution. Required advice keeps
its canonical independent quorum; the orchestrator cannot approve itself.

If a final review requires a fix, batch fixes, rerun affected checks/evidence,
refresh `/green` at the new head, and repeat final `/er` then final `/advice`
where applicable until approved. No cycle-count limit substitutes for finishing;
stop only for a genuine blocker/decision or the governing autonomy deadline.
Report READY only after applicable closing verdicts and current readiness checks
pass. PARTIAL, FAIL, INCONCLUSIVE, WITHHELD, or an unavailable required reviewer
leaves its gate open. READY never supplies merge authorization. Earlier-SHA review applicability for readiness does not satisfy a stricter exact-head condition on any separately authorized automatic-merge route. Preserve that governing merge condition unless the human explicitly changes it; do not infer a new automatic-merge permission from this policy.

## Review records in the PR description

For every review type that runs, including `/es`, `/er`, `/advice`, `/wa`, `/cs`,
other named lanes and native reviews, update the PR description with the exact
reviewed SHA, review type/phase, verdict or status, gist URL, timestamp, and
reviewer/coverage. Document reviews additionally retain document hashes; their
context SHA does not turn document approval into code approval.

For evidence-gate compatibility, keep one current marker in the PR body:
`**Evidence**: <gist-url> (head <sha>)`, pointing to the authorized sanitized
evidence-review receipt for current applicability. Update that index only;
preserve the historical ledger, receipt URLs, and original capture SHAs.
Underlying raw artifacts may remain private. Missing publication authority or
an inaccessible receipt leaves this marker incomplete; never fabricate its URL.

Publish each completed review's sanitized receipt as a gist only within the
approved disclosure scope. A gist is link-accessible, not private storage; omit
credentials, private source, personal communications, and sensitive artifacts
unless separately authorized. Verify the gist URL and intended reviewer access
before calling publication complete. If tools or permissions prevent publishing,
record `PUBLICATION BLOCKED` with the exact reason and local receipt location;
never invent a gist URL or passing verdict, and do not claim the record complete.

Keep `PENDING`, `UNAVAILABLE`, `FAILED`, and `SUPERSEDED` results visible as well
as approvals. Read the current body before updating it. Use the idempotency key
review type + phase + reviewed SHA + receipt identity; append a new record only
when that key or status is new. Retries with unchanged key and unchanged status
are a no-op. A status transition (including PENDING to PASS with the same receipt)
appends a dated superseding event identifying its prior record; an applicability
change likewise creates a new event without erasing history. Preserve prior rounds and visual
tables. For a moved head, add a current-applicability review and retain the
original tested SHA and capture link, instead of rewriting historical receipts.
Read back the PR body after each update; uncertain writes require readback before
retrying. Optional/skipped reviews are recorded honestly without fabricated gists.

## Slow CI — never block-wait

Documentation-only changes use the CI exception immediately; the ten-minute threshold below applies only to changes that require CI.

**CI that does not exist is not CI to wait on.** Apply the canonical
`../pr-green-definition/SKILL.md` § No-CI exception only after
recording the bounded workflow/path applicability or eligible-runner-capacity
evidence it requires. If that evidence cannot establish a qualifying
exception, leave Gate 1 unproven. For a qualifying exception, record
`Gate 1: CI NOT APPLICABLE — <reason>` with the proving command/output and
run the documented bounded local equivalent when one exists; otherwise leave
the result unproven. Never replace this with `sleep N` + `gh pr checks`, and
never call unrun CI passed.

For checks queued/pending more than 10 minutes, follow the local-equivalent exception in `../pr-green-definition/SKILL.md`: run the workflow's actual command and post current-head proof. Passing local equivalents satisfy Gate 1 for backlogged checks; remote completion is not required for those checks. Failed checks, no-conflict verification, and merge authorization remain separate requirements.

## CodeRabbit/Bugbot — optional advisory reviewers

Neither draft-phase gate above nor `/green` includes CodeRabbit or Bugbot approval. **CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait, at any phase.

## Merge authorization

Merge authorization follows the shared size-tiered rule in `~/.codex/AGENTS.md` § Merge safety and any explicit target-repository contract. This skill does not require or waive a human `MERGE APPROVED` phrase where the governing rule does not; explicit local approval requirements remain in force.
