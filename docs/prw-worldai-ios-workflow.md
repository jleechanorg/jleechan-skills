# Building WorldAI for iOS with /prw

## Make the result visible

I used `/prw` while building the WorldAI iOS app to turn AI-assisted implementation into changes I could inspect. The useful output was more than a pull request: it was a working change, a captioned before/after demonstration, and evidence that a reviewer could check independently.

WorldAI is an AI-powered RPG and storytelling product. Players make decisions in an ongoing adventure, with an AI game master responding to those decisions. Building its iOS client meant bringing an existing product and backend onto a mobile surface, not starting the entire system from scratch.

This page explains the technique for other developers. It is a case-study guide, not a replacement for the executable workflow contract or a claim that every feature, build, or platform has passed acceptance.

The [Develop with idea velocity presentation](https://docs.google.com/presentation/d/1qLdMzZaIuP9IdpTBomuOGJTAspCEJo6Esu10zWFrhm4/edit?slide=id.iosNov2026#slide=id.iosNov2026) gives the broader iOS development context.

## Start with a difference you can see immediately

**Mobile web, not native iOS:** [frontend PR #459](https://github.com/jleechanorg/worldai_frontend/pull/459) changes the artwork in the invitation to install the iOS app. This is the clearest matched pair: the same signed-out page, invitation, text and buttons stay visible while the header changes.

| Before: tightly cropped character portrait | After: twin dragons and a central figure |
| --- | --- |
| ![Mobile-web iOS invitation before: a tightly cropped blond face fills the header](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/ios-pr459-route-marker-corrective-2026-11-02/baseline-main/mobile-screen.png) | ![Mobile-web iOS invitation after: two dragons flank a central figure above the same controls](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/ios-pr459-route-marker-corrective-2026-11-02/candidate-e5/mobile-screen.png) |

The change is obvious without reading the diff, and the unchanged controls give the reviewer a useful comparison. The gold dragon's head is still partly cropped: the screenshot reveals that limitation instead of hiding it. These stills demonstrate the artwork and layout, not that Install, Continue or Open app works.

Both captures used signed-out Chromium with an iPhone user agent at 390 × 844 CSS pixels, the same committed capture driver and a real development backend. Captured baseline: `1fcd6ba3bf035547875f8325d81dafed6bea706c`; candidate: `e5f1459f49fe50faaf95e59e7bad3a13f7d6f24d`. The [original reproduction record](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/ios-pr459-route-marker-corrective-2026-11-02/REPRODUCE.md) retains the source, route and process context; this is not Safari, native-app or production-deployment proof.

Both original PNGs were downloaded and visually inspected, and their hashes matched the [published manifest](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/ios-pr459-route-marker-corrective-2026-11-02/DELIVERY-SHA256SUMS). Before SHA256: `1db5131dba850389b4be4f2a3906e306a494d9e47c05a92cbd3ceafb2fa94ebe`. After SHA256: `ed066536188eae901962911da46247ef9cbe2c8d4a9284f11bbdd5674322ba06`.

## Show a readability bug, not just a new design

**Mobile web, not native iOS:** [merged frontend PR #483](https://github.com/jleechanorg/worldai_frontend/pull/483) fixes a visibly broken God Mode response. The same stored paragraph appears in both screenshots; this is the existing dark interface, not the paper/Journal redesign.

| Before: monospace text and overlapping inline-code boxes | After: proportional text and a clean tinted identifier |
| --- | --- |
| ![God Mode before: monospace paragraph with overlapping outlined boxes around a wrapped identifier](https://gist.githubusercontent.com/jleechan2015/7e38c650a5062b04df8c8c2bb6933976/raw/983ee0d78696dbea47be9e7e447baa3a7ec34bf1/godmode-web-before-real-wrapped.png) | ![God Mode after: the same paragraph in proportional text with a wrapped tinted identifier and no overlapping border](https://gist.githubusercontent.com/jleechan2015/7e38c650a5062b04df8c8c2bb6933976/raw/373d92dbdd8623d474049f36d4705aa212f211eb/godmode-web-after-real-wrapped.png) |

Look at the wrapped identifier in **Current Status & Pending Inquiries**. Before, its borders overlap nearby lines; after, the tinted text stays within its lines. The proportional font also changes wrapping, so the crops contain different amounts of surrounding text. They show the same response section, not a pixel-aligned screen or a newly generated answer.

The original PR records Chromium mobile emulation at 393 × 852 CSS pixels and 2× scale. These 786 × 1120 PNGs are chat-column crops. Baseline was deployed development source `2751ef25`; the after still was captured at `ddbbfbae`. The PR separately records web-runtime applicability to merged head `00eda31b85f002534f3f31ab4885a1308724d8a2`; that is not a fresh capture at the merged head. The [sanitized run receipt](https://gist.githubusercontent.com/jleechan2015/7e38c650a5062b04df8c8c2bb6933976/raw/c18698e68e95015f13f93ecdb04350aa0b8074bb/real-run-receipt-sanitized.json) records genuine app sign-in and the real development backend. The viewed response was already stored; no gameplay turn or LLM call was made for this comparison.

Both originals were downloaded, visually inspected and matched to the [published checksums](https://gist.githubusercontent.com/jleechan2015/7e38c650a5062b04df8c8c2bb6933976/raw/316c11b66179c41091a5cb69f32ad7b7b58f13ed/checksums.sha256). Before SHA256: `7f9cbaf019061566709fc21d6b06ff7ef4c8687c9d27274d9fa3be50ccd5cbff`. After SHA256: `b7a72e31cf4b49694a9f1bd72373ec90c7e55c2e2f894baa634354f5ab9e2e88`. This proves the observed completed-response layout, not streaming, native iOS, unbreakable strings, fenced code blocks or production deployment.

## See a native bug that screenshots actually catch

A clearer native example is the Settings label repair from [WorldAI frontend PR #439](https://github.com/jleechanorg/worldai_frontend/pull/439#native-settings-label-repair--e397-red-to-02ea-green). Look at **Background Theme → Embers** in these historical iOS simulator screenshots: the same Night Settings screen and selected option make the defect easy to compare.

| Before: the label splits midword | After: the whole label fits |
| --- | --- |
| ![Native Night Settings before: selected background label wraps as Ember on one line and s below](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr439-native-pill-02ea1446-20261102/comparison/e397-night-default-red.png) | ![Native Night Settings after: selected background label reads Embers on one line](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr439-native-pill-02ea1446-20261102/screenshots/393-night-default.png) |

**What to inspect:** before, the selected button reads `Ember` / `s`, making the whole option row taller. After, `Embers` stays on one line alongside Stars, Aurora and None; the Display section below moves upward. The surrounding Settings content, Night theme and selected option are visibly comparable. The status-bar clock differs, so these are separate captures, not an identical-state pixel diff.

**Why this demonstrates the workflow:** a source diff or passing component test cannot show this native text wrap. The pair exposes a specific failure and a visible repair at the affected control. It also makes the claim falsifiable: the reviewer can read the word itself rather than infer success from a green test or a caption.

**Provenance and limits:** the [published packet](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr439-native-pill-02ea1446-20261102/evidence.md) retains the earlier RED screenshot; the linked PR identifies its source as `e39768d8ed503eed9dbe1c97aca410800022e366`. The after screenshot is the 393-point, default-text-size capture at `02ea14465f6d04b86dc13b74d4f6b6dd57031014`. The [source receipt](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr439-native-pill-02ea1446-20261102/provenance/source-receipt.json) records candidate source and matching built/installed bundle hashes for the 393- and 375-point simulators. That receipt binds the candidate; it does not supply equivalent installed-bundle provenance for the older RED image. Retain that asymmetry rather than claiming both builds were independently reproduced.

Both PNGs were downloaded, decoded and visually inspected for this guide update; their bytes match the [published manifest](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr439-native-pill-02ea1446-20261102/manifest.tsv). Before SHA256: `bcaf0656e56585ea8fe1e928aeadb723d15a793920ea8b315f8f054b6bc925cb`. After SHA256: `2bdbfa59d9d96fa2632ce4e92508200029c60f243285f22fb8fca19021d9abfa`.

These stills support the narrow whole-label layout claim, not tapping, settings persistence, every accessibility size, a physical iPhone, or release acceptance. The source PR's broader visual review remained **PARTIAL / REQUEST CHANGES** for uncovered consumers; this useful screenshot pair is not a blanket approval of that PR. No new app run or capture was made for this guide.

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
