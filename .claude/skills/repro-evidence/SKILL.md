---
name: repro-evidence
description: Generic, domain-agnostic /repro workflow for isolated state reproduction, twin clones, evidence exports, same-symptom verdicts, and red/green provenance.
---

# Repro evidence (canonical)

This `.claude` skill is the canonical source of truth for reproduction workflows across projects in this repository. It defines the discipline for reproducing bugs against isolated, real environments with verifiable evidence before attempting any fix.

## 0. Routing & When to Use

| User intent | Run |
|-------------|-----|
| `/repro`, `/repro <target_id_or_payload>`, or "reproduce this bug" | Default isolate + targeted repro in section 2 |
| "first copy/snapshot read-only, second gets actions" | Twin baseline + test subject in section 5 |
| Canonical vs variant replay / comparative testing | Isolated clone comparison under identical inputs across configurations |
| Complex multi-step regression suite | Targeted regression suite only when explicitly requested |

Do not silently substitute a broader, mocked, or easier harness for the requested repro.

## 1. Required environment

Always use real, unmocked instances of the target system for evidence-bearing repros (real database, real backend/services, real auth flows) — never a mocked or stubbed environment.

Key environment principles:
- **Real persistence & runtime**: Connect to a real local or sandbox instance (e.g., local database container, sandbox tenant, local daemon) rather than in-memory mocks.
- **Dedicated test target/tenant**: Run reproductions against dedicated test entities, test databases, or ephemeral test namespaces so production or baseline data is never altered.
- **Explicit credentials & configs**: Ensure all required environment variables and credentials point directly to the isolated reproduction environment before executing commands.

## 2. Default: isolate state + targeted bug repro

Goal: Create a safe, isolated copy or snapshot of the reported state in a test environment, then reproduce the reported bug via the narrowest faithful path.

1. **Identify & locate source state**: Identify the source entity, snapshot, fixture, record ID, or environment state where the bug occurred.
2. **Isolate/clone to test environment**: Clone or snapshot the state into a safe, mutable sandbox target (e.g., a database snapshot, container image, test account/tenant, fixture file, or branch worktree depending on the target stack).
3. **Twin baseline for destructive replays**: For destructive or state-altering replays, create two copies: a `baseline read-only` copy and a `test subject` copy (see §5).
4. **Align state**: Align the test subject to the exact instant/state where the reported bug occurred without mutating the baseline.
5. **Replay triggering action**: Replay only the exact user action, API request, CLI command, or input sequence needed to trigger the reported bug against the unmocked target.
6. **Export post-replay state**: Dump or export the post-replay state from the target system to disk.
7. **Save evidence**: Save raw request/response captures, error logs, stdout/stderr streams, and pre/post state snapshots when the repro touches runtime or persisted service state.

### 2.1 First-touch state proof for stale persisted-state bugs

When the bug involves stale persisted state, orphaned sessions/records, legacy flags, schema migrations, cleanup hooks, or routing/state loops:

1. **Capture pre-state directly**: Capture the isolated test subject's pre-state via the most direct, low-level read path available (e.g., direct DB query, raw storage inspection, direct file read) BEFORE making any application-level API call that could clean, migrate, normalize, or project state.
2. **Avoid pre-action observers**: Do not call administrative fetch endpoints, state-summarizing APIs, UI initialization routes, or preview endpoints before the evidence-bearing action unless the claim explicitly includes those first-touch paths.
3. **Execute production ingress as first touch**: Run the exact production ingress being validated (e.g., primary streaming endpoint, user action handler, webhook handler) as the first application touch.
4. **Capture post-state directly**: Capture the post-state with another direct, low-level read.
5. **Record routing/transition evidence**: Record selected handler, routing branch, or transition evidence when the claim asserts state transitions or recovery from stuck states.

> [!WARNING]
> If a pre-action observer can itself mutate, sanitize, or seal the state, the evidence only proves that cleanup logic exists somewhere; it does NOT prove that the reported production path is fixed.

## 3. Red/green code provenance requirement

A RED repro must never run against the candidate fix codepath. Before labeling any run RED or GREEN, explicitly record the code and environment provenance:

- **RED replay**: Must run against a pre-fix checkout, pre-fix deployment, or an explicitly human-approved baseline/main environment without the fix applied.
- **GREEN replay**: Must run against the candidate fix checkout or deployment.
- **Ambiguous environment**: An unknown or unproven remote deployment version is NOT valid RED evidence. Label it `AMBIGUOUS ENVIRONMENT` until the deployed commit SHA and configuration are proven or explicitly approved by a human.
- **Historical red artifact**: If only the original production/reported artifact shows the failure and no fresh replay was executed, label it `HISTORICAL RED ARTIFACT`, not a fresh red replay.

Never compare a fixed-branch replay against another fixed-branch replay and call the first run RED.

## 4. Same-symptom requirement (fail closed)

A reproduction only counts if the IDENTICAL user-visible phenotype reappears, not a loosely-related internal signal. Before running a repro, write down the exact observable bug phenotype in concrete terms:

