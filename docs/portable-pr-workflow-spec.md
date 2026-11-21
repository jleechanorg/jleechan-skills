# A portable spec for AI-reviewed changes

**The smallest workflow is a short spec, an exact candidate, relevant proof, and an independent AI review.** A pull request can hold all four. No slash command, planning framework, agent product, stage labels, or orchestration service is required.

## Goals

1. Make the intended outcome and what would count as success clear before substantial work.
2. Make it possible for another reader to verify exactly what was tested, reviewed, and left open.
3. Catch consequential defects without imposing the same cost on a typo and an authentication change.
4. Give the next person or agent enough context to resume without duplicating work.
5. Keep a decision that the change is ready separate from permission to merge or release it.

## Tenets

- **Specify the outcome, not the ceremony.** State the current behavior, desired behavior, constraints, non-goals, and acceptance checks. For a small change, the PR body is enough. For a consequential change, have an independent AI review the exact spec before implementation. That review does not approve the future code.
- **Bind claims to exact material.** Record repo and base/head for code; hash standalone documents and evidence where needed. Evidence names the tested revision and environment. Never relabel old evidence with a new revision.
- **Require before/after proof, and match it to the claim.** A test proves only the behavior it exercised, in its actual environment. For deployment or metrics, inspect the running surface or original events and calculation; source, mocks, and CI alone cannot establish those claims.
- **Separate authoring and judgment.** The author can self-review but cannot supply an independent vote. Give an independent reviewer the complete scoped packet and acceptance criteria, not prior verdicts or the answer you expect. Partial reviews provide findings, not approval. Don’t turn missing evidence or an unavailable reviewer into a pass.
- **Scale the work to risk.** Scale the depth, not the before/after requirement. A docs correction can use the exact before/after text and source review without a runtime test. Changes to user data, identity, money, availability, or irreversible behavior may need more independent review, realistic failure tests, and rollout or rollback evidence. Local policy can be stricter.
- **Maintain one accountable driver.** Keep one current record with owner, revision, open gates, next action, and a resume trigger when blocked. A sent handoff is not pickup. Don’t start a competing writer just because the current one is waiting.
- **Readiness is not authority.** Green checks, a review verdict, and the word “ready” do not grant merge, deployment, or spending permission.

## Building blocks

| Block | What goes in | What comes out |
|---|---|---|
| **Specify** | Goal, risk, constraints, known failures | Short spec with observable acceptance criteria and non-goals |
| **Make the change** | Spec and agreed scope | Exact base/head or equivalent immutable artifact, plus the changed-path inventory |
| **Prove it** | Acceptance criteria and candidate | Claim → matched before/after artifacts → tested revisions and environments → observed difference |
| **Review it** | Exact candidate, acceptance criteria, scoped source and evidence | Independent coverage, findings, verdict, and what would clear a blocker |
| **Decide** | Current candidate, applicable evidence and reviews, required checks, unresolved blockers | Ready, not ready, or withheld; separately record which action, if any, is authorized |
| **Continue or hand off** | Latest record and remaining work | One driver, next action, job handle or blocker, and a wake condition |

These are not mandatory serial stages. Proof and review can run in parallel when inputs are stable. One reviewer can cover both source and evidence for a small change if they actually inspect both and record the two judgments separately. A team can split those roles when risk or policy requires it.

## Mandatory before/after evidence

For each changed claim, state the expected difference and show what actually happened on the **before** revision and the **after** candidate. Use the same input, starting state, steps, and relevant environment on both sides. Record both revisions and any meaningful differences. On a regression, the same acceptance check must first expose the old failure, then pass on the candidate. On a new feature, show the old missing capability or prior behavior. If a meaningful baseline cannot be reproduced or retrieved, record the gap and withhold readiness for the claim. A prose reconstruction is not a baseline.

| Change | Required proof |
|---|---|
| **UI** | Capture **captioned before/after video** for interaction, timing, motion, or a transition. Show the actual action through the settled result. Use **captioned before/after screenshots** for a static claim, such as copy, spacing, or layout. Match the device or viewport, state, and settings relevant to the claim. A mock or DOM assertion is not visual proof. |
| **Backend** | Run a **real full-stack integration test** on both revisions. Make an actual network request to the running application through its real request entry point, middleware, and handler, using the real dependencies needed to support the claim. Capture the **raw API request and response**: method, path, relevant headers, payload, response status, and body. Independently read back consequential writes, queue activity, or other side effects; a 2xx alone proves none of them. For work with no HTTP API, retain the equivalent raw input and output at its real entry point, plus any side-effect readback. |
| **Source or documentation only** | Show the exact before/after source or text and what changed. No runtime evidence is required for a change that makes no runtime claim. |

