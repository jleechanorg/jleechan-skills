---
name: testing-layers
description: Select the correct WorldArchitect.AI testing layer and understand its evidence value.
---

# Testing Layers — When to Use Each Layer and How to Decide

## Purpose

This skill defines the **concrete test directory structure** for Your Project, the **decision principles** for choosing the right testing layer, and the **evidence implications** of each layer. Use this when creating new tests, reviewing test coverage, or evaluating `/es` evidence completeness.

## Directory Map

| Layer | Directory | Runner | Count | Evidence Class |
|---|---|---|---|---|
| **1. Unit** | `$PROJECT_ROOT/tests/` | `./vpython -m pytest $PROJECT_ROOT/tests/test_*.py` | ~295 files | Mock (no `/es` credit) |
| **1b. Unit (top-level)** | `tests/` | `./vpython -m pytest tests/test_*.py` | ~4 files | Mock (no `/es` credit) |
| **2. End-to-End**| `$PROJECT_ROOT/tests/test_end2end/` | `./vpython -m pytest $PROJECT_ROOT/tests/test_end2end/` | ~30 files | Mock (no `/es` credit) — see `/end2end-testing` skill |
| **3. MCP API** | `testing_mcp/` | `./vpython testing_mcp/test_*.py --server http://127.0.0.1:8001` | ~139 files | Server + LLM (full `/es`) — see `/llm-testing` skill |
| **4. HTTP API** | `testing_http/` | `./vpython testing_http/test_*.py` | ~25 files | Server (partial `/es`) |
| **5. Browser** | `testing_ui/` | `./vpython testing_ui/test_*.py` | ~40 files | Server + LLM + Browser (full `/es` + video) — see `/llm-testing` skill |

### Shared Libraries

| Library | Path | Purpose |
|---|---|---|
| MCP test base | `testing_mcp/lib/base_test.py` | `MCPTestBase` — server lifecycle, evidence bundle, provenance |
| MCP campaign utils | `testing_mcp/lib/campaign_utils.py` | `finish_character_creation`, `process_action`, `get_campaign_state` |
| MCP client | `testing_mcp/lib/mcp_client.py` | MCP protocol client for `tools_call` |
| Evidence utils | `testing_mcp/lib/__init__.py` | `capture_provenance`, `create_evidence_bundle`, `write_with_checksum` |
| Browser test base | `testing_ui/lib/browser_test_base.py` | `BrowserTestBase` — Playwright lifecycle, screenshots, video |
| HTTP test config | `testing_http/lib/config.py` | Server URL config, auth bypass |

### Execution Environment

- **Layer 1-2, 4 (Unit, E2E, HTTP)**: Default test environment is `TEST_MODE=mock` (via `run_tests.sh`).
- **Layer 3 & 5 (MCP, Browser)**: Must use real services. Set `MCP_TEST_MODE=real`, `TEST_MODE=real`, `MOCK_SERVICES_MODE=false`, `TESTING_AUTH_BYPASS=true`. **Use `/llm-testing`** as the canonical entry point — it forces the zero-mock real-LLM run and is the only valid source of `/es` evidence.
- **Never use mock mode** for `testing_mcp/` or `testing_ui/` — this is a hard policy (`/llm-testing` enforces it: a run with any mock flag set is void)

---

## Decision Principles — Which Layer to Test At

### Principle 1: Does the LLM's judgment affect the outcome?

If the behavior under test is **deterministic server code** that runs the same way regardless of what the LLM said, a **unit test** is the correct tier. The LLM is just a trigger — you can simulate it with a dict.

**CRITICAL DEFAULT RULE**: Unit tests should ONLY be done if we are 100% confident we can test the logic entirely self-contained. The logic must be truly small and self-contained. Otherwise, strongly consider Layer 2 (End-to-End) first by default.

- ✅ Unit: `dict.pop("level")` works identically whether the dict came from Gemini or a test fixture
- ✅ Unit: Boolean functions checking two dicts (`is_level_up_active()`)
- ❌ Not unit: "Does the server block a mutation shape that Gemini actually produces?"

### Principle 2: Is the boundary being tested at the LLM↔Server interface?

Real LLM tests prove the **contract between model output and server consumption** works. Mocks assume the shape is correct; real calls prove it.

- ✅ MCP/Browser: Prompt asks Gemini to hallucinate a state mutation → server blocks it
- ✅ MCP/Browser: LLM generates a rewards_box → server normalizes and persists it
- ❌ Not MCP: Server-side dict normalization logic (use unit test)

### Principle 3: Is there an integration seam that mocks would hide?

Streaming, parsing, Firestore persistence, DOM rendering — bugs live in the glue, not the logic. If proving "data flows correctly through N layers," real E2E adds value.

- ✅ Browser: LLM → streaming parser → state persistence → page load → DOM → no lockout UI
- ✅ MCP: MCP `process_action` → rewards engine → Firestore write → state read-back
- ❌ Not MCP: Pure function with dict in → dict out (use unit test)

### Principle 4: Is it a multi-function or multi-file flow of execution?

If the behavior spans multiple functions, files, or subsystems but does NOT require real LLM judgment (e.g., standard request routing, validation pipelines, state serialization, or game state updates), **Layer 2 (End-to-End)** is the preferred layer. It provides high integration confidence across the callstack while remaining fast and deterministic via Mock LLMs. **Strongly consider Layer 2 first by default unless the logic is truly small and self-contained.**

