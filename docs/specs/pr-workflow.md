# A portable spec for AI-reviewed changes

Start with a short spec, a pinned candidate, matched before/after proof, and independent AI review. A PR, issue, or shared file can hold all four. You do not need a planning framework or slash command.

## Goals and tenets

- Define success before substantial work: current behavior, desired outcome, non-goals, and observable acceptance checks. A PR description is enough for a small change. Ask an independent AI to review consequential or ambiguous designs before implementation.
- Prove each changed claim at the boundary where it matters. Scale proof and reviewer depth to risk. Use the smallest evidence that can fail for the right reason.
- Pin what was actually tested and read. Never attach an old observation to a new revision without checking the affected source, configuration, and environment.
- Keep one accountable driver and one durable record. A review request is not a review, a handoff is not pickup, and readiness does not authorize merge, release, or spend.

## Workflow

1. **Specify.** Write acceptance checks and choose evidence for each claim before implementing.
2. **Implement.** Record base, head, changed paths, and any relevant configuration or dependencies.
3. **Prove.** Run the same acceptance check against before and after: match inputs, starting state, steps, and relevant conditions. A fix shows the old failure and the new success; a new feature shows the old absence and the new behavior. Use the exact diff for source or documentation with no runtime impact.
4. **Review.** Give an independent AI the complete relevant diff, changed source, acceptance checks, and proof. Separate source and evidence findings, even when one person reviews both. The author or driver cannot supply an independent vote. For high-risk changes, set the independent reviewer count and required controls in repository policy.
5. **Decide.** Mark **READY** only with applicable proof, required checks, and independent review at the current candidate. Use **NOT READY** for a demonstrated failure, **WITHHELD** for a material evidence or coverage gap. Record separately who can merge or release. Keep the next action and resume trigger visible while blocked.

## Choose evidence by claim

Every row requires before and after. Use more than one row when a change makes more than one kind of claim.

| Change and example | Required before/after proof | What the reviewer checks |
|---|---|---|
| **Static UI:** make a badge readable in Light mode. | Captioned screenshots or readable settled frames in captioned video from the rendered interface. Match viewport, text scale, theme, and sign-in state. Cover the sizes and modes affected by the diff or required by repository policy. | The actual pixels, text, contrast, and clipping. Layout at rest needs no video. |
| **UI interaction or transition:** remove a flash between sign-in and the dashboard. | Captioned videos from the same starting state, through the action and the settled result, at the relevant viewport or device. Capture ordinary loading for a normal-load claim. | The action happened, the transient state is visible or absent, and the correct destination settles. Paused frames can explain but cannot replace the sequence. |
| **Backend with real production or staging records:** an API misreads records created under an older schema. | Real requests to both revisions using authorized representative records, or an approved faithful copy when comparing revisions in isolation. Capture the raw request/response and independently read back affected state. Use serving-environment evidence if the claim is about that environment. | The record shape actually triggers the bug; the same lookup returns the correct data after the change. Use a read-only probe or approved copy instead of mutating customer records for proof. |
| **Backend with dedicated test data:** an upload finalizes twice or disappears on reload. | Run the real app and relevant services for both revisions. Use controlled accounts and seeded records in a disposable database, test bucket, or preview. Capture the raw requests/responses and independently read back bytes, identity, and write count. | A different database or isolated project is fine if it preserves the semantics being tested. A fake store cannot prove the real store; an emulator proves emulator scope. Add an overlapping-request control if claiming concurrency safety. |
| **Backend with a captured fixture:** interrupted provider response previously saved an invalid story. | Replay the same real captured request/response or ordered stream through the real app entry point on both revisions. Replace only the captured external boundary; keep actual parsing, workflow, serialization, and persistence path under test. Apply the fixture provenance rules below. | The old app mishandles the preserved interruption; the new app returns the intended status or marker and saves the intended state. Replay proves how the app handles that sample, not what the provider emits today. |
| **Unit test only:** a pure formatter converts 60 seconds to the wrong label. | Run the same focused test on both revisions. Show the incorrect value then expected value; keep the test command and assertions. For a behavior-preserving refactor, show the invariant passes on both and review the diff. | No network, rendering, storage, auth, or deployed behavior is affected by the claim. No higher-layer run is needed for this deterministic scope. |
| **Live model or provider:** a prompt should return a schema field through an actual provider. | Compare current real requests under a pinned provider/model and matched input or state. Save complete relevant raw replies and, for app claims, also follow the real app through persistence or projection. Follow approved budgets. | Distinguish one observed capability from reliable behavior. Use enough matched samples for a frequency claim; a stub or historical reply cannot prove current model behavior. |
| **Performance, telemetry, or rollout:** reduce mobile transfer bytes, ship a flag, or log a signup. | Compare measured traces or raw events and recompute the claimed metric. For a deployed change, read back the serving revision and actual activation or sink. Include representative controls, repeat measurements when noisy, and keep environment differences explicit. | Compare the same journey and units; confirm the claimed destination or sink actually changed. A rendered page, merge, or 2xx is not measurement or delivery proof. |
| **Documentation or source only:** correct an installation link without changing execution. | Exact text diff and link/structure check, with absence documented for a new file. | No runtime behavior is affected; all new claims and links match their sources. |

### Capture actual behavior

UI proof comes from the actual served builds and real application path, not an injected DOM, mock screen, or hand-seeded browser response. Record the served build, capture time, and conditions for each side. For motion, show a continuous sequence through the result; don't splice out the transition being reviewed.

### Raw integration records and fixture provenance

Capture the method, route, relevant headers, payload, status, and response body on each revision; use equivalent raw inputs and outputs for jobs or non-HTTP services. For streaming, retain ordered events and the terminal outcome. Read back writes, queues, or downstream events separately from the response. Keep originals private, and share traceable sanitized copies. If redaction hides a fact needed for the claim, withhold it.

A **real capture** fixture must have the original capture timestamp with timezone, a safe opaque receipt ID, the source environment and backend revision or provider/model, a fixture digest, and a **revision-pinned Gist URL** containing sanitized provenance and a verifiable pointer to the backend or model capture. A digest verifies the bytes, not their origin. A reviewer must be able to corroborate provenance against the authorized source or an independently verified capture receipt. Put only safe metadata in the Gist and use restricted links for protected captures. Never publish a private payload, credential, or correlation ID to meet the Gist requirement. Keep capture time separate from replay time. Preserve event order, omissions, malformed values, and the actual failure. If authors supply or materially alter the behavior-defining payload, label it **synthetic contract fixture**. If no safe, verifiable provenance link can be supplied, do not count it as real-capture proof.

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

Models that lose track of work may need an explicit **goal** or scheduled **nudger**. A goal records the exact outcome, candidate, unmet gates, and stop condition and keeps them in the driver’s context. A nudger periodically rechecks the existing owner, current SHA, last verified result, and resume trigger; it asks the same owner to take the next permitted step when actionable. It does not create a second writer, repeat unchanged alerts, or turn a timer into execution proof. Stop after verified completion or cancellation; honor pauses, holds, and permissions. Use a native `/goal` command or cron only if the implementation supports and authorizes it.

[The jleechan-skills PR Workflow Manager](../../.claude/skills/pr-workflow-manager/SKILL.md) is one implementation. Its stages, review routes, and host tooling are optional for teams implementing this spec.
