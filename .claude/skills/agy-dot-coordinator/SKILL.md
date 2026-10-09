---
name: agy-dot-coordinator
description: Send short AGY-written coordination pings through the existing Dot tool and native scheduler.
---

# Antigravity dot coordinator

The default native wrapper now runs `scripts/ping-dots.py`: one due configured account, one short reminder generated in order by AGY, Codex Luna, then Claude Haiku 5.5, and one existing Dot `send-once` call. A failed, malformed, empty, or oversized provider result advances to the next provider. Only a valid reminder reaches the one Dot send attempt; a send failure never falls back to another provider or retries. `--generator agy|codex|haiku` selects one provider, and `--generate-only` exercises generation without sending. The reminder asks the Dot to inventory real active work first and permit capacity refusal only with fresh receipts for at least six distinct tasks, each showing the exact action happening now. It excludes idle, stalled, finished, queued, and review-waiting work from the active count, and keeps permission/approval or measured resource blocks separate from capacity refusal.

Configure exactly three accounts in the existing Dot rotation. Mac slots are :00/:20/:40; Linux slots are :30/:50/:10 for those accounts respectively. Missed slots are not replayed. The existing lock, STOP file, historical delivery holds, and Dot draft/authentication safeguards remain. There is no new ledger, browser transport, retry loop, or process framework.

`python3 scripts/ping-dots.py --account <configured-key>` sends one real ping. Do not use it merely to test installation. Native service installation/activation still requires the authorized owner handoff. A tested script or enabled timer is not proof that all six host/account pairs delivered.

## Legacy event-driven worker reference

The following documents only the retained `agy-dot-coordinator-worker.sh` manual interface. Its event gates, state mutations, cadence descriptions, and rejected AGY option do not apply to `ping-dots.py` or the current native wrapper.

The worker sends through the existing dot Chrome transport. It does not infer new authority or execute repository work. Latest direct user instructions override contextual priorities; respect task owners, cancellations, approvals and authentication holds.

### Sources and configuration

Use one canonical host package, with optional discovery links pointing to it. Required companion: the installed `dot` skill with `scripts/dot.sh`, Python 3, Bash, flock, timeout and its supported Node/browser runtime. Recipients come only from `DOT_CONFIG_FILE` (default `~/.config/dot/config.json`) rotation/accounts, or explicit `--account`. No account rotation on quota errors.

Store private contextual workstream defaults in `~/.config/dot/coordinator-priorities.txt` (or `COORDINATOR_PRIORITIES_FILE`), never in portable source. The message preserves these as defaults, suggests changes with reasons and does not reassign owners. Missing defaults retain the recipient's existing plan.

### Send gates

- Scheduled wakes are quiet without an explicit owner-supplied change/request ID and summary. No automatic change detection or compulsory full rollup runs.
- Skip routine sends whenever the dot read reports Thinking, Working or Searching; `--force` cannot bypass this, deduplication or unresolved receipt holds. This conservative text signal may defer a send when those words appear in ordinary text.
- Delta/blocker messages require owner-supplied `COORDINATOR_CHANGE_ID` and `COORDINATOR_CHANGE_SUMMARY`, plus one `--account`. IDs identify meaningful task/incident revisions, not a timestamp generated every wake. Summaries are bounded to 2000 characters. No automatic change classifier or producer is installed.
- `--full-rollup` (or `COORDINATOR_FULL_ROLLUP=1`) selects a complete cross-track review only for an explicit request or owner-reported material cross-track change. It requires the same single account, stable request/change ID and summary. There is no daily cap or cooldown barrier; different requests may run on the same day. Active owners and unresolved receipts still defer it; repeating an ID still retained in the shared dedup ledger does not resend. It cannot combine with urgent-incident mode.
- `COORDINATOR_URGENT=1` permits a material incident notification during active work/cooldown, with incident-only scope. It never requests a full WIP review or grants authority. Preserve draft and profile locking.
- The shared ledger for changes, rollups and incidents retains only the last 128 verified IDs per account. This is bounded deduplication: reusing an evicted ID can send again. Callers must not replay older events after they age out, or reuse an ID for a different request kind. Unchanged/duplicate events and quiet wakes do not open the browser.
- Success requires rc=0 AND an exact standalone `DOT_SENT_VERIFIED` transport receipt. Empty composer, nonzero exit or a substring is insufficient. Unverified sends persist a delivery hold; resolve actual receipt with the owner before manually clearing it. Errors preserve the receipt ledger.
- The optional legacy `--use-agy` sender is rejected because it lacks the direct receipt contract. No model is invoked by default.

