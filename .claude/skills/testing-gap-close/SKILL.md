---
name: testing-gap-close
description: Mandatory architectural and testing processes to get testing_mcp and testing_ui tests through the /es and /er evidence gates
---

# Testing Gap Close Strategy

This skill codifies the mandatory architectural and testing processes required to get `testing_mcp` and `testing_ui` tests to pass `/es` (Evidence Standards) and `/er` (Evidence Review) verification gates.

## Select evidence for the claim

There is no universal evidence triad for every PR. Resolve the current project root
and read its `AGENTS.md`, the scoped `testing_mcp/AGENTS.md` or `testing_ui/CLAUDE.md`
when those paths are involved, and the current evidence-standards owner. Select the
lowest sufficient evidence class for each actual claim. Capture request, provider,
server, persistence, and UI artifacts only when that claim requires them; do not
invent missing provider traffic or require unrelated evidence classes.

## Mandatory Execution Protocols

When investigating or resolving gaps in `/es` bundle generation, follow these non-negotiable protocols:

### 1. Hardening the Server Boot Lifecycle
Use the server target required by the claim and the scoped test owner. A local
behavior claim uses the authorized local server route; use gunicorn only when the
claim depends on its worker or deployment behavior.
- **Mock Fallback Banned**: Never rely on `TEST_MODE=mock` for production `/es` verification.
- **Environment Parity**: Set only the environment required by the claim. Tests under `testing_mcp/` and `testing_ui/` must authenticate with real Firebase Auth and dedicated test accounts; explicitly set `TESTING_AUTH_BYPASS=false ALLOW_TEST_AUTH_BYPASS=false`. Their scoped owners prohibit bypass, mocks, and synthetic results. Offline mocks remain valid for deterministic tests outside those directories and never count as live-service proof.
- **Worker Stability**: Use the scoped test-owned server lifecycle and teardown. Stop only the exact process started by the test after verifying its PID/ownership; never use broad `pkill` patterns or force-kill unrelated workers.

### 2. Validate evidence required by the claim
- Resolve the current project root and follow the scoped test owner for its harness and capture contract. Require complete streaming traces only when the claim exercises streaming and its evidence class requires them.
- When the claim includes a streamed interaction, verify the run reaches the completion event required by that harness; do not require unrelated trace files for claims that do not exercise those paths.

### 3. Evidence packaging and checksums
- Use the helper and metadata required by the scoped test owner for the selected evidence class; keep scratch output in a unique `/tmp/<repo>/...` run directory.
- Verify the checksum mode required by the current `/es` or `/er` contract for that claim. Do not assert a universal bundle schema beyond that contract.

### 4. Bundle Archival and Git Registration
- Keep bulky and ephemeral evidence under a unique `/tmp/<repo>/...` run directory. When an evidence artifact must outlive the session or a gate requires publication, use an authorized hosted evidence route and link its receipt with the tested SHA in the PR description. Never copy evidence bundles into the repository tree.
