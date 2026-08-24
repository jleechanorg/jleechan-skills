---
name: test-classification
description: Mandatory test tier naming rules (E2E, integration, unit) — file patterns, E2E criteria, evidence claim-class matrix
type: policy
---

# Test Classification — Mandatory Naming and Content Rules

**These rules are enforced. Violations are trust violations.**

## File naming determines test tier

| File pattern | Tier | Requirements |
|---|---|---|
| `*_e2e_*` or `*_e2e.py` or `*e2e*` | **E2E** | Must meet ALL criteria below |
| `*_integration_*` | **Integration** | Real I/O, real APIs, but may skip full pipeline |
| `*_test_*` or `test_*` (default) | **Unit** | May use mocks, stubs, fakes |

## E2E test mandatory criteria

A test file named with "e2e" MUST satisfy ALL of these. If ANY is false, rename to `*_integration_*` or `*_smoke_*`:

1. **Spawns real external work** — e.g., `ao spawn` a session that actually runs, `gh pr create`, etc.
2. **Waits for that work to complete** — not spawned and immediately killed. The external process must do real work.
3. **Verifies an outcome that only exists if the full pipeline ran** — e.g., a PR was created, CI passed, a merge happened.
4. **Creates its own test data** — does not rely on pre-existing PRs, sessions, or resources.
5. **Takes >60 seconds** — if it completes in under a minute, it's not E2E.

## What is NOT an E2E test

- Importing a module and checking it's callable → **unit test**
- Writing to a temp file and reading it back → **unit test**
- Calling a real API to check status of a pre-existing resource → **integration test**
- Spawning a session and immediately killing it → **smoke test**
- Constructing an event in code and routing it through a function → **integration test**

## Before committing any test with "e2e" in the name

Ask: "If I showed this to the user and said 'the E2E test passes', would they agree this proves the system works end-to-end?" If there's any doubt, use a more honest name.

## Evidence claim-class matrix — fail-closed verdicts

When reviewing or producing evidence, identify the **claim class** before issuing a verdict. Verdict is **INSUFFICIENT** (not PASS) if required proofs for the claimed class are missing.

| Claim class | Required proofs | Example |
|---|---|---|
| **Unit test coverage** | Test file path, pass/fail counts, coverage % | "27 unit tests pass" |
| **Integration test** | Test log with real I/O, API calls shown, timing | "Real GitHub API call to PR #300" |
| **Pipeline E2E** | Session spawn proof, event routing proof, outcome recording proof | "AO session jc-421 routed RetryAction" |
| **PR-lifecycle E2E** | PR creation (URL+timestamp+actor), transition proof (CI/review timeline), merge outcome, cleanup proof | "PR created → CI green → CR approved → merged → branch deleted" |
| **`/green`** | Current-head CI passes and PR is mergeable | "CI SUCCESS at HEAD; mergeable=MERGEABLE" |

### Fail-closed verdict rules

1. **State the claim class explicitly** before any verdict — e.g., "Claim: pipeline E2E"
2. **PASS** only if ALL required proofs for the stated class are present and verified
3. **INSUFFICIENT** if any required proof is missing — never downgrade the claim class to avoid this
4. **FAIL** if proofs contradict the claim
5. A pipeline E2E verdict does NOT satisfy a PR-lifecycle E2E claim. Do not conflate them.

### PR-lifecycle E2E minimum evidence set

- PR creation proof: full URL, timestamp, creating actor
- Transition proof: CI check timeline, review state changes, comment resolution
- Mergeability/merge outcome: final mergeable state or merge commit SHA
- Cleanup proof: branch deletion, session kill, worktree removal
