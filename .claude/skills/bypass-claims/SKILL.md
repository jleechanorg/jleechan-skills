---
name: bypass-claims
description: Bypass-claim evidence standards for any fast-path, short-circuit, LLM skip, template bypass, or cache hit claim in this repo.
---

# Bypass-claim evidence standards

**Applies to**: any "fast-path", "short-circuit", "LLM skip", "template bypass", or "cache hit" claim in this repo.

## Core rule

A test that proves a code path **bypasses an expensive operation** is only valid if the input it feeds the system is **captured from the real client**, not reconstructed from server-side reference files the bypass itself consults.

If the test's input and the bypass's gate both derive from the same file, the test is tautological — it proves the helper works when handed its own reference input, not that production actually reaches the helper.

## Required evidence for any bypass claim

1. **Client-captured input** — the exact byte string the real client sends, captured via one of:
   - Browser DevTools network tab export (HAR file)
   - Playwright/Puppeteer intercepted request body
   - Firestore-persisted payload from a real production session
   - JS constant extracted directly from the frontend source the browser serves (e.g. regex extract of `DEFAULT_X` from `campaign-wizard.js`)
   - **NOT ALLOWED**: reading the same backend file the bypass's gate reads
   - **NOT ALLOWED**: reconstructing the input from helper functions that share code with the gate
2. **Latency delta proof** — measured wall-clock time of the request with the bypass vs. without. Bypass must be meaningfully faster (typically ≥5× for LLM skips).
3. **Server log proof** — grep of the real server's stdout/stderr for the bypass's log line (e.g. `"Using pre-generated Dragon Knight template opening"`) AND absence of the expensive operation's log line (e.g. `"generate_content"`, `"/interaction/stream"` chunks).
4. **Production trace match** — if the bypass claim concerns an existing production bug, fetch a real affected record from Firestore/logs and show its persisted input hash/bytes match what your test feeds.
5. **Sync guard** — a CI-blocking unit test asserting the two (or more) sources of the bypass gate input stay byte-equal. Hash constants baked into `constants.py` MUST have a generator script AND a test that regenerates and compares.

## Forbidden patterns

- Loading the test description from `$PROJECT_ROOT/data/*_canonical_description.txt` and feeding it to an endpoint whose bypass hashes that same file → **circular provenance**
- Calling the bypass helper directly in a unit test and claiming it proves "the server bypasses the LLM" → **unit test masquerading as pipeline test**
- Measuring latency by calling the helper function in a loop → **does not cover routing, middleware, auth, prompt assembly, or any layer between ingress and the gate**
- Any test whose PASS does not require the real HTTP handler to execute end-to-end → not a bypass claim test

## Claim-class verdict rules

| Evidence present | Verdict |
|---|---|
| Unit test of helper only | **Unit** — cannot claim bypass |
| Helper + real HTTP call with server-derived input | **INSUFFICIENT** — circular provenance |
| Helper + real HTTP call with client-captured input + latency delta + server log grep | **PASS** for bypass claim |
| Above + sync guard test + production trace match | **PASS** for pipeline-bypass claim |

## Writing the failing test first (RED)

Before fixing any bypass bug:

1. Write the test that feeds **client-captured** input to the real local server (`./local.sh`).
2. Assert the latency threshold AND the bypass log line AND the absence of the expensive-operation log.
3. Run it — it MUST fail on the current broken code. If it passes on broken code, the test is not exercising the real path.
4. Only then fix the root cause.
5. Rerun — it MUST pass.
6. Record both RED and GREEN evidence bundles with full absolute paths.

## Sync guard pattern

Whenever a bypass gate depends on two or more sources of truth being byte-identical (a JS constant and a backend file, a generated prompt and a baked-in SHA, etc.), the repo MUST include:

