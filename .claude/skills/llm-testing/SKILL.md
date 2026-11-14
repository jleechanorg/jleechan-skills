---
name: llm-testing
description: Prove model-dependent behavior with a real server, real services, and the provider/runner required by the repository's testing owner.
---

# /llm-testing — Real-LLM Zero-Mock Testing Guide

**Purpose**: The authoritative layer for proving behavior that depends on the **LLM's
judgment**. Where `/end2end-testing` (Layer 2) deliberately *fakes* external APIs for speed and
determinism, `/llm-testing` (Layers 3–5) does the opposite: **real LLM, real services, zero
mocks**, on a real server (local or remote preview). Use it when the active repository requires real-model evidence for the changed
behavior; do not extend one project's changed-path requirements to every repository.

## Core principle — ZERO MOCKS

A `/llm-testing` run is invalid if it uses a fake model or substitutes mocked
services for any real boundary the evidence claims to exercise. Inspect the
actual server process using the target repository's documented flags.

The production path uses a real LLM → the test must use a real LLM. Faking the model means the
test cannot prove model-owned behavior (routing, level-up commit, reconciliation, narrative,
streaming). **No exceptions.** If you only need to prove deterministic helper logic with faked
externals, that is `/end2end-testing` (Layer 2), not `/llm-testing`.

## Locate the real-service runner

Read the active repository's testing policy for its API or browser driver,
launch target, provider, credentials, test account and evidence. Use the
documented runner rather than assuming directory names, interpreter, cloud
services or transport. Do not import another project's auth bypasses or
provider opt-outs. If the required real runner is unavailable, mark that proof
missing; do not silently substitute a mock.

For an AGY-backed repository, its installer owns the sanitized runtime location,
credential copying, and generated environment file. A missing runtime requires
setup and diagnosis; it does not authorize switching to the Gemini SDK. Preserve
the selected provider's permission profile and the repository's test-account rules.

Before an authorized paid request, preflight the actual launched server process,
not just its parent shell or health endpoint: verify the effective credential
selection after wrapper/venv activation, the required authenticated test
identity, selected provider and required credential availability. Check each
required operation’s permission nonbillably; a successful read does not prove
write access. If a safe authorized check is unavailable, report it unverified.
Never print secret values. If activation replaced a required path, correct the
task-scoped launch
without changing persistent defaults or other services, then recheck. Health or
a terminal frame alone is not evidence of a successful provider turn or event.
Inspect the runner and server for retries; keep them within the user-approved
attempt scope. If a prerequisite fails, diagnose it before any billable call.

Exercise the production streaming transport when the claim involves it or the
repository's testing owner requires it. Distinguish
transport/SSE delivery from provider-native token streaming: evidence for one does
not prove the other. If the selected provider cannot establish the claim, identify
that limitation and use only a testing method authorized by the governing owner.

## When to use /llm-testing (vs lower layers)

Use it whenever **the LLM's judgment affects the outcome** or you cross the **LLM↔server
boundary**:

- agent routing / intent classification, level-up / rewards / XP, game-state persistence,
  character creation finalize, conclude/finalize prompts, streaming delivery, any prompt change.

Model-compliance claims require the real model and relevant service boundary.
Unit and mocked tests support deterministic claims but cannot establish real-model
behavior. The repository decides which changed paths require each evidence layer.

## Invocation

For `/llm-testing <feature-or-blocker>`, locate the matching driver and read its
scoped owner before running. Use its supported interpreter, arguments, account,
provider, and environment. A repository that specifies direct `python3` with
explicit `PYTHONPATH` must not receive a copied `vpython` or pytest invocation.
Print the full absolute evidence path and record the actual command and target.

## Evidence (ties to /es)

- Evidence bundle: Use the location required by the repository's testing owner.
  Print the **full absolute path**.
- Include streaming artifacts when the claim involves streaming or the repository's
  testing owner requires them. Use that owner's capture format, including request
  and completion captures where required. A non-streaming claim does not require
  unrelated streaming artifacts.
- UI/interactive behavior also requires a **captioned video** (`.mp4`/`.gif`/`.cast`) tied to the
  PR HEAD SHA.
- Provenance: input captured from the real client, never reconstructed from backend reference
  files (no circular provenance). See `.claude/skills/bypass-claims/SKILL.md`.
- Apply evidence-standards' staleness-tolerance diff test and final evidence
  sequencing. Re-run affected evidence for a material behavior change; re-affirm
  qualifying nonbehavioral changes while preserving the original tested SHA,
  timestamps, artifact hashes, and explicit diff assessment. Never relabel an old
  capture as a new run.

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
- Non-streaming evidence offered for a streaming claim or where the repository's
  testing owner requires the production streaming path.
