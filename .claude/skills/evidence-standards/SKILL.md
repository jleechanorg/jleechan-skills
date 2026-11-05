---
name: evidence-standards
description: General cross-project evidence standards (user scope). Use for the /es skill. Repo-level .claude/skills/evidence-standards/SKILL.md files add project-specific extensions — always consult both.
when-to-use: Before /er, /green, gate fixes, or AO worker dispatch on a PR that touches production code paths. Also when claiming a behavior is "fixed" or "working" and you need to prove it.
---

# /es — Evidence Standards (user scope)

## Claim-proportionate evidence and publication

For proportional evidence classes, follow [pr-lifecycle](../pr-lifecycle/SKILL.md#proportional-exceptions-and-fast-paths). For PR-description publication, follow its [stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit). This skill owns evidence content and integrity, not a second lifecycle policy.

Compact proof keeps primary artifacts, source provenance and hashes; mark irrelevant server/PID/provider fields N/A with reasons instead of inventing runtime metadata. Source hashes alone do not prove execution.

## Summary

Evidence must **prove what you claim**. The strongest evidence is a raw request/response capture from the real production code path; a unit test in isolation proves only its bounded deterministic claim, not a live boundary. Match proof to the claim, label every claim with its evidence layer, and never substitute a green test suite for proof of integration correctness. This file is the policy; the companion files (see § Cross-references) cover structure and recording.

- **Diff-Derived Claim Coverage (Including Platform-Divergent Paths)**: Evidence must cover every user-visible behavior the diff adds or changes, not only the PR's stated claims; build the claim list from the diff itself (see `evidence-coverage`). On the pr-lifecycle one-liner fast path (literal-text-only change), that behavior is the literal text, and the PR-body before/after quote (plus its pinning assertion where a test already covers the text) is the evidence. Code that runs on only one platform (`Platform.OS` branches, `*.web.*`/`*.native.*` files, `window`/`document`/`history` listeners, native-only modules) must be listed path by path, with its user-visible behavior proved on the platform where it executes.

**After any evidence-gathering pass, you MUST reconfirm** what the evidence proves and what it does NOT prove, in your response to the user as well as in the bundle's "What This Evidence Does NOT Prove" section. That section lists untested scope only: observed behavior that the user's acceptance or the UI's own disclosure forbids is a FAIL, never a limit or follow-up (`evidence-review` check 9).

## Continuous video only — slideshows are forbidden

When a claim asks for video, the artifact MUST come from a genuine continuous browser, screen, or terminal capture (including a continuous `.cast` or native event timeline) that preserves the real timeline across the applicable before→after transition and, when a user action exists, from before that action through the resulting state. Never create, deliver, attach, or approve slideshow output, even when labeled sampled, selected-frame, summary footage, or “not video”: screenshot-concat files, sampled or selected-frame montages, repeated-still padding, and still-image sequences encoded as MP4 are forbidden even when they have captions, real pixels, a normal frame rate, valid H.264 metadata, or a successful decode. A contact sheet, screenshot, or diagnostic frame extraction is allowed only as a static diagnostic and never substitutes for video evidence.

Check the producer and publisher, not only the output container: trace the artifact to the continuous recorder, its raw timeline, and the applicable before-to-after transition, including the action and resulting state when a user action exists. Decode and checksum probes establish file integrity only; they do not establish continuity. A real capture may contain unchanged waiting intervals, but a derived caption, transcode, redaction, or authorized trim is valid only when it preserves the timeline of an actual continuous source. If only a slideshow exists, the video claim FAILS and the evidence is undelivered; do not relabel it as a limitation, N/A, or PASS because transport, tests, or metadata succeeded.

## Aiming gate — run BEFORE spending on an evidence campaign

Before the first expensive call (real-LLM batch, browser run, replay sweep), write one sentence:

> "This campaign will explain **<the reported symptom>**, and if it comes back
> <expected result>, the explanation is <X>."

If you cannot name a reported symptom (a user complaint, a production rate, a failing turn), **you are not gathering evidence, you are decorating a claim.** Stop and re-aim.

Hard rules:

- **A "Known gaps" / "unproven" list is a disclosure artifact, not a work queue.** It records what is unproven, not what matters; working it top to bottom is not prioritization.
- **The originating symptom outranks every listed gap.** When they disagree about where to spend, spend on the symptom.
- **Writing "this proves nothing about <the actual bug>" into your own bundle is a stop signal, not a disclosure.** Re-aim before continuing; the caveat is no substitute for hitting the target.
- For a model-behavior bug, prefer replaying **real captured production input through the real path** (`~/.claude/skills/ablation/SKILL.md`) over synthesizing new prompts. Synthetic prompts test the schema; captured payloads test the bug.
- Forensics on already-captured data (logs, BigQuery, Firestore) is usually cheaper AND closer to the symptom than any new generation campaign. Cost it first.

Recurrence log: violated 2026-08-16 (research fanout instead of ablation), 2026-08-18 (ranked a 4-6% lever while a 58% one sat unranked), and 2026-09-07 (360 real Gemini calls proving schema conformance while the reported ~75% memory miss went unmeasured; a zero-LLM-call forensics pass the same day found the two real root causes).

## Derived-artifact rule: a number in prose must exist in an artifact

A computed figure (p-value, denominator, interval, rate) stated in a README, PR body or commit message must be readable from a committed artifact, not only from the prose asserting it.

- **"summary.json now carries X" requires that file's checksum to have changed.** Editing only the prose regenerates nothing: re-run the producer, diff the artifact, then make the claim.
- **Commit the computation, not just the result.** Put the function in the script the bundle names; a shell one-liner is unreproducible once it scrolls away.
- **Then run it and confirm it reproduces the published number.** A committed function that disagrees with the README looks reproducible and is wrong, which is worse than none.
- Recompute every headline figure from the raw rows, not from your own summary, before publishing.

Observed 2026-09-07: a bundle claimed `fisher_exact_greater()` "reproduces both values" while the committed filter used a different cohort (n=70 vs n=50) and returned different p-values, and claimed `summary.json` "now carries the data" while that file's hash was unchanged. Review caught both, not self-check.

## Core principle: raw req/resp > unit tests > nothing

For claims about integrated or live production behavior:

1. **Raw request/response capture from the real code path** (HTTP, JSONL, logs, video) — Layer 2.
2. **Real-service capture with mocks only at the network boundary** (`httpx.MockTransport`, `responses`, `respx` with a recorded body) — Layer 2 mock-at-network.
3. **Unit test in isolation** (monkeypatched, no real callstack) — Layer 1, **insufficient for integrated/live claims**, but sufficient for a bounded deterministic claim under § Unit proof and claim boundaries.
4. **No evidence** — invalid for any non-trivial claim.

Real beats fast: a 30-second test against the real local server beats a 200-test mock suite for proving "the server behaves like X."

### Strict UI Evidence Invariant: Mocks Forbidden — Real Server UI Required

Synthetic mock JSON, DOM fixture injection, or calling frontend rendering functions with hand-crafted JSON in the browser console is **strictly forbidden for UI evidence**. Only UI driven by a **real running server** (local development server or live deployed preview) rendering real backend responses is valid Layer 2 UI evidence. Unit and mocked-fixture captures are supporting evidence only and do NOT prove UI integration correctness.

### UI changes require a genuine implementation BEFORE/AFTER comparison

Every UI change, except a diff on the pr-lifecycle one-liner fast path (literal-text-only), requires paired screenshots or video of the **pre-change implementation (BEFORE)** and **candidate implementation (AFTER)**. Prefer captioned video; video is required for interaction, navigation, streaming, animation, timing or multi-step claims. Paired screenshots suffice only for a simple static visual change whose claim does not depend on motion or sequence; state why that exception fits. Keep required desktop/mobile coverage.

- Use comparable route, scenario, account/role, starting data/state, viewport and theme on both revisions; disclose unavoidable differences. For a new feature, BEFORE shows its actual prior absence or previous experience.
- Bind each capture to the actual served app/build SHA and capture-driver revision (plus any dirty diff/hash), exact launch/capture commands, original UTC capture time, environment, and raw artifact paths/hashes. A checkout SHA alone does not establish which code the browser received.
- A candidate-only journey's pre-click and post-click states are **not** a pre-change baseline. Never fabricate BEFORE with DOM edits, fixtures, relabelled AFTER media or an unverified PR-body claim.
- Preserve original raw media, timestamps and provenance. Map captioned, trimmed or redacted derivatives to their raw source hashes and transformation commands; never overwrite or retimestamp originals. Open both images, or play both videos and extract relevant frames, to verify the claimed difference.
- Reuse verified captures only after the delta-and-claim applicability check (§ Evidence Staleness Tolerance); do not rerun them merely because HEAD moved. If no applicable baseline can safely be captured or recovered, record `BEFORE: WITHHELD — <reason>` and withhold the comparison claim. Never reproduce unsafe behavior just to obtain media. This waives no separate bug-reproduction, real-server, review or publication requirement.

## Evidence Envelope Declaration (breadth claims: "all / per / each / every / across N")

Before producing evidence for a claim over a **set** (all 14 agents, every mode, each class), FIRST declare the **envelope** and get acceptance:

1. **Requested set** — enumerated from the source of truth, not memory.
2. **Reachable set** — the subset the *real production path* can physically emit, plus the **exact structural gate** (code condition) that bounds it.
3. **Cost to expand** — what it takes to reach more of the set.
4. **Accept** the envelope before doing the work.

Reachability is **computed, never a hardcoded list** (a frozen "X is unreachable" verdict is itself a ZFC violation): state it as the observed union of real routing plus the named structural exclusion. **Never manufacture breadth via a non-production path** (direct SDK, mock, reconstructed input); fake-complete is FAIL, and honest-partial plus envelope wins.

**No silent partial — lead with the gap.** The FIRST line of breadth evidence MUST be **"DELIVERED X of N; DID NOT DELIVER N−X (reason)"**, before any "✓"; burying the shortfall is a silent partial failure, worse than refusing. In that line, separate **gate-excluded** (true impossibility; name the gate) from **not-yet-driven** (reachable, no scenario built yet). Never report "undriven" as "impossible."

**Generate the report from a per-item ledger, not free narration.** One row per requested element: `item | status (DELIVERED / GATE-EXCLUDED / NOT-YET-DRIVEN / UNDETERMINED) | reason | artifact`. Compute counts from the ledger so no item is dropped and no cause is applied to a group without a per-row reason. **Before writing GATE-EXCLUDED, confirm the gate is intrinsic to the item, not to a turn/run type**: a gate on "turns emitting tool_requests" excludes turns, not agents, so a tool-capable agent is NOT-YET-DRIVEN/UNDETERMINED, never statically impossible. A static "impossible list" that is really a per-run property is a ZFC violation.

## Evidence Staleness Tolerance — the delta and the claim decide, not the path

**A moving HEAD does NOT invalidate evidence by itself.** Evidence captured at a prior SHA stays valid at HEAD while the delta between them leaves every claim it backs intact. A docs typo, comment, type-hint or lint-only commit usually needs no fresh run; a changed test assertion, evidence driver/capture, prompt, contract or executable instruction that a claim depends on does. Flagging evidence "stale" only because the SHA moved is an over-correction.

**The check is a diff, not a SHA comparison:**

1. Determine the evidence SHA (from `metadata.json.provenance.git_head` or the bundle README).
2. `git diff <evidence-sha> HEAD` — read every changed file's content diff against the claims it could affect.
3. If **every** content diff leaves the reviewed claims, assertions and drivers intact, the evidence remains valid; record the reviewed delta, relevant checks and current applicability. Path category is only a starting hint: a test, evidence driver/capture, prompt, contract, schema, or `.claude/`/`.codex/`/`.cursor/` skill or agent file whose assertion, driver or executable instruction changed can invalidate the proof it supports.
4. Never classify from file names alone; a comment edit and a behavior edit look identical in a name list.

**Fresh evidence IS required when the delta changes production behavior or anything a claim depends on:** a test assertion, evidence driver/capture or executable instruction backing the claim; production code (the repo's source tree excluding its test dirs, **including** prompt/template surfaces; the repo-level /es file names the exact paths); API/endpoints/game logic/agent routing; runtime config (env vars, feature flags); DB schema/migrations; or a deploy/preview workflow. For a mixed diff, rerun only the proof its behavior or claim-dependent changes affect.

**Rationale:** rerunning real-server + real-LLM evidence for a docs typo or test rename burns hours for zero added confidence. If the behavior's code is byte-identical at HEAD and no assertion or driver backing it changed, the proof is valid at HEAD. Repo-level files may add project-specific context (e.g. the worldarchitect.ai overlay: `evidence-standards.md` under `<repo>/.claude/skills/` § "Claim-scoped evidence revalidation"). Shared [pr-lifecycle precedence](../pr-lifecycle/SKILL.md#precedence-and-scope) governs conflicting lifecycle copies; domain-specific proof and separate safety/merge restrictions remain. Repo overlays cannot waive the delta-and-claim test above.

## Evidence Sequencing — expensive evidence runs LAST, once

Before a behavior fix, obtain fresh evidence of the reported failure at the lowest sufficient layer and preserve the baseline revision, inputs and output. Source/trace inspection and authorized diagnostic instrumentation may be needed to build that reproducer. A missing reproducer blocks an unproven fix claim, not continued diagnosis. Real-service failures still need the real boundary; a fast unit test cannot substitute for a cross-service reproduction.

Cheap gates (unit/focused tests, lint, compile) iterate freely per commit. Review scheduling follows `pr-lifecycle/SKILL.md`'s canonical lifecycle; keep enforcing the required correctness and evidence checks. Final expensive evidence (real-server + real-LLM runs, packaged RED/GREEN comparisons, browser/video capture, bundle assembly) runs ONCE, at the END, after code is complete: all review findings resolved or explicitly deferred, focused tests green, no known remaining code work. Freeze the HEAD, then run the expensive stack against it. Mid-iteration runs are voided by the next fix (PR #9604/#9640, 2026-09-01: ~40 of 50 commits were evidence churn, and the RED/GREEN pair and bundle still needed a full rerun). The final comparison may replay the preserved baseline beside the completed candidate; scheduling that package last does not defer the initial failure reproduction past the fix.

Rerun expensive evidence ONLY on a material change under § Evidence Staleness Tolerance. Triage review findings by materiality FIRST: findings that block correct behavior must be fixed and reverified, while style, nit, doc or wording feedback may be tracked without weakening required correctness gates. Batch ALL pending behavioral fixes into ONE new SHA before any rerun; never rerun per finding.

Evidence harness/infra code is not the feature: building or hardening capture harnesses inside the feature PR moves the HEAD and voids gates. Land harness changes in their own PR first, then freeze the feature head.

Before an expensive FINAL run, record a reusable launch capsule: FINAL or DIAGNOSTIC, exact worktree and SHA, absolute interpreter, command and output paths, nonsecret effective provider/model settings, and dedicated test-account scope. Run cheap import, browser and provider-selection preflight through that same invocation before provider calls, and confirm behavior work is settled for FINAL. Reviewers reuse the exact capsule. Setup failures remain setup failures until raw provider proof supports a product or auth diagnosis.

Before expensive capture, verify the actual producer identity and provider, downstream logging target, and readiness in the child that will run it. Confirm canonical control IDs and the observed terminal envelope; an absent optional success field does not mean `false`. Reuse the existing pipeline; do not add mocks or retry loops. If a harness fails after controlled state was persisted, resume it through the real SDK only when readback proves its preconditions, and record the resume source and limits. Complete published PR-body media (including the GIF derivative manifest) and direct raw RED/GREEN delivery before starting the final `/er`. This sequencing does not delay cheap code or advice review, which may run earlier or concurrently.

## Evidence class table

| Class | Description | Layer | Acceptable for production claim? |
|---|---|---|---|
| **real-callstack + real-LLM** | Real `https://generativelanguage.googleapis.com/...` POST, real response streamed | Layer 2 | **Yes** (required for LLM-behavior claims) |
| **real-callstack + mock-at-network** | Real callstack, HTTP boundary mocked with recorded body | Layer 2 | Yes, for non-LLM claims |
| **real-callstack + real-BQ/HTTP** | Real BigQuery / Firestore / HTTP insert | Layer 2 | Yes |
| **real-callstack + in-process SDK mock** | `gemini_provider.get_client = lambda: _FakeClient()` — SDK short-circuited | Layer 1 synthetic-LLM | **No** (named anti-pattern, see below) |
| **unit test** | Isolated deterministic execution | Layer 1 | Bounded deterministic claims only; never live-boundary proof |
| **none** | No artifact, just assertion | — | No |

## Unit proof and claim boundaries

Choose sufficient evidence with `pr-lifecycle` § Change-impact review and test depth, `/4layer` and `testing-layers`, never by line count alone. `/es` stays the evidence-classification gate; it does not force every production edit through live LLM or browser capture.

A bounded deterministic claim may use fresh focused unit RED/GREEN and affected regressions when the changed logic is self-contained and no service, model, security, persistence or browser boundary is implicated. A small single-function fix can qualify; small size alone does not. State exactly what the unit proof covers and does not cover, keeping commands, results and tested SHA.

Unit proof is insufficient for model compliance, auth, persistence races or browser behavior, and no amount of unit coverage proves an unexercised integration or live boundary. Integration claims need the implicated real callstack and boundary; model behavior needs real-provider proof where lower layers cannot establish the claim. Never replace required real-service captures with mocks or replays; all existing real-service-only directory contracts remain in force. Non-production work still needs proportionate checks, and a test assertion, shared driver, CI rule or agent policy change can invalidate existing evidence.

### SDK-mock named anti-pattern

Mocks at the **in-process function boundary are not mocks at an external API boundary.** When the production path includes a third-party SDK (`google.genai`, `openai`, `anthropic`, ...), mocking a wrapper inside the codebase replaces the whole SDK with fabricated objects: the downstream call-graph runs end to end, but the data flowing through it is synthetic.

**Detection signal:** the verify script imports the production module AND overrides any function in that module's call-graph that talks to the SDK. If the SDK constructor itself is reachable, the LLM is real; if the SDK is short-circuited, the LLM is synthetic regardless of what else is real.

**Per-claim layer label is mandatory.** Every /er verdict claim ends with `[Layer N source]`:

- `[Layer 1 unit]` — monkeypatched, no real callstack
- `[Layer 1 synthetic-LLM]` — real callstack but in-process SDK mock
- `[Layer 2 mock-at-network]` — real callstack, HTTP boundary mocked with recorded body
- `[Layer 2 real-LLM]` — real callstack, real provider POST, real response streamed
- `[Layer 2 real-BQ]` — real callstack, real BigQuery HTTP insert

A claim mixing Layer 2 (real BQ) with Layer 1 (synthetic LLM) is **not** Layer 2 proof for its LLM-behavior part: the /er verdict for that claim must be **PARTIAL** or **FAIL**, not **PASS**. A claim without a layer label is non-compliant and its verdict is downgraded to PARTIAL.

## Evidence access and publication

Keep the original evidence and its provenance intact. Give the intended reviewer accessible reproduction directions and artifact links in the PR, a checked-in document, an access-controlled receipt/store, or an authorized gist, including the reviewed/tested SHA, dependencies, exact commands and expected results the evidence class requires. Underlying artifacts may stay in authorized private hosting. The separate sanitized review receipt follows `pr-lifecycle` § Review records in the PR description, including its gist URL (or, for a one-liner fast-path `/es` record, the PR-body section), exact reviewed SHA, and `PUBLICATION BLOCKED` state when publication cannot complete. Artifact hosting is not review-record completion.

Publish or send artifacts only to the current task's authorized audience and destination. Sanitize any shareable copy, keep private originals, and identify the relationship between them. An unlisted gist is accessible to anyone with its URL; it is not an access-controlled secret store.

In authorized evidence, redact authentication tokens, including bearer, access, refresh, custom and session tokens and token-bearing URL components. Account emails and IDs may stay visible; their presence alone is not a privacy defect or an extra redaction or approval gate. Ordinary game/test content likewise needs no separate privacy certification merely because it is readable.

Follow any actual repository gate requiring particular in-tree evidence paths.

## Bundle anatomy (minimal)

The canonical bundle is the iteration directory the project's evidence harness produces on the dedicated Scratch volume, resolved dynamically via `~/.claude/skills/scratch-space/SKILL.md` (`diskm scratch-new <repo-path> <purpose> --kind evidence`, or `$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "<repo>/evidence/<date>-<slug>")`). For the WorldArchitect MCP harness, see `bundle-anatomy.md` in this directory. At minimum, a bundle contains:

- `metadata.json` — git provenance (`git_head`, `merge_base`, `commits_ahead_of_main`, `diff_stat_vs_main`), server runtime (PID, port, cmdline, env vars), `bundle_version`, `run_id`, `iteration`, `bundle_timestamp`
- `run.json` — `scenarios[]` array (each with `name`, `errors`, `campaign_id` if any)
- `evidence.md` — human summary + **Claim → Artifact Map** (required)
- `methodology.md` — env, commands, pass criteria, threshold values used
- `README.md` — package manifest (test name, run id, branch, commit)
- A complete aggregate manifest named `checksums.sha256` OR per-file `*.sha256` siblings covering every substantive file, including every claim-map artifact (aggregate paths are bundle-relative; sibling entries use **local basename** so `sha256sum -c` works)
- `artifacts/` — server.log, lsof/ps output, optional browser recordings
- Trace JSONL captures when the harness emits them: `request_responses.jsonl` (MCP), `llm_request_responses.jsonl` (LLM), `http_request_responses.jsonl` (HTTP+SSE)

Use the canonical producer's existing format with an explicit mapping from its
actual artifact paths/fields to the responsibilities above. Equivalent filenames
or structured command records do not require duplicate files or a reconstructed
stdout collection log. For example, a producer's `manifest.json` may carry the
package inventory and provenance, while a run receipt carries commands, exits
and raw-output paths; identify those exact fields rather than asserting generic
compliance. Keep all applicable raw data and owner-required fields/media; this
mapping is not an exemption for absent proof.

Reconcile an independent artifact inventory against checksum coverage. Verify
every digest; a mismatch, missing listed file, or uncovered substantive/claim-map
artifact is an integrity failure under `/er`, not a warning. Checksums do not
hash themselves; integrity coverage concerns the substantive artifacts they
index. No checksums means integrity is unverified and approval is withheld.
Other existing producer manifest names remain valid when explicitly identified
and mapped to the same complete aggregate contract; `checksums.sha256` is the
recognized default, not a demand to recreate a producer's inventory as stdout.
Preflight and freeze the complete bundle with existing producer/sealing utilities
before formal review. Reviewers inspect it read-only; corrections belong to the
producer and require an explicit updated identity and applicable delta review.

`evidence.md` MUST include a **Claim → Artifact Map** (claim → file →
key field) and a **"What This Evidence Does NOT Prove"** section.

## Examples (3 short ones)

### Example 1 — Raw HTTP request/response (the dominant case)

```text
# artifacts/scenario_03_capture.jsonl
{"type":"request","method":"POST","path":"/interaction/stream","body":{"campaign_id":"abc123","action":"attack","target_ac":13}}
{"type":"response","status":200,"stream_chunks":[
  {"event":"tool_call","name":"roll_dice","args":{"formula":"1d20+5"}},
  {"event":"tool_result","value":18,"die":"d20","modifier":5,"total":23},
  {"event":"narration","text":"Your blade finds the gap in the ogre's guard."}
]}
```

Proves: real callstack, real dice RNG, and a real LLM (or recorded response) reached the wire in the right order. Strongest evidence for "the server behaves like X."

### Example 2 — Real LLM call with layer label

```text
# Claim: "real Gemini response is logged verbatim with DC set before roll"
- Claim Y: real Gemini response is logged verbatim → [Layer 2 real-LLM, Layer 2 real-BQ]
- evidence: artifacts/llm_request_responses.jsonl contains a `type:response`
  entry with `model: gemini-3.8-flash`, a real `https://generativelanguage.googleapis.com/...`
  POST in the wire log, and a `dc_reasoning` field set before the `random.randint()` call.
```

The layer labels stop a real-LLM claim from being silently downgraded to a synthetic-LLM one.

### Example 3 — Video / cast evidence (UI behavior)

```text
# PR description includes:
- Evidence bundle: <scratch-root>/your-project.com/fix-attack-roll/iteration_001/ (resolved as in § Bundle anatomy)
- Video: https://storage.googleapis.com/<bucket>/agent-evidence/<repo>/<pr>-<topic>/attack-roll.mp4
  (or another host the current task authorizes; NOT github.com/.../releases/download/untagged-* — that is a red flag)
- Paired inline GIF of the same run, embedded in the PR body (see § Visual Evidence)
- metadata.json contains browser_origin, gateway_url, server.pid, artifact_manifest
- Video is pipeline output (asciinema .cast in bundle, converted to mp4
  for hosting), not a manual screen recording
```

UI claims need a captioned `.mp4`/`.gif`/`.cast` produced by the test pipeline; `ui-video-evidence.md` and `tmux-video-evidence.md` in this directory hold the recording rules. Docs-only / test-only PRs use `N/A - no UI behavior changed`.

**The video must show the element under test changing in the pixels, not in a caption.** A captioned clip that frames only page chrome while the element is below the fold does NOT prove the change: the caption is harness-authored text from the test's own DOM reads, so it asserts the state rather than demonstrating it. The recording must `scrollIntoView` the specific control/field and settle so its before→after change is visible in the frames. When reviewing UI video (`/er`), **extract frames and look** (`ffmpeg -i <video> -vf fps=1 /tmp/frames/f_%02d.png`); if the element is never in frame, or the only on-screen evidence is a caption overlay, the UI evidence is FAIL even if the video exists, is captioned and the test passed. Acceptance by video also requires an independent AI content review (not the author or orchestrator) of the published video's frames per acceptance step (`evidence-review` check 4); privacy, playback and turn-record reviews do not count.

## Visual Evidence & Mandatory Inline Rendering in PRs

Visual comparisons under `## Visual Evidence` in PR descriptions must render **directly inline** on GitHub, so reviewers can inspect differences without clicking away:

1. **Inline Image Tags (`<img>` or `![]()`)**:
   - Markdown `[screenshot](https://...)` renders only as a text link, so the reviewer cannot see the image in the PR conversation; it fails visual review.
   - Use HTML `<img src="..." width="..." alt="...">` (strongly preferred in tables, where it controls width so images do not distort or overflow columns) or markdown `![alt](url)`.

2. **Standard Viewport Widths for Tables**:
   - **Desktop screenshots** (in 2-column Before/After tables): `width="450"` (or `width="400"`)
   - **Mobile screenshots** (375×812 in 2-column Before/After tables): `width="360"` (or `width="300"`)
   - **Side-by-side comparison slides**: `width="800"`

3. **Standard PR Table Format**:
   ```markdown
   ## Visual Evidence

   ### Desktop (1440×900) Comparison

   | Before (baseline `<before_sha>`) | After (candidate `<after_sha>`) |
   | :---: | :---: |
   | <img src="<before_desktop_url>" width="450" alt="Before Desktop"> | <img src="<after_desktop_url>" width="450" alt="After Desktop"> |

   ### Mobile (375×812) Comparison

   | Before (baseline `<before_sha>`) | After (candidate `<after_sha>`) |
   | :---: | :---: |
   | <img src="<before_mobile_url>" width="360" alt="Before Mobile"> | <img src="<after_mobile_url>" width="360" alt="After Mobile"> |

   ### Walkthrough Video

   | Before | After |
   | :---: | :---: |
   | <img src="https://storage.googleapis.com/<bucket>/<path>/before.gif" width="300" alt="Before walkthrough"> | <img src="https://storage.googleapis.com/<bucket>/<path>/after.gif" width="300" alt="After walkthrough"> |
   | [▶ before.mp4](https://storage.googleapis.com/<bucket>/<path>/before.mp4) (SHA256: `<sha256>`) | [▶ after.mp4](https://storage.googleapis.com/<bucket>/<path>/after.mp4) (SHA256: `<sha256>`) |
   ```

4. **Google Cloud Storage media (default host)**:
   - **Default host.** Upload media to the authorized evidence bucket (for example `gs://<evidence-bucket>/agent-evidence/<repo>/<pr>-<topic>-<date>/`) and link it as `https://storage.googleapis.com/<evidence-bucket>/<object>`. That URL grants no access by itself: browser playback works only for objects already authorized for the intended reviewers (public-read, for example).
   - A GitHub attachment is also acceptable (for video, the only form GitHub plays inline), as is any other host the current task authorizes. Media that must stay private stays in authorized private hosting; never make evidence public merely to satisfy a link check. A URL the intended reviewer cannot open and play is never acceptable.
   - Never link `gs://…` (not clickable) or `https://storage.cloud.google.com/…`, which redirects reviewers to a Google login.
   - GitHub plays inline only videos uploaded as GitHub attachments, so an external mp4 renders as a link. Every video therefore gets an **inline GIF** of the same run (`ffmpeg -i in.webm -vf "fps=6,scale=300:-1:flags=lanczos" out.gif`) next to a **playable mp4 link**. Prefer MP4/H.264 (`-c:v libx264 -pix_fmt yuv420p`) for the broadest player compatibility; WebM may be added but never replaces the required MP4/H.264 variant.
   - Screenshots are inline `<img>` from an authorized host that renders for the intended reviewer, showing the real captured pixels of the claimed state, not placeholders, crops that hide the changed element, or icons.
   - Verify before claiming the stage exit:
     - Every URL resolves with the expected `content-type` (`video/mp4`, `image/gif`, `image/png`) **for the intended reviewer**: `curl -sI <url>` for a public object, or the reviewer's own authorized access when the media stays private. Record which access mode applies instead of forcing public access to prove reachability.
     - Every inline GIF and screenshot appears in the **rendered** PR body *and is the right image*. GitHub exposes each rendered image's original URL; compare those with the media this receipt declares: `gh api repos/<owner>/<repo>/pulls/<n> -H "Accept: application/vnd.github.html+json" --jq .body_html | grep -o 'data-canonical-src="[^"]*"'`. A bare image count is not acceptable: `grep -c` counts matching *lines* (one line holding two images reports `1`), and unrelated images can match an aggregate number.
     - The sanitized gist receipt lists the same media with their sha256 hashes and access mode. Redact bearer, signed-query and other credential-bearing URL components; record the protected location plus hash instead of the token, since a gist is link-accessible.

5. **Anti-Patterns (Reject in Review)**:
   - ❌ `| [screenshot](url) | [screenshot](url) |` (text link only — fails inline rendering)
   - ❌ Raw uncaptioned image dumps with no Before/After comparison table
   - ❌ Testing only desktop and skipping mobile (375×812)
   - ❌ Committing heavy image binaries directly into the git repository (use authorized storage or unlisted gists)
   - ❌ A video only as a text link, with no inline GIF of the same run
   - ❌ `gs://` or `storage.cloud.google.com` media links, or webm as the only playable form with no MP4/H.264 variant
   - ❌ Making private evidence public, or changing bucket access, only to satisfy a reachability check
   - ❌ Media only in a gist, a comment or a bundle README instead of inline in the PR description

## Cross-references

This is the **user-scope (global)** `/es` policy. For complete evidence standards, always read both this skill and the relevant repo-level file:

1. **Master policy** — `~/.claude/CLAUDE.md` § "Evidence — match proof to the claim" and § Unit proof and claim boundaries above. Use the current claim-based rule, not obsolete blanket production/size-only exceptions. Preserve UI-video and risk-specific requirements; the repo overlay names its triggers.
2. **Repo-level /es** — most repos mirror this skill at `<repo>/.claude/skills/evidence-standards/SKILL.md` (or, in repos that keep it flat, `evidence-standards.md` under `<repo>/.claude/skills/`) with project-specific extensions (e.g. `your-project.com` has dice-claim, campaign-isolation, BigQuery and Gemini specifics). **Always read both** and apply the [scoped precedence rule](../pr-lifecycle/SKILL.md#precedence-and-scope); repository domain proof does not override the shared lifecycle.
3. **Companion files in this directory** — `bundle-anatomy.md` (bundle structure, JSONL shapes, integrity rules), `tmux-video-evidence.md` (tmux/asciinema recording), `ui-video-evidence.md` (browser/UI video).

Adjacent skills: `evidence-review` (`/er` — the per-claim audit), `tdd-evidence-workflow` (TDD-specific evidence patterns), `streaming-evidence-standards` (streaming-response signed-payload evidence), `ui-bug-proof` (RED-before-GREEN UI bug reproduction).