- ✅ Layer 2 E2E: Routing a user input through the API, checking if the correct agent is selected, and verifying the mock LLM output updates the database correctly.
- ❌ Not Layer 2: Verifying if Gemini actually hallucinates a specific value (use Layer 3/5).

**Mandatory coverage rule**: When a PR creates or updates multiple non-test files under `$PROJECT_ROOT/**`, it must add or update a Layer 2 E2E test unless the PR explicitly justifies why the changed code is unreachable through an end-to-end application path. The E2E must exercise every newly introduced or modified production code path in that PR, including cross-file handoffs, and assertions must fail if any new path is skipped.

### Principle 5: Is the cost proportional to the risk?

A Gemini call costs time and tokens. A unit test costs milliseconds. If the logic is a 5-line dict operation with no ambiguity, the risk of a failure that manifests only under LLM pressure is near zero.

- ✅ Unit: `block_unauthorized_level_mutations()` — deterministic `.pop()` on dict keys
- ✅ Unit: Schema validation, field normalization, boolean flag checks
- ❌ Not unit: Streaming parser correctly handles chunked JSON from Gemini (use MCP)

### Principle 6: Can the test pass vacuously?

If a real-LLM test can pass **without the guard ever firing** (because the LLM didn't cooperate with the diagnostic prompt), it's not actually testing what it claims.

- **Mitigation**: Check server logs for the guard log line (e.g., `UNAUTHORIZED_LEVEL_UP_PENDING_CCS_MUTATION`)
- **Mitigation**: Verify the raw LLM response attempted the mutation before asserting the block
- **Rule**: If you can't verify the guard fired, the test is probabilistic, not deterministic. Document this.

---

## Summary Decision Matrix

| Question | Yes → | No → |
|---|---|---|
| Does LLM judgment affect the outcome? | Layer 3+ (MCP/HTTP/Browser) | Layer 1/2 (Unit/E2E) |
| Testing an LLM↔Server contract? | Layer 3+ | Layer 1/2 |
| Integration seam that mocks hide? | Layer 3+ | Layer 1/2 |
| Risk justifies cost of real LLM call? | Layer 3+ | Layer 1/2 |
| User-visible UI behavior? | Layer 5 (Browser) | Layer 3 or 4 |
| Can it pass vacuously? | Fix the harness first | Proceed |

---

## Evidence Implications by Layer

| Layer | `/es` Evidence Credit | What It Proves | What It Does NOT Prove |
|---|---|---|---|
| **Unit** | ❌ None — supporting only | Logic correctness in isolation | Integration, real LLM shapes, persistence, UI rendering |
| **E2E** | ❌ None — supporting only | High-fidelity callstack integration with mock services | Real LLM shapes, browser behavior |
| **MCP** | ✅ Server + LLM | Real server processes real LLM output correctly | UI rendering, browser behavior |
| **HTTP** | ⚠️ Server only (no LLM unless explicitly called) | HTTP API contract, auth, response shapes | LLM behavior, UI rendering |
| **Browser** | ✅ Full (Server + LLM + UI + Video) | End-to-end user-visible behavior | Nothing — highest confidence |

### Evidence Bundle Requirements

- **MCP tests** using `MCPTestBase` auto-emit: `metadata.json`, `collection_log.jsonl`, `raw_llm_request_responses.jsonl`, `raw_http_request_responses.jsonl`
- **Browser tests** using `BrowserTestBase` auto-emit: all MCP artifacts + screenshots + `.webm` video + VTT subtitles
- **Unit/E2E tests** do not emit `/es` bundles — they are CI gate artifacts only

---

## When Creating a New Test

1. **Identify the claim**: What behavior are you proving?
2. **Apply the 6 principles**: Is LLM judgment involved? Integration seams? Cost justified?
3. **Choose the lowest sufficient layer**: Strongly consider Layer 2 (E2E) by default unless the logic is 100% self-contained (Layer 1). Don't use Browser when MCP suffices.
4. **Verify non-vacuous**: If using Layer 3+, ensure the test can detect when the target path was NOT exercised.
5. **Emit evidence**: Layer 3+ tests must produce `/es`-compliant bundles. Use `MCPTestBase` or `BrowserTestBase`.

### Multi-File `mvp_site` PR Coverage Checklist

For PRs that add or modify more than one non-test file under `$PROJECT_ROOT/**`:

- Add or update at least one Layer 2 E2E test in `$PROJECT_ROOT/tests/test_end2end/`.
- The test must drive the application through the real in-process route/service flow that reaches all changed production files.
- The assertions must prove each changed code path ran and produced the intended observable state, response, or persistence effect.
- Do not count a unit test, import check, or mock-only direct function call as satisfying this requirement.
- If Layer 3+ evidence is also required, keep the Layer 2 E2E as the deterministic CI guard and use Layer 3+ for real service proof.

## References

- `.claude/skills/end2end-testing.md` — Layer 2 E2E patterns: fake implementations, Flask API test base class, multi-phase LLM testing
- `.claude/skills/evidence-standards.md` — evidence class system, minimum viable checklist
- `.claude/skills/pr-blocker-min-repro.md` — 4-layer (now 5-layer) repro protocol
- `.claude/commands/4layer.md` — command to run the repro ladder
- `.claude/commands/tdd.md` — TDD workflow command
- `AGENTS.md` — `testing_mcp` and `testing_ui` execution policy (real mode only)
