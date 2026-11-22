# A portable spec for AI-reviewed changes

Start with a short spec, a pinned candidate, matched before/after proof, and independent AI review. A PR, issue, or shared file can hold all four. You do not need a planning framework or slash command.

## Why this exists

AI drivers fail in predictable ways. They report success from a sent message, a 2xx or a green check. They reuse evidence from an older revision, review their own work, stop on a gate they made up, or offer an old incident log instead of reproducing the bug. This spec keeps the parts that prevent those failures and drops the ceremony.

## Goals

*What the workflow must achieve.*

1. Make the intended outcome and what counts as success clear before substantial work, so a reviewer judges against a target, not a story.
2. Let another reader verify exactly what was tested, reviewed and left open, so trust comes from artifacts instead of the author's word.
3. Catch consequential defects while small changes still ship quickly, so effort lands where the risk is.
4. Give the next person or agent enough context to resume without redoing work or starting a competing writer.
5. Merges, releases and spend happen only with the authority of whoever owns them.

## Tenets

*The principles for making trade-offs while doing the work; each says why.*

- **Specify the outcome, not the ceremony.** State current behavior, desired outcome, non-goals and observable acceptance checks before substantial work; a PR description is enough for a small change. Have an independent AI review consequential or ambiguous designs before implementation. *Why:* without a target, any result can be argued into a pass.
- **Prove each changed claim, freshly, at the boundary where it matters.** Run the same check before and after. For a fix, reproduce the failure yourself on the base revision for this change (fresh means run for this change, not rerun on every head move; afterwards rerun only when the delta touches what the evidence proves); only an independently accepted safety reason excuses that run. Use the smallest evidence that can fail for the right reason. *Why:* a test proves only what it exercised, and an old record shows what happened then, not what this revision does.
- **Pin what was tested and read.** Name the revision, environment and inputs; never move an old observation onto a new revision without checking the affected source, configuration and environment. *Why:* evidence detached from its revision can't be checked or trusted.
- **Separate authoring and judgment.** The author or driver cannot supply an independent vote; reviewers get the complete material, not the expected answer. *Why:* self-review and partial reads miss exactly the defects the author can't see.
- **Scale depth to risk, not the proof requirement.** Every change still shows before and after; higher-risk changes get more reviewers and realistic failure tests. A trivial-change fast path can skip extra review, but never before/after proof for a behavior claim, and never applies to a high-risk change. *Why:* uniform heavy process gets skipped, uniform light process misses real risk.
- **Keep one accountable driver who finishes.** One owner, one durable record, one next action. A review request is not a review and a handoff is not pickup. A blocker names the specific authority the driver lacks, or a step shown, with evidence, to be impossible; anything else is the next action. *Why:* invented blockers and silent handoffs strand work an agent could finish.
- **Bound review and side quests.** Choose the reviewers and a deadline before asking; a lapsed deadline is missing review, not approval, so replace the reviewer or report WITHHELD. Batch every finding into one revision, fix blockers now, and re-review only what that revision affects. Stop when the required reviewers approve at the current head with no blocking finding; record nonblocking findings and unrelated discoveries as follow-ups instead of widening the change. A finding that violates an acceptance check is never a follow-up. *Why:* every extra round moves the head and resets votes, and an open-ended loop or side quest spends the time the outcome needed.
- **Readiness is not authority.** Green checks, verdicts and "ready" never grant merge, release or spend. *Why:* those decisions belong to whoever holds that authority, and conflating them is how unreviewed changes ship.

## Workflow

