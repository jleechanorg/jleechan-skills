---
name: agy-dot-coordinator
description: Send short AGY-written coordination pings through the existing Dot tool and native scheduler.
---

# Antigravity Dot Coordinator

The Antigravity Dot Coordinator periodically generates and sends structured coordination reminders to active ChatGPT "Dot" assistants across configured rotation accounts using native system schedulers (`launchd` on macOS, `systemd` on Linux).

## Architecture & Workflow

Each scheduled invocation executes `scripts/ping-dots.py` via `scripts/agy-dot-coordinator-wrapper.sh`:

1. **Slot & Account Resolution**: Determines the due account for the current time slot from `DOT_CONFIG_FILE` (default `~/.config/dot/config.json`). Exactly three distinct accounts must be configured.
2. **Lock & State Check**: Acquires an exclusive non-blocking `flock` on `/tmp/ai.gemini.agy-dot-coordinator.lock`. Aborts safely if another ping is running, if `STOP` exists in the state directory, or if the account has an unresolved unverified delivery hold.
3. **Provider Generation Ladder**: Generates a standard reminder paragraph using the provider sequence:
   - **Primary**: AGY (`agy --input-format stream-json`)
   - **Secondary**: Codex Luna (`gpt-6-luna`)
   - **Tertiary**: Claude Haiku (`claude-haiku-5-5`)
   A failed, malformed, empty, or oversized (>1,200 characters) provider output advances to the next provider. No provider retry or backoff is performed.
4. **Byte-for-Byte Contract Verification**: Verifies that the model returned the exact required reminder instructions. Any unauthorized alteration fails generation and triggers provider fallback.
5. **Transport Dispatch**: Appends attribution and the no-new-authority notice, writes to a temporary file, and invokes `dot.sh --account <account> send-once <file>`. Requires `rc=0` and standalone `DOT_SENT_VERIFIED` output. Send failures never retry or switch providers.

## Scheduling & Rotation

Coordination pings run on fixed 20-minute offsets across exactly three rotation accounts:

| Host OS | Account 1 | Account 2 | Account 3 | Scheduler Mechanism |
|---|---|---|---|---|
| **macOS** | `:00` | `:20` | `:40` | `launchd` (`ai.gemini.agy-dot-coordinator.plist`) |
| **Linux** | `:30` | `:50` | `:10` | `systemd` timer (`ai.gemini.agy-dot-coordinator.timer`) |

Missed slots are not replayed. Scheduled runs outside a valid 120-second window stay quiet without sending.

## CLI Usage

```bash
# Send one scheduled ping to the currently due account
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/agy-dot-coordinator/scripts/ping-dots.py"

# Send ping to an explicit account
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/agy-dot-coordinator/scripts/ping-dots.py" --account <configured-account-key>

# Generate and print reminder for an account without sending
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/agy-dot-coordinator/scripts/ping-dots.py" --account <configured-account-key> --generator codex --generate-only

# Send ping to an explicit account using a specific provider (delivers live message)
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/agy-dot-coordinator/scripts/ping-dots.py" --account alpha --generator agy
```

*(From within the skill directory, `python3 scripts/ping-dots.py ...` also works.)*

### Options

- `--account <name>`: Target one configured account key instead of calculating the due slot.
- `--generator {auto,agy,codex,haiku}`: Select model provider (default: `auto` ladder).
- `--generate-only`: Generate and print the reminder to stdout; bypass Dot transport send.

## Coordination Contract & Invariants

- **Exact Opening**: Reminders always begin with:  
  `Inventory the work I asked for in the last 24 hours and verify what’s done versus not done.`
- **Durable Progress**: Directs the recipient to resume unfinished authorized requests from durable checkpoints and acceptance gaps, and to identify feasible alternate execution/validation steps before waiting.
- **Capacity vs Authority**: Six concurrent tasks is a throughput capacity target, never authorization for new work or an excuse to stall safe existing work.
- **Permission Boundaries**: Work already approved by the owner requires no repeated re-approval; explicit user authorization remains mandatory for merge, destructive actions, credentials, and task-scope changes.
- **Attribution Suffix**: Every delivered message ends with:  
  `From <AGY|Codex|Claude Haiku> coordinator: automated reminder; no new authority.`

## Legacy Event-Driven Worker Reference

The manual interface `scripts/agy-dot-coordinator-worker.sh` remains available for ad-hoc, owner-supplied event notifications (deltas, incidents, full rollups). It does not govern routine scheduled `ping-dots.py` executions.

### Key Behaviors

- **Delta Notifications**: Require `COORDINATOR_CHANGE_ID` and `COORDINATOR_CHANGE_SUMMARY`. Respects a 1,200-second cooldown per account.
- **Full Rollup**: `COORDINATOR_FULL_ROLLUP=1` requests a complete cross-track review for explicit manual audits. Bypasses daily/cooldown barriers but respects active-owner and deduplication gates.
- **Incident Escalation**: `COORDINATOR_URGENT=1` bypasses active work and cooldown gates for critical notifications without full WIP review.
- **Bounded Deduplication**: Maintains an LRU ledger of the last 128 verified change IDs per account to prevent duplicate sends.
- **Manual Overrides**: `--force` bypasses delta cooldown only; never bypasses active-owner locks, receipt holds, or deduplication.
