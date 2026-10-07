---
name: dot-portfolio-coordinator
description: Coordinate existing dot work and track all portfolio items across GitHub roadmap and Beads. Reconciles cross-project goals, preserves authorization continuity, publishes sanitized draft PR dashboards, and dispatches scoped material events through a receipt-safe sender.
---

# Dot Portfolio Coordinator

The Dot Portfolio Coordinator is an authorized, separate coordination system that tracks declared portfolio items across GitHub repositories and Beads stores, maintains roadmap-owned goals, and coordinates safe communication with the ChatGPT "dot" assistant.

## Architectural Boundaries & Core Invariants

1. **Strict Registry & Host Binding**:
   - Sources are explicitly declared in `references/sources.json`.
   - Identified by composite key `(github_host, owner/repository, source_namespace, bead_id)`.
   - Unregistered repositories discovered during organization scans are flagged as coverage gaps; access is never silently expanded.
2. **Deterministic Collection & Stale Resilience**:
   - Beads stores collected via native `br list --status all --json --limit 0`.
   - GitHub inventories collected with full pagination (including draft PRs, head SHAs, and check statuses).
   - Version-bound cursors committed only upon complete final-page collection.
   - 304 Not Modified reuses recorded snapshots.
   - Partial or failed collections preserve last-known items as stale/partial rather than erasing unseen work.
3. **Model Admission & Sandboxed Reasoning**:
   - Inference requires verified sandbox isolation, endpoint allowlists, read-only isolated snapshots, and absence of host mounts or write credentials.
   - If isolation guarantees cannot be proven, the admission gate MUST return `capability_blocked`.
   - Never run unisolated full-permissions models and pretend output validation establishes isolation.
4. **Deterministic Structural Proposal Validation**:
   - Validates that every proposed item references a genuine snapshot task key with matching citations and source versions.
   - Rejects invented entities, endpoints, or injected shell commands.
   - Generates deterministic, stable action IDs (`act_<hash>`) for restart idempotence.
5. **Real Beads Control Journal & CAS Protocol**:
   - Designated host sole-writer lock (`fcntl.flock`).
   - Domain repository task stores are strictly read-only; mutations are permitted ONLY on roadmap control records (`coordinator-control`).
   - Optimistic concurrency control via `--if-unchanged <updated_at>` and `--append-notes`.
   - Compares observed full-record digest immediately before write and rereads post-write state.
6. **Original Authority & Cumulative Budget Ledger**:
   - Binds authenticated human principals to original GitHub comments via immutable comment IDs, versions, and content digests.
   - Unsupported channels (Slack, native conversation) return `capability_blocked`.
   - No keyword consent classifiers: words like "I approve" or "routine" do not bypass principal binding.
   - Cumulative budget ledger tracks allocations, idempotently handles repeat reservations, settles verified spend, and blocks overruns.
7. **Audience-Filtered Roadmap Publication**:
   - Renders only two allowlisted derived projections: `coordinator/WORK.md` and `coordinator/COVERAGE.json`.
   - Native `.beads/issues.jsonl`, raw control notes, and private principal IDs are excluded.
   - Publishes via an isolated checkout on dedicated branch `coordinator/portfolio-snapshot` and owned draft PRs.
   - Fast-forward pushes only (never force-pushes, never pushes directly to main).
   - Remote readback verifies file contents at the pushed SHA.
   - Closed-unmerged PRs trigger a publication hold until owner resolution.
8. **Receipt-Safe Sender Subcomponent**:
   - Reuses relative sibling dot transport (`../../dot/scripts/dot.sh`).
   - Quiet exit 0 on empty input.
   - Persists pending immutable authorization binding and uncertainty hold before transport invocation.
   - Requires standalone `DOT_SENT_VERIFIED` and exit 0 for verified delivery.
   - Uncertainty holds block subsequent sends until deliberate owner reconciliation (`--reconcile-receipt`).
   - Emits exactly one machine-readable `COORDINATOR_RESULT` JSON line.

## CLI Usage

The controller CLI is located at `scripts/coordinator-portfolio.py`:

```bash
# Reserve budget for an execution attempt
python3 scripts/coordinator-portfolio.py reserve --request '{"task_key": {...}, "grant_version": "v1", "action_id": "act-1", "attempt_id": "att-1", "currency": "USD", "max_cost": 0.10}'

# Settle actual verified spend
python3 scripts/coordinator-portfolio.py settle --request '{"reservation_id": "res_act-1_att-1", "actual_cost": 0.08, "evidence_reference": "https://...", "evidence_digest": "..."}'

# Check reservation status
python3 scripts/coordinator-portfolio.py status --reservation-id res_act-1_att-1

# Resolve notification authorization reference
python3 scripts/coordinator-portfolio.py resolve-notification --ref bd-ctrl-1/act-1/att-1

# Run finite observation loop (12-hour default)
python3 scripts/coordinator-portfolio.py observe --duration 43200 --interval 300 --run-dir /tmp/dot-portfolio-observe
```

The sender subcomponent is located at `scripts/dot-portfolio-coordinator-sender.sh`:

```bash
# Read-only status query
./scripts/dot-portfolio-coordinator-sender.sh --status --json --account default

# Deliver material event with explicit authorization reference
COORDINATOR_CHANGE_ID="ev-001" COORDINATOR_CHANGE_SUMMARY="Update" ./scripts/dot-portfolio-coordinator-sender.sh --authorization-ref bd-ctrl-1/act-1/att-1 --account default
```
