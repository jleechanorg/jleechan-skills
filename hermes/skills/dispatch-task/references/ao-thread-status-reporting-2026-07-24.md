# AO thread status reporting — Go-AO + Hermes handoff (2026-07-24)

This reference replaces the legacy `mctrl supervisor` model with the
**AO-native** status reporting path. Load this whenever:

- the user asks why an AO worker "stopped reporting back" to a Slack thread,
- a Slack thread went silent while an AO session is still `[working]` /
  `[no_signal]`,
- the dispatch fails with `Internal server error (INTERNAL_ERROR)` from
  the Go `ao` daemon,
- the user invokes `/a`, `/fullrun`, `/finish`, `/f`, `/agento`, `/auto`,
  or types `agent-orchestrator-go` / `auto-commit-orchestrator-ts` and asks
  about the difference, or
- any babysit / progress reporter is being (re)designed.

## TL;DR

The `agent-orchestrator-golang` repo (active `ao` binary at
`~/.local/bin/ao`, version `dev`) no longer ships the `ai.mctrl.supervisor`
loop that the old TypeScript `auto-commit-orchestrator-ts` fork used for
"worker reported back to the originating thread." Status reporting is now an
**AO-native** pipeline:

```text
coding-agent hooks (ao hooks <harness> <event>)
  → AO activity dispatcher        (backend/internal/adapters/agent/activitydispatch)
  → AO activity state             (backend/internal/adapters/agent/activitystate)
  → AO CDC broadcast              (backend/internal/cdc/broadcast.go)
  → Hermes reporter (subscriber)  (lives outside the AO Go repo)
  → originating Slack thread      (channel + thread_ts from bead notes)
```

The TypeScript `auto-commit-orchestrator-ts` fork's `mctrl` supervisor is
**deprecated**. Do not patch `~/.hermes/scripts/mctrl_supervisor*` — they
are historical only. Do not route new reporting through them. SOUL.md
already bans `mctrl` for coding tasks; the same applies to status
reporting.

## Go `ao` CLI — current contract (verified 2026-07-24)

The Go CLI does **not** accept the legacy TypeScript-era flags `--model`,
`--agent`, `--repo`, `--task`, or a positional path. The Go contract is
project-based:

```text
ao project add --path <abs> --id <id> --name <name> --worker-agent <harness>
ao spawn    --project <id> --harness <harness> --prompt <text> \
            --name <≤20 chars> [--branch <b>] [--claim-pr <N>] [--issue <id>]
```

Constraints:

- `--name` is hard-limited to **20 characters** (`--name must be 20
  characters or fewer`).
- `ao project add` takes only flags — positional paths return
  `accepts 0 arg(s), received 1`.
- If you forget `--worker-agent claude-code`, AO cannot resolve a harness
  and the failure surfaces as `INTERNAL_ERROR` deep inside the daemon (not
  at the CLI). Always pass it at project-add time **and** at spawn time.
- `ao project rm` exists for cleaning up test registrations; use it when
  re-registering the same path under a new id.

Verify the Go CLI before assuming a dispatch flag set works — run
`ao spawn --help` and `ao project add --help` first; never copy from older
notes without checking. Old examples (including some lines in
`~/.hermes/skills/dispatch-task/SKILL.md`) are stale against the Go CLI.

## Failure pattern: daemon `ready` while hooks log "stale run-file"

Symptom chain (verified live 2026-07-24):

1. `ao status --json` reports `state=ready`, `health=ok`, `ready=ready`.
2. `~/.ao/data/hooks.log` is full of:
   ```text
   session=<id> ao hooks <harness> <event>: AO daemon is not running
     (stale run-file at $HOME/.ao/running.json)
   ```
3. `ao spawn` then returns `Internal server error (INTERNAL_ERROR)
   request <host>/<req-id>` after the project registration succeeds.
4. The session inventory (`ao session ls`) shows a flood of `[no_signal]`
   workers from prior dispatches that never received activity callbacks.

This is the same class of regression as
`references/ao-spawn-internal-error-orphan-sessions-2026-07-24.md`, but
its trigger is a stale run-file pointer (`~/.ao/running.json`), not a
missing harness.

**Do not rely on `ao status --json state=ready` alone as a "AO is fine"
gate.** The hook log is the ground truth for whether the worker activity
pipeline is actually live.

Recovery recipe:

```bash
# 1. Confirm the three signals disagree
ao status --json | jq -r '.state,.health,.ready'
tail -50 ~/.ao/data/hooks.log | grep -c 'AO daemon is not running'
cat ~/.ao/running.json
ps -p $(jq -r .pid ~/.ao/running.json 2>/dev/null) -o pid,command= 2>&1 | head -3

# 2. Stop recorded daemon, clear stale run-file, restart
PID=$(jq -r .pid ~/.ao/running.json 2>/dev/null)
[ -n "$PID" ] && kill -TERM "$PID" 2>/dev/null
rm -f ~/.ao/running.json
ao start          # restart daemon; verify with `ao status --json` health=ok

# 3. Re-arm only AFTER `tail -f ~/.ao/data/hooks.log` shows normal activity
#    callbacks instead of "AO daemon is not running" lines.
```

