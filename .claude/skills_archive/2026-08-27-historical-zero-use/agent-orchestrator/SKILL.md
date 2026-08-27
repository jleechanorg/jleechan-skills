---
name: agent-orchestrator
description: "Use this skill when working in repositories managed by Agent Orchestrator or when the user asks how to use `ao` properly. Covers the default AO workflow: bootstrap with `ao start`, dispatch work with `ao spawn`, inspect progress with `ao status` or `ao session ls`, steer sessions with `ao send`, and recover or clean up sessions safely. Includes strict parameter fidelity, pre-spawn cap cleanup, quota-wall fallback, and post-spawn verification."
---

# Agent Orchestrator

Use AO for durable coding work instead of manually creating worktrees or running agent CLIs directly. User-specified AO constraints (`--agent`, `--runtime`, `--project`, `--claim-pr`, target PR/branch/evidence standard) are mandatory — never substitute another agent/runtime because defaults exist.

## Default workflow

1. Bootstrap the repo or project with `ao start`.
2. Dispatch non-trivial coding work with `ao spawn`.
3. Inspect live state with `ao status` or `ao session ls`.
4. Send follow-up instructions with `ao send`.
5. Recover or clean up sessions with `ao session restore` and `ao session cleanup`.

## Commands to prefer

```bash
# Start AO in the current repo
ao start

# Start AO for another local repo or clone from GitHub
ao start ~/path/to/repo
ao start https://github.com/owner/repo

# Dispatch work
ao spawn "fix the flaky GitHub SCM retry path"
ao spawn -p agent-orchestrator bd-1234
ao spawn --project agent-orchestrator --claim-pr 456

# Inspect and steer work
ao status
ao session ls
ao send <session-id> "Also update the failing test coverage."

# Recovery and cleanup
ao session restore <session-id>
ao session cleanup --dry-run
```

## Read first

- `~/.hermes/agent-orchestrator.yaml` — **ALWAYS read this first** to resolve `--agent` shorthands (e.g. `agy`=`antigravity`); `defaults.agent` is the default when none specified.
- `references/config.md` — config schema for editing `agent-orchestrator.yaml`.
- `~/.claude/skills/ao-worker-dispatch/SKILL.md` — pre-dispatch checklist (venv, commit discipline, branch drift, CodeRabbit verify).
- `~/.claude/skills/ao-operator-discipline/SKILL.md` — strict parameter fidelity + post-spawn verification.
- `~/.claude/skills/ao-spawn-gate/SKILL.md` — pre-spawn safety gate.
- `~/.claude/skills/ao-session-monitor/SKILL.md` — proper tmux inspection for live workers.
- `~/.claude/skills/ao-model-override/SKILL.md` — override the worker's model (e.g. claude-sonnet-4-6, claude-opus-4-7) WITHOUT editing `~/.hermes/agent-orchestrator.yaml`. Use whenever the user names a specific model and the project default isn't it (e.g. "use claude sonnet with AO"). `ao spawn` has NO `--model` flag; the only inline override is `AO_CONFIG_PATH` pointing at a temp copy of the config — the skill ships `spawn-with-model.sh` for this.

## Working rules

- Prefer `ao spawn` for coding, debugging, CI fixes, review follow-up, and multi-step work.
- Use direct shell commands only for quick diagnostics or when AO itself is unavailable.
- If multiple projects are configured and cwd does not disambiguate, pass `-p, --project`.
- Prefer the existing AO session lifecycle over ad hoc worktrees and hand-run agent CLIs.
- When editing AO config, read `references/config.md`.

## When not to use AO

- Tiny read-only checks: `git status`, `gh pr view`, `rg`, simple file inspection.
- One-off local diagnostics where starting a full worker would be slower than the task.

## Step 0 — Pre-spawn cap check (added 2026-06-27)

**Before every `ao spawn`, run this pre-flight.**

**Cap authority:** the operator policy cap lives in `~/.claude/skills/ao-spawn-safety/SKILL.md` (currently a 30-worker absolute cap with 15-worker batches). Honor that; do not restate the numbers here.

