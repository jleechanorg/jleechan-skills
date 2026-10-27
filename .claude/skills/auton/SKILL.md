---
name: auton
description: Diagnose why the automation system is not autonomously completing draft readiness and driving PRs to green. Invoked by `/auton`; measures canonical zero-touch readiness, detects stale sessions, and reviews worker outcomes.
---

# Autonomy Diagnostic Skill

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


## Purpose

**Run /auton AFTER a work block ends** — retrospective review of what workers did, what failed, and why. It is the post-mortem tool.

**Run /babysit WHILE work is happening** — live triage, parallel worker dispatch, DRIVER mode nudges. It is the concurrent monitoring tool.

| Skill | When | Mode | Output |
|-------|------|------|--------|
| `/babysit` | During active workers | Live monitoring, dispatch | Per-PR status, DRIVER nudges |
| `/auton` | After block completes | Retrospective | Outcome table, root causes, metrics |

When invoked, diagnose why the jleechanclaw + AO system is not autonomously
completing draft readiness and `/green`. Use the canonical `pr-lifecycle`,
`pr-green-definition`, and `zero-touch` skills for current readiness and
merge-authority decisions.

## Read first (mandatory before answering)

Before classifying any tmux or cmux session, follow the shared
`~/.codex/AGENTS.md` full-buffer rule: read the full available history, then
verify current process and activity evidence. A commit-time gap alone is a
triage signal, not a stalled-state verdict.

> **⚠️ DUAL-CONFIG WARNING (2026-04-15):** Two AO config directories exist with different purposes:
> - `~/.openclaw/` — CLI/interactive use (used by `ao spawn`, `ao config`, etc.)
> - `~/.openclaw_prod/` — worker use (used by lifecycle-workers via launchd plist `AO_CONFIG_PATH`)
> **Always diagnose BOTH or verify which is active** — they can diverge and cause auth failures.

1. `~/.hermes/` — Hermes agent config (the agent since 2026-04-12; OpenClaw is dead)
2. `~/.openclaw_prod/agent-orchestrator.yaml` — AO worker config (used by lifecycle-workers)
3. `~/.openclaw/agent-orchestrator.yaml` — AO CLI config (used by interactive `ao` commands)
4. `~/.codex/AGENTS.md` — agent policies
5. `~/.openclaw/SOUL.md` — AO decision-making policy (legacy; Hermes uses its own)

**NOTE: ao-pr-poller is DEPRECATED and removed. Do NOT check for it or report its absence as a problem.**

## The system's intended behavior

```
AO lifecycle-worker (every ~5 min via launchd)
  ↓ detects non-green PR (backfillAllPRs: true)
  ↓ spawns agento session (ao spawn --claim-pr)
  ↓ agento: reads comments, fixes code, pushes
  ↓ agento: keeps the PR draft through the applicable draft gates per pr-lifecycle
  ↓ agento: marks ready only after draft readiness passes
  ↓ CI passes and mergeability is rechecked through /green
  ↓ agento reports ready; merge remains separately human-authorized
```

Use the current `/green` and PR lifecycle owners when diagnosing readiness. CodeRabbit
and Bugbot are optional advisory reviewers; neither their state nor a legacy
automation workflow determines readiness. A green PR is not merge authorization:
the final merge follows shared policy and the target repository's current contract.

## Usage

- `/auton` — Run full autonomy diagnostic
- `/auton <description>` — Focus on a specific failure mode

**YOU (Claude) must execute the following steps immediately when `/auton` is invoked.**

## Diagnostic questions (answer each with evidence)

### 0. Verify active config path (MUST DO FIRST — 2026-04-15 lesson)
```bash
# Find which config workers actually use
ps aux | grep "lifecycle-worker" | grep -v grep | head -5

# Check if both configs exist and are different
diff ~/.openclaw/agent-orchestrator.yaml ~/.openclaw_prod/agent-orchestrator.yaml 2>/dev/null && echo "configs IDENTICAL" || echo "⚠️ configs DIVERGE"

# If configs differ, the WORKER config is the source of truth for auth/model issues
# Workers read AO_CONFIG_PATH from their process env — verify it:
ps aux | grep "lifecycle-worker" | grep -v grep | grep -o "AO_CONFIG_PATH=[^ ]*"
```
**Why this matters:** `~/.openclaw/` (CLI) and `~/.openclaw_prod/` (workers) can diverge. The 2026-04-15 auth outage was caused by `~/.openclaw_prod/` having `model: gemini-3-flash-preview` while `~/.openclaw/` had `MiniMax-M2.7`. Always check the worker config first for auth issues.

