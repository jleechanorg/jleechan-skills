---
name: testing-layers
description: Select the lowest test layer that proves the actual claim, and report what the result does not prove.
---

# Testing Layers — When to Use Each Layer and How to Decide

## Purpose

Directory map, layer-selection principles and evidence value of each test layer for Your Project. Use it when creating tests, reviewing coverage, or judging `/es` evidence completeness.

## Discover the repository's test map

Locate the target repository's tests, supported runners, scoped instructions,
and real-service fixtures. The table below names evidence layers, not assumed
directories, cloud services, environment flags, or authorization.

| Layer | Evidence class |
|---|---|
| **1. Unit** | Deterministic logic in isolation |
| **2. Composed integration** | Calls across components; any faked boundaries remain unproven |
| **3. Application or tool API** | Real server, provider, auth and persistence only where actually exercised |
| **4. HTTP API** | Protocol and server behavior over real HTTP; distinguish fake and real services |
| **5. Browser or native UI** | Rendered behavior on the tested client and revision |

Use the real model and real services when the claim requires them. Follow the
repository's documented accounts, flags, service restrictions and proof
requirements. Do not substitute mocks or auth bypasses for live acceptance.

## Claim boundary

Follow `pr-lifecycle` § Change-impact review and test depth and
`evidence-standards` § Unit proof and claim boundaries: unit proof can establish
self-contained deterministic behavior, not model compliance, auth, persistence
races or browser behavior. `/es` classification is independent of whether a real
LLM or browser run is necessary. Non-production labels, one file or a small line
count never replace inspecting the actual claim and risk, and local
real-service-only rules stay mandatory.

## Decision Principles — Which Layer to Test At

### Principle 1: Does the LLM's judgment affect the outcome?

If the behavior under test is **deterministic server code** that runs the same way whatever the LLM said, a **unit test** is the correct tier: the LLM is only a trigger, simulated with a dict. Move to a higher layer only when the claim crosses a service or integration boundary the unit test cannot exercise.

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

Spanning multiple functions or files is not by itself a reason for E2E: choose an integration layer only when the path between components is material to the claim. A deterministic composed test may use mocks where the active policy allows them; keep a unit test when it suffices.

- ✅ Layer 2 E2E: Routing a user input through the API, checking if the correct agent is selected, and verifying the mock LLM output updates the database correctly.
- ❌ Not Layer 2: Verifying if Gemini actually hallucinates a specific value (use Layer 3/5).

Select tests from the changed claims and affected boundaries, never a
production-file-count threshold. Exercise the changed path at the lowest
sufficient layer, add an integration test when a unit test would miss a material
seam, and state a concrete reason when no application-level path can exercise a
claim.

### Principle 5: Is the cost proportional to the risk?

A Gemini call costs time and tokens; a unit test costs milliseconds. For a 5-line unambiguous dict operation, the risk of a failure that appears only under LLM pressure is near zero.

- ✅ Unit: `block_unauthorized_level_mutations()` — deterministic `.pop()` on dict keys
- ✅ Unit: Schema validation, field normalization, boolean flag checks
- ❌ Not unit: Streaming parser correctly handles chunked JSON from Gemini (use MCP)

### Principle 6: Can the test pass vacuously?

A real-LLM test that can pass **without the guard ever firing** (because the LLM ignored the diagnostic prompt) does not test what it claims.

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
5. **Emit evidence**: Layer 3+ tests must produce `/es`-compliant bundles. Use the repository’s documented fixture and capture helpers.

## References

Resolve the current `/end2end-testing`, `/4layer`, `/tdd`, evidence-standards,
and PR-lifecycle owners through the active command/skill catalog. Resolve the
project root and read its root and scoped instructions for execution policy.