State: `~/.local/state/ai.gemini.agy-dot-coordinator/state_<account>.json` and consolidated `state.json`. State overrides and `COORDINATOR_DOT_SCRIPT`/`COORDINATOR_LOCK_FILE` support isolated tests. Only the worker owns the flock execution lock; wrapper does not reacquire it.

### Scheduling and deployment

Existing host schedules are independent of send eligibility. The Mac template wakes at :00/:20/:40; Linux template at :15/:45. Do not replace a live schedule merely to change gates. The existing installer scripts register/restart services: do not run them for a no-restart package refresh. With the execution lock held and no competing package editor, preserve the complete old package, verify source/destination hashes, then atomically replace changed files and keep undo receipts. Never copy credentials or browser profiles for deployment.

`--status` reads account timestamps; `--dry-run` still reads the dot UI, so neither replaces an isolated transport test. Use tests with a fake dot transport for verification. For live proof, observe the next natural scheduler tick and its Worker SHA256 plus gate result; never send duplicate messages merely to test delivery.

### Explicit full-rollup example

After a direct user request or an owner-reported material cross-track change, use an ID unique to that semantic request (not a timestamp minted on every wake):

```bash
COORDINATOR_CHANGE_ID="request:review-release-dependencies" \
COORDINATOR_CHANGE_SUMMARY="User requested a complete review of release dependencies" \
  scripts/agy-dot-coordinator-worker.sh --account <configured-account> --full-rollup
```

This sends a real message; do not invoke it merely to test installation. Omit `--full-rollup` for a brief delta/blocker notification. Default scheduled invocations have no signals and stay quiet. No producer for these signals is installed by this package.

### Deferral and resumption

This worker sends owner-supplied events; it does not autonomously observe, reprioritize, or review all work. Keep any separate periodic all-task review with its existing owner. There is no automatic stall detector or pending-event queue.

A normal delta uses `--account`, `COORDINATOR_CHANGE_ID` and `COORDINATOR_CHANGE_SUMMARY`; it observes the default 1200-second cooldown (30-second scheduling tolerance) and active-owner gate. An authorized owner may explicitly use `--force` to bypass only the delta cooldown for that supplied event; scheduled wakes do not supply this override. `--force` never bypasses active-owner, receipt-hold or retained-ID gates and grants no new authority. A material stall can be reported as that scoped delta only when an authorized owner has evidence. `COORDINATOR_URGENT=1` selects a bounded incident notification and bypasses active/cooldown gates, without bypassing receipt holds or retained-ID deduplication. Full-rollup requests use the same inputs plus `--full-rollup`.

Deferrals for active work, cooldown, lock contention or unresolved receipts can return exit0 without delivery; exit0 is not an acknowledgement. The caller must retain its event and retry the same semantic ID after the owner is idle/cooldown expires or contention clears, or deliberately use the documented authorized `--force` cooldown-only override. Periodic no-input wakes do not resume it. Confirm the account's SUCCESS state and retained ID before acknowledging delivery. An uncertain-send hold requires the owner to reconcile the actual transport receipt before any manual state repair; never clear it blindly to retry. Do not mint a new ID for a deferred or uncertain attempt.
