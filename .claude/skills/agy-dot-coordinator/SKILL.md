---
name: agy-dot-coordinator
description: Coordinate existing dot work with collaborative priorities, quiet daily rollups, explicit state-change events and verified delivery.
---

# Antigravity dot coordinator

The worker sends through the existing dot Chrome transport. It does not infer new authority or execute repository work. Latest direct user instructions override contextual priorities; respect task owners, cancellations, approvals and authentication holds.

## Sources and configuration

Use one canonical host package, with optional discovery links pointing to it. Required companion: the installed `dot` skill with `scripts/dot.sh`, Python 3, Bash, flock, timeout and its supported Node/browser runtime. Recipients come only from `DOT_CONFIG_FILE` (default `~/.config/dot/config.json`) rotation/accounts, or explicit `--account`. No account rotation on quota errors.

Store private contextual workstream defaults in `~/.config/dot/coordinator-priorities.txt` (or `COORDINATOR_PRIORITIES_FILE`), never in portable source. The message preserves these as defaults, suggests changes with reasons and does not reassign owners. Missing defaults retain the recipient's existing plan.

## Send gates

- Scheduled wakes request at most one rollup per 86400 seconds/account. Legacy last-sent time conservatively initializes this limit.
- Skip routine sends whenever the dot read reports Thinking, Working or Searching; `--force` cannot bypass this, deduplication or daily limits. This conservative text signal may defer a send when those words appear in ordinary text.
- Extra messages require owner-supplied `COORDINATOR_CHANGE_ID` and `COORDINATOR_CHANGE_SUMMARY`, plus one `--account`. IDs identify meaningful task/incident revisions, not a timestamp generated every wake. Summaries are bounded to 2000 characters. No automatic change classifier or producer is installed.
- `COORDINATOR_URGENT=1` permits a material incident notification during active work/cooldown, with incident-only scope. It never requests a full WIP review or grants authority. Preserve draft and profile locking.
- Remember the last 128 verified change IDs per account. Do not replay older events after they age out. Unchanged/duplicate events and daily-cap skips do not open the browser.
- Success requires rc=0 AND an exact standalone `DOT_SENT_VERIFIED` transport receipt. Empty composer, nonzero exit or a substring is insufficient. Unverified sends persist a delivery hold; resolve actual receipt with the owner before manually clearing it. Errors preserve the receipt ledger.
- The optional legacy `--use-agy` sender is rejected because it lacks the direct receipt contract. No model is invoked by default.

State: `~/.local/state/ai.gemini.agy-dot-coordinator/state_<account>.json` and consolidated `state.json`. State overrides and `COORDINATOR_DOT_SCRIPT`/`COORDINATOR_LOCK_FILE` support isolated tests. Only the worker owns the flock execution lock; wrapper does not reacquire it.

## Scheduling and deployment

Existing host schedules are independent of send eligibility. The Mac template wakes at :00/:20/:40; Linux template at :15/:45. Do not replace a live schedule merely to change gates. The existing installer scripts register/restart services: do not run them for a no-restart package refresh. With the execution lock held and no competing package editor, preserve the complete old package, verify source/destination hashes, then atomically replace changed files and keep undo receipts. Never copy credentials or browser profiles for deployment.

`--status` reads account timestamps; `--dry-run` still reads the dot UI, so neither replaces an isolated transport test. Use tests with a fake dot transport for verification. For live proof, observe the next natural scheduler tick and its Worker SHA256 plus gate result; never send duplicate messages merely to test delivery.