⚠️ **Corrected 2026-07-25 — this cap is NOT software-enforced.** This section previously claimed AO enforces `MAX_CONCURRENT_SESSIONS=20` per project at `packages/core/dist/session-manager.js:853`, overridable via `AO_MAX_CONCURRENT_SESSIONS`. That is stale: `~/projects/agent-orchestrator` has no `packages/core/` tree and no `MAX_CONCURRENT_SESSIONS` constant anywhere outside `node_modules`, and `~/.hermes/agent-orchestrator.yaml` sets no concurrency limit. **Nothing will reject an over-cap spawn for you** — do not rely on a `Reason: N active sessions >= cap` rejection that will never arrive. The count check below is the only gate.

The script below still honors `AO_MAX_CONCURRENT_SESSIONS` if you export it, purely as a local override for the pre-flight arithmetic.

```bash
# 1. Count active sessions on the target project (exclude terminal status)
PROJ="${1:-worldarchitect}"
ACTIVE=$(ao session ls -p "$PROJ" 2>/dev/null \
  | grep -E "^\s+(wa|jc|ao|cc|co)-" \
  | grep -cvE '\[(done|failed|cancelled|exited|archived)\]')
CAP="${AO_MAX_CONCURRENT_SESSIONS:-30}"   # policy cap — see ao-spawn-safety/SKILL.md
echo "[/ao preflight] project=$PROJ active=$ACTIVE cap=$CAP"

# 2. If at or near cap, run auto-cleanup (DRY-RUN first, then real)
if [ "$ACTIVE" -ge "$((CAP - 1))" ]; then
  echo "[/ao preflight] at/near cap → running cleanup --dry-run"
  ao session cleanup -p "$PROJ" --dry-run 2>&1 | tail -20

  # The CLI's cleanup() removes sessions where ANY of:
  #   - PR is MERGED or CLOSED
  #   - Linked issue is COMPLETED
  #   - Runtime (tmux handle) reports !isAlive()
  # See packages/core/dist/session-manager.js:2079-2174
  # It will NOT kill: stuck-but-alive workers (e.g. quota-blocked LLM)
  # Those need explicit `ao session kill <id>` (destructive — needs user OK).

  echo "[/ao preflight] applying cleanup (real)"
  ao session cleanup -p "$PROJ" 2>&1 | tail -10

  # Re-count after cleanup
  ACTIVE=$(ao session ls -p "$PROJ" 2>/dev/null \
    | grep -E "^\s+(wa|jc|ao|cc|co)-" \
    | grep -cvE '\[(done|failed|cancelled|exited|archived)\]')
  echo "[/ao preflight] post-cleanup active=$ACTIVE cap=$CAP"
fi

# 3. If STILL at/near cap after cleanup → surface stuck sessions and STOP
if [ "$ACTIVE" -ge "$((CAP - 1))" ]; then
  echo "[/ao preflight] ⚠️ still at/near cap after cleanup; stuck sessions:"
  ao session ls -p "$PROJ" 2>/dev/null \
    | grep -E "^\s+(wa|jc|ao|cc|co)-" \
    | grep -vE '\[(done|failed|cancelled|exited|archived)\]'
  echo ""
  echo "[/ao preflight] cleanup could not free enough slots."
  echo "  Stuck sessions are alive (tmux IS responding) but not progressing —"
  echo "  likely quota-blocked. To free slots, explicit user approval required:"
  echo "    ao session kill <session-id>     # destructive, needs user OK"
  echo "    OR raise cap: set AO_MAX_CONCURRENT_SESSIONS env on the"
  echo "    orchestrator launchd plist and bounce ao start."
  echo ""
  echo "[/ao preflight] STOPPING — refusing to spawn over cap."
  exit 1
fi

# 4. Pre-spawn sanity: also check no duplicate of (project, issue, prompt) exists
#    (AO has its own duplicate detection, but explicit check surfaces the cause)
echo "[/ao preflight] OK — proceeding to spawn"
```

**Bug-ref (2026-06-27):** dispatch-task v1.3.0 claimed "AO has no worker-count
cap" — that was wrong. `MAX_CONCURRENT_SESSIONS=20` is enforced at runtime. See
`packages/core/dist/session-manager.js:853`. Cap can be raised via
`AO_MAX_CONCURRENT_SESSIONS` env var on the `ao start` launchd plist (requires
restart of the orchestrator daemon, PID 4341).

**When to skip Step 0:** if the user has already issued `ao session cleanup`
or `ao session kill` in the current turn, the cleanup has already run — go
straight to spawn.

## Step 0.5 — Quota-wall auto-fallback (added 2026-06-27)

