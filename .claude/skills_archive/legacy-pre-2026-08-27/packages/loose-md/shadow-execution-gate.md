---
description: Run a Shadow Execution Gate for high-risk changes using isolated replay, objective evidence, and promotion criteria
type: process
scope: project
---

# Shadow Execution Gate

## Purpose
Use a reproducible shadow run before promotion when changes are risky, cross-cutting, or expensive to debug post-merge.

This is a general software technique, not PairV2-specific.

## When to use it
- Runtime/orchestration changes.
- CI workflow or environment changes.
- Refactors touching multiple subsystems.
- Any change where a rollback would be costly.
- Any PR with unclear integration risk.

## Trigger policy (default)
Run Shadow Execution when any condition is true:
1. A critical path file is changed.
2. Changed files >= 8.
3. Core diff size >= 150 lines.
4. Prior incident/flakiness exists in touched area.

## Core workflow
1. Build candidate from current branch.
2. Re-apply/replay in isolated workspace (`/tmp/.../shadow/...`).
3. Execute representative tasks/tests (small + large scenario where relevant).
4. Collect evidence bundle.
5. Compare against gate criteria.
6. Produce explicit decision: `READY_FOR_PROMOTION` or `NOT_READY`.

## Evidence bundle (minimum)
- Exact commit SHA and branch.
- Commands executed.
- Pass/fail summary.
- Runtime/latency and retry metrics where applicable.
- Artifact completeness/missing artifacts.
- Key logs for failed steps.
- Decision rationale tied to acceptance criteria.

## Decision rules
- Promote only if all required criteria pass and no critical regressions are observed.
- If any required criterion fails, block promotion and record targeted follow-up work.

## Reporting template
- Scope tested:
- Scenarios executed:
- Evidence summary:
- Regressions found:
- Decision:
- Required follow-up:

## Anti-patterns
- Treating a single local test run as equivalent to shadow validation.
- Skipping artifact/log capture.
- Declaring success without explicit go/no-go criteria.
- Relying on implicit confidence instead of measured evidence.