After recovery, **re-arm any babysit / progress-reporter crons** that
silently self-disabled while the pipeline was broken. The reporter should
not classify a session as "stalled" until at least one full hook roundtrip
has succeeded post-restart.

## Reporting contract — what the Hermes reporter must do

The Hermes-side reporter (subscribes to AO's CDC stream) must:

1. Translate AO events into Slack thread replies:
   - `session-start` → "🔭 Babysit armed for session `<name>`"
   - `activity`     → silent (or periodic 5-min heartbeat per SOUL.md
     `dispatched-task-acks`)
   - `terminal`     → completion summary, PR URL if `claim-pr` known
   - `failure`      → explicit failure classification with one-line
     escalation; never silently re-try

2. **Post to the originating thread** (channel + thread_ts from the bead
   notes / spawn origin), never to a home-channel fallback. The 5b-leak
   incident (2026-06-19) showed that falling back to a home channel is a
   routing bug, not a feature.

3. Verify that a worker `claim-pr`'d PR exists on a configured remote
   BEFORE classifying the task as finished — the `agent-orchestrator-golang`
   repo intentionally mirrors the TypeScript fork's "finished =
   remote-reviewable" contract.

4. During long runs, post a periodic in-thread progress ping at least every
   5 minutes (per SOUL.md `dispatched-task-acks`).

5. Send MCP Agent Mail notification to Hermes (if MCP Mail is enabled —
   per SOUL.md `mcp-agent-mail-no-passive-slack-listening`, the Slack bridge
   stays OFF unless the user explicitly enables it).

## Python 3.14 helper-layer blocker — workaround during a session

The Hermes Python helper layer (`skill_view`, `session_search`, the
`hermes_tools.*` API in `execute_code`) can fail mid-session with:

```text
'DaemonThreadPoolExecutor' object has no attribute '_initializer'
```

This is the Python 3.14 `concurrent.futures.thread` regression (PR #132836;
executor no longer stores `_initializer` / `_initargs` on the instance —
they live on a `WorkerContext`). Canonical skill:
`py314-threadpoolexecutor-initializer-fix`.

**Do not restart the gateway mid-session** to clear it — that drops the
current Hermes session. Instead:

- Bypass `skill_view` by calling `skill_manage(action='write_file', ...)`
  directly when you know the path.
- Bypass `session_search` and `memory` helpers by reading the underlying
  files directly (`~/.hermes/state.db` is read-only-safe via the bundled
  Python sqlite helpers, but the helper wrapper is what's broken).
- For `execute_code`, fall back to inline `terminal` calls — the raw
  subprocess works fine; the failure is purely in the in-process thread
  pool.

After the session, the durable fix is the gateway restart documented in
the canonical skill. But **do not do it inside a session that depends on
the gateway** — schedule the restart via launchd or run it from a separate
shell.

## How this differs from `auto-commit-orchestrator-ts` (the fork)

| Capability                       | `auto-commit-orchestrator-ts` fork             | `agent-orchestrator-golang` (current)            |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------ |
| Completion reporter              | `ai.mctrl.supervisor` (deprecated)             | AO CDC broadcast → external subscriber           |
| Activity hooks                   | per-adapter, daemon-collected                  | same model, routed through `activitydispatch`    |
| Origin metadata on spawn         | bead notes (`slack_trigger_ts`, `slack_trigger_channel`) | bead notes **and** AO session metadata; CDC event includes session id |
| Polling pattern                  | `mctrl` 30s loop                               | event-driven via CDC; polling discouraged        |
| CLI flags                        | `--model`, `--agent`, `--repo`, `--task`       | `--project`, `--harness`, `--prompt`, `--name`  |
| Project registration             | implicit                                       | explicit `ao project add --path ...`             |
| Name length limit                | n/a                                            | 20 characters                                    |
| Failure when harness unresolved  | surface error                                  | silent → `INTERNAL_ERROR` deep in daemon        |
| Run-file state                   | ephemeral                                      | persistent `~/.ao/running.json` — **can go stale**; verified failure pattern |

If a future user asks "why did my old `mctrl` setup stop working?" — the
answer is the rows above: the active AO moved to an event-driven model,
and the old supervisor loop is no longer the path. The TypeScript fork
still has `mctrl` for backward compatibility, but it is not what
`agent-orchestrator-golang` runs.

## Where the hooks log proves the model

When `tail ~/.ao/data/hooks.log` is full of:

```text
session=worldarchitect-64 ao hooks claude-code pre-tool-use: AO daemon is not running
session=worldarchitect-64 ao hooks claude-code post-tool-use: AO daemon is not running
session=worldarchitect-64 ao hooks claude-code notification: AO daemon is not running (stale run-file at $HOME/.ao/running.json)
```

…then **no activity events will reach the Hermes reporter**, no thread
status updates will be posted, and `ao session ls` will show the affected
sessions as `[no_signal]` even though `ao status --json` reports
`ready`. The fix is the recovery recipe in §"Failure pattern", not
retries.
