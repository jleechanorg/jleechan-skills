# Building WorldAI for iOS with /prw

## Make the result visible

I used `/prw` while building the WorldAI iOS app to turn AI-assisted implementation into changes I could inspect. The useful output was more than a pull request: it was a working change, a captioned before/after demonstration, and evidence that a reviewer could check independently.

WorldAI is an AI-powered RPG and storytelling product. Players make decisions in an ongoing adventure, with an AI game master responding to those decisions. Building its iOS client meant bringing an existing product and backend onto a mobile surface, not starting the entire system from scratch.

This page explains the technique for other developers. It is a case-study guide, not a replacement for the executable workflow contract or a claim that every feature, build, or platform has passed acceptance.

The [Develop with idea velocity presentation](https://docs.google.com/presentation/d/1qLdMzZaIuP9IdpTBomuOGJTAspCEJo6Esu10zWFrhm4/edit?slide=id.iosNov2026#slide=id.iosNov2026) gives the broader iOS development context.

## Watch a real captioned comparison

**Shared mobile-web example, not native iOS:** [watch the 6.6-second image-zoom comparison](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr257-mobile-zoomin-cde4015-20261024-v4/media/comparison-baseline-then-green.mp4).

[![Six frames from the captioned before/after zoom comparison](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr257-mobile-zoomin-cde4015-20261024-v4/contact-sheet.png)](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr257-mobile-zoomin-cde4015-20261024-v4/media/comparison-baseline-then-green.mp4)

The captions distinguish the baseline's whole-page enlargement from the candidate's image zoom. The after sequence moves from a fitted scene to a horse-face close-up, then holds the enlarged view. That makes the intended difference inspectable in a few seconds.

This is a 392 × 852 mobile-web recording. It does not prove native iOS behavior, physical touch, or a deployed release. Baseline source: `f77686750f4b357a92b6c07138b16a3f95936bc6`. Captured candidate: `1bd96c706ea282f35f3b62139ddc470c761a294c`. The [original scope and provenance](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr257-mobile-zoomin-cde4015-20261024-v4/README.md) carries the capture context. Video SHA256: `127233f2f2bcf813c2b9bb5269afdf40be94f9cf3e7fbb5f23fcba8937a09760`.

## Pair that with evidence from the native surface

Here is a separate historical iPad simulator comparison for campaign-list portraits:

| Before | After |
| --- | --- |
| ![Native iPad simulator campaign list before row portraits](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/campaign-list-portraits-pr276/campaign_list_before_ios.png) | ![Native iPad simulator campaign list after row portraits](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/campaign-list-portraits-pr276/campaign_list_after_ios.png) |

The after image shows a portrait at the right edge of a campaign row. The comparison also has an unrelated counter difference, `50/50` versus `50/7246`; it is not a perfectly identical-state pair.

These are iPad Pro 13-inch simulator stills, using the same Release binary with swapped JavaScript bundles and a local backend against real Firestore. They are not physical-iPad, iPhone, or deployed-service proof. The source revisions are `93a1e74d0fef48bcc30173cccb36f04225ff875c` before and `5e86deadb16d55f4d899639e52e51299e7c04278` after. The original capture clock is not unambiguously established here, so no new capture time is assigned.

Before SHA256: `df630be4a0c0b7c121467a40e952ecb2fdf9fbc7dbdefce74e5676f2fd1fabd7`. After SHA256: `414038466bbef7e7c0607877c3e1cbe6d0238576d0cf21639374df64aa825c32`.

The two examples illustrate different proof scopes. Keep that distinction visible even when a shared codebase serves both web and iOS.

## What /prw contributes

`/prw` is the entry into a repeatable PR process: define the outcome, implement a bounded change, produce evidence, review it independently, and resolve the remaining checks. Human merge and release decisions remain separate.

The exact stages, exceptions, reviewer requirements, and evidence rules live in the [canonical PR lifecycle](../.claude/skills/pr-lifecycle/SKILL.md). The [workflow manager](../.claude/skills/pr-workflow-manager/SKILL.md) discovers that contract and the target repository's own instructions. This article does not define another set of gates.

For a mobile game, the central question is simple: **can someone see the intended behavior working on the surface being claimed?** A passing component test helps, but it cannot show whether text is readable on an iPhone, a keyboard covers a button, or a streaming response moves the screen unexpectedly.

## The loop I want a reviewer to see

1. **A concrete user story.** Describe the player action, expected result, and what must remain unchanged. For example, a player should be able to read a response without unrelated scrolling interrupting them.
2. **The original behavior.** Capture the problem on the relevant baseline before changing it, when a meaningful before state exists. Keep the source revision and environment attached to that recording.
3. **A focused implementation.** Keep the change small enough that its effects can be explained. Use tests at the appropriate layer to catch regressions.
4. **The same journey afterward.** Repeat the scenario on the candidate, using matched content, device or viewport, and starting state where possible.
5. **A captioned comparison.** Make the difference visible without asking the reviewer to reconstruct it from a commit message.
6. **Independent inspection.** A reviewer watches the actual evidence, checks its provenance, and explains what it proves and what remains untested.

This is a way to connect a player-facing claim to code and observations. It is not an invitation to generate a polished demo that hides a failure.

## Make the before/after video the centerpiece

Use one short comparison video for one clear claim. Keep the original recordings as supporting artifacts. A combined edit should make every cut and speed change apparent; never splice different runs into an apparently continuous successful interaction.

Suggested caption structure, **illustrative rather than an execution receipt**:

| Segment | What to show | What the caption explains |
| --- | --- | --- |
| Context | Relevant screen and initial state | Platform, baseline/candidate identity, and the behavior being tested. |
| Before | The actual action and visible problem | What the player did and the observable failure. |
| After | The matched action on the candidate | The changed behavior, without claiming unseen internals. |
| Hold | The resulting screen long enough to inspect | Readability, layout, controls, and any remaining limitation. |

Good captions describe pixels and actions: “Before: the response moves out of view while text streams.” Avoid captions such as “All scrolling fixed,” which claim more than a single recording establishes. Do not imply a tap, network request, or persistence operation solely because something changed on screen.

Keep captions readable at phone size and away from the controls being demonstrated. A reviewer should be able to pause the video and still inspect the relevant UI. If the clip is sped up, label that explicitly and keep the original timing available.

## Visual evidence and tests answer different questions

| Evidence | Useful for | Does not establish by itself |
| --- | --- | --- |
| Unit or component tests | Deterministic state and rendering logic, edge cases | A real iOS interaction or production integration |
| Real browser capture | The observed browser behavior | Native iOS behavior |
| iOS simulator capture | The observed native simulator journey | A physical device, hardware, or production rollout |
| Physical-device capture | The observed device/build journey | Every device, every account, or every later build |
| Server request/response and persisted state | The correlated backend transition | That the player saw the result |
| Mock or proposed design | Intended appearance and a discussion of options | Executed application behavior |

For WorldAI, these boundaries matter. A story can render correctly while its saved state is wrong. A backend turn can complete while the phone never displays it. A mobile-web capture can look convincing without exercising the native app at all. Label the actual surface and pair visual evidence with the relevant lower-level proof.

## Give reviewers an evidence package they can use

Put the comparison beside the claim in the PR description, with direct links to the original media. A useful package includes:

- The user story and exact claim being evaluated.
- Baseline and candidate source revisions, plus the actual app build and platform.
- Original execution times, scenario, viewport or device, and relevant configuration.
- Before/after video, representative stills, and their hashes.
- Commands, results, and logs for the tests that support the claim.
- A claim-to-artifact map and explicit coverage gaps.
- The independent reviewer's observations and verdict, bound to the evidence they actually inspected.

Hashes verify that the bytes match; they do not prove how the recording was made. A link that opens is not a visual review. The reviewer needs to inspect the actual frames and, for interaction claims, the relevant motion and transitions.

Sanitize before sharing. Keep credentials, authentication state, private communications, account identifiers, and unrelated source out of public artifacts. Verify that the intended reviewer can access each link without exposing a private account or generating a new public share of private material.

## Reuse evidence without pretending it is new

A new commit does not automatically require another recording. Inspect the intervening change against the original claim. If the rendered behavior, scenario, and relevant dependencies are unchanged, record why the original evidence still applies. Keep its original revision and execution time.

If the change affects the behavior being shown, its test driver, or its assumptions, generate and review the affected proof again. Never relabel an old video as a new run. Missing proof remains missing even when CI is green.

## Try the workflow on one real change

Start with a small bug or feature in a repository you already own. Read [installation and rollback guidance](../INSTALL.md), then load [the /prw entry point](../.claude/skills/prw/SKILL.md) in your supported coding agent. Installation, authenticated tools, and a working device or simulator are separate prerequisites.

Give the agent the outcome, the existing PR or source scope, and the proof you expect:

> Drive this change through /prw. Preserve the repository's instructions and existing source owner. Demonstrate the user-visible result with a matched, captioned before/after recording on the claimed platform, retain the original artifacts, and obtain independent review. Report anything not proved. Do not infer merge or deployment authority.

The transferable idea is **make the change reviewable by sight, then connect that observation to its source and tests**. That helps an AI RPG developer assess whether the experience actually improved, rather than judging only the size of a diff or the confidence of an agent's summary.

## Related reusable skills

- [UI video evidence](../.claude/skills/ui-video-evidence/SKILL.md)
- [Video captioning](../.claude/skills/video-caption/SKILL.md)
- [Evidence standards](../.claude/skills/evidence-standards/SKILL.md)
- [Evidence review](../.claude/skills/evidence-review/SKILL.md)
- [UI bug proof](../.claude/skills/ui-bug-proof/SKILL.md)