### 1. Is AO lifecycle-worker and orchestrator running?
```bash
# Lifecycle-worker
launchctl list com.agentorchestrator.lifecycle-jleechanclaw

# Orchestrator — sessions are hash-prefixed, NEVER use hard-coded "ao-orchestrator"
# Correct pattern:
orch_session=$(tmux list-sessions 2>/dev/null | grep "ao-orchestrator" | cut -d: -f1)
if [ -n "$orch_session" ]; then
  echo "ao-orchestrator FOUND: $orch_session"
  tmux capture-pane -t "$orch_session" -p -S -10
else
  echo "ao-orchestrator NOT FOUND"
fi
```
```bash
launchctl list com.agentorchestrator.lifecycle-jleechanclaw
tail -20 /tmp/ao-lifecycle-jleechanclaw.log
```

### 3. Are sessions being spawned?
```bash
tmux list-sessions | grep -E "^[a-z]{2}-[0-9]+"
ao session ls --project agent-orchestrator 2>/dev/null || echo "ao session ls failed"
```

### 4. Are sessions doing work? (or idle/zombie)
```bash
# For each jc-* session, check if agent is alive
tmux list-sessions -F '#{session_name}' | grep jc- | while read s; do
  cmd=$(tmux list-panes -t "$s" -F '#{pane_current_command}' 2>/dev/null)
  echo "$s: $cmd"
done
```

### 5. What are the non-green reasons per PR?
```bash
gh pr list --repo jleechanorg/agent-orchestrator --state open \
  --json number,title,mergeable,mergeStateStatus,reviewDecision

```

### 6. Is CR rate-limited?
```bash
gh api repos/jleechanorg/jleechanclaw/issues/comments?per_page=5 | \
  python3 -c "import json,sys; [print(c['user']['login'],c['body'][:100]) for c in json.load(sys.stdin) if 'rate limit' in c['body'].lower()]"
```

### 7. Is draft readiness + `/green` working correctly?
```bash
# Verify current-head CI and mergeability, and current-candidate applicability of required gate artifacts.
# Follow pr-lifecycle: use a reasoned SHA-binding assessment for earlier receipts;
# retain original tested/reviewed SHAs and timestamps; affected or uncertain coverage requires independent review.
gh api repos/jleechanorg/agent-orchestrator/pulls/<PR_NUM> --jq '{head:.head.sha,mergeable,mergeable_state,draft}'
```

### 8. Is the stray-worktree bug blocking spawns?
```bash
git -C ~/.openclaw worktree list | grep -v "~/.openclaw\b\|~/.worktrees"
# Any /private/tmp/ or unexpected paths = stray worktree blocking new spawns
```

## Full diagnostic sweep (Group A + Group B, run in parallel)

For a comprehensive /auton run, run **Group A** (infrastructure & session state) and **Group B** (GitHub & rate limits) together for speed, then cross-reference.

### Group A — Infrastructure & Session State