- A regeneration script (e.g. `scripts/regenerate_dragon_knight_canonical.py`) that rebuilds the hash/constant from the canonical source
- A CI-enforced unit test that runs the regeneration in memory and asserts equality with the committed constant
- A comment on the constant pointing to the regeneration script

Without the sync guard, any future edit to either source silently breaks the bypass — the same bug this skill exists to prevent.

## Canonical frontend-source helper (Dragon Knight)

`testing_utils/dragon_knight_frontend_source.py` exposes
`get_frontend_default_dragon_knight_description()` — the **only** sanctioned
way for any Dragon Knight bypass test to obtain the description field. It
statically parses `$PROJECT_ROOT/frontend_v1/js/campaign-wizard.js` for the
`DEFAULT_DRAGON_KNIGHT_DESCRIPTION` template literal and fails loudly if the
shape changes. Any test that reads
`$PROJECT_ROOT/data/dragon_knight_canonical_description.txt` for its request
payload is a circular-provenance violation and must be rewritten to use this
helper.

## Checklist for any new fast-path / bypass / cache-hit claim

Before shipping an optimization that claims to skip an expensive operation on
a subset of inputs, the repo MUST grow the following five artifacts. The
Dragon Knight fast-path is the template; copy its structure.

1. **Client-captured input helper** under `testing_utils/` (mirror of
   `testing_utils/dragon_knight_frontend_source.py`). The helper is the
   single sanctioned way to obtain the "real client bytes" any bypass test
   needs. It MUST NOT read the backend reference file the gate consults.
2. **Sync-guard unit test** (mirror of
   `$PROJECT_ROOT/tests/test_dragon_knight_frontend_backend_sync.py`). Asserts
   that running the gate's own prompt builder on the client-captured input
   produces the baked-in SHA / cache key. Wired into a job required by
   branch protection so drift blocks merges.
3. **Regeneration script** under `scripts/` (mirror of
   `scripts/regenerate_dragon_knight_canonical.py`). One command rebuilds
   the constant (and any coupled backend data file) from the client helper.
   Supports `--check` for a CI dry-run. Referenced by a comment directly
   above the constant in code.
4. **Pipeline integration test with fatal LLM spy** (mirror of
   `$PROJECT_ROOT/tests/test_dragon_knight_pipeline_evidence.py`). Drives the
   real server function (not the helper) with client-captured input,
   patches every LLM entrypoint with an `AssertionError`-raising spy, and
   asserts zero spy hits on the canonical path and ≥1 on a negative
   control. Evidence bundle allocated via `setUpModule()` with atomic
   `os.replace()` for the `latest` symlink so parallel runs don't race.
5. **Real-server UI test** (mirror of
   `testing_ui/test_dragon_knight_fastpath_real_frontend.py`). Boots
   gunicorn, POSTs client-captured bytes through the real frontend helper,
   asserts the fast-path marker appears in server stdout and no LLM API
   markers do, AND records wall-clock latency delta vs. a non-canonical
   control. CI path filter MUST include every file the gate reads (JS
   constant, backend canonical file, prompt builder, template module).

If any of these five artifacts is missing, the bypass claim is INSUFFICIENT
regardless of how many helper-level tests pass.

## Prior incident (PR #6137)

Dragon Knight fast-path claimed to skip `get_initial_story()` LLM call for default campaigns. Three separate "evidence" tests (commits `351d3c24d`, `12960e46b`, `285d89699`) all PASSED. Reality: preview server took 32s on real dragon-knight creation. Root cause: tests loaded `description` from `$PROJECT_ROOT/data/dragon_knight_canonical_description.txt` (18k chars) — the same file the bypass's SHA gate hashes — while the actual frontend `campaign-wizard.js` ships a 41k-char version. The hash could never match in production; the test could never detect it.

Fix requires: (a) either sync frontend byte-equal to backend canonical OR drop the SHA gate in favor of `campaign_type + custom_options` matching, AND (b) a real-server UI test that posts the frontend default string AND (c) a sync guard CI test.
