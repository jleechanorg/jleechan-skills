---
name: evidence-standards
description: General cross-project evidence standards (user scope). Use for the /es skill. Repo-level .claude/skills/evidence-standards.md files add project-specific extensions — always consult both.
when-to-use: Before /er, /green, gate fixes, or AO worker dispatch on a PR that touches production code paths. Also when claiming a behavior is "fixed" or "working" and you need to prove it.
---

# /es — Evidence Standards (user scope)

## Claim-proportionate evidence and publication

For proportional evidence classes, follow [pr-lifecycle](../pr-lifecycle/SKILL.md#proportional-exceptions-and-fast-paths). For PR-description publication, follow its [stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit). This skill owns the evidence-content and integrity checks below, not a second lifecycle policy.

Compact proof retains primary artifacts, source provenance and hashes; mark irrelevant server/PID/provider fields N/A with reasons instead of inventing runtime metadata. Source hashes alone do not prove execution.

## Summary

Evidence must **prove what you claim**. The strongest evidence is a raw
request/response capture from the real production code path; a unit test in
isolation proves only its bounded deterministic claim, not a live boundary. Match proof to the claim, label
every claim with its evidence layer, and never substitute a green test suite
for proof of integration correctness. The companion files in this directory
(`bundle-anatomy.md`, `tmux-video-evidence.md`, `ui-video-evidence.md`) cover
the structural and recording details; this file is the policy.

**After running any evidence-gathering pass, you MUST always reconfirm** by
explicitly stating what the evidence proves vs what it does NOT prove — this
applies to the response you give the user, not just the bundle's own
"What This Evidence Does NOT Prove" section (below).

## Aiming gate — run BEFORE spending on an evidence campaign

Before the first expensive call (real-LLM batch, browser run, replay sweep),
write one sentence:

> "This campaign will explain **<the reported symptom>**, and if it comes back
> <expected result>, the explanation is <X>."

If you cannot name a reported symptom — a user complaint, a production rate, a
failing turn — **you are not gathering evidence, you are decorating a claim.**
Stop and re-aim.

Hard rules:

- **A "Known gaps" / "unproven" list is a disclosure artifact, not a work
  queue.** It records what is unproven, which is not the same as what matters.
  Working it top-to-bottom is documentation gravity, not prioritization.
- **The originating symptom outranks every listed gap.** If a gap and the
  symptom disagree about where to spend, spend on the symptom.
- **If you find yourself writing "this proves nothing about <the actual bug>"
  into your own bundle, that is a stop signal, not a disclosure.** You have
  just written down that you aimed at the wrong target. Re-aim before
  continuing; do not ship the caveat as a substitute for hitting the target.
- For a model-behavior bug, prefer replaying **real captured production input
  through the real path** (`../ablation/SKILL.md`) over
  synthesizing new prompts. Synthetic prompts test the schema; captured
  payloads test the bug.
- Forensics on already-captured data (logs, BigQuery, Firestore) is usually
  cheaper AND closer to the symptom than any new generation campaign. Cost it
  first.

Recurrence log: violated 2026-08-16 (research fanout instead of ablation),
2026-08-18 (ranked a 4-6% lever while a 58% one sat unranked), and 2026-09-07
(360 real Gemini calls proving schema conformance while the reported ~75% memory
miss went unmeasured; a zero-LLM-call forensics pass on the same day found the
two real root causes).

## Derived-artifact rule: a number in prose must exist in an artifact

If a README, PR body, or commit message states a computed figure (p-value,
denominator, interval, rate), that figure must be readable from a committed
artifact — not only from the prose asserting it.

- **"summary.json now carries X" requires that file's checksum to have
  changed.** If you edited only the prose, you did not regenerate anything.
  Re-run the producer, then diff the artifact, then make the claim.
- **Commit the computation, not just the result.** A p-value produced by a
  shell one-liner is unreproducible the moment the shell scrolls away. Put the
  function in the script the bundle names.
- **Then actually run it and confirm it reproduces the published number.** A
  committed function that returns a different value than the README is worse
  than no function: it looks reproducible and is wrong.
- Recompute every headline figure from the raw rows, not from your own summary,
  before publishing. Summaries inherit their bugs silently.

Observed 2026-09-07: a bundle claimed `fisher_exact_greater()` "reproduces both
values" while the committed filter used a different cohort (n=70 vs n=50) and
returned different p-values, and claimed `summary.json` "now carries the data"
while that file's hash was unchanged. Both were caught by review, not by
self-check.

## Aiming gate — run BEFORE spending on an evidence campaign

Before the first expensive call (real-LLM batch, browser run, replay sweep),
write one sentence:

> "This campaign will explain **<the reported symptom>**, and if it comes back
> <expected result>, the explanation is <X>."

If you cannot name a reported symptom — a user complaint, a production rate, a
failing turn — **you are not gathering evidence, you are decorating a claim.**
Stop and re-aim.

Hard rules:

- **A "Known gaps" / "unproven" list is a disclosure artifact, not a work
  queue.** It records what is unproven, which is not the same as what matters.
  Working it top-to-bottom is documentation gravity, not prioritization.
- **The originating symptom outranks every listed gap.** If a gap and the
  symptom disagree about where to spend, spend on the symptom.
- **If you find yourself writing "this proves nothing about <the actual bug>"
  into your own bundle, that is a stop signal, not a disclosure.** You have
  just written down that you aimed at the wrong target. Re-aim before
  continuing; do not ship the caveat as a substitute for hitting the target.
- For a model-behavior bug, prefer replaying **real captured production input
  through the real path** (`../ablation/SKILL.md`) over
  synthesizing new prompts. Synthetic prompts test the schema; captured
  payloads test the bug.
- Forensics on already-captured data (logs, BigQuery, Firestore) is usually
  cheaper AND closer to the symptom than any new generation campaign. Cost it
  first.

## Derived-artifact rule: a number in prose must exist in an artifact

If a README, PR body, or commit message states a computed figure (p-value,
denominator, interval, rate), that figure must be readable from a committed
artifact — not only from the prose asserting it.

- **"summary.json now carries X" requires that file's checksum to have
  changed.** If you edited only the prose, you did not regenerate anything.
  Re-run the producer, then diff the artifact, then make the claim.
- **Commit the computation, not just the result.** A p-value produced by a
  shell one-liner is unreproducible the moment the shell scrolls away. Put the
  function in the script the bundle names.
- **Then actually run it and confirm it reproduces the published number.** A
  committed function that returns a different value than the README is worse
  than no function: it looks reproducible and is wrong.
- Recompute every headline figure from the raw rows, not from your own summary,
  before publishing. Summaries inherit their bugs silently.

## Core principle: raw req/resp > unit tests > nothing

For claims about integrated or live production behavior:

1. **Raw request/response capture from the real code path** (HTTP, JSONL, logs, video) — Layer 2.
2. **Real-service capture with mocks only at the network boundary** (`httpx.MockTransport`, `responses`, `respx` with a recorded body) — Layer 2 mock-at-network.
3. **Unit test in isolation** (monkeypatched, no real callstack) — Layer 1, **insufficient for integrated/live claims**, but sufficient for a bounded deterministic claim under the rule below.
4. **No evidence** — invalid for any non-trivial claim.

Real beats fast. A 30-second test against the real local server beats a 200-test
mock suite for proving "the server behaves like X."

### Strict UI Evidence Invariant: Mocks Forbidden — Real Server UI Required

Synthetic mock JSON, DOM fixture injection, or invoking frontend rendering functions
with hand-crafted JSON objects in the browser console is **strictly forbidden for UI evidence**.
Only UI driven by a **real running server** (local development server or live deployed preview instance)
rendering real backend responses counts as valid Layer 2 UI evidence. Unit and mocked-fixture
captures are supporting evidence only and do NOT prove UI integration correctness.

## Evidence Envelope Declaration (breadth claims: "all / per / each / every / across N")

Before producing evidence for a claim that covers a **set** (all 14 agents, every mode, each class), FIRST declare the **envelope** and get acceptance:

1. **Requested set** — enumerate from source of truth, not memory.
2. **Reachable set** — the subset the *real production path* can physically emit, plus the **exact structural gate** that bounds it (state the code condition).
3. **Cost to expand** — what it takes to reach more of the set.
4. **Accept** the envelope before doing the work.

Reachability is **computed, never a hardcoded list** (a frozen "X is unreachable" verdict is itself a ZFC violation). State it as the observed union of real routing + the named structural exclusion. **Never manufacture breadth via a non-production path** (direct-SDK, mock, reconstructed input) — fake-complete is INSUFFICIENT; honest-partial + envelope wins. Without this step, breadth asks collapse into honest-partial (which reads as *the model refusing*) or fabricated-complete (correctly rejected).

**No silent partial — lead with the gap.** When delivering breadth evidence, the FIRST line MUST be **"DELIVERED X of N; DID NOT DELIVER N−X (reason)"** before any "✓". Leading with the win and burying the shortfall is a silent partial failure — worse than refusing, because it hides that the ask wasn't met. In that same line, separate **gate-excluded** (true impossibility — name the gate) from **not-yet-driven** (reachable, just no scenario built — fixable). Never report "undriven" as "impossible."

**Generate the report from a per-item ledger, not free narration.** One row per requested element: `item | status (DELIVERED / GATE-EXCLUDED / NOT-YET-DRIVEN / UNDETERMINED) | reason | artifact`. Counts are computed from the ledger so no item is silently dropped and no cause is applied to a group without a per-row reason. **Before writing GATE-EXCLUDED, confirm the gate is intrinsic to the item, not to a turn/run type** — e.g. a gate on "turns emitting tool_requests" excludes turns, not agents, so a tool-capable agent is NOT-YET-DRIVEN/UNDETERMINED, never statically impossible. A static "impossible list" that is really a per-run property is a ZFC violation.

## Evidence Staleness Tolerance — the delta and the claim decide, not the path

**A moving HEAD does NOT invalidate evidence by itself.** Evidence captured at a prior SHA
stays valid at HEAD as long as the delta between the evidence SHA and HEAD leaves every
claim the evidence backs intact. A docs typo, comment, type-hint, or lint-only commit usually
does not require a fresh evidence run; a changed test assertion, evidence driver/capture,
prompt, contract, or executable instruction that a claim depends on does. Flagging evidence "stale" because the head SHA moved
— without checking *what* moved — is an over-correction; check the diff, not the SHA equality.

**The check is a diff, not a SHA comparison:**

1. Determine the evidence SHA (from `metadata.json.provenance.git_head` or the bundle README).
2. `git diff <evidence-sha> HEAD` — read every changed file's content diff against the claims it could affect.
3. If **every** content diff leaves the reviewed claims, assertions, and drivers intact,
   evidence remains valid; record the reviewed delta, relevant checks, and current applicability.
   Path category is a starting hint only: a test, evidence driver/capture, prompt, contract, schema, or
   `.claude/`/`.codex/`/`.cursor/` skill or agent file whose assertion, driver, or executable instruction
   changed can invalidate the proof it supports — read its diff against the claim it backs.
4. Never classify from file names alone; a comment edit and a behavior edit look identical in a name list.

**Fresh evidence IS required when the delta changes production behavior or anything a claim
depends on** between the SHAs: a test assertion, evidence driver/capture, or executable instruction
backing the claim; production code (the repo's source tree excluding its test dirs, **including** prompt/template surfaces — the repo-level /es file names the exact paths),
API/endpoints/game logic/agent routing, runtime config (env vars, feature flags), DB schema/migrations,
or a deploy/preview workflow. For a mixed diff, rerun proof affected by its actual
behavior or claim-dependent changes; a path alone does not invalidate every capture.

**Rationale:** rerunning real-server + real-LLM evidence for a docs typo or test rename burns
hours of LLM time for zero added confidence. The evidence proves a *behavior*; if the behavior's
code is byte-identical at HEAD and no assertion or driver backing it changed, the proof is
byte-valid at HEAD. Repo-level files may add
project-specific context (e.g. `<repo>/.claude/skills/evidence-standards.md` §
"Claim-scoped evidence revalidation"). Follow explicit repository requirements for their domain;
shared [pr-lifecycle defaults](../pr-lifecycle/SKILL.md#precedence-and-scope) fill only details the
repository leaves silent. A local workflow may alter which shared gates apply, but an applicable evidence
claim cannot waive the delta-and-claim test above.

## Evidence Sequencing — expensive evidence runs LAST, once

Before a behavior fix, obtain fresh evidence of the reported failure at the
lowest sufficient layer and preserve the baseline revision, inputs, and output.
Source/trace inspection and authorized diagnostic instrumentation may be needed
to construct that reproducer. A missing reproducer blocks an unproven fix claim,
not continued diagnosis. Real-service failures still require the real boundary;
a fast unit test cannot substitute for a cross-service reproduction.

Cheap gates (unit/focused tests, lint, compile) iterate freely per commit.
Review scheduling follows `pr-lifecycle/SKILL.md`'s canonical lifecycle and
composition contract; continue to enforce the required correctness and
evidence checks. Final expensive evidence (real-server + real-LLM runs, packaged RED/GREEN comparisons,
browser/video capture, bundle assembly) runs ONCE, at the END: only after code is
complete — all review findings resolved or explicitly deferred, focused tests
green, no known remaining code work. Freeze the HEAD, then run the expensive
stack against it. Running expensive evidence mid-iteration guarantees it is
voided by the next fix (PR #9604/#9640, 2026-09-01: ~40 of 50 commits were
evidence churn; the RED/GREEN pair and bundle had to be scheduled for a full
rerun anyway). The final comparison may replay the preserved baseline alongside
the completed candidate only if that baseline is labeled `derived` with its
source (artifact, build SHA, run); scheduling that package last does not defer the initial
failure reproduction until after the behavior fix.

Rerun expensive evidence ONLY on a material change per the Staleness Tolerance
delta-and-claim test above: the delta changes production behavior, or any test
assertion, evidence driver/capture, or executable instruction a claim depends on. When review
findings arrive after evidence, classify materiality FIRST; batch ALL pending
fixes into ONE new SHA before any rerun — never a rerun per finding.

Review findings are triaged by materiality. Findings that block correct
behavior must be fixed and reverified; style, nit, doc, or wording feedback
may be tracked without weakening the required correctness gates. Batch pending
behavioral fixes into one new SHA before rerunning affected evidence.

Evidence harness/infra code is not the feature: building or hardening capture
harnesses inside the feature PR moves the HEAD and voids gates. Land harness
changes in their own PR first, then freeze the feature head.

Before an expensive FINAL run, record a reusable launch capsule: FINAL or
DIAGNOSTIC, exact worktree and SHA, absolute interpreter, command and output
paths, nonsecret effective provider/model settings, and dedicated test-account
scope. Run cheap import, browser, and provider-selection preflight through that
same invocation before provider calls; confirm behavior work is settled for
FINAL. Reviewers must reuse the exact capsule. Setup failures remain setup
failures until raw provider proof supports a product or auth diagnosis.

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

Use `pr-lifecycle` § Change-impact review and test depth, `/4layer`, and
`testing-layers` to choose sufficient evidence, not selected by line count alone.
`/es` remains the evidence-classification gate; it does not force every production
edit through live LLM or browser capture.

A bounded deterministic claim may use fresh focused unit RED/GREEN and affected
regressions when the changed logic is self-contained and no service, model,
security, persistence, or browser boundary is implicated. A small single-function
fix can qualify; small size alone does not qualify. State exactly what the unit
proof covers and does not cover, retaining commands, results, and tested SHA.

Unit proof is insufficient for model compliance, auth, persistence races, or
browser behavior. Integration claims require the implicated real callstack and
boundary; model behavior needs real-provider proof where lower layers cannot
establish the claim. Never replace required real-service captures with mocks or
replays. Non-production work still requires proportionate checks; a test assertion,
shared driver, CI rule, or agent policy change can invalidate existing evidence.

No amount of unit coverage proves an unexercised integration or live boundary.
All existing real-service-only directory contracts remain in force.

### SDK-mock named anti-pattern

Mocks at the **in-process function boundary are not mocks at an external API
boundary.** When the production code path includes a third-party SDK
(`google.genai`, `openai`, `anthropic`, ...), mocking a wrapper inside the
codebase substitutes the entire SDK with fabricated objects. The downstream
call-graph runs end-to-end, but the data flowing through it is synthetic.

**Detection signal:** the verify script imports the production module AND
overrides any function in that module's call-graph that talks to the SDK. If
the SDK constructor itself is reachable, the LLM is real. If the SDK is
short-circuited, the LLM is synthetic regardless of what else is real.

**Per-claim layer label is mandatory.** Every /er verdict claim must end with
`[Layer N source]`:

- `[Layer 1 unit]` — monkeypatched, no real callstack
- `[Layer 1 synthetic-LLM]` — real callstack but in-process SDK mock
- `[Layer 2 mock-at-network]` — real callstack, HTTP boundary mocked with recorded body
- `[Layer 2 real-LLM]` — real callstack, real provider POST, real response streamed
- `[Layer 2 real-BQ]` — real callstack, real BigQuery HTTP insert

A claim that mixes Layer 2 (real BQ) with Layer 1 (synthetic LLM) is **not**
Layer 2 proof for the LLM-behavior part. The /er verdict for that claim must
be **PARTIAL** or **INSUFFICIENT**, not **PASS**. A claim that lacks the
layer label is non-compliant and the verdict must be downgraded to PARTIAL.


## Evidence access and publication

Keep the original evidence and its provenance intact. Provide the intended
reviewer with accessible reproduction directions and artifact links in the PR,
a checked-in document, an access-controlled receipt/store, or an authorized gist.
Include the reviewed/tested SHA, dependencies, exact commands and expected results
required for the applicable evidence class. These underlying evidence artifacts
may remain in authorized private hosting. The separate sanitized review receipt
must follow `pr-lifecycle` § Review records in the PR description, including
its gist URL, exact reviewed SHA, and `PUBLICATION BLOCKED` state when publication
cannot complete. Do not confuse artifact hosting with review-record completion.

Publish or send artifacts only within the current task's authorized audience and
destination. Sanitize any shareable copy while retaining private originals and
identifying the relationship between them. An unlisted gist is accessible to
anyone with its URL; do not treat it as an access-controlled secret store.
Follow any actual repository gate requiring particular in-tree evidence paths.

## Bundle anatomy (minimal)

The canonical bundle shape is the iteration directory produced by the
project's evidence harness. For the WorldArchitect MCP harness, see
`bundle-anatomy.md` in this directory. At minimum, a bundle contains:

- `metadata.json` — git provenance (`git_head`, `merge_base`, `commits_ahead_of_main`, `diff_stat_vs_main`), server runtime (PID, port, cmdline, env vars), `bundle_version`, `run_id`, `iteration`, `bundle_timestamp`
- `run.json` — `scenarios[]` array (each with `name`, `errors`, `campaign_id` if any)
- `evidence.md` — human summary + **Claim → Artifact Map** (required)
- `methodology.md` — env, commands, pass criteria, threshold values used
- `README.md` — package manifest (test name, run id, branch, commit)
- `*.sha256` sibling files for every substantive file (use **local basename** so `sha256sum -c` works)
- `artifacts/` — server.log, lsof/ps output, optional browser recordings
- Trace JSONL captures when the harness emits them: `request_responses.jsonl` (MCP), `llm_request_responses.jsonl` (LLM), `http_request_responses.jsonl` (HTTP+SSE)

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

Proves: real callstack, real dice RNG, real LLM (or recorded response) reached
the wire, in the right order. Strongest evidence for "the server behaves
like X."

### Example 2 — Real LLM call with layer label

```text
# Claim: "real Gemini response is logged verbatim with DC set before roll"
- Claim Y: real Gemini response is logged verbatim → [Layer 2 real-LLM, Layer 2 real-BQ]
- evidence: artifacts/llm_request_responses.jsonl contains a `type:response`
  entry with `model: gemini-3.8-flash`, a real `https://generativelanguage.googleapis.com/...`
  POST in the wire log, and a `dc_reasoning` field set before the `random.randint()` call.
```

The layer labels make it impossible to silently downgrade a real-LLM claim to
a synthetic-LLM claim.

### Example 3 — Video / cast evidence (UI behavior)

```text
# PR description includes:
- Evidence bundle: /tmp/your-project.com/fix-attack-roll/iteration_001/
- Video: https://storage.googleapis.com/<bucket>/agent-evidence/<repo>/<pr>-<topic>/attack-roll.mp4
  (or another host the current task authorizes; NOT github.com/.../releases/download/untagged-* — that is a red flag)
- Paired inline GIF of the same run, embedded in the PR body (see § Visual Evidence)
- metadata.json contains browser_origin, gateway_url, server.pid, artifact_manifest
- Video is pipeline output (asciinema .cast in bundle, converted to mp4
  for hosting), not a manual screen recording
```

For UI claims, a captioned `.mp4`/`.gif`/`.cast` is required, produced by the
test pipeline. See `ui-video-evidence.md` and `tmux-video-evidence.md` in this
directory for the recording rules. Docs-only / test-only PRs use
`N/A - no UI behavior changed`.

**The video must visually show the element under test changing, in the pixels —
not a caption.** A captioned clip that frames only the page chrome while the
element under test is below the fold does NOT prove the change: the caption is
text the test wrote from its own DOM reads (harness-authored), so it asserts the
state rather than demonstrating it. The recording must `scrollIntoView` the
specific control/field and settle so its before→after change is visible in the
frames. When reviewing UI video (`/er`), **extract frames and look**
(`ffmpeg -i <video> -vf fps=1 /tmp/frames/f_%02d.png`); if the element is never
in-frame, or the only on-screen evidence is a caption overlay, the UI evidence is
INSUFFICIENT even if the video exists, is captioned, and the test passed.

## Visual Evidence & Mandatory Inline Rendering in PRs

Visual comparisons under `## Visual Evidence` in PR descriptions must render images **directly inline** on GitHub so reviewers can visually inspect the differences without having to click away to external links:

1. **Inline Image Tags (`<img>` or `![]()`)**:
   - In Markdown, `[screenshot](https://...)` is a text hyperlink that renders only as plain blue clickable text. It fails the visual review requirement because the reviewer cannot see the image in the PR conversation.
   - Use HTML `<img src="..." width="..." alt="...">` (strongly preferred in markdown tables) or markdown image syntax `![alt](url)`.
   - HTML `<img>` tags inside markdown table cells allow precise width control so images do not distort or overflow table columns.

2. **Standard Viewport Widths for Tables**:
   - **Desktop screenshots** (in 2-column Before/After tables): `width="450"` (or `width="400"`)
   - **Mobile screenshots** (375×812 in 2-column Before/After tables): `width="360"` (or `width="300"`)
   - **Side-by-side comparison slides**: `width="800"`

3. **Standard PR Table Format**:
   ```markdown
   ## Visual Evidence

   ### Desktop (1440×900) Comparison

   | Before (`origin/main`) | After (PR head `<sha>`) |
   | :---: | :---: |
   | <img src="<before_desktop_url>" width="450" alt="Before Desktop"> | <img src="<after_desktop_url>" width="450" alt="After Desktop"> |

   ### Mobile (375×812) Comparison

   | Before (`origin/main`) | After (PR head `<sha>`) |
   | :---: | :---: |
   | <img src="<before_mobile_url>" width="360" alt="Before Mobile"> | <img src="<after_mobile_url>" width="360" alt="After Mobile"> |

   ### Walkthrough Video

   | Before | After |
   | :---: | :---: |
   | <img src="https://storage.googleapis.com/<bucket>/<path>/before.gif" width="300" alt="Before walkthrough"> | <img src="https://storage.googleapis.com/<bucket>/<path>/after.gif" width="300" alt="After walkthrough"> |
   | [▶ before.mp4](https://storage.googleapis.com/<bucket>/<path>/before.mp4) (SHA256: `<sha256>`) | [▶ after.mp4](https://storage.googleapis.com/<bucket>/<path>/after.mp4) (SHA256: `<sha256>`) |
   ```

4. **Google Cloud Storage media (default host)**:
   - **Default host.** Upload media to the authorized evidence bucket (for example `gs://<evidence-bucket>/agent-evidence/<repo>/<pr>-<topic>-<date>/`) and link it as `https://storage.googleapis.com/<evidence-bucket>/<object>`. That URL syntax grants no access by itself: a direct browser playback works only for objects already authorized for the intended reviewers (public-read, for example). Media that must stay private uses the private-host exception below rather than being made public.
   - A GitHub attachment is also acceptable — for video it is the only form GitHub plays inline — as is any other host the current task authorizes. Media that must stay private stays in authorized private hosting; never make evidence public merely to satisfy a link check. What is never acceptable is a URL the intended reviewer cannot open and play.
   - Never link `gs://…` (not clickable) or `https://storage.cloud.google.com/…`, which redirects reviewers to a Google login.
   - GitHub plays inline only videos uploaded as GitHub attachments, so an external mp4 renders as a link. Every video therefore gets an **inline GIF** of the same run (`ffmpeg -i in.webm -vf "fps=6,scale=300:-1:flags=lanczos" out.gif`) next to a **playable mp4 link** (prefer MP4/H.264 — `-c:v libx264 -pix_fmt yuv420p` — for the broadest player compatibility; WebM may be supplied additionally, but does not replace the required MP4/H.264 variant).
   - Screenshots are inline `<img>` from an authorized host that renders for the intended reviewer, showing the real captured pixels of the claimed state, not placeholders, crops that hide the changed element, or icons.
   - Verify before claiming the stage exit:
     - Every URL resolves with the expected `content-type` (`video/mp4`, `image/gif`, `image/png`) **for the intended reviewer**: `curl -sI <url>` for a public object, or the reviewer's own authorized access when the task keeps the media private. Record which access mode applies instead of forcing public access to prove reachability.
     - Every inline GIF and screenshot appears in the **rendered** PR body *and is the right image*. GitHub exposes each rendered image's original URL, so compare them with the media this receipt declares: `gh api repos/<owner>/<repo>/pulls/<n> -H "Accept: application/vnd.github.html+json" --jq .body_html | grep -o 'data-canonical-src="[^"]*"'`. Do not accept a bare image count: `grep -c` counts matching *lines* (one line holding two images reports `1`), and an aggregate number can be matched by unrelated images.
     - The sanitized gist receipt lists the same media with their sha256 hashes and access mode. Redact bearer, signed-query and other credential-bearing URL components — record the protected location plus hash instead of the token, since a gist is link-accessible.

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

This is the **user-scope (global)** `/es` policy. For complete evidence
standards, always read both this skill and the relevant repo-level file:

1. **Master policy** — `~/.claude/CLAUDE.md` § "Evidence — match proof to the claim"
   and this skill's Unit proof and claim boundaries. Use the current claim-based
   rule rather than obsolete blanket production/size-only exceptions. Preserve
   UI-video and risk-specific requirements; the repo overlay names its triggers.
2. **Repo-level /es** — most repos mirror this skill at
   `<repo>/.claude/skills/evidence-standards.md` with project-specific
   extensions (e.g. `your-project.com` has dice-claim, campaign-isolation,
   BigQuery, and Gemini specifics). **Always read both**. Explicit repository
   requirements govern their domain; shared
   [lifecycle defaults](../pr-lifecycle/SKILL.md#precedence-and-scope) apply
   only where repository instructions are silent.
3. **Companion files in this directory** — `bundle-anatomy.md` (bundle
   structure, JSONL shapes, integrity rules), `tmux-video-evidence.md`
   (tmux/asciinema recording), `ui-video-evidence.md` (browser/UI video).

Adjacent skills: `evidence-review` (`/er` — the per-claim audit), `tdd-evidence-workflow`
(TDD-specific evidence patterns), `streaming-evidence-standards`
(streaming-response signed-payload evidence), `ui-bug-proof` (RED-before-GREEN
UI bug reproduction).
