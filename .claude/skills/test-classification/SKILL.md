---
name: test-classification
description: Mandatory test tier naming rules (E2E, integration, unit) — file patterns, E2E criteria, evidence claim-class matrix
type: policy
---

# Test Classification — Mandatory Naming and Content Rules

**These rules are enforced. Violations are trust violations.**

## File naming is a cue, not evidence of a test tier

| File pattern | Tier | Requirements |
|---|---|---|
| `*_e2e_*` or `*_e2e.py` or `*e2e*` | Candidate **E2E** | Classify by the executed path and claim criteria below |
| `*_integration_*` | **Integration** | Real I/O, real APIs, but may skip full pipeline |
| `*_test_*` or `test_*` (default) | **Unit** | May use mocks, stubs, fakes |

## E2E test criteria

A test named "E2E" must exercise the complete application path relevant to its
stated claim, reach the claimed terminal outcome, and verify observable results.
The claim and executed path determine the tier; elapsed time does not. Use the
repository's current test-layer owner for runner and service requirements.

For tests that claim external workflow completion, wait for that external work
and verify its final outcome. Use isolated test data when the flow mutates state;
non-mutating checks may use a known resource when that matches the claim.

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
| **`/green`** | Required current-head checks pass through CI or an applicable documented local exception, and the PR is mergeable | Follow the current `/green` owner for backlog and documentation-only exceptions |

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