```bash
# A1–A2. Use ../ao-session-monitor/SKILL.md for orchestrator and worker state.
# Before any state verdict, follow ~/.codex/AGENTS.md's full-buffer rule and
# verify the session's current process/activity evidence.

# A3. Is AO lifecycle-worker running? Check per-project (7 projects = 7 workers is normal)
lw_count=$(ps aux | grep -c "[l]ifecycle-worker")
lw_per_project=$(ps aux | grep "[l]ifecycle-worker" | awk '{print $NF}' | sort -u | wc -l | tr -d ' ')
echo "Lifecycle-worker process count: $lw_count (unique projects: $lw_per_project)"
# Only flag as duplicate if same project appears more than once
ps aux | grep "[l]ifecycle-worker" | awk '{print $NF}' | sort | uniq -d | while read dup; do
  echo "⚠️  DUPLICATE lifecycle-worker for project: $dup"
  ps aux | grep "[l]ifecycle-worker" | grep "$dup"
done

# A3b. ZOMBIE SESSION DETECTION — cross-reference AO session store vs tmux
# Sessions marked "killed" in AO but still alive in tmux are zombies — lifecycle-worker won't manage them
echo "--- AO session store state (agent-orchestrator project) ---"
ao session ls --project agent-orchestrator 2>/dev/null || echo "ao session ls failed"
echo "--- Zombie check: AO-marked-killed sessions still in tmux ---"
AO_DATA=$(ls ~/.agent-orchestrator/bb5e6b7f8db3-agent-orchestrator/sessions/ 2>/dev/null)
for s in $AO_DATA; do
  sfile=~/.agent-orchestrator/bb5e6b7f8db3-agent-orchestrator/sessions/$s
  [ -f "$sfile" ] || continue
  status=$(grep "^status=" "$sfile" 2>/dev/null | cut -d= -f2)
  tmux_name=$(grep "^tmuxName=" "$sfile" 2>/dev/null | cut -d= -f2)
  [ "$status" = "killed" ] || continue
  # Guard: skip sessions with empty tmuxName (old metadata files) — avoids false positives
  [ -n "$tmux_name" ] || continue
  # Check if the tmux session is still alive
  if tmux has-session -t "$tmux_name" 2>/dev/null; then
    pr=$(grep "^pr=" "$sfile" | cut -d= -f2 | grep -oE "[0-9]+$")
    echo "  ZOMBIE: $s (tmux=$tmux_name, PR=#$pr) — AO=killed but tmux still running"
  fi
done

# A4. Is the orchestrator launchd service running? (ao-pr-poller is DEPRECATED — check ai.agento.orchestrators instead)
echo "=== Orchestrator launchd service ==="
launchctl print gui/$(id -u)/ai.agento.orchestrators 2>/dev/null | grep -E "state|PID" | head -5 || echo "ai.agento.orchestrators: NOT REGISTERED"
tail -5 /tmp/ao-orchestrators.log 2>/dev/null || echo "No orchestrator log"

# A5. Stray worktrees blocking spawns?
git -C ~/.openclaw worktree list 2>/dev/null | grep -v "~/.openclaw\b\|~/.worktrees" || true
```

### Group B — GitHub & Rate Limits

```bash
# B1. Rate limits — check before making API calls
gh api rate_limit --jq '.resources | {core: .core.remaining, graphql: .graphql.remaining}'

# B2. Open PRs with status
gh pr list --repo jleechanorg/agent-orchestrator --state open --json number,title,mergeable,reviewDecision,statusCheckRollup --jq '.[] | {number, title, mergeable, reviewDecision, ci: (.statusCheckRollup // [] | map(select(.conclusion != "")) | map(.conclusion) | unique)}'

# B3. Non-green reasons from poller log
tail -100 /tmp/ao-pr-poller.log 2>/dev/null | grep -E "not green|SKIP|WARNING|ERROR" | tail -20

# B4. Recent spawning activity
tail -50 /tmp/ao-pr-poller.log 2>/dev/null | grep -E "Spawning|SUCCESS" | tail -10

# B5. PR worker coverage check (deterministic — exits non-zero if uncovered PRs)
$HOME/.openclaw/scripts/check-pr-worker-coverage.sh 2>/dev/null || echo "Coverage script not found or returned non-zero (uncovered PRs exist)"
```

### Cross-reference — CHANGES_REQUESTED gap detection

After both groups complete, cross-reference:
1. List PRs with `reviewDecision: CHANGES_REQUESTED`
2. Check if each CR_REQ PR has an active worker session (from Group A2)
3. If a CR_REQ PR has **no active session**, flag it as a gap — the orchestrator should be addressing it

### PRs without recent commits

A long gap since the last commit is a prompt to inspect the current PR and
worker, not proof that work stalled. Re-pin the PR head, read the full session
history under the shared buffer rule, and verify current process/activity
evidence before classifying it. If the state cannot be established, report it
as `UNVERIFIED` and include the exact evidence still needed.

### Zero-Touch PR Measurement

Use the canonical `~/.claude/skills/zero-touch/SKILL.md` definition and retain
its evidence boundary. Measure the worker's contribution to reaching a
mergeable-quality PR; do not infer zero-touch status from who merged the PR or
from a reviewer bot's state. Final merge authorization remains separate.

### Sessions associated with merged or closed PRs

A merged or closed PR is a reason to inspect its worker session, not proof that
the session is idle or disposable. Read the full session history and verify
current process/worktree ownership before reporting its state. Do not terminate
sessions automatically; follow the owning cleanup procedure and authorization.