- **Source entity / environment & identifier**: The exact record, account, endpoint, or system context.
- **Exact input / action sequence**: The precise payload, command, or user event being replayed.
- **Exact user-visible symptom required**: The specific error message, UI anomaly, incorrect output, corrupted field, or failed response that constitutes the bug.
- **Prior artifact(s) to reproduce**: Prior logs, response bodies, or state dumps that must be repeated, omitted, or contradicted.
- **Falsification criteria**: Evidence that would disprove the repro claim.

Do not call a related internal signal a reproduction unless the same observable symptom appears in the new run.

### Illustrative Examples:

- **Stale cached value re-served after invalidation**:
  - *Reported bug*: User updates profile name to "Alice", but subsequent `GET /user/profile` continues returning old name "Bob" with cache header `X-Cache: HIT`.
  - *Valid REPRO*: Fresh replay in isolated environment updates profile, executes `GET /user/profile`, and receives "Bob" with `X-Cache: HIT`.
  - *RELATED*: An internal cache key was not purged in Redis, but the API endpoint returned the updated name "Alice" (e.g. bypassed cache or fetched from DB). Label `RELATED INTERNAL CACHE DESYNC`, not `ORIGINAL BUG REPRO`.
  - *NON-REPRO*: API returns "Alice" with `X-Cache: MISS`. Label `NON-REPRO FOR ORIGINAL PHENOTYPE`.
- **Orphaned session token causing 500 on checkout**:
  - *Reported bug*: Expired session token triggers unhandled null pointer exception and HTTP 500 error on `POST /checkout`.
  - *Valid REPRO*: Replay against cloned session state reproduces the exact unhandled exception stack trace and HTTP 500 response.
  - *RELATED*: Replay returns HTTP 400 with `Invalid session payload`. Label `RELATED VALIDATION ERROR`, not `ORIGINAL BUG REPRO`.
- **Batch job silent record drop**:
  - *Reported bug*: Records with null timestamp are silently omitted from export CSV without error log.
  - *Valid REPRO*: Cloned dataset containing null timestamp records yields export CSV missing those exact rows with zero error logs.
  - *RELATED*: Batch job fails with explicit `NullPointerException` log. Label `RELATED LOGIC ERROR`, not `ORIGINAL BUG REPRO`.

### Mandatory Verdict Table

For every claimed reproduction, construct a verdict table:

| Original required symptom | New observation | Evidence file / reference | Verdict |
|---------------------------|-----------------|---------------------------|---------|
| `<Exact user-visible failure>` | `<Exact observation from fresh run>` | `<path/to/evidence/file>` | `REPRO` / `RELATED` / `NON-REPRO` |

**Only `REPRO` satisfies the repro task.** `RELATED` and `NON-REPRO` provide valuable diagnostics, but they do not complete the repro task and must never be described as "the original bug reproduced."

## 5. Twin baseline + test subject

When the initial state must remain pristine for comparative verification or multiple replay attempts:

1. **Create two independent copies**: Snapshot/clone the source state into two separate entities or sandbox targets.
2. **Assign roles**: Designate one as `baseline read-only` and the other as `test subject`.
3. **Protect the baseline**: Never apply actions, test mutations, manual patches, or destructive commands to the `baseline read-only` instance.
4. **Mutate only test subject**: Perform alignment, intermediate state adjustments, cleanup, and replay exclusively on the `test subject`.
5. **Export comparison**: Export both snapshots only when a direct before/after diff is required; otherwise export the `test subject` along with raw execution evidence.

## 6. Save evidence after repro

Export the post-replay state and execution artifacts to a discoverable local directory using a standardized path convention:

```bash
# Recommended evidence directory convention:
# /tmp/<project-name>/repro-exports/<slug-or-timestamp>/

mkdir -p /tmp/<project>/repro-exports/<slug>

# Example export commands depending on the stack:
# 1. Database dump / query output:
# pg_dump -d <test_db> -t <table_name> > /tmp/<project>/repro-exports/<slug>/post_state.sql
# 2. Raw API / HTTP responses:
# curl -s -D /tmp/<project>/repro-exports/<slug>/headers.txt -o /tmp/<project>/repro-exports/<slug>/response.json ...
# 3. Log captures:
# cp /path/to/test-service.log /tmp/<project>/repro-exports/<slug>/execution.log
```

Ensure all relevant evidence files (raw request/response payloads, logs, state diffs, error traces) are saved and referenced in the final verdict table.

## 7. Checklist

| Step | Done? |
|------|-------|
| Source entity/state identified and isolated to a test sandbox | |
| Red/green code and environment provenance recorded | |
| Same-symptom criteria written before replay | |
| Baseline/test clone separation preserved (if destructive replay) | |
| Exact input/action sequence replayed against unmocked system | |
| First-touch direct pre-state captured (for stale persisted-state bugs) | |
| Production ingress under test was the first application touch | |
| Post-replay state export saved to evidence directory | |
| Raw payload captures, logs, and state snapshots saved | |
| Verdict table filled with `REPRO`, `RELATED`, or `NON-REPRO` | |
