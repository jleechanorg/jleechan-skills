---
name: llm-testing
description: Real-LLM, zero-mock testing layer — forces testing_mcp/ or testing_ui/ tests against a real local or remote server with real Gemini, real Firestore, and no mock flags. The execution mechanism behind /es evidence.
---

# /llm-testing — Real-LLM Zero-Mock Testing Guide

**Purpose**: The authoritative layer for proving behavior that depends on the **LLM's
judgment**. Where `/end2end-testing` (Layer 2) deliberately *fakes* external APIs for speed and
determinism, `/llm-testing` (Layers 3–5) does the opposite: **real LLM, real services, zero
mocks**, on a real server (local or remote preview). This is the execution mechanism that produces
the `/es` evidence required for every non-test change under `$PROJECT_ROOT/**`.

## Core principle — ZERO MOCKS

A `/llm-testing` run is **invalid** if any of these are set:

- `TEST_MODE=mock`
- `MOCK_SERVICES_MODE` (any truthy value)
- `USE_MOCK_FIREBASE`
- `USE_MOCK_GEMINI`
- `FORCE_TEST_MODEL=true`
- any mock-server / fake-LLM / fake-firestore flag

The production path uses a real LLM → the test must use a real LLM. Faking the model means the
test cannot prove model-owned behavior (routing, level-up commit, reconciliation, narrative,
streaming). **No exceptions.** If you only need to prove deterministic helper logic with faked
externals, that is `/end2end-testing` (Layer 2), not `/llm-testing`.

## Directories (run targets)

| Layer | Directory | Runner | What it proves |
|-------|-----------|--------|----------------|
| **3. MCP API** | `testing_mcp/` | `vpython testing_mcp/<domain>/test_*.py` (**direct, NOT pytest**) | Real server + real LLM over the MCP/HTTP API; game-state, rewards, level-up, routing |
| **5. Browser/UI** | `testing_ui/` | `python3 $PROJECT_ROOT/main.py testui` with `TESTING_AUTH_BYPASS=true` | Real browser + real server + real LLM; user-visible/interactive behavior |

`testing_mcp/` tests subclass `MCPTestBase` (`testing_mcp/lib/base_test.py`) which auto-starts a
real local server on the worktree port and health-checks before running.

## Environment (real services)

```bash
export TESTING_AUTH_BYPASS=true
export GOOGLE_APPLICATION_CREDENTIALS=$HOME/serviceAccountKey.json
# DO NOT set any mock flag (see "Core principle" above)
# DO NOT set AGY_PROVIDER_ENABLED=false by habit (see "AGY is the cost-saving default" below)
```

- **AGY is the cost-saving default real-LLM provider.** Since PR #7971 (2026-06-29,
  `008c55aaaa`), `is_agy_provider_mode()` (`$PROJECT_ROOT/llm_providers/provider_gateway.py`)
  makes the `agy` CLI (flat-rate Google Antigravity backend) the default LLM for
  local/test real-LLM runs — precedence `explicit opt-out > WORLDAI_PROD >
  GAE_ENV=standard > default-on > opt-in`. **Do not pass `AGY_PROVIDER_ENABLED=false`
  reflexively** — there are exactly TWO narrow reasons to opt out: (1) validating the
  production Gemini-SDK streaming/tool-calling path, or (2) a flow that depends on strict
  JSON-mode output and hits agy's known JSON-reliability gap (agy lists "JSON-only response
  grammar" as a non-goal — forced via prompt preamble only; the worldai-claw RNW harness
  saw agy return invalid gameplay JSON killing every stream, 2026-07-07). Check whether your
  flow parses strict JSON before assuming this applies. If you do opt out, state the reason
  in the evidence bundle rather than opting out silently.
  The "agy needs interactive TTY auth" belief is stale — `$PROJECT_ROOT/install.sh` provisions a
  persisted OAuth token under `AGY_RUNTIME_HOME` (default `/tmp/agy-clean-home-v1`) and
  writes `$AGY_RUNTIME_HOME/worldai-agy.env`; source that file before the run. The shared
  local test launcher fails closed with this setup command when the runtime is missing;
  it must not silently switch to the Gemini SDK. Mock mode
  still wins over agy (`mock > agy > Gemini SDK`), so this changes cost, not the zero-mock
  guarantee.
- **Local real server** (default): the harness starts it for you (`MCPTestBase`).
- **Remote preview** (allowed): pass `--preview-url <gcp_preview_url>` to run against the
  PR's auto-deployed Cloud Run preview. Real services either way.