Use dedicated test data and isolated environments. An emulator can support an integration claim scoped to that emulator; a stub at the dependency being claimed cannot prove that dependency works. Label substitutions. Preserve original captures in an authorized location and share only sanitized copies that are traceable to their originals and retain the fields and behavior needed to evaluate the claim. Reviewers need not access protected originals if these copies support the claim. If redaction hides a material fact and it cannot be verified safely, withhold the affected claim. Never publish tokens, credentials, or private payload data. Summaries can explain the result, not replace the captures. UI and backend rules both apply when the change makes both kinds of claim.

### Default decision rules

- **READY**: every required check and independent review applies to the current candidate, all required claims are proved, and no supported blocker is open.
- **NOT READY**: a required check failed, evidence contradicts a required claim, or a supported blocking defect remains.
- **WITHHELD**: material scope is missing, inaccessible, stale, or awaiting the applicable reviewer or check. Skipped, cancelled, pending, and not applicable are different states. A justified, policy-permitted exemption is not a passing check.
- If the base, candidate, evidence, environment, or relevant policy changes, recheck what the change affects. Carry a receipt forward only when an explicit delta assessment shows its claim still holds. Keep the original reviewed/tested identity in the record.
- At the decision point, check live source identity, required checks, open blockers, and repository requirements again. Only execute a separately authorized action.

## Copy this into a PR or task record

```text
Outcome / current problem:
Acceptance checks / spec link and revision:
Constraints / non-goals:
Risk / required checks and reviews / justified non-proof exemptions:
Candidate (base → head, or artifact digest):
Claim → shareable before artifact/revision/environment → shareable after artifact/revision/environment → observed difference:
Carried-forward receipts and why they still apply:
Independent review (candidate, coverage, verdict, blockers):
Current decision and scope:
Driver / next action / wake condition:
Merge or release authorization (separate):
```

### Copyable independent AI review

> Review this exact candidate against the attached spec and acceptance checks. Open the complete scoped source or documents and the before/after evidence needed for each claim, including applicable UI captures and traceable, sanitized copies of raw integration records. Do not request protected originals when safe copies are sufficient. Report the exact candidate, what you actually opened, anything missing, and separate source and evidence findings. For each blocking finding give a location, a concrete failure or risk, and how to clear it. Give a verdict for the **assigned scope**: **CHANGES REQUESTED** if you establish a blocker; otherwise **WITHHELD** if required material is missing, stale, or inaccessible; otherwise **APPROVED** only after full required coverage. A narrower scope must be agreed before review and cannot stand in for overall readiness. Do not infer unseen behavior or authorize any action.

### Example: an autosave fix

**Spec:** Draft text saves every ten seconds. Force-closing after a confirmed save and reopening restores the last committed text once. Text after the last successful save may be lost. No cloud sync in scope.

**Proof:** A matched pair of captioned device videos shows typing, the save indicator, force-close, and reopen: the old version loses the committed text; the new version restores it once. A failed-write test verifies that the UI does not report “Saved.” If this change also touches a server save, run the same real API test against both revisions and retain the raw request, response, and persisted-state readback privately; attach traceable, sanitized copies. Without the required pair, the affected claim remains withheld.

## Make it your own

Put the short record in a PR template, an issue, or a file. Implement the blocks as one skill, several small skills, or ordinary team checklists. Configure risk tiers, which checks count, independent reviewer count and eligibility, and merge authority in your own repository policy. Automation should read and update the same record, not invent a second definition of ready.

*Source: extracted from the pinned [PR lifecycle](https://github.com/jleechanorg/jleechan-skills/blob/d0c27052dcbb3762b4221d63a58bd4946869c631/.claude/skills/pr-lifecycle/SKILL.md), [review routing](https://github.com/jleechanorg/jleechan-skills/blob/d0c27052dcbb3762b4221d63a58bd4946869c631/.claude/skills/pr-lifecycle/review-routing.md), [advice](https://github.com/jleechanorg/jleechan-skills/blob/d0c27052dcbb3762b4221d63a58bd4946869c631/.claude/skills/advice/SKILL.md), and [evidence standards](https://github.com/jleechanorg/jleechan-skills/blob/d0c27052dcbb3762b4221d63a58bd4946869c631/.claude/skills/evidence-standards/SKILL.md). This is an adaptable spec, not a substitute for a repository’s existing gates.*