If Step 0 didn't free enough slots AND the stuck sessions are quota-blocked
(rather than genuinely busy), suggest spawning on a **different agent provider**
that has its own quota pool. The default `--agent` for `worldarchitect` was
flipped to `minimax` on 2026-06-27 — verify that's the live value before
suggesting alternatives.

```bash
# 1. Detect quota wall — count sessions whose tmux pane shows the
#    "weekly limit" message or other quota-block signals
PROJ="${1:-worldarchitect}"
QUOTA_HITS=0
for SESS_DIR in ~/.agent-orchestrator/*/sessions/; do
  for SESS in "$SESS_DIR"/*; do
    [ -f "$SESS" ] || continue
    # Match the target project via session-prefix (wa-* = worldarchitect)
    [[ "$(basename "$SESS")" == wa-* ]] || continue
    TMUX=$(grep -oE 'tmux-target=[^[:space:]]+' "$SESS" | head -1 | cut -d= -f2)
    [ -n "$TMUX" ] || continue
    PANE=$(tmux capture-pane -t "$TMUX" -p 2>/dev/null | tail -50)
    if echo "$PANE" | grep -qE 'weekly limit|You.{0,3}ve hit your.*limit|RESOURCE_EXHAUSTED|429.*quota|quota.*exceeded'; then
      QUOTA_HITS=$((QUOTA_HITS + 1))
    fi
  done
done

# 2. If >2 sessions on the target project hit quota wall, suggest minimax
if [ "$QUOTA_HITS" -ge 2 ]; then
  echo "[/ao Step 0.5] ⚠️ $QUOTA_HITS wa-* sessions appear quota-blocked."
  echo "[/ao Step 0.5] Three independent quota pools are available:"
  echo "  --agent minimax     # MiniMax/M3 (default for worldarchitect since 2026-06-27)"
  echo "  --agent codex       # GPT-5.4 — separate pool, good for code-heavy work"
  echo "  --agent claude-code # Sonnet — reserved for CodeRabbit-class reasoning"
  echo ""
  echo "[/ao Step 0.5] Suggested next spawn:"
  echo "  ao spawn --agent codex \"$TASK\"     # routes around the quota wall"
fi
```

**Why this matters:** When 14+ workers all hit the same provider's quota wall
simultaneously, no amount of cleanup frees them — they're alive but unable to
respond. The fix is to spawn on a **different provider**, not to kill the stuck
ones.

**Bug-ref (2026-06-27, Slack thread 1782582007.796799):** wa-2901 was archived 5×
in 3 minutes cycling on PR #7980 conflicts because the LLM was quota-blocked
and could not process the steer message. Same pattern across wa-2882/wa-2883
(PR #7592), wa-2898/wa-2899/wa-2900/wa-2902/wa-2903/wa-2904. All `agent=claude-code`.

## Parameter fidelity and post-spawn verification rules

1. Respect explicit AO parameters exactly:
   - `--agent`
   - `--runtime`
   - `--project`
   - `--claim-pr`
   - target PR / branch / evidence standard

2. Never substitute another agent/runtime because defaults exist.

3. After every `ao spawn`, verify the spawned session file under `~/.agent-orchestrator/.../sessions/<session>`:
   - `agent=<expected>`
   - `runtimeHandle.data.launchCommand` contains the expected CLI

4. If the user asked for Codex workers, the session must show:
   - `agent=codex`
   - `launchCommand` contains `codex`

5. After metadata verification, inspect the tmux pane with at least 20 lines:
   - `tmux capture-pane -pt <tmux-session>:0.0 -S -40`

6. If verification fails, kill and replace the worker. Do not continue with a mismatched worker.

## Output requirements

When reporting AO setup or supervision, include:
- the exact session ids
- the target PR URLs
- proof of `agent=<expected>`
- proof of `launchCommand`
- whether each worker is productive, drifting, or dead
- **the preflight cap-check output (active count, dry-run, post-cleanup count)**

## Related files

- Config reference: `references/config.md`
- CLI help: `ao --help`, `ao spawn --help`, `ao start --help`
- Repo policies: `AGENTS.md`, `CLAUDE.md`
- **Binary installation norms:** [Binary Installation — Canonical Install Paths](../../AGENTS.md#binary-installation--canonical-install-paths) — `scripts/setup.sh` for repo maintainers, `npm install -g @jleechanorg/ao-cli` for others; `ao doctor` must pass after any install or update
