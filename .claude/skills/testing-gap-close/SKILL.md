---
name: testing-gap-close
description: Mandatory architectural and testing processes to get testing_mcp and testing_ui tests through the /es and /er evidence gates
---

# Testing Gap Close Strategy

This skill codifies the mandatory architectural and testing processes required to get `testing_mcp` and `testing_ui` tests to pass `/es` (Evidence Standards) and `/er` (Evidence Review) verification gates.

## The Evidence Triad Requirement

Any PR touching `$PROJECT_ROOT/` or its subdirectories must produce an evidence bundle containing the complete "Evidence Triad" to pass Skeptic Gate (`/er`):
1. `http_request_responses.jsonl`
2. `llm_request_responses.jsonl`
3. `gemini_http_request_responses.jsonl`

## Mandatory Execution Protocols

When investigating or resolving gaps in `/es` bundle generation, follow these non-negotiable protocols:

### 1. Hardening the Server Boot Lifecycle
Tests must run against a **real local gunicorn server**.
- **Mock Fallback Banned**: Never rely on `TEST_MODE=mock` for production `/es` verification.
- **Environment Parity**: You must inject `WORLDAI_DEV_MODE=true` to enable comprehensive logging. `TESTING_AUTH_BYPASS=true` is allowed **only for local test runs** — never in CI, production, or deploy-like contexts. Do not treat this bypass as a standard operating mode. Implementers MUST add a CI guard step (e.g., a workflow pre-step that exits 1 when `TESTING_AUTH_BYPASS` is set) to prevent this env var from leaking into any non-local run; CI pipelines should fail loudly if `TESTING_AUTH_BYPASS` is present outside an explicit local-development marker.
- **Worker Stability**: Use scoped shutdown during test teardown to prevent orphaned worker lock-ups. Preferred order: (1) send SIGTERM to the test-managed PID file, (2) kill the specific bound port with `lsof -ti :<port> | xargs kill`, (3) target the test-owned process group with `kill -- -$(ps -o pgid= -p <pid>)`. Only fall back to `pkill -9 -f gunicorn` as a last resort when scoped methods fail, since broad signal matching can kill unrelated gunicorn workloads on shared environments.

### 2. Evidence Signature Validation (`EvidenceSignatureGuard`)
- The server intercept wrappers in `base_test.py` must enforce `REQUIRE_FULL_TRACE_LOGS=True`.
- Ensure that the testing framework actually executes streaming requests all the way to completion. The payload triggers a "done" event which `evidence_utils.py` relies upon to synthesize the traces. If tests exit early, the `EvidenceSignatureGuard` will fail the bundle.

### 3. Automated Synthesis & Checksumming
- You must use the `save_evidence()` helper to automatically aggregate `run.json`, `metadata.json`, and terminal output into versioned `/tmp` iteration directories (e.g., `iteration_003`).
- **Checksum Mode**: Always verify that `checksum_mode: per_file_checksums` is active so `.sha256` checksums are generated. `/er` validation will reject bundles that lack strict cryptographic provenance.

### 4. Bundle Archival and Git Registration
- After the evidence is generated in `/tmp/.../iteration_XXX`, it MUST be copied into the persistent repository path: `docs/evidence/pr-<number>/` (e.g., `docs/evidence/pr-6851/`).
- The PR description must be explicitly updated with the Markdown link to this `docs/evidence/` bundle and the remote HEAD SHA URL.