### Full diagnostic report output format

```
## Autonomy Diagnostic — <date>

### System health
- Poller: RUNNING / STOPPED / ERRORING
- AO lifecycle-worker: RUNNING / STOPPED (count: N) ⚠️ if >3
- Orchestrator session: SPAWNING / IDLE / STUCK / NOT FOUND
- Active worker sessions: N (M working, K idle, J completed)
- Rate limits: core=N, graphql=N
- Open PRs: N total, N non-green

### Orchestrator state
<What the orchestrator is doing based on tmux capture — spawning new sessions? idle? stuck on error?>

### Per-PR status
| PR | Non-green reason | Session | Session state | Activity |
|---|---|---|---|---|
| #NNN | <reason> | ao-NNN / none | WORKING/IDLE/COMPLETED/QUEUED | <indicator or "—"> |

### CHANGES_REQUESTED gaps
<List PRs with CR CHANGES_REQUESTED that have NO active session — these need attention>
(If none, say "All CR_REQ PRs have active sessions ✓")

### Stalled PRs (>1hr gap, not readiness-complete)
| PR | Gap | Review state | Mergeable | Worker | Title |
|---|---|---|---|---|---|
<List each stalled PR. If worker=no, this is a coverage gap requiring ao spawn.>
(If none, say "No stalled PRs ✓")

### Zombie session check
<Sessions where AO status=killed but tmux still alive — lifecycle-worker is NOT managing these>
| Session | AO status | tmux alive | PR | Action needed |
(If none, say "No zombie sessions ✓")

### AO session store vs tmux desync
<"ao session ls" result vs tmux count — if AO says 0 active but tmux has sessions, flag as desync>

### Lifecycle-worker duplicate check
<Count per project — only flag if SAME PROJECT has >1 worker. Multi-project = expected.>

### Recent Merge Quality (last 7 days)
For each recently merged PR, report the observed merge actor as a fact and
assess readiness using the current PR lifecycle evidence. Do not infer
zero-touch status from the merge actor. Use the canonical `pr-lifecycle`,
`pr-green-definition`, and `zero-touch` skills.

### Zero-Touch Rate (last 7 days)
| Metric | Value |
|---|---|
| Total merged | N |
| Zero-touch (per `zero-touch` skill: no pre-green human/terminal intervention) | N (NN%) |
| Operator-assisted (human/terminal touched the branch before green) | N (NN%) |
<List zero-touch PRs by number>

### Root cause
<Primary reason the system is not progressing PRs autonomously>

### Recommended fix
<Concrete next step>
```

This full-sweep output format is the report to use for a live/comprehensive `/auton` run. The "Output format" section further below is the retrospective 48h-worker-review format — use whichever fits the invocation (or both, if doing a full retrospective + live-state run).

## Common failure modes

| Symptom | Root cause | Fix |
|---|---|---|
| Sessions spawn but die immediately | `--claim-pr` fails (stray worktree) | clear stale paths / targeted unlock |
| Sessions alive but no pushes | Agent hits rate limit or auth failure | Check agent logs, re-auth |
| Optional reviewer has not approved | No required-gate failure established | Read useful feedback if present; do not wait on optional reviewers |
| Draft checks pass but PR never becomes ready | readiness transition missing | Verify applicable gate coverage and the ready transition per `pr-lifecycle`, including a reasoned SHA-binding assessment of earlier receipts without relabeling original tested/reviewed SHAs and timestamps |
| `/green` appears to pass but CI is pending | stale or incomplete status evaluation | Use the canonical current-head `/green` query |
| `/tmp/ao-pr-poller.log` missing | **NOT A BUG** — ao-pr-poller is deprecated/removed | Ignore; its absence is correct and expected |
| PR has required human review feedback | Worker has not addressed a required review | Check the target repository's current review contract |
| Spawned sessions are idle shells | `is_agent_alive_in_session` returns false | Check Hermes gateway is running (`hermes gateway status`) |

## Worker Session Review (48h fanout)

When diagnosing autonomy health, **read every active worker session** from the last 48h and produce an outcome table. This is mandatory for any /auton run — system-level health checks alone miss per-worker failure classes.

### Step 1 — Enumerate 48h sessions

