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
3. **Model Admission & Schema-Bound Decision**:
   - The selected canonical driver runs full-permission and is schema-bound decision-only; admission is completeness checking, not OS or sandbox isolation.
   - Proposals must adhere strictly to the coordination dialogue packet schema, validating candidate bindings, task keys, and grant bindings without claiming sandbox isolation.
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
   - Two-phase interactive prepare/commit/abort protocol: waits for prepared transport context before final source and grant revalidation immediately prior to commit.
   - Requires standalone `DOT_SENT_VERIFIED` and exit 0 for verified delivery.
   - Uncertainty holds block subsequent sends until deliberate operator ledger recovery; `--reconcile-receipt` is unsupported/unavailable.
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

# Generic observe-only loop (no messages; 12-hour default)
run_dir="$(mktemp -d /tmp/dot-portfolio-observe.XXXXXX)"
python3 scripts/coordinator-portfolio.py observe --duration 43200 --interval 300 --run-dir "$run_dir"
```

Active messaging requires a pinned pilot config, account grants, and an explicitly supplied approved private source registry. The registry must name concrete repositories and provide an exact `host_binding` for every Beads source; the shipped portable `references/sources.json` is a template, not an active registry. Set `run_dir` to the config's `state_dir`, an owner-owned private directory under `/tmp` (mode `0700`). Use a separate directory from an observe-only run; the controller creates it privately if missing.

```bash
# Active current-work check-ins, bounded by the pilot config and grants
run_dir=/tmp/dot-portfolio-pilot
python3 scripts/coordinator-portfolio.py observe --sources /path/to/private-approved-sources.json --interval 300 --send-messages --pilot-config /path/to/pilot.json --run-dir "$run_dir"
```

The sender subcomponent is located at `scripts/dot-portfolio-coordinator-sender.sh`:

```bash
# Read-only status query
./scripts/dot-portfolio-coordinator-sender.sh --status --json --account default

# Deliver material event with validated operator grant file and sha256
# (Note: --authorization-ref is inert/unsupported and not used for grant enforcement; --reconcile-receipt is unavailable)
COORDINATOR_CHANGE_ID="ev-001" COORDINATOR_CHANGE_SUMMARY="Update" ./scripts/dot-portfolio-coordinator-sender.sh --account default --state-dir /path/to/state --grant-file /path/to/grant.json --grant-sha256 <sha256> message.txt
```