1. **Specify.** Write acceptance checks and choose evidence for each claim before implementing.
2. **Implement.** Record base, head, changed paths, and any relevant configuration or dependencies.
3. **Prove.** Run the same acceptance check against before and after: match inputs, starting state, steps, and relevant conditions. A fix shows the old failure and the new success; a new feature shows the old absence and the new behavior. Reproduce the failure yourself on the base revision; an earlier incident record can support the claim but cannot replace that fresh run. If the base revision cannot be run safely, record the before side as withheld with the reason and narrow the claim; the verdict stays WITHHELD unless an independent reviewer accepts that reason. Use the exact diff for source or documentation with no runtime impact.
4. **Review.** Classify every changed path for readiness. Give independent reviewers the complete base-to-head diff, changed files at both revisions (or verified absence), acceptance checks, and proof. Separate source and evidence findings. A scoped review counts only for its stated scope, not as full readiness coverage. The author or driver cannot supply an independent vote. A repository may define narrow, documented fast paths for trivial changes; a fast path never applies to a high-risk change, never removes before/after proof for a behavior claim, and is recorded when used. Batch findings into one revision and re-review only the affected scope. For high-risk changes (for example security, credentials, data integrity, persistence, deployment, or merge policy), use at least two independent reviewers unless repository policy requires more, and set any extra controls there.
5. **Decide.** Mark **READY** only with applicable proof, required checks, and independent review at the current candidate. Use **NOT READY** for a demonstrated failure, **WITHHELD** for a material evidence or coverage gap. Record separately who can merge or release. Keep the next action and resume trigger visible while blocked. A blocker names the specific authority the driver lacks or the step that is impossible; work the driver can do (fixtures, captures, publication to an evidence store authorized for the task, choosing an evidence route, finding records, fixing the code or configuration behind a failing check without weakening the check) is the next action, not a blocker. An impossible step needs evidence that it is impossible.

## Choose evidence by claim

Every row requires before and after. Use more than one row when a change makes more than one kind of claim.

| Change and example | Required before/after proof | What the reviewer checks |
|---|---|---|
| **Static UI:** make a badge readable in Light mode. | Captioned screenshots or readable settled frames in captioned video from the rendered interface. Match viewport, text scale, theme, and sign-in state. Cover the sizes and modes affected by the diff or required by repository policy. | The actual pixels, text, contrast, and clipping. Layout at rest needs no video. |
| **UI interaction or transition:** remove a flash between sign-in and the dashboard. | Captioned videos from the same starting state, through the action and the settled result, at the relevant viewport or device. For a loading or first-paint claim, start recording before navigation or the trigger and keep the ordinary load through the result. | The action happened, the transient state is visible or absent, and the correct destination settles. Paused frames can explain but cannot replace the sequence. |
| **Backend with real production or staging records:** an API misreads records created under an older schema. | Real requests to both revisions using authorized representative records, or an approved faithful copy when comparing revisions in isolation. Capture the raw request/response and independently read back affected state. Use serving-environment evidence if the claim is about that environment. | The record shape actually triggers the bug; the same lookup returns the correct data after the change. Use a read-only probe or approved copy instead of mutating customer records for proof. |
| **Backend with dedicated test data:** an upload finalizes twice or disappears on reload. | Run the real app and relevant services for both revisions. Use controlled accounts and seeded records in a disposable database, test bucket, or preview. Capture the raw requests/responses and independently read back bytes, identity, and write count. | A different database or isolated project is fine if it preserves the semantics being tested. A fake store cannot prove the real store; an emulator proves emulator scope. Add an overlapping-request control if claiming concurrency safety. |
| **Backend with a captured fixture:** interrupted provider response previously saved an invalid story. | Replay the same real captured request/response or ordered stream through the real app entry point on both revisions. Replace only the captured external boundary; keep actual parsing, workflow, serialization, and persistence path under test. Apply the fixture provenance rules below. | The old app mishandles the preserved interruption; the new app returns the intended status or marker and saves the intended state. Replay proves how the app handles that sample, not what the provider emits today. |
| **Unit test only:** a pure formatter converts 60 seconds to the wrong label. | Run the same focused test on both revisions. Show the incorrect value then expected value; keep the test command and assertions. For a behavior-preserving refactor, show the invariant passes on both and review the diff. | No network, rendering, storage, auth, or deployed behavior is affected by the claim. No higher-layer run is needed for this deterministic scope. |
| **Live model or provider:** a prompt should return a schema field through an actual provider. | Compare current real requests under a pinned provider/model and matched input or state. Save complete relevant raw replies and, for app claims, also follow the real app through persistence or projection. Follow approved budgets. | Distinguish one observed capability from reliable behavior. Use enough matched samples for a frequency claim; a stub or historical reply cannot prove current model behavior. |
| **Performance, telemetry, or rollout:** reduce mobile transfer bytes, ship a flag, or log a signup. | Compare measured traces or raw events and recompute the claimed metric. For a deployed change, read back the serving revision and actual activation or sink. Include representative controls, repeat measurements when noisy, and keep environment differences explicit. | Compare the same journey and units; confirm the claimed destination or sink actually changed. A rendered page, merge, or 2xx is not measurement or delivery proof. |
| **Documentation or source only:** correct an installation link without changing execution. | Exact text diff and link/structure check, with absence documented for a new file. | No runtime behavior is affected; all new claims and links match their sources. |

