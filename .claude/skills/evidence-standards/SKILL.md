---
name: evidence-standards
description: General cross-project evidence standards (user scope). Use for the /es skill. Repo-level .claude/skills/evidence-standards.md files add project-specific extensions — always consult both.
when-to-use: Before /er, /green, gate fixes, or AO worker dispatch on a PR that touches production code paths. Also when claiming a behavior is "fixed" or "working" and you need to prove it.
---

# /es — Evidence Standards (user scope)

## Summary

Evidence must **prove what you claim**. The strongest evidence is a raw
request/response capture from the real production code path; a unit test in
isolation proves nothing about real behavior. Match proof to the claim, label
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
  through the real path** (`~/.claude/skills/ablation/SKILL.md`) over
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

## Core principle: raw req/resp > unit tests > nothing

Ordered by strength, for a production behavior claim:

1. **Raw request/response capture from the real code path** (HTTP, JSONL, logs, video) — Layer 2.
2. **Real-service capture with mocks only at the network boundary** (`httpx.MockTransport`, `responses`, `respx` with a recorded body) — Layer 2 mock-at-network.
3. **Unit test in isolation** (monkeypatched, no real callstack) — Layer 1, **insufficient for production claims**.
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

## Evidence Staleness Tolerance — only PRODUCTION changes stale evidence

**A moving HEAD does NOT invalidate evidence by itself.** Evidence captured at a prior SHA
stays valid at HEAD as long as **no production-code change** landed between the evidence SHA
and HEAD. Docs, tests, skills, ordinary PR-policy changes, CI-lint, type-hints, and comment-only commits stacked on top
do **not** require a fresh evidence run. Flagging evidence "stale" because the head SHA moved
— without checking *what* moved — is an over-correction; check the diff, not the SHA equality.

**The check is a diff, not a SHA comparison:**

1. Determine the evidence SHA (from `metadata.json.provenance.git_head` or the bundle README).
2. `git diff --name-only <evidence-sha> HEAD` — classify every changed file.
3. If **every** changed file is non-behavioral (test-only, docs-only `*.md`/`docs/`/`CLAUDE.md`/`AGENTS.md`,
   `.claude/`/`.codex/`/`.cursor/` skills & agents, test/lint CI workflows **excluding** `deploy*`/`*preview*`,
   type-hints/comments) → evidence remains valid; document the tolerance and move on.
4. For any `.py` file you classify as "comment/type-hint only," run the full content diff
   (`git diff <evidence-sha> HEAD -- <file>`) — `--name-only` can't tell a comment edit from a behavior edit.

