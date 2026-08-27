---
name: user-story
description: Produce zero-code, zero-tech product specs and VISUAL user stories for any project/product — what the user sees, hears, and does, at a bar where a stranger could rebuild the experience without reading code. Slash command /user-story.
---

# /user-story — zero-code specs & visual user stories

Produce (or audit) a product's **experience contract**: user stories + visual mocks so complete that someone could rewrite the product without ever reading its code. Works for any project — games, apps, sites, tools.

## Check for a repo-local companion FIRST

Before starting, look for a product-specific skill in the target repo — `.claude/skills/user-story-*/SKILL.md` (e.g. `user-story-worldai` in your-project.com). If one exists, READ IT: it holds the docset paths, which evidence source settles which claim in that product, the traps that have already produced false claims there, and the list of claims already refuted — none of which belongs in this file. This file is the general law; the repo file is the local practice. **Neither is sufficient alone.**

When a session learns something durable, route it deliberately: general practice belongs here, product specifics belong in the repo skill. Putting a repo's paths, campaign IDs, or one product's traps in this file is how it rots.

## The bar: the Rewritability Test

The finished docset passes when an adversarial reader can answer, for every flow: *what does the user see, what can they do, what happens next, what does failure look like* — from the docs alone. Verdicts: **REWRITABLE-AS-IS / REWRITABLE-WITH-GAPS (listed precisely) / NOT-REWRITABLE.** (Real case: your-project.com 2026-07-25 audit — 100 well-formed stories still scored NOT-REWRITABLE because 7/9 core flows had zero visual documentation and ~35 stories used function names as acceptance criteria.)

## Story law

- Form: `As a <user>, I want <goal>, So that <benefit>` + 3–6 checkbox acceptance criteria. INVEST applies (Independent, Negotiable, Valuable, Estimable, Small, Testable). Split stories with >6 criteria.
- **Observable criteria only**: every criterion names something the user can SEE, HEAR, or DO on screen. "Result, not recipe." A future teammate must be able to verify each criterion by looking at the running product, without interpretation.
- Use **Given/When/Then** for stateful flows (preconditions matter: combat turns, interrupts, resumption); plain checklists for simple presence/behavior.
- **Negative and failure states are mandatory content**, not appendix: what the user sees when things are slow, invalid, unavailable, or failing. Every wait has a visible state; every error has a face.
- User-visible time bounds are allowed ("appears within a few seconds", "never a blank screen"); internal latency/architecture numbers are not.
- Each story carries: `priority` (v1-critical | v1-nice | later) and `source` (traceability to a parent spec/story or NEW).

## Zero-code / zero-tech law (banned content)

API names, schemas, function/class/file names, agent/service/model names, database/infra terms, framework references, "the system validates/processes/routes...". If a criterion needs a code identifier to mean anything, it is not a criterion — rewrite it as the behavior the user observes. (The author MAY read code to *discover* behavior; the output must stand without it.)

## Evidence tiering (use the cheapest class that can actually settle the claim)

1. **Prose describing flow and expected behavior, containing no code** — the base layer, and the only layer for things with no rendered surface (background instrumentation, data model, responsibility splits, integration contracts). These pages need no screenshots and a coverage audit must not report them as missing captures; label them as the non-visual half.
2. **Stills, as many as possible** — the default for anything about what a screen looks like.
3. **Captioned clips, only where nothing else can work** — a timing guarantee, an incremental reveal, an animation. **Not everything needs a video.** A before/after frame PAIR and transcript excerpts from two distant points are legitimate, cheaper alternatives for most behavioral claims; reserve recording for claims a pair genuinely cannot settle. Audit the ratio: count behavioral claims, then count which are backed by a pair, a transcript, a clip, or nothing. Only the last group needs new capture.

