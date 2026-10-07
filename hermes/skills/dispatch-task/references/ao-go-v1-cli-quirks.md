# ao-go v1.x CLI quirks (verified 2026-07-17)

The ao-go binary (`$HOME/.local/bin/ao`, ~20MB, post-2026-07-06) has
diverged from the older TS CLI (`$HOME/.nvm/.../bin/ao`). This file
consolidates the verified gotchas so dispatch recipes don't burn budget on
re-deriving them.

## Flags that DISAPPEARED in v1.x (verified 2026-07-17)

| Flag | Old CLI | ao-go v1.x |
|---|---|---|
| `ao start --no-dashboard --no-open` | launches a background daemon | **returns `unknown flag: --no-dashboard` and exits 2** |
| `ao start <project>` | launches a daemon for one project | not supported; `ao start` now resolves the desktop app, opens it, and exits |
| `ao status --project <id>` | per-project status | **not in `ao status --help`**; use `ao status --json` and filter |
| `ao start --skip-pull` etc. | various | none of the daemon-control flags apply |
| `--agent <name>` on `spawn` | accepted | **rejected** — use `--harness <name>` (see v1.4 notes) |

`ao start --json` (no flags) is the canonical "make sure the desktop app + daemon
are up" call:

```bash
$HOME/.local/bin/ao start --json
# { "resolved": true, "fetched": false, "opened": true, "appPath": "/Applications/Agent Orchestrator.app" }
```

After that, poll `$HOME/.ao/running.json` to confirm the daemon is
healthy:

```bash
$HOME/.local/bin/ao status --json
# { "state": "ready", "pid": 27758, "port": 64927, "startedAt": "...", "health": "ok", "ready": "ready" }
```

## Daemon-hang recovery (verified 2026-07-17)

Symptom: `ao status --json` returns `"state": "unhealthy"` with
`"error": "healthz: Get \"http://127.0.0.1:3001/healthz\": context deadline exceeded"`
even though `lsof -nP -iTCP:3001 -sTCP:LISTEN` shows `ao-go` PID listening.
The daemon has been stuck for hours (verified: 37h uptime, still unhealthy).

Cause: `ao-go` daemon process is wedged but the listening socket stays open.
The new `ao start --json` will not kill/restart the existing daemon.

Recovery (≤30s end-to-end):

```bash
# 1. Identify the stuck daemon
lsof -nP -iTCP:3001 -sTCP:LISTEN | awk 'NR>1 {print $2}' | head -1
# (record PID; verified wedged PID was 1139)

# 2. SIGTERM (NOT SIGKILL first — daemon flushes running.json cleanly on SIGTERM)
kill -TERM <pid>

# 3. Wait for the socket to close
for i in $(seq 1 20); do sleep 1; \
  lsof -nP -iTCP:3001 -sTCP:LISTEN >/dev/null 2>&1 || { echo "old-daemon-stopped at ${i}s"; break; }; done

# 4. Re-launch via the desktop-app path
$HOME/.local/bin/ao start --json

# 5. Confirm ready
for i in $(seq 1 20); do sleep 1; \
  out=$($HOME/.local/bin/ao status --json 2>/dev/null || true); \
  echo "$out" | grep -q '"state": "ready"' && { echo "READY: $out"; exit 0; }; done
$HOME/.local/bin/ao status --json; exit 1
```

Verified 2026-07-17: this exact sequence restored `state: ready` after a 37h
hang and was followed by a successful `ao spawn --project jleechanclaw`.

## `ao spawn --name` length limit (verified 2026-07-17)

```
--name must be 20 characters or fewer
```

The CLI truncates silently in some prior versions but in v1.x it errors out.
Pick short slugs: `pat-gate-codex` (14), `worldai-test` (13), not
`pat-outbound-secret-gate` (24).

## Project registry (v1.5+ has multiple resolution paths)

`ao project add --path $HOME/projects/<repo> --id <id>` registers
projects in `~/.ao/data/ao.db` `projects` table. The legacy
`agent-orchestrator.yaml` is **not** read by the daemon. Always confirm a
project before spawning:

```bash
sqlite3 $HOME/.ao/data/ao.db \
  "SELECT id, display_name, path FROM projects WHERE archived_at IS NULL ORDER BY display_name;"
```

## `--harness` vs `--agent`

v1.x accepts `--harness <name>`; the legacy `--agent <name>` returns
"agent could not be resolved; pass --agent or configure
`ao project set-config <id> --worker-agent <agent>`" even when the project
and harness are valid. The error message is misleading — it's the flag name
that changed, not the agent lookup.

```bash
# CORRECT (v1.x)
$HOME/.local/bin/ao spawn --project jleechanclaw \
  --harness codex --name pat-gate --prompt "..."

# WRONG (silent fail)
$HOME/.local/bin/ao spawn --project jleechanclaw \
  --agent codex --name pat-gate --prompt "..."
```

## Codex worker auto-loads skills + auto-runs spawn prompt (v1.5+)

Verified 2026-07-17: a Codex worker spawned via `--harness codex` immediately
self-loaded `using-ao`, `agent-orchestrator`, `ponytail`, `file-justification`,
`root-cause-first`, `harness-engineering`, `hermes-deploy-pipeline`,
`beads-issue-tracking`, `harness-postmortem`, and `evidence-standards` skills
on the first turn. It also began acting on the spawn prompt without an
explicit Enter.

Therefore:

- **DO** copy the full task brief to `AO-TASK-BRIEF.md` in the worktree root
  before spawning — the worker reads it directly from disk even if the tmux
  paste-buffer is truncated.
- **DO NOT** try to "wait for the worker to be ready" before sending — it is
  already running.
- **DO NOT** push `/model` slash commands to a Codex worker unless you have a
  specific reason: the `gpt-5.6-sol high` mid-tier default is correct for
  standard fix/review/evidence lanes; the `gpt-5.3-codex-spark` tier is faster
  but may not satisfy all skill auto-loads.

## Benign noise to ignore

- `PreToolUse hook (failed) error: PreToolUse hook returned unsupported permissionDecision:allow` — fires
  on every Bash/Read call under Codex's `--dangerously-bypass-hook-trust`. The
  tool still runs; the hook is just complaining about the schema of the
  `--agent` flag (see `codex-path-deletion-guard` skill for the
  permissionDecision schema fix).
- `Tip: New Use /fast to enable our fastest inference` — Codex CLI's standard
  welcome banner.
- `WARN: Skill descriptions were shortened to fit the 2% skills context budget.`
  Codex auto-truncates description fields; the skills still load fully.

## Canonical spawn recipe (v1.x, verified 2026-07-17)

```bash
GHV="$(env -u GH_TOKEN -u GITHUB_TOKEN gh auth token --hostname github.com)"
cd $HOME/repos/jleechanclaw
env -i HOME="$HOME" PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
  GH_TOKEN="$GHV" AO_BOT_GH_TOKEN="$GHV" AO_MAX_CONCURRENT_SESSIONS=30 \
  $HOME/.local/bin/ao spawn \
    --project jleechanclaw \
    --harness codex \
    --name <≤20-char-slug> \
    --prompt "Read \$BRIEF. Execute fully. Use mid-tier model only. Bead <id>. Push and verify remote before stopping."
```

If the daemon is unhealthy, run the recovery block above BEFORE the spawn.

## See also

- `codex-path-deletion-guard` — PreToolUse hook schema gotchas
- `babysit-ao-pr-loop` — running the spawned worker to merge
