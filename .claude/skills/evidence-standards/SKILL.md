---
name: evidence-standards
description: General cross-project evidence standards (user scope). Use for the /es skill. Repo-level .claude/skills/evidence-standards/SKILL.md files add project-specific extensions — always consult both.
when-to-use: Before /er, /green, gate fixes, or AO worker dispatch on a PR that touches production code paths. Also when claiming a behavior is "fixed" or "working" and you need to prove it.
---

# /es — Evidence Standards (user scope)

## Claim-proportionate evidence and publication

For proportional evidence classes, follow [pr-lifecycle](../pr-lifecycle/SKILL.md#proportional-exceptions-and-fast-paths); for PR-description publication, follow its [stage-exit receipt contract](../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit). This skill owns the evidence-content and integrity checks below, not a second lifecycle policy.

Compact proof retains primary artifacts, source provenance and hashes; mark irrelevant server/PID/provider fields N/A with reasons instead of inventing runtime metadata. Source hashes alone do not prove execution.

## Summary

Evidence must **prove what you claim**: match proof to the claim, label every
claim with its evidence layer, and never substitute a green test suite for
proof of integration correctness. The companion files (`bundle-anatomy.md`,
`tmux-video-evidence.md`, `ui-video-evidence.md`) cover structure and
recording; this file is the policy.

- **Diff-Derived Claim Coverage (Including Platform-Divergent Paths)**: cover every user-visible behavior the diff adds or changes, not only the PR's stated claims; build the claim list from the diff itself (see `evidence-coverage`). On the pr-lifecycle one-liner fast path (literal-text-only change), the behavior is the literal text, and the PR-body before/after quote (plus its pinning assertion where a test already covers the text) is the evidence. For code that runs on only one platform (`Platform.OS` branches, `*.web.*`/`*.native.*` files, `window`/`document`/`history` listeners, native-only modules), list each such path and prove its user-visible behavior on the platform where it executes.

**After any evidence-gathering pass, you MUST reconfirm** what the evidence
proves vs what it does NOT prove — in your response to the user, not only in
the bundle's "What This Evidence Does NOT Prove" section. That section lists
untested scope only: observed behavior that the user's acceptance or the UI's
own disclosure forbids is a FAIL, never a limit or follow-up
(`evidence-review` check 9).

## Aiming gate — run BEFORE spending on an evidence campaign

Before the first expensive call (real-LLM batch, browser run, replay sweep),
write one sentence:

> "This campaign will explain **<the reported symptom>**, and if it comes back
> <expected result>, the explanation is <X>."

If you cannot name a reported symptom — a user complaint, a production rate, a
failing turn — **you are not gathering evidence, you are decorating a claim.**
Stop and re-aim.

- **A "Known gaps" / "unproven" list is a disclosure artifact, not a work
  queue.** It records what is unproven, not what matters; working it
  top-to-bottom is documentation gravity, not prioritization.
- **The originating symptom outranks every listed gap.** When they disagree
  about where to spend, spend on the symptom.
- **Writing "this proves nothing about <the actual bug>" into your own bundle
  is a stop signal, not a disclosure** — you aimed at the wrong target. Re-aim
  before continuing; do not ship the caveat as a substitute for hitting it.
- For a model-behavior bug, prefer replaying **real captured production input
  through the real path** (`~/.claude/skills/ablation/SKILL.md`) over
  synthesizing prompts: synthetic prompts test the schema; captured payloads
  test the bug.
- Forensics on already-captured data (logs, BigQuery, Firestore) is usually
  cheaper AND closer to the symptom than any new generation campaign. Cost it
  first.

Recurrence log: 2026-08-16 (research fanout instead of ablation), 2026-08-18
(ranked a 4-6% lever while a 58% one sat unranked), 2026-09-07 (360 real Gemini
calls proving schema conformance while the reported ~75% memory miss went
unmeasured; a zero-LLM-call forensics pass that day found both real root causes).

## Derived-artifact rule: a number in prose must exist in an artifact

A computed figure (p-value, denominator, interval, rate) stated in a README, PR
body, or commit message must be readable from a committed artifact, not only
from the prose asserting it.

- **"summary.json now carries X" requires that file's checksum to have
  changed.** Editing only the prose regenerates nothing: re-run the producer,
  diff the artifact, then make the claim.
- **Commit the computation, not just the result.** A shell one-liner's p-value
  is unreproducible once the shell scrolls away; put the function in the script
  the bundle names.
- **Then actually run it and confirm it reproduces the published number.** A
  committed function that returns a different value than the README is worse
  than none: it looks reproducible and is wrong.
- Before publishing, recompute every headline figure from the raw rows, not
  from your own summary; summaries inherit their bugs silently.

Observed 2026-09-07: a bundle claimed `fisher_exact_greater()` "reproduces both
values" while the committed filter used a different cohort (n=70 vs n=50) and
returned different p-values, and claimed `summary.json` "now carries the data"
while its hash was unchanged. Review caught both; self-check did not.

## Core principle: raw req/resp > unit tests > nothing

For claims about integrated or live production behavior:

1. **Raw request/response capture from the real code path** (HTTP, JSONL, logs, video) — Layer 2.
2. **Real-service capture with mocks only at the network boundary** (`httpx.MockTransport`, `responses`, `respx` with a recorded body) — Layer 2 mock-at-network.
3. **Unit test in isolation** (monkeypatched, no real callstack) — Layer 1: **insufficient for integrated/live claims**; sufficient for a bounded deterministic claim (§ Unit proof and claim boundaries).
4. **No evidence** — invalid for any non-trivial claim.

Real beats fast: a 30-second test against the real local server beats a
200-test mock suite for proving "the server behaves like X."

### Strict UI Evidence Invariant: Mocks Forbidden — Real Server UI Required

Synthetic mock JSON, DOM fixture injection, or calling frontend rendering
functions with hand-crafted JSON in the browser console is **strictly forbidden
as UI evidence**. Only UI driven by a **real running server** (local dev server
or live deployed preview) rendering real backend responses is valid Layer 2 UI
evidence. Unit and mocked-fixture captures are supporting evidence only and do
NOT prove UI integration correctness.

### UI changes require a genuine implementation BEFORE/AFTER comparison

Every UI change, except a pr-lifecycle one-liner fast-path diff
(literal-text-only), requires paired screenshots or video of the **pre-change
implementation (BEFORE)** and **candidate implementation (AFTER)**. Prefer
captioned video; video is required for interaction, navigation, streaming,
animation, timing, or multi-step claims. Paired screenshots suffice only for a
simple static visual change whose claim does not depend on motion or sequence;
state why that exception fits. Keep required desktop/mobile coverage.

- Use comparable route, scenario, account/role, starting data/state, viewport,
  and theme on both revisions; disclose unavoidable differences. For a new
  feature, BEFORE shows its actual prior absence or previous experience.
- Bind each capture to the actual served app/build SHA and capture-driver
  revision (plus any dirty diff/hash), exact launch/capture commands, original
  UTC capture time, environment, and raw artifact paths/hashes. A checkout SHA
  alone does not establish which code the browser received.
- A candidate-only journey's pre-click and post-click states are **not** a
  pre-change-code baseline. Do not fabricate BEFORE with DOM edits, fixtures,
  relabelled AFTER media, or an unverified claim in a PR body.
- Preserve original raw media, timestamps, and provenance; map captioned,
  trimmed, or redacted derivatives to their raw source hashes and
  transformation commands; never overwrite or retimestamp originals. Open both
  images, or play both videos / extract relevant frames, to verify the claimed
  difference.
- Reuse verified captures only after the delta-and-claim applicability check
  (§ Evidence Staleness Tolerance); do not rerun them merely because HEAD
  moved. If no applicable baseline can safely be captured or recovered, record
  `BEFORE: WITHHELD — <reason>` and withhold the comparison claim. Never
  reproduce unsafe behavior just to obtain media. This does not waive separate
  bug-reproduction, real-server, review, or publication requirements.

## Evidence Envelope Declaration (breadth claims: "all / per / each / every / across N")

Before producing evidence for a claim over a **set** (all 14 agents, every mode, each class), FIRST declare the **envelope** and get acceptance:

1. **Requested set** — enumerate from source of truth, not memory.
2. **Reachable set** — the subset the *real production path* can physically emit, plus the **exact structural gate** (code condition) that bounds it.
3. **Cost to expand** — what it takes to reach more of the set.
4. **Accept** the envelope before doing the work.

Reachability is **computed, never a hardcoded list** (a frozen "X is unreachable" verdict is itself a ZFC violation): state it as the observed union of real routing plus the named structural exclusion. **Never manufacture breadth via a non-production path** (direct-SDK, mock, reconstructed input) — fake-complete is INSUFFICIENT; honest-partial + envelope wins. Without the envelope, breadth asks collapse into honest-partial (which reads as *the model refusing*) or fabricated-complete (correctly rejected).

**No silent partial — lead with the gap.** The FIRST line of breadth evidence MUST be **"DELIVERED X of N; DID NOT DELIVER N−X (reason)"**, before any "✓"; leading with the win and burying the shortfall is a silent partial failure, worse than refusing. In that line, separate **gate-excluded** (true impossibility — name the gate) from **not-yet-driven** (reachable, no scenario built — fixable). Never report "undriven" as "impossible."

**Generate the report from a per-item ledger, not free narration.** One row per requested element: `item | status (DELIVERED / GATE-EXCLUDED / NOT-YET-DRIVEN / UNDETERMINED) | reason | artifact`. Compute counts from the ledger so no item is silently dropped and no cause is applied to a group without a per-row reason. **Before writing GATE-EXCLUDED, confirm the gate is intrinsic to the item, not to a turn/run type** — a gate on "turns emitting tool_requests" excludes turns, not agents, so a tool-capable agent is NOT-YET-DRIVEN/UNDETERMINED, never statically impossible. A static "impossible list" that is really a per-run property is a ZFC violation.

## Evidence Staleness Tolerance — the delta and the claim decide, not the path

**A moving HEAD does NOT invalidate evidence by itself.** Evidence captured at a
prior SHA stays valid at HEAD as long as the delta between the evidence SHA and
HEAD leaves every claim it backs intact. Flagging evidence "stale" because the
SHA moved, without checking *what* moved, is an over-correction. Rerunning
real-server + real-LLM evidence for a docs typo or test rename burns hours of
LLM time for zero added confidence: if the behavior's code is byte-identical at
HEAD and no assertion or driver backing it changed, the proof is byte-valid at HEAD.

**The check is a diff, not a SHA comparison:**

1. Determine the evidence SHA (from `metadata.json.provenance.git_head` or the bundle README).
2. `git diff <evidence-sha> HEAD` — read every changed file's content diff against the claims it could affect.
3. If **every** content diff leaves the reviewed claims, assertions, and drivers intact,
   evidence remains valid; record the reviewed delta, relevant checks, and current applicability.
4. Never classify from file names alone; a comment edit and a behavior edit look identical in a
   name list. Path category is a starting hint only: a test, evidence driver/capture, prompt,
   contract, schema, or `.claude/`/`.codex/`/`.cursor/` skill or agent file whose assertion,
   driver, or executable instruction changed can invalidate the proof it supports.

A docs typo, comment, type-hint, or lint-only commit usually needs no fresh run.
**Fresh evidence IS required when the delta changes production behavior or
anything a claim depends on:** a test assertion, evidence driver/capture,
prompt, contract, or executable instruction backing the claim; production code
(the repo's source tree excluding its test dirs, **including** prompt/template
surfaces — the repo-level /es file names the exact paths); API/endpoints/game
logic/agent routing; runtime config (env vars, feature flags); DB
schema/migrations; or a deploy/preview workflow. For a mixed diff, rerun the
proof affected by its actual behavior or claim-dependent changes; a path alone
does not invalidate every capture.

Repo-level files may add project-specific context (e.g. the worldarchitect.ai
overlay: `evidence-standards.md` under `<repo>/.claude/skills/` §
"Claim-scoped evidence revalidation"). Shared [pr-lifecycle precedence](../pr-lifecycle/SKILL.md#precedence-and-scope) governs conflicting lifecycle copies; domain-specific proof and separate safety/merge restrictions remain. Repo overlays cannot waive the delta-and-claim test.

## Evidence Sequencing — expensive evidence runs LAST, once

**Reproduce first.** Before a behavior fix, obtain fresh evidence of the
reported failure at the lowest sufficient layer and preserve the baseline
revision, inputs, and output. Source/trace inspection and authorized diagnostic
instrumentation may be needed to construct that reproducer. A missing
reproducer blocks an unproven fix claim, not continued diagnosis. Real-service
failures still require the real boundary; a fast unit test cannot substitute
for a cross-service reproduction.

**Iterate cheap, finish expensive.** Cheap gates (unit/focused tests, lint,
compile) iterate freely per commit. Review scheduling follows
`pr-lifecycle/SKILL.md`'s canonical lifecycle and composition contract; keep
enforcing the required correctness and evidence checks. Final expensive
evidence (real-server + real-LLM runs, packaged RED/GREEN comparisons,
browser/video capture, bundle assembly) runs ONCE, at the END: only after code
is complete — all review findings resolved or explicitly deferred, focused
tests green, no known remaining code work. Freeze the HEAD, then run the
expensive stack against it. Mid-iteration expensive evidence is voided by the
next fix (PR #9604/#9640, 2026-09-01: ~40 of 50 commits were evidence churn;
the RED/GREEN pair and bundle needed a full rerun anyway). The final comparison
may replay the preserved baseline alongside the completed candidate;
scheduling that package last does not defer the initial failure reproduction
until after the behavior fix.

**Rerun only on a material change** per the Staleness Tolerance delta-and-claim
test. When review findings arrive after evidence, classify materiality FIRST:
findings that block correct behavior must be fixed and reverified; style, nit,
doc, or wording feedback may be tracked without weakening the required
correctness gates. Batch ALL pending behavioral fixes into ONE new SHA before
any rerun — never a rerun per finding.

**Harness code is not the feature.** Building or hardening capture harnesses
inside the feature PR moves the HEAD and voids gates. Land harness changes in
their own PR first, then freeze the feature head.

**Launch capsule.** Before an expensive FINAL run, record: FINAL or DIAGNOSTIC,
exact worktree and SHA, absolute interpreter, command and output paths,
nonsecret effective provider/model settings, and dedicated test-account scope.
Run cheap import, browser, and provider-selection preflight through that same
invocation before provider calls; confirm behavior work is settled for FINAL.
Reviewers must reuse the exact capsule. Setup failures remain setup failures
until raw provider proof supports a product or auth diagnosis.

**Preflight the producer.** Before expensive capture, verify the actual
producer identity and provider, downstream logging target, and readiness in
the child that will run it. Confirm canonical control IDs and the observed
terminal envelope; an absent optional success field does not mean `false`.
Reuse the existing pipeline; do not add mocks or retry loops. If a harness
fails after controlled state was persisted, resume it through the real SDK only
when readback proves its preconditions, and record the resume source and
limits. Complete published PR-body media (including the GIF derivative
manifest) and direct raw RED/GREEN delivery before starting the final `/er`
evidence review. This sequencing does not delay cheap code or advice review,
which may run earlier or concurrently.

## Evidence class table

| Class | Description | Claim label | Acceptable for production claim? |
|---|---|---|---|
| **real-callstack + real-LLM** | Real provider POST (e.g. `https://generativelanguage.googleapis.com/...`), real response streamed | `[Layer 2 real-LLM]` | **Yes** (required for LLM-behavior claims) |
| **real-callstack + mock-at-network** | Real callstack, HTTP boundary mocked with recorded body | `[Layer 2 mock-at-network]` | Yes, for non-LLM claims |
| **real-callstack + real-BQ/HTTP** | Real BigQuery / Firestore / HTTP insert | `[Layer 2 real-BQ]` | Yes |
| **real-callstack + in-process SDK mock** | `gemini_provider.get_client = lambda: _FakeClient()` — SDK short-circuited | `[Layer 1 synthetic-LLM]` | **No** (named anti-pattern, below) |
| **unit test** | Isolated deterministic execution, monkeypatched, no real callstack | `[Layer 1 unit]` | Bounded deterministic claims only; never live-boundary proof |
| **none** | No artifact, just assertion | — | No |

## Unit proof and claim boundaries

Choose sufficient evidence with `pr-lifecycle` § Change-impact review and test
depth, `/4layer`, and `testing-layers`, not by line count alone. `/es` remains
the evidence-classification gate; it does not force every production edit
through live LLM or browser capture.

A bounded deterministic claim may use fresh focused unit RED/GREEN and affected
regressions when the changed logic is self-contained and no service, model,
security, persistence, or browser boundary is implicated. A small
single-function fix can qualify; small size alone does not. State exactly what
the unit proof covers and does not cover, retaining commands, results, and
tested SHA.

Unit proof is insufficient for model compliance, auth, persistence races, or
browser behavior; no amount of unit coverage proves an unexercised integration
or live boundary. Integration claims require the implicated real callstack and
boundary; model behavior needs real-provider proof where lower layers cannot
establish the claim. Never replace required real-service captures with mocks
or replays. Non-production work still requires proportionate checks; a test
assertion, shared driver, CI rule, or agent policy change can invalidate
existing evidence. All existing real-service-only directory contracts remain
in force.

### SDK-mock named anti-pattern

Mocks at the **in-process function boundary are not mocks at an external API
boundary.** When the production path includes a third-party SDK
(`google.genai`, `openai`, `anthropic`, ...), mocking a wrapper inside the
codebase replaces the whole SDK with fabricated objects: the downstream
call-graph runs end-to-end, but the data flowing through it is synthetic.

**Detection signal:** the verify script imports the production module AND
overrides any function in that module's call-graph that talks to the SDK. If
the SDK constructor itself is reachable, the LLM is real; if the SDK is
short-circuited, the LLM is synthetic regardless of what else is real.

**Per-claim layer label is mandatory.** Every /er verdict claim must end with
`[Layer N source]` from the class table; a claim backed by several layers lists
each (e.g. `[Layer 2 real-LLM, Layer 2 real-BQ]`), which makes it impossible to
silently downgrade a real-LLM claim to a synthetic-LLM one. A claim mixing
Layer 2 (real BQ) with Layer 1 (synthetic LLM) is **not** Layer 2 proof for its
LLM-behavior part: its /er verdict must be **PARTIAL** or **INSUFFICIENT**, not
**PASS**. A claim lacking the layer label is non-compliant; downgrade its
verdict to PARTIAL.

## Evidence access and publication

Keep the original evidence and its provenance intact. Give the intended
reviewer accessible reproduction directions and artifact links in the PR, a
checked-in document, an access-controlled receipt/store, or an authorized gist,
including the reviewed/tested SHA, dependencies, exact commands and expected
results required for the applicable evidence class. These underlying artifacts
may remain in authorized private hosting. The separate sanitized review receipt
follows `pr-lifecycle` § Review records in the PR description, including its
gist URL (or, for a one-liner fast-path `/es` record, the PR-body section),
exact reviewed SHA, and `PUBLICATION BLOCKED` state when publication cannot
complete. Artifact hosting is not review-record completion.

Publish or send artifacts only within the current task's authorized audience
and destination. Sanitize any shareable copy while retaining private originals
and identifying the relationship between them. An unlisted gist is accessible
to anyone with its URL; it is not an access-controlled secret store.

For authorized evidence, redact authentication tokens — bearer, access,
refresh, custom and session tokens, and token-bearing URL components. Account
emails and IDs may remain visible; their presence alone is not a privacy defect
or an additional redaction or approval gate. Ordinary game/test content
likewise needs no separate privacy certification merely because it is readable.

Follow any actual repository gate requiring particular in-tree evidence paths.

## Bundle anatomy (minimal)

The canonical bundle is the iteration directory the project's evidence harness
produces on the dedicated Scratch volume, resolved dynamically via
`~/.claude/skills/scratch-space/SKILL.md` (`diskm scratch-new <repo-path> <purpose> --kind evidence`, or `$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "<repo>/evidence/<date>-<slug>")`). For the WorldArchitect MCP harness, see
`bundle-anatomy.md` in this directory. At minimum, a bundle contains:

- `metadata.json` — git provenance (`git_head`, `merge_base`, `commits_ahead_of_main`, `diff_stat_vs_main`), server runtime (PID, port, cmdline, env vars), `bundle_version`, `run_id`, `iteration`, `bundle_timestamp`
- `run.json` — `scenarios[]` array (each with `name`, `errors`, `campaign_id` if any)
- `evidence.md` — human summary, a **Claim → Artifact Map** (claim → file → key field), and a **"What This Evidence Does NOT Prove"** section (both required)
- `methodology.md` — env, commands, pass criteria, threshold values used
- `README.md` — package manifest (test name, run id, branch, commit)
- `*.sha256` sibling files for every substantive file (use **local basename** so `sha256sum -c` works)
- `artifacts/` — server.log, lsof/ps output, optional browser recordings
- Trace JSONL captures when the harness emits them: `request_responses.jsonl` (MCP), `llm_request_responses.jsonl` (LLM), `http_request_responses.jsonl` (HTTP+SSE)

## UI video evidence

JSONL capture shapes live in `bundle-anatomy.md`. For a UI claim, the PR
description links the evidence bundle (resolved per § Bundle anatomy), a
playable video on an authorized host (e.g.
`https://storage.googleapis.com/<bucket>/agent-evidence/<repo>/<pr>-<topic>/attack-roll.mp4`;
a `github.com/.../releases/download/untagged-*` URL is a red flag), and a paired
inline GIF of the same run (§ Visual Evidence). The bundle's `metadata.json`
carries `browser_origin`, `gateway_url`, `server.pid`, and `artifact_manifest`.

A captioned `.mp4`/`.gif`/`.cast` produced by the test pipeline (e.g. an
asciinema `.cast` in the bundle converted to mp4 for hosting) is required, not
a manual screen recording; see `ui-video-evidence.md` and `tmux-video-evidence.md` in this
directory for the recording rules. Docs-only / test-only PRs use
`N/A - no UI behavior changed`.

**The video must visually show the element under test changing, in the pixels —
not a caption.** A caption is text the test wrote from its own DOM reads
(harness-authored), so it asserts the state rather than demonstrating it; a
clip framing only page chrome while the element sits below the fold proves
nothing. The recording must `scrollIntoView` the specific control/field and
settle so its before→after change is visible in the frames. When reviewing UI
video (`/er`), **extract frames and look**
(`ffmpeg -i <video> -vf fps=1 /tmp/frames/f_%02d.png`); if the element is never
in-frame, or the only on-screen evidence is a caption overlay, the UI evidence
is INSUFFICIENT even if the video exists, is captioned, and the test passed.
Acceptance by video also requires an independent AI content review (other than
the author or orchestrator) of the published video's frames per acceptance step
(`evidence-review` check 4); privacy, playback, and turn-record reviews do not count.

## Visual Evidence & Mandatory Inline Rendering in PRs

Visual comparisons under `## Visual Evidence` in PR descriptions must render
**directly inline** on GitHub so reviewers can inspect them without clicking
away:

1. **Inline image tags.** `[screenshot](https://...)` renders only as clickable
   text and fails visual review. Use HTML `<img src="..." width="..." alt="...">`
   (strongly preferred in tables, for precise width control without distortion
   or overflow) or `![alt](url)`.

2. **Standard widths.** Desktop screenshots in 2-column Before/After tables:
   `width="450"` (or `400`); mobile (375×812): `width="360"` (or `300`);
   side-by-side comparison slides: `width="800"`.

3. **Standard PR table format**:
   ```markdown
   ## Visual Evidence

   ### Desktop (1440×900) Comparison

   | Before (baseline `<before_sha>`) | After (candidate `<after_sha>`) |
   | :---: | :---: |
   | <img src="<before_desktop_url>" width="450" alt="Before Desktop"> | <img src="<after_desktop_url>" width="450" alt="After Desktop"> |

   ### Mobile (375×812) Comparison
   <!-- same table shape, width="360" -->

   ### Walkthrough Video

   | Before | After |
   | :---: | :---: |
   | <img src="https://storage.googleapis.com/<bucket>/<path>/before.gif" width="300" alt="Before walkthrough"> | <img src="https://storage.googleapis.com/<bucket>/<path>/after.gif" width="300" alt="After walkthrough"> |
   | [▶ before.mp4](https://storage.googleapis.com/<bucket>/<path>/before.mp4) (SHA256: `<sha256>`) | [▶ after.mp4](https://storage.googleapis.com/<bucket>/<path>/after.mp4) (SHA256: `<sha256>`) |
   ```

4. **Media hosting (Google Cloud Storage is the default host)**:
   - Upload to the authorized evidence bucket (e.g. `gs://<evidence-bucket>/agent-evidence/<repo>/<pr>-<topic>-<date>/`) and link as `https://storage.googleapis.com/<evidence-bucket>/<object>`. That URL grants no access by itself: browser playback works only for objects already authorized for the intended reviewers (e.g. public-read).
   - A GitHub attachment is also acceptable — for video it is the only form GitHub plays inline — as is any other host the current task authorizes. Media that must stay private stays in authorized private hosting; never make evidence public, or change bucket access, merely to satisfy a link check. Never acceptable: a URL the intended reviewer cannot open and play, `gs://…` (not clickable), or `https://storage.cloud.google.com/…` (redirects to a Google login).
   - An external mp4 renders only as a link, so every video gets an **inline GIF** of the same run (`ffmpeg -i in.webm -vf "fps=6,scale=300:-1:flags=lanczos" out.gif`) next to a **playable mp4 link**. Prefer MP4/H.264 (`-c:v libx264 -pix_fmt yuv420p`) for broadest compatibility; WebM may be added but never replaces the MP4/H.264 variant.
   - Screenshots are inline `<img>` from an authorized host that renders for the intended reviewer, showing the real captured pixels of the claimed state — not placeholders, crops that hide the changed element, or icons.
   - Verify before claiming the stage exit:
     - Every URL resolves with the expected `content-type` (`video/mp4`, `image/gif`, `image/png`) **for the intended reviewer**: `curl -sI <url>` for a public object, or the reviewer's own authorized access when the media stays private. Record which access mode applies instead of forcing public access to prove reachability.
     - Every inline GIF and screenshot appears in the **rendered** PR body *and is the right image*: compare GitHub's original-URL attributes with the media the receipt declares (`gh api repos/<owner>/<repo>/pulls/<n> -H "Accept: application/vnd.github.html+json" --jq .body_html | grep -o 'data-canonical-src="[^"]*"'`). A bare image count is not acceptable: `grep -c` counts matching *lines* (one line holding two images reports `1`), and an aggregate can be matched by unrelated images.
     - The sanitized gist receipt lists the same media with sha256 hashes and access mode. Redact bearer, signed-query and other credential-bearing URL components — record the protected location plus hash instead of the token, since a gist is link-accessible.

5. **Reject in review** (beyond the violations above): raw uncaptioned image
   dumps with no Before/After table; desktop-only testing that skips mobile
   (375×812); heavy image binaries committed to git (use authorized storage or
   unlisted gists); a video only as a text link with no inline GIF; media only
   in a gist, a comment or a bundle README instead of inline in the PR
   description.

## Cross-references

This is the **user-scope (global)** `/es` policy. For complete evidence
standards, always read both this skill and the relevant repo-level file:

1. **Master policy** — `~/.claude/CLAUDE.md` § "Evidence — match proof to the claim"
   and § Unit proof and claim boundaries above. Use the current claim-based rule,
   not obsolete blanket production/size-only exceptions. Preserve UI-video and
   risk-specific requirements; the repo overlay names its triggers.
2. **Repo-level /es** — `<repo>/.claude/skills/evidence-standards/SKILL.md`, or
   in flat repos `evidence-standards.md` under `<repo>/.claude/skills/`, adds
   project-specific extensions (e.g. `your-project.com` has dice-claim,
   campaign-isolation, BigQuery, and Gemini specifics). **Always read both** and
   apply the [scoped precedence rule](../pr-lifecycle/SKILL.md#precedence-and-scope);
   repository domain proof does not override the shared lifecycle.
3. **Companion files in this directory** — `bundle-anatomy.md` (bundle
   structure, JSONL shapes, integrity rules), `tmux-video-evidence.md`
   (tmux/asciinema recording), `ui-video-evidence.md` (browser/UI video).

Adjacent skills: `evidence-review` (`/er` — the per-claim audit),
`tdd-evidence-workflow` (TDD-specific evidence patterns),
`streaming-evidence-standards` (streaming-response signed-payload evidence),
`ui-bug-proof` (RED-before-GREEN UI bug reproduction).