**Fresh evidence IS required only when a production change exists** between the SHAs:
production code (the repo's source tree excluding its test dirs, **including** prompt/template surfaces — the repo-level /es file names the exact paths),
API/endpoints/game logic/agent routing, runtime config (env vars, feature flags), DB schema/migrations,
or a deploy/preview workflow — or any **mixed** diff containing at least one such file.

**Rationale:** rerunning real-server + real-LLM evidence for a docs typo or test rename burns
hours of LLM time for zero added confidence. The evidence proves a *behavior*; if the behavior's
code is byte-identical at HEAD, the proof is byte-valid at HEAD. Repo-level files may add
path-specific context (e.g. `<repo>/.claude/skills/evidence-standards.md` §"Evidence Staleness
Tolerance for Test/Docs-Only Changes") and take precedence on conflict.

## Evidence Sequencing — expensive evidence runs LAST, once

Before a behavior fix, obtain fresh evidence of the reported failure at the
lowest sufficient layer and preserve the baseline revision, inputs, and output.
Source/trace inspection and authorized diagnostic instrumentation may be needed
to construct that reproducer. A missing reproducer blocks an unproven fix claim,
not continued diagnosis. Real-service failures still require the real boundary;
a fast unit test cannot substitute for a cross-service reproduction.

Cheap gates (unit/focused tests, lint, compile) iterate freely per commit.
Adversarial code-review rounds are cheap per-pass, but must continue to enforce
the required correctness and evidence checks. Final expensive evidence (real-server + real-LLM runs, packaged RED/GREEN comparisons,
browser/video capture, bundle assembly) runs ONCE, at the END: only after code is
complete — all review findings resolved or explicitly deferred, focused tests
green, no known remaining code work. Freeze the HEAD, then run the expensive
stack against it. Running expensive evidence mid-iteration guarantees it is
voided by the next fix (PR #9604/#9640, 2026-09-01: ~40 of 50 commits were
evidence churn; the RED/GREEN pair and bundle had to be scheduled for a full
rerun anyway). The final comparison may replay the preserved baseline alongside
the completed candidate; scheduling that package last does not defer the initial
failure reproduction until after the behavior fix.

Rerun expensive evidence ONLY on a material change per the Staleness Tolerance
diff test above: a production-behavior file in the evidenced path changed, or
the artifact producer changed in a way that alters captured bytes. When review
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
| **unit test** | `mock.patch(...)`, no real callstack | Layer 1 | **No** for production claims (3 exceptions below) |
| **none** | No artifact, just assertion | — | No |

## Disallow unit tests as evidence (with 3 exceptions)

**Unit-only proof is NOT sufficient.** A behavior verified only by unit tests
(Layer 1, mocked/isolated) is not proven. `/es` and `/er` must treat unit-only
evidence as **INSUFFICIENT** and explicitly warn the user when a claim rests
on unit tests alone. The minimum acceptable proof is **Layer 2** end-to-end
integration — real callstack exercised, mocks only at external API boundaries
(network, third-party services). For production code paths that include an
LLM or external service, real-service evidence is required (no mocked
provider).

**Exception 1:** non-production changes (docs, tests, tooling/scripts) — no
evidence required.

**Exception 2:** production changes under 100 delta lines of non-test code —
unit-only IS acceptable.

**Exception 3:** (none — these two are the only carve-outs from the
"unit-only is insufficient" rule.)

This applies regardless of how many unit tests pass or how high coverage is.
"All unit tests green" does not constitute proof of integration correctness,
server behavior, or LLM output.

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
required for the applicable evidence class. A gist is one supported location;
it is not an independent prerequisite for a passing verdict.

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
  entry with `model: gemini-3-pro`, a real `https://generativelanguage.googleapis.com/...`
  POST in the wire log, and a `dc_reasoning` field set before the `random.randint()` call.
```

The layer labels make it impossible to silently downgrade a real-LLM claim to
a synthetic-LLM claim.

### Example 3 — Video / cast evidence (UI behavior)

```text
# PR description includes:
- Evidence bundle: /tmp/your-project.com/fix-attack-roll/iteration_001/
- Video: https://<project-host>/releases/download/evidence-2026-06-16/attack-roll.mp4
  (NOT github.com/.../releases/download/untagged-* — that is a red flag)
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

## Cross-references

This is the **user-scope (global)** `/es` policy. For complete evidence
standards, always read both this skill and the relevant repo-level file:

1. **Master policy** — `~/.claude/CLAUDE.md` § "Evidence — match proof to the claim" (the
   `Evidence-first` rule, the `Unit-only proof is NOT sufficient` rule with its
   three-exception wording, the UI-video requirement, and the PR-touching
   trigger list — the repo-level /es file names the repo's exact trigger paths).
2. **Repo-level /es** — most repos mirror this skill at
   `<repo>/.claude/skills/evidence-standards.md` with project-specific
   extensions (e.g. `your-project.com` has dice-claim, campaign-isolation,
   BigQuery, and Gemini specifics). **Always read both** — the global file
   is the floor; the repo-level file is the ceiling.
3. **Companion files in this directory** — `bundle-anatomy.md` (bundle
   structure, JSONL shapes, integrity rules), `tmux-video-evidence.md`
   (tmux/asciinema recording), `ui-video-evidence.md` (browser/UI video).

Adjacent skills: `evidence-review` (`/er` — the per-claim audit), `tdd-evidence-workflow`
(TDD-specific evidence patterns), `streaming-evidence-standards`
(streaming-response signed-payload evidence), `ui-bug-proof` (RED-before-GREEN
UI bug reproduction).