```bash
# Sessions created in last 48h
tmux list-sessions -F '#{session_name} #{session_created}' | awk -v cutoff=$(date -v-48H +%s 2>/dev/null || date -d '48 hours ago' +%s) '$2 > cutoff {print $1}'

# AO status summary (shows branch, PR, CI, steer count)
ao status 2>/dev/null
```

### Step 2 — Read each session (parallel)

For each worker session, read the full available transcript before assessing
it, then inspect the latest lines for current state. Follow the shared
full-buffer rule and `../ao-session-monitor/SKILL.md`; do not pipe a partial
capture through `tail` or classify a session from a short excerpt.

Extract per-session:
- **Task**: what prose was in the initial spawn?
- **PR produced**: branch + PR number (if any)
- **Outcome**: MERGED / GREEN-AWAITING / OPEN-NOT-READY / IDLE / MIS-SPAWNED
- **Steers**: count of `ao send` corrections or redirections visible in transcript
- **Blocker**: one-line root cause if not merged

### Step 3 — Cross-check PR states

```bash
gh pr view <N> --repo <owner>/<repo> --json state,merged,mergeable,reviewDecision
```

### Worker outcome table format

```
| Worker | Repo | PR | Outcome | Steers | Key Issue |
|--------|------|----|---------|----|-----------|
| ao-NNNN | repo | #N branch | MERGED ✅ / GREEN ✅ / OPEN ⚠️ / IDLE ❌ | N | one-line |
```

## Root Cause Taxonomy

These are the observed failure classes across 48h windows. Assign each stalled worker exactly one root cause:

| Class | Name | Symptom | Fix |
|-------|------|---------|-----|
| RC-1 | **Spawn context gap** | Worker asked "what task should I do?" — no task prose in spawn | Always include prose: `ao spawn --bead bd-xxx "Implement X: ..."` |
| RC-2 | **Scope drift** | Worker documented the problem instead of solving it (PR title contains "docs" when impl was requested) | Send `ao send <session> "DRIVER: implement, not document. Fix <file>:<line>"` |
| RC-3 | **Stall-without-escalate** | Worker went idle at a gate (CI, draft gates) without sending `ao send` to orchestrator | Steer worker with DRIVER mode |
| RC-4 | **Wrong-bead correction** | Worker pivoted to merged/non-existent bead after receiving correction | Always `br show <bead>` before sending any `ao send` correction |
| RC-5 | **Hook noise** | `PostToolUse hook error: unbound variable` slowing worker but not blocking | Fix hook script (`pr_create_pattern` unbound var); non-critical if worker still progresses |
| RC-6 | **Context exhaustion** | Worker context hit limit mid-task; state partially preserved in handoff | Check session for "context is N% remaining" lines; spawn fresh worker with recap |
| RC-7 | **Auth / model failure** | Worker gets 401 or model-not-found after SCM failures | Check `AO_CONFIG_PATH` env; verify API key; restart worker |

## Autonomy Metrics

Report these at the end of every /auton run:

| Metric | Definition | Target |
|--------|-----------|--------|
| **End-to-end success rate** | (MERGED + GREEN-AWAITING) / total workers in window | >60% |
| **Avg steers/worker** | total human steers / workers | <0.5 |
| **Spawn context gap rate** | mis-spawned workers / total | 0% |
| **Stall rate** | Verified stalled workers / total | <20% |

## Output format

```
## Autonomy Diagnostic — <date>

### System health
- AO lifecycle-worker: RUNNING / STOPPED
- Orchestrator session: FOUND (hash-prefixed name) / NOT FOUND
- Active sessions: N (M with live agents)
- Open PRs: N total, N non-green

### Worker session review (48h)
| Worker | Repo | PR | Outcome | Steers | Key Issue |
|--------|------|----|---------|----|-----------|
| ... | ... | ... | ... | ... | ... |

### Per-PR status
| PR | Non-green reason | Session | Session state |
|---|---|---|---|
| #NNN | <reason from log> | jc-NNN | alive/zombie/none |

### Root causes (by class)
- RC-1 Spawn context gap: N workers (list sessions)
- RC-2 Scope drift: N workers
- RC-3 Stall-without-escalate: N workers
- ...

### Metrics
- End-to-end success rate: N% (target >60%)
- Avg steers/worker: N (target <0.5)
- Spawn context gap rate: N% (target 0%)
- Stall rate: N% (target <20%)

### Recommended fixes (ordered by impact)
1. <most impactful fix first>
```
