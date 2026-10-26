---
name: testing-layers
description: Select the correct WorldArchitect.AI testing layer and understand its evidence value.
---

# Testing Layers — When to Use Each Layer and How to Decide

## Purpose

This skill defines the **concrete test directory structure** for Your Project, the **decision principles** for choosing the right testing layer, and the **evidence implications** of each layer. Use this when creating new tests, reviewing test coverage, or evaluating `/es` evidence completeness.

## Directory Map

| Layer | Directory | Runner | Evidence class |
|---|---|---|---|
| **1. Unit** | `$PROJECT_ROOT/tests/` | Use the repository's targeted test runner | Deterministic claims only; no live-service credit |
| **1b. Unit (top-level)** | `tests/` | Use the repository's targeted test runner | Deterministic claims only; no live-service credit |
| **2. End-to-End** | `$PROJECT_ROOT/tests/test_end2end/` | Use the repository's targeted test runner and E2E owner | Deterministic composed claims; no live-service credit |
| **3. MCP API** | `testing_mcp/` | Follow `$PROJECT_ROOT/testing_mcp/AGENTS.md` | Real server/provider/auth evidence only for claims exercised |
| **4. HTTP API** | `testing_http/` | Follow current project test instructions | Evidence for the exercised HTTP/server claim |
| **5. Browser** | `testing_ui/` | Follow `$PROJECT_ROOT/testing_ui/CLAUDE.md` | Real authenticated browser evidence for the exercised UI claim |

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

- **Layers 1-2 and offline HTTP tests** may use deterministic mocks when the test lives outside `testing_mcp/` and `testing_ui/` and its claim is offline. These tests support only their stated deterministic claim.
- **Layers 3 and 5** must use real server, Firestore, Firebase Auth, and live provider responses as required by their scoped owners. Resolve the project root; follow `testing_mcp/AGENTS.md` and `testing_ui/CLAUDE.md`, including explicit `TESTING_AUTH_BYPASS=false ALLOW_TEST_AUTH_BYPASS=false` for acceptance. Any offline mocks, bypass, or synthetic results in those directories invalidate acceptance evidence.
- Use `/llm-testing` only when the claim requires real model-behavior evidence; deterministic claims use the lowest sufficient layer under the claim boundary below.

---

## Claim boundary

Follow `pr-lifecycle` § Change-impact review and test depth and
`evidence-standards` § Unit proof and claim boundaries. Unit proof can establish
self-contained deterministic behavior, but not model compliance, auth,
persistence races, or browser behavior. `/es` classification is independent of
whether a real LLM or browser run is necessary. Non-production labels, one file,
or a small line count cannot replace inspecting the actual claim and risk.
The real-service-only directory rules above remain mandatory.

## Decision Principles — Which Layer to Test At

### Principle 1: Does the LLM's judgment affect the outcome?

If the behavior under test is **deterministic server code** that runs the same way regardless of what the LLM said, a **unit test** is the correct tier. The LLM is just a trigger — you can simulate it with a dict.

Use a unit test when an isolated deterministic test proves the claim. Use a higher layer when the claim crosses a service or integration boundary that the unit test cannot exercise. Do not require E2E work solely because a change spans multiple functions or files.

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

If the claim spans multiple functions or files, choose an integration layer only when that boundary is material to the claim. A deterministic composed test outside `testing_mcp/` and `testing_ui/` may use mocks; retain a unit test when it is sufficient for the actual behavior.

- ✅ Layer 2 E2E: Routing a user input through the API, checking if the correct agent is selected, and verifying the mock LLM output updates the database correctly.
- ❌ Not Layer 2: Verifying if Gemini actually hallucinates a specific value (use Layer 3/5).

Select tests from the changed claims and affected boundaries, not a file-count
threshold. Exercise the changed path at the lowest sufficient layer and add an
integration test when a unit test would miss a material seam. State a concrete
reason when no application-level path can exercise a claim.

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
| **Unit** | Bounded deterministic claims only | Logic correctness in isolation | Integration, real LLM shapes, persistence, UI rendering |
| **E2E** | Deterministic composed claims only | High-fidelity callstack integration with mock services | Real LLM shapes, browser behavior |
| **MCP** | ✅ Server + LLM | Real server processes real LLM output correctly | UI rendering, browser behavior |
| **HTTP** | ⚠️ Server only (no LLM unless explicitly called) | HTTP API contract, auth, response shapes | LLM behavior, UI rendering |
| **Browser** | Real browser proof for the exercised claim | Observed end-to-end UI behavior | Unexercised flows or services |

### Claim-scoped Evidence Artifacts

- MCP and browser acceptance runs use the artifacts required by their scoped owners for the claim. Do not assume every run must include provider traces for paths it did not exercise.
- Browser-visible behavior retains the repository's explicit video and visual-review requirements.
- Unit/E2E tests record commands, results, tested SHA, and claim limits; they may satisfy bounded deterministic claims, never live-service proof.

---

## When Creating a New Test

1. **Identify the claim**: What behavior are you proving?
2. **Apply the 6 principles**: Is LLM judgment involved? Integration seams? Cost justified?
3. **Choose the lowest sufficient layer** for the claim. Don't use Browser when MCP suffices, and don't use MCP when an offline deterministic test proves the bounded claim.
4. **Verify non-vacuous**: If using Layer 3+, ensure the test can detect when the target path was NOT exercised.
5. **Emit evidence**: Layer 3+ tests must produce `/es`-compliant bundles. Use `MCPTestBase` or `BrowserTestBase`.

### Multi-file changes

For a multi-file change, inspect the changed claims and material boundaries. A
deterministic unit test may prove an isolated behavior; use a composed or real
integration test when the claim depends on the path between components. Do not
require a blanket E2E tier solely from the number of production files changed.

## References

Resolve the current `/end2end-testing`, `/4layer`, `/tdd`, evidence-standards,
and PR-lifecycle owners through the active command/skill catalog. Resolve the
project root and read its `AGENTS.md` plus any scoped `testing_mcp/AGENTS.md` or
`testing_ui/CLAUDE.md` for directory-specific execution policy.
