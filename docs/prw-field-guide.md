# PR workflow: make an AI-assisted game change reviewable

Use PR workflow (`/prw` for short) to connect a small game change to tests, a visible before/after comparison and independent review. Start with one player action and follow the worked example below.

Status: experimental. Updated 2026-11-09. Source: [jleechan-skills](../README.md). Licence: [MIT](../LICENSE); the notice is reproduced below.

Contents: [Prerequisites](#what-you-need) · [Workflow](#a-six-step-loop) · [Worked example](#worked-example-reading-while-a-response-streams) · [Evidence receipt](#copyable-evidence-receipt) · [Source](#canonical-source) · [Licence](#mit-notice)

## The problem

A coding agent can produce a convincing explanation, a pull request and passing tests without showing that the player-facing experience works. For an AI RPG, that gap matters: the backend can finish a turn while the phone never displays it, or a screenshot can look correct while a streaming response moves the text out of view.

Follow the method manually, or install the complete workflow to use the slash command. The target repository's instructions and the [canonical lifecycle](../.claude/skills/pr-lifecycle/SKILL.md) determine the applicable gates.

## What you need

- One repository and a small, explicit player-facing change you are authorized to make.
- The repository's instructions, the existing source owner, and the correct baseline and candidate revisions.
- A way to run the real application on the surface you intend to claim: browser, simulator or physical device.
- Appropriate tests, a recording tool, and an independent reviewer who can inspect the actual artifacts.
- A private evidence location accessible to that reviewer. Public sharing requires separate permission.

For the automated workflow, follow the [installation guide](../INSTALL.md), choosing the `prw` profile for an isolated install. Inspect the installer and use a fresh destination before changing your normal setup. Copying only `prw/SKILL.md` does not install the workflow.

The [profile definition](../shared/install-profiles.json) selects twelve workflow skills and four explicit command aliases, plus linked dependencies. It excludes browser and personal-infrastructure integrations unless explicitly selected. Git access, authorized GitHub operations, reviewer tools, application dependencies, capture tools and service accounts remain separate prerequisites. Report unavailable dependencies before claiming their gates pass.

## A six-step loop

### 1. Define one observable outcome

Write the player action, expected result and invariants before changing code. Avoid broad outcomes such as “fix scrolling.” Choose something inspectable, such as “while the player reads an earlier paragraph, streaming a new response does not pull that paragraph out of view.”

Record the actual repository, branch and commit. If there is already a PR or an assigned source owner, continue that work rather than opening a competing implementation.

### 2. Preserve a real before state

When a meaningful baseline exists, record the failing journey before the fix. Keep the original source revision, app build, platform, starting state and capture time. Do not recreate the baseline by selectively disabling the candidate or drawing a proposed screen.

For comparisons, hold the scenario, viewport or device, and content steady where possible. Document unavoidable differences. A changed portrait, story or account state can make a comparison look better for reasons unrelated to the code.

### 3. Implement and test a bounded change

Change the relevant behavior and run the tests required by the repository. Use unit tests for deterministic logic and integration tests for the boundaries involved. If the claim depends on live persistence, authentication, model behavior or native interaction, a mocked component test does not prove that boundary.

Keep baseline reproduction separate from the final polished comparison. Gather the complete candidate evidence after the behavioral changes stabilize so that the expensive run covers one coherent revision.

### 4. Repeat the same journey on the candidate

Capture the triggering action, the transition and the resulting state. Use continuous video for scrolling, streaming, navigation, timing or multi-step interactions. A still image can support a static layout claim, but cannot prove a spinner moved or an edit survived an asynchronous response.

Label browser captures as browser captures. A mobile viewport is not native iOS, an iOS simulator is not a physical phone, and a local build is not a deployed release.

### 5. Package the evidence beside the claim

Make a short captioned comparison and retain the originals. Explain cuts, holds and speed changes. Keep the relevant controls and text visible. Never assemble stills into apparent interaction footage or splice separate attempts into one apparently successful run.

Store source revisions, test results, original media, artifact hashes, and a claim-to-artifact map together. Hashes establish byte identity; they do not establish that a capture came from the stated environment.

### 6. Get independent inspection and close the gaps

Ask the reviewer to inspect the actual frames and relevant motion, check provenance, and state what each artifact proves. A working download link or a checklist of filenames is not a visual review.

Resolve blocking findings, rerun affected proof, and retain valid unaffected proof with an explicit applicability assessment. Preserve the original capture and review revisions when reusing evidence. Missing proof stays missing even when CI is green.

Some repositories opt into six labelled stages. The six steps here describe the evidence-producing method, not those stage labels. `FINAL_READY` and permission to merge or deploy remain separate decisions.

## Worked example: reading while a response streams

This worked test design starts every result as **NOT RUN**.

**User story:** A player can scroll back to read earlier text while the next response streams, then deliberately return to the newest text.

**Scope:** The actual application on a declared platform. Choose a stable test campaign and an authorized request path. Record any real-service cost before running. A deterministic unit fixture can test scroll-state logic, but must not be labelled real streaming proof.

**Before and after procedure:**

1. Open the same starting scene on each revision. Record the viewport/device, app build, fixture or state identifier, and initial scroll position in the private receipt.
2. Start one response through the application's normal supported action.
3. While text is arriving, scroll up until a chosen earlier paragraph is visible. Capture the action and subsequent updates continuously.
4. Observe whether that paragraph remains readable without an unrequested jump to the newest text. Record the visible behavior rather than a guessed internal cause.
5. Use the application's intended control or gesture to return to the newest text. Observe that the remaining response and completion state are reachable.
6. Repeat on the candidate with the same scenario. If content, timing or service responses differ, disclose those differences and narrow the claim accordingly.

**Acceptance record:**

| Claim | Required observation | Initial result |
| --- | --- | --- |
| Reading position is preserved during updates | Continuous candidate footage showing scroll action and later arriving text without the unwanted jump | NOT RUN |
| Latest response remains reachable | Actual return-to-latest action and resulting screen | NOT RUN |
| Deterministic scroll-state logic is covered | Repository test command, output and candidate revision | NOT RUN |
| Native behavior works | Native capture on the stated simulator/device, if that is part of the claim | NOT RUN |

This test does not establish model quality, durable campaign state, behavior on every device or production rollout. Add separate proof only when those claims are in scope.

## Copyable evidence receipt

Use this with the repository's existing PR record rather than maintaining a competing source of truth. Replace placeholders; do not mark an unrun item as passed.

```text
Claim and user story:
Repository / PR / source owner:
Baseline revision / candidate revision:
Actual app build and platform:
Capture time and timezone:
Starting state and known before/after differences:
Reproduction steps and expected observations:
Test command / result / execution time:
Original before media / original after media:
Comparison media and declared edits, holds or speed changes:
Artifact hashes:
Claim -> artifact and time range -> observed result:
Independent reviewer / inspected artifacts / verdict:
What this evidence does not prove:
Outstanding blocker / owner / next permitted action:
```

Keep credentials, authentication storage, private communications and unrelated source out of a shareable receipt. Retain sensitive reproduction details only in the authorized private evidence store when needed. Verify the reviewer's access without widening it unnecessarily.

## Canonical source

The entry chain is [prw](../.claude/skills/prw/SKILL.md) → [PR Workflow Manager](../.claude/skills/pr-workflow-manager/SKILL.md) → [PR Lifecycle](../.claude/skills/pr-lifecycle/SKILL.md). The lifecycle owns review routing, exceptions, evidence applicability and readiness; this guide applies that contract to a game-UI example.

For the full requirements, read [evidence standards](../.claude/skills/evidence-standards/SKILL.md), [evidence review](../.claude/skills/evidence-review/SKILL.md) and [UI video guidance](../.claude/skills/ui-video-evidence/SKILL.md).

## MIT notice

MIT License

Copyright (c) 2025 WorldArchitect.AI Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