- **Streaming is PRIMARY**: any test exercising an LLM response must use streaming mode; evidence
  must show `/interaction/stream` captures + the streaming done payload (see
  `.claude/skills/streaming-evidence-standards`). **This transport requirement is unaffected by
  provider choice** — every real-LLM test still hits `/interaction/stream`, whether agy or the
  Gemini SDK serves the request behind it; neither opt-out reason below is a license to skip
  `/interaction/stream` and use a non-streaming request path instead.
  - **Transport vs. provider streaming**: an agy-backed run exercises the real
    `/interaction/stream` transport/SSE plumbing, but agy itself does NOT provide token-by-token
    *provider-level* streaming (`generate_content_stream` returns one completed response, not
    incremental chunks) or native tool-call grammar. A claim specifically about model-level
    streaming behavior or tool-calling needs an explicit Gemini SDK run
    (`AGY_PROVIDER_ENABLED=false`), stated as the reason in the evidence bundle — that run still
    goes through `/interaction/stream`; only the backend behind it changes.
  - The strict-JSON-mode opt-out reason (agy's known JSON-reliability gap) is the same: it
    changes which backend serves `/interaction/stream`, not whether the test uses it.

## When to use /llm-testing (vs lower layers)

Use it whenever **the LLM's judgment affects the outcome** or you cross the **LLM↔server
boundary**:

- agent routing / intent classification, level-up / rewards / XP, game-state persistence,
  character creation finalize, conclude/finalize prompts, streaming delivery, any prompt change.

Per repo policy, **every non-test change under `$PROJECT_ROOT/**` requires `/es` evidence**, and that
evidence MUST come from a `/llm-testing` run (real server + real LLM) — never from unit tests,
mocked tests, pasted pytest output, or mock-mode CI. Those are supporting checks only.

## Invocation

```bash
# Layer 3 — MCP API, real LLM, local server (direct runner, never pytest):
cd $PROJECT_ROOT
TESTING_AUTH_BYPASS=true GOOGLE_APPLICATION_CREDENTIALS=$HOME/serviceAccountKey.json \
  vpython testing_mcp/core/test_level_up_organic.py --level-up-scenario single-organic --class-name paladin

# Layer 3 — against a remote GCP preview server:
vpython testing_mcp/core/test_<feature>.py --preview-url <preview_url>

# Layer 5 — Browser/UI, real LLM:
TESTING_AUTH_BYPASS=true python3 $PROJECT_ROOT/main.py testui
```

`/llm-testing <feature-or-blocker>` — locate the matching `testing_mcp/` (or `testing_ui/`)
driver, run it with the zero-mock real-services env above, and print the full absolute evidence
bundle path.

## Evidence (ties to /es)

- Evidence bundle: `/tmp/your-project.com/<branch>/<test_name>/latest/` — print the **full
  absolute path**.
- Must include streaming artifacts (`streaming_evidence.json`, `/interaction/stream` captures in
  `http_request_responses.jsonl`, streaming done payload).
- UI/interactive behavior also requires a **captioned video** (`.mp4`/`.gif`/`.cast`) tied to the
  PR HEAD SHA.
- Provenance: input captured from the real client, never reconstructed from backend reference
  files (no circular provenance). See `.claude/skills/bypass-claims.md`.
- Re-run when production files change after the evidence SHA (`git diff <evidence_sha>..HEAD --
  $PROJECT_ROOT/` must be empty before claiming a layer green).

## Relationship to the other testing commands

- **`/end2end-testing`** — Layer 2, **faked** externals, deterministic, fast. Use first to iterate
  logic cheaply.
- **`/llm-testing`** — Layers 3 & 5, **real** LLM + services, zero mocks. Use to PROVE behavior.
- **`/4layer`** — the repro ladder (unit → end2end → **llm-testing (MCP)** → **llm-testing
  (browser)**); climb only as needed.
- **`/testing-layers`** — the decision guide for picking a layer; `/llm-testing` is the canonical
  Layer 3/5 entry point.
- **`/es`** — the evidence-standards gate; `/llm-testing` is how you generate evidence that passes
  it.

## Anti-patterns (a /llm-testing run that does NOT count)

- Any mock flag set (the run is void).
- Flask test client instead of a real server (no real HTTP/MCP boundary).
- TTFC/latency numbers from an in-process client (not a real server round-trip).
- Asserting on backend reference data the test itself seeded (circular provenance).
- Non-streaming finish turns when streaming is the production path.