### Capture actual behavior

UI proof comes from the actual served builds and real application path, not an injected DOM, mock screen, or hand-seeded browser response. Record the served build, capture time, and conditions for each side. For motion, show a continuous sequence through the result; don't splice out the transition being reviewed. For added or removed copy, the matching state must show its absence on the side without it.

### Raw integration records and fixture provenance

Capture the method, route, relevant headers, payload, status, and response body on each revision; use equivalent raw inputs and outputs for jobs or non-HTTP services. For streaming, retain ordered events and the terminal outcome. Read back writes, queues, or downstream events separately from the response. Keep originals private, and share traceable sanitized copies. If redaction hides a fact needed for the claim, withhold it.

A **real capture** fixture must have the original capture timestamp with timezone, a safe opaque receipt ID, the source environment and backend identity or provider/model, a fixture digest, and a sanitized provenance receipt with a verifiable pointer to the backend or model capture. Link a revision-pinned, reviewer-accessible receipt in a destination authorized for the task, such as a revision-pinned Gist or an immutable access-controlled receipt already available to the intended reviewers. The receipt covers provenance only; it does not waive separate PR publication requirements. Require the verified serving revision for a revision-specific claim. Otherwise, mark an unknown revision explicitly and limit the claim to replay of the verified capture. A digest verifies the bytes, not their origin. A reviewer must be able to corroborate provenance against the authorized source or an independently verified capture receipt. Put only safe metadata in a shared receipt and use restricted links for protected captures. Never widen access or publish a private payload, credential, or correlation ID to satisfy provenance. Keep capture time separate from replay time. Preserve event order, omissions, malformed values, and the actual failure. If authors supply or materially alter the behavior-defining payload, label it **synthetic contract fixture**. If no safe, verifiable provenance link can be supplied, do not count it as real-capture proof.

## What to reject in review

- A screenshot offered as proof of no flash, or a browser viewport labeled as native-device proof.
- An endpoint mock used to prove auth or storage, or a 2xx used to prove a write without readback.
- A fabricated fixture labeled real, an inconvenient failure edited into success, or a curated replay offered as proof of live provider reliability.
- A green check marked as a passing journey when the job skipped that journey, or a finished merge treated as deployed success.
- A truncated source read counted as a vote; a prior review copied onto a new SHA without claim-specific delta verification; review instructions that give the reviewer the expected answer.

## Copy into a PR, issue, or file

```text
Outcome, non-goals, and acceptance checks:
Base → head, environment, and changed paths:
Claim | before artifact/revision | after artifact/revision | observed result | limits
Required checks / independent reviewers:
Review receipt: exact candidate, complete coverage, findings, verdict
Driver / next permitted action / blocker or resume trigger:
Ready / not ready / withheld:
Merge or release authority (separate):
```

Reviewer prompt: “Read the complete assigned source and open the matched evidence for each claim. Report the exact revisions, what you inspected, what is missing, and a concrete failure and clearance test for each blocker. Return APPROVED, CHANGES REQUESTED, or WITHHELD for the assigned scope. Do not infer a wider verdict.”

## Implementations and follow-through

Use this spec to design or evaluate a workflow; the target repository still owns its operational policy and permissions. An implementation can plug in its own spec store, evidence runner, review transport, readiness gate, and resume mechanism. Each reads or writes the same claim and decision record; none may quietly redefine what counts as proof or add authority. A template and manual review suffice.

Models that lose track of work may need an explicit **goal** or scheduled **nudger**. A goal records the exact outcome, candidate, unmet gates, and stop condition and keeps them in the driver’s context. A nudger periodically rechecks the existing owner, current SHA, last verified result, and resume trigger; it asks the same owner to take the next permitted step when actionable, and to keep going until READY. The owner stops early only when a step needs authority it lacks, a step is shown to be impossible, or the user pauses, holds or stops the work. READY ends the nudger's work; it never extends to merge, release or spend. It does not create a second writer, repeat unchanged alerts, or turn a timer into execution proof. Stop after verified completion or cancellation; honor pauses, holds, and permissions. Use a native `/goal` command or cron only if the implementation supports and authorizes it.

[The jleechan-skills PR Workflow Manager](../../.claude/skills/pr-workflow-manager/SKILL.md) is one implementation. Its stages, review routes, and host tooling are optional for teams implementing this spec.