**Verify a clip before promoting it: extract frames and compare them.** Confirm frame 1 is not blank, and confirm the frames differ *in the way the caption claims*. A recording whose frames are all one state proves nothing, and a caption is an assertion, not a demonstration. (Real case: a clip promoted as the strongest evidence in a docset had a length counter on screen that never changed once — nothing had ever streamed.)

## Propagate every correction to every assertion site

The most common way a spec rots is a fix landing where the reviewer pointed and nowhere else. Before calling any correction done, grep the whole docset for the claim and fix **every** occurrence — **state tables above all**, because rebuilders implement from tables while reviewers read prose. A document that now contradicts itself with equal confidence in both directions is worse than the one that was merely wrong.

Give the docset a written **precedence rule** for when two parts disagree: the capture wins; a dated hedged caveat beats a bare confident assertion; and if no capture covers the disputed state, nothing settles it — mark it undetermined rather than picking the more confident sentence.

(Real case: four separate instances in a single pass — three committed by someone who had just read this diagnosis and was actively trying to avoid it. Knowing the failure mode does not prevent it; re-grepping does.)

## Visual mandate (the half most specs skip)

Stories alone never pass the bar. The docset includes a **visual companion**:
- A **screen-flow map**: every screen/scene/overlay the user can reach, as a flowchart or list with transitions.
- **A real capture per distinct screen and per key moment.** If the screen EXISTS in the running product, a real screenshot is mandatory and a hand-drawn mock is NOT a substitute — an authored mock cannot contradict its author, so it launders assumption into evidence. ASCII/HTML mocks are for screens that do NOT yet exist (proposed/planned) and must be labelled as proposals, never as documentation of current behavior. Bug-repro fixtures never count. Cover the moment-to-moment loop first (the thing the user does 95% of the time), then onboarding, progression, settings, and every failure state.
- **Coverage invariant**: every screen listed in the screen-flow map has either a real capture the reviewer opened, or an explicit "not photographed — a rebuilder must decide this" note. Silence is not allowed: an undocumented screen and an unphotographed one look identical to a reader, and only the second is honest. A journey with any screen in neither state fails the bar.
- Mocks are referenced FROM stories ("see M4") so criteria and pictures verify each other.
- **Open before you cite**: before writing or keeping any sentence that describes a screenshot's content — including a "not captured" / "unconfirmed" / "invalid capture" disclaimer — open the image in this pass and write down what is literally visible. A caption may only claim what was seen. A cropped or cut-off capture must say so and is evidence only for the region actually visible, never for the rest of the screen. A false disclaimer (claiming a real capture is missing or wrong) is as severe as a fabrication and destroys evidence that already exists — treat it the same way.
- **Match the evidence class to the claim.** A still frame settles what a screen LOOKS like and nothing else. A claim about behavior over time — streaming, animation, scroll, a transition, a state change, or anything that holds "across scenes/sessions" — needs a frame PAIR, a recording, or a transcript excerpt from two distant points. Audit this: sort the acceptance criteria into static vs behavioral and count them. A docset whose stories are two-thirds behavioral and whose evidence is entirely screenshots has proven a third of itself and asserted the rest. (Real case: 4 documented claims — a "gold never updates" gap, a checkpoint cadence, an injury behavior, and a "never observed" disclaimer — survived FOUR rounds of adversarial document review and were all false. Long transcripts refuted them in one pass. Document review cannot catch a well-formed claim that is simply untrue about the product.)
- **"Unproven" is not the safe default — it is a different error.** Disclaiming a real capability is as wrong as asserting a fake one, and it is the harder mistake to notice because it feels like caution. Before writing "no evidence confirms this", confirm the test could have detected it: right environment, right layer, right configuration. (Real case: a lane honestly reported "text does not stream" after measuring a one-step jump — against a dev server that cannot stream. Production config showed 45 chunks over 7 seconds. The spec was one commit from disclaiming a shipped feature.)
- **Match the capture's STATE to the claim's STATE, and date it.** A capture only settles a claim about the exact condition it was taken in. An empty field cannot settle how a filled one renders; a value typed this session cannot settle what happens after a reload; a recording made on a dev server cannot settle production. And evidence is a DATED observation, not a timeless fact — a defect visible in a months-old artifact may be long fixed, so documenting it as current behavior is itself a false claim. Record when every artifact was captured, and re-check anything old before writing it as present-tense. (Real case: one claim was asserted, retracted, reinstated, then corrected again across four passes, each flip from generalising off a single screenshot of the wrong state. Separately, four findings rested on a transcript last touched thirteen months earlier.)
- **A capture proves the pixels, not the cause.** Describing a screen correctly and attributing it correctly are two different claims, and the second needs its own evidence. Before documenting a screen as feature X, establish that X is why it rendered — otherwise a failure state gets written up as a shipped feature and a rebuilder builds the wrong thing from an entirely accurate screenshot. Failure states are mandatory content, but they must be labelled as failure states.
- **Record the capture environment**: each capture session logs the account tier, feature flags, and access mode active when it ran (e.g. allowlisted vs. waitlisted account, private-beta gate on/off). A screen gated behind an operator-controlled mode is itself a story and a captured state, not an assumed default — two captures of "the same" screen taken under different modes are not comparable without this.
- **Captures that share an environment are ONE sample, not many.** "It appears in every screenshot we hold" proves nothing about the default experience if every screenshot was taken under the same flag, account, or debug mode — the observations aren't independent, so repetition adds no evidence. Before writing "always", check whether anything could have produced it in *all* your captures at once; if so, the honest disposition is *undetermined*, plus the one test that would settle it. Undetermined-and-said-so is a terminal state under the coverage invariant; a confident "always" inferred from a confounded set is a fabrication with a screenshot attached. (Real case: a multi-agent review graded an element BLOCKER as "always-present, every player sees it" from three frames that all had a debug badge lit in the header.)
- **A control's state and the content around it may be from different moments.** In any continuously-growing feed — a chat log, a story log, an activity stream — a toggle or radio reports what is selected *now*, while the content above it records what *earlier* actions produced. Photographing the two together does not make them one event, and reading them as one produces confident, wrong captions in both directions. To document what a mode/filter/setting *does*, capture its output and its own control in a single frame. (Real case: five reviewers, an adversarial verifier, and a judge all concluded two mocks were swapped and recommended swapping the citations; the frames were scrollback, and the recommended fix would have created two new false captions.)
- Captures come from the real running product, headless (real browser/simulator automation, never a GUI takeover of the user's screen).

## Process

1. **Ground**: inventory what exists (docs, mocks, screenshots, the running product; code read-only for behavior discovery). For an audit-only run, stop after producing the gap list + verdict.
2. **Journey-map**: enumerate the user's journeys (first run → core loop → progression → edge/failure). The core loop gets the most stories and mocks.
3. **Draft per section**: group stories by experience area (not by architecture). Games: define the experience goal per section first (how should the player FEEL).
4. **Adversarial review — four lenses, refute-by-default**: (a) *purity* — kill tech leakage; (b) *observability* — kill any criterion not verifiable on screen; (c) *coverage+dedup* — merge near-duplicates, add missing behaviors incl. failure states; (d) *evidence* — reopen every cited screenshot and every disclaimer against the artifact; re-verify claimed-absent UI with a positive control (grep something known-present, then confirm the zero-hit) before trusting "doesn't exist"; when a citation is fixed, re-read the surrounding prose for stale claims it no longer supports. Fix inline during assembly.
5. **Assemble**: one USER_STORIES doc (vision paragraph → how-to-read note → TOC → sections → coverage appendix mapping every parent-spec area to stories or "out of scope: infra"). Every doc on disk must appear in the index — diff the file list against the index's entries; zero unlisted, zero phantom.
6. **Mock pass**: produce/collect the visual companion (UI_MOCKS doc + screenshots dir); every story's screens exist in it.
7. **Rewritability verdict**: an **independent reviewer who did not author the docset** runs the bar adversarially. Have them attempt a **paper rebuild** of one or two flows and report the exact point they stall — a stall is a precise, actionable gap in a way a general criticism never is, and a stall at a point the docset itself discloses is the disclosure working. Reviewers reading for different lenses (core loop, first use, evidence integrity, failure states, cold read with no context) find more than several reading for the same thing; diversity beats redundancy. Hand every finding to a verifier told to REFUTE it, and treat a pass that refutes nothing as a signal to re-check by hand, not as a green light. Mechanical checks (link/index/regex sweeps) are necessary but not sufficient — a reviewer who runs only the queries and never opens an image will report a cleaner docset than the one that exists. Before writing any verdict line, the reviewer must open at least one screenshot per journey/flow and no fewer than 8 total, and write down what is literally visible in each — only then compare that note to the citing doc's claim. Record the verdict + gaps + the count of images opened in the doc header.
8. **User review gate**: the user reads and approves before the docset is treated as the product contract.

## Scale & tooling

Small products: run steps 2–7 inline. Large products (≥50 stories): fan out section drafting and the four review lenses as parallel subagents/workflow stages with explicit models (proven pattern: worldai-2d-user-stories workflow, 2026-07-25 — 6 mappers + 1 new-journeys author + 3 adversarial reviewers + 1 assembler).

## Anti-patterns (each cost a real audit finding)

- Acceptance criteria that are code pointers ("`_is_x_enabled` reads from game state") — the spec IS the identifier; rewrite as behavior.
- Bug-repro HTML fixtures counted as UI mocks.
- A hand-drawn mock standing in for a screen that exists and could have been photographed — it documents the author's assumption, not the product.
- Infra/API/devops stories mixed into a product experience spec — split them out.
- Visual documentation only for auth/settings while the core loop (the actual product) has none.
- "The feature works correctly" / "loads quickly" — untestable vagueness.
- A "not captured" / "unconfirmed" / "invalid" disclaimer that doesn't match the image when reopened — as severe as a fabrication, and invisible to link-checking since the file is still cited somewhere.
- A citation gets fixed but the paragraph around it doesn't — re-check surrounding prose whenever a caption or capture changes, not just the sentence that was flagged.
- Asserting a UI element exists (or a claim is absent) without a positive-control check against source or a live capture first.
- A doc that exists on disk but is missing from the index — a reader who starts at the index never finds it.
- An accurate screenshot filed under the wrong cause — e.g. an error screen documented as a shipped feature because nobody asked why it rendered. The pixels survive review; the meaning is wrong.
- A rewritability verdict rendered from link-checks and regex sweeps alone, zero images opened — mechanical cleanliness is not evidence cleanliness, and it is exactly what a self-grading author's own review will look like.

## Deliverables

Small/medium products: `USER_STORIES.md` (+ `UI_MOCKS.md` or a screenshots dir) in the target repo's docs. Large products (≥50 stories, per Scale & tooling): an `INDEX.md` fanning out to per-journey and per-story docs plus a `screenshots/` dir — the shape `your-project.com:docs/user-stories-ui/` actually uses (it contains no USER_STORIES.md or UI_MOCKS.md; verified 2026-07-28). Either way, the rewritability verdict lives in the entry doc's header. Plus a **`METHODOLOGY.md`** (required going forward; known pre-mandate exceptions: worldai_claw `docs/plans/dragonknight-2d/` and `docs/plans/worldai-2d/`, both verified to lack it): where the material came from, which evidence class settles which claim, how it was reviewed, and — critically — **what went wrong and the rule each failure produced**. A reader deciding how much to trust a page needs the method, and a methodology listing only successes is not one. Keep the audit trail in a `reviews/` directory, including verdicts later invalidated and notes on review findings that were themselves wrong; it is a record, not a story to tidy. Commit per the repo's landing profile.
