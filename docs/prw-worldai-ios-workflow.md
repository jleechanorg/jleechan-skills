# Building WorldAI for iOS with /prw

## Make the result visible

I used `/prw` while building the WorldAI iOS app to turn AI-assisted implementation into changes I could inspect. The useful output was more than a pull request: it was a working change, a captioned before/after demonstration, and evidence that a reviewer could check independently.

WorldAI is an AI-powered RPG and storytelling product. Players make decisions in an ongoing adventure, with an AI game master responding to those decisions. Building its iOS client meant bringing an existing product and backend onto a mobile surface, not starting the entire system from scratch.

This page explains the technique for other developers. It is a case-study guide, not a replacement for the executable workflow contract or a claim that every feature, build, or platform has passed acceptance.

The [Develop with idea velocity presentation](https://docs.google.com/presentation/d/1qLdMzZaIuP9IdpTBomuOGJTAspCEJo6Esu10zWFrhm4/edit?slide=id.iosNov2026#slide=id.iosNov2026) gives the broader iOS development context.

## Start with a difference you can see immediately

**Mobile web, not native iOS:** [merged frontend PR #459](https://github.com/jleechanorg/worldai_frontend/pull/459) changes the artwork in the invitation to install the iOS app. This is the clearest matched pair: the same signed-out page, invitation, text and buttons stay visible while the header changes.

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
| ![God Mode before: monospace paragraph with overlapping outlined boxes around a wrapped identifier](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr674-docs-godmode-pr483-20261104/godmode-web-before-real-wrapped.png) | ![God Mode after: the same paragraph in proportional text with a wrapped tinted identifier and no overlapping border](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr674-docs-godmode-pr483-20261104/godmode-web-after-real-wrapped.png) |

Look at the wrapped identifier in **Current Status & Pending Inquiries**. Before, its borders overlap nearby lines; after, the tinted text stays within its lines. The proportional font also changes wrapping, so the crops contain different amounts of surrounding text. They show the same response section, not a pixel-aligned screen or a newly generated answer.

The original PR records Chromium mobile emulation at 393 × 852 CSS pixels and 2× scale. These 786 × 1120 PNGs are chat-column crops. Baseline was deployed development source `2751ef25`; the after still was captured at `ddbbfbae`. The PR separately records web-runtime applicability to merged head `00eda31b85f002534f3f31ab4885a1308724d8a2`; that is not a fresh capture at the merged head. The [sanitized run receipt](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr674-docs-godmode-pr483-20261104/real-run-receipt-sanitized.json) records genuine app sign-in and the real development backend. The viewed response was already stored; no gameplay turn or LLM call was made for this comparison.

Both originals were downloaded, visually inspected and matched to the [published checksums](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr674-docs-godmode-pr483-20261104/checksums.sha256). Before SHA256: `7f9cbaf019061566709fc21d6b06ff7ef4c8687c9d27274d9fa3be50ccd5cbff`. After SHA256: `b7a72e31cf4b49694a9f1bd72373ec90c7e55c2e2f894baa634354f5ab9e2e88`. This proves the observed completed-response layout, not streaming, native iOS, unbreakable strings, fenced code blocks or production deployment.

## Compare the whole avatar screen

**Mobile web, not native iOS:** [merged frontend PR #295](https://github.com/jleechanorg/worldai_frontend/pull/295) removes an extra confirmation for a free initial portrait that replaces no player choice. The wizard viewport makes the consequence visible beside the launch action.

| Before: preview waits for Use | After: portrait attached, with Remove near launch |
| --- | --- |
| ![Avatar wizard before: generated preview with a green Use this portrait button](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr295-current-612-20261026/baseline-preview.png) | ![Avatar wizard after: Portrait attached and Remove avatar directly beneath Enter the World](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr295-current-612-20261026/portrait-attached-undo.png) |

This is a workflow change, not a wholesale visual redesign: the surrounding dark wizard stays familiar. The baseline Use button was already visible. The after still shows the attached state and visible Remove affordance described by the PR's automatic-attachment flow, not a completed removal, persistence after launch, or recovery from every failure.

The captures use the same 393 × 852 CSS viewport, but the original before PNG is 786 × 1704 and the after PNG is 393 × 852. Their generated faces and description text differ; do not attribute those content differences or image density to the UI fix. Both show the completed portrait-generation stage of the Custom wizard, rather than identical generated content.

Baseline source is `36ec31987e851327bf5df9659d6ef86210a97b26`; after capture is `612b6e58ac88bf8f1813031038c66ec7bbdf8b4f`. The PR records source applicability to merged head `19b2063c287f4ed8e8c54fa62f9ac1fe4178500b`: the intervening changes do not alter portrait runtime. This is historical capture applicability, not a fresh merged-head run. The [runtime receipt](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr295-current-612-20261026/runtime-receipt.json) and [manifest](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr295-current-612-20261026/manifest.json) document real Firebase SDK sign-in and a real local development backend. The broader video includes a labelled injected suggestion-transport failure; these two stills show the successful preview/attached states. Native behavior and larger text remain outside this proof.

Both original images were visually inspected and matched the [published checksums](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr295-current-612-20261026/checksums.sha256). Before SHA256: `ec78d09b3fe619c03ae14ff07ca955fef98ebc0bb49d4e06008541e9579db78f`. After SHA256: `914fae4efe51887df51942ca0fad33cfcaf51eff03de5c245e097794a27fbce8`.

## Make text-generation waiting visible

**Mobile web, not native iOS:** [merged frontend PR #189](https://github.com/jleechanorg/worldai_frontend/pull/189) shows the portrait editor while it is generating a suggested character description, before portrait-image generation.

| Before: loading status below the controls | After: progress beside the description field |
| --- | --- |
| ![Portrait editor before: Writing description indicator and Loading suggested description status below Generate portrait](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/packaged/01-baseline-pending.png) | ![Portrait editor after: Writing description indicator plus Preparing suggested description above the editable text field](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/packaged/02-candidate-pending.png) |

Both screenshots retain the central loading indicator and **Writing description…** label. The change is not the introduction of that indicator: the candidate puts **Preparing suggested description…** next to the text field and allows typing while the request is pending. A still shows the waiting state, not spinner motion or editability by itself; the [original 19.6-second comparison](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/packaged/07-pr189-mobile-web-comparison.mp4) and [candidate run record](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/candidate/result.json) carry the interaction evidence.

Baseline source: `5fdbd38cb09a6a80bff0d2ed8f73e7a61899a4ea`; candidate and merged PR head: `71b8a44b505b3ad38b870756969dfdb6ebb11afd`. Both used a 393 × 852 mobile-web viewport, real backend and genuine Firebase SDK sign-in. These are natural pending requests, not mocked or intercepted responses. The baseline ends while pending; the candidate record separately shows a typed edit surviving the real response. No portrait-image generation request occurred. This example proves neither native behavior nor image generation, save, persistence or model quality.

The original captioned PNGs are 393 × 968, including their evidence bands; some long caption text is clipped. Both were downloaded and visually inspected against [published checksums](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/SHA256SUMS). Before SHA256: `1f46e33c1ad9b9f35672d2e4d2157effbce6f8d07ad9471fa6708efa9cb87e1b`. After SHA256: `d958b6ef7e6f8540a04d59ca45f6342d176df008da3a2861f5c9a1e4001f739f`. [Bundle provenance](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr189-mobile-web-71b8a44b/bundle-manifest.json) preserves the original capture records. No new capture was made for this guide.

## Show a substantial panel reorganization

**Mobile web, not native iOS:** [merged frontend PR #281](https://github.com/jleechanorg/worldai_frontend/pull/281) turns the Equipment panel's dense bullet summary into structured rows with slot labels, prominent item names, subdued attributes and dividers.

| Before: dense equipment bullets | After: structured equipment rows |
| --- | --- |
| ![Equipment before: armor, weapons and tools in a dense bullet summary](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr281/ebc636a1-20261028T1610Z/canonical-v3/normal/before-equipment-still.png) | ![Equipment after: item rows with Main Hand, Off Hand, Armor and other slot labels](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr281/ebc636a1-20261028T1610Z/canonical-v3/normal/after-equipment-still.png) |

The same campaign and equipment-response hash anchor the comparison. This is a real layout change, not different fixture content dressed up as a before/after. The taller structured presentation requires scrolling; the after still does not show the entire inventory. The original annotated stills retain large source/redaction overlays above the panel rather than presenting a cleaned-up mockup.

Captured baseline: `740d2a1b3a0839b4ecc7dc18a0aa7f1955fd26a7`; after: `ebc636a15d45a4ff695f09340c01b47ccedf2d06`, the final PR head. The baseline is the recorded comparison source, not a claim that it equals the merge base. The [evidence index](https://storage.googleapis.com/wa-test-evidence/agent-evidence/worldai_frontend/pr281/ebc636a1-20261028T1610Z/canonical-v3/manifest.json) records Chromium mobile web at 393 × 852, genuine SDK sign-in, authenticated panel reads, unchanged backend and matching response hashes. The published annotated PNGs are 786 × 1930. They do not establish native scrolling, Dynamic Type, lifecycle, physical-device behavior or deployment.

Both originals were downloaded and visually inspected against their published hashes. Before SHA256: `03b35e5b1b9ed2e8b83e7a55593bb4005bf0210630952203b65de286bfe9b0eb`. After SHA256: `e03bdbcbfbf37fbaac2973eff550d1d57df067a51878fdb05953efe4fda3dc2a`. No new capture or image alteration was made for either added example.

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
