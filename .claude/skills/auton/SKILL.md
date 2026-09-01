---
name: auton
description: Diagnose why the automation system is not autonomously completing draft readiness and driving PRs to green. Invoked by `/auton`; measures canonical zero-touch readiness, detects stale sessions, and reviews worker outcomes.
---

# Autonomy Diagnostic Skill

## Purpose

**Run /auton AFTER a work block ends** — retrospective review of what workers did, what failed, and why. It is the post-mortem tool.

**Run /babysit WHILE work is happening** — live triage, parallel worker dispatch, DRIVER mode nudges. It is the concurrent monitoring tool.

| Skill | When | Mode | Output |
|-------|------|------|--------|
| `/babysit` | During active workers | Live monitoring, dispatch | Per-PR status, DRIVER nudges |
| `/auton` | After block completes | Retrospective | Outcome table, root causes, metrics |

When invoked, diagnose why the jleechanclaw + AO system is not autonomously
completing draft readiness and `/green`. Use the canonical `draft-first-pr`,
`pr-green-definition`, and `zero-touch` skills; historical N-green/Skeptic
machinery below must not override those current policies.

## Read first (mandatory before answering)

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
  ↓ agento: keeps the PR draft through /es, /er, and /advice
  ↓ agento: marks ready only after draft readiness passes
  ↓ CI passes and mergeability is rechecked through /green
  ↓ agento reports ready; merge remains separately human-authorized
```

**Key config to verify** (from the ACTIVE config — run Step 0 first):
```yaml
worker-signals-completion:
  auto: true
  action: skeptic-review
  skepticModel: codex
```
And the repo must have a healthy `skeptic-cron.yml` workflow. `approved-and-green` may still exist, but it is no longer the canonical merge executor.

If `worker-signals-completion` is missing, `auto: false`, or not `action: skeptic-review`, that is the local skeptic trigger gap.

**Full autonomy means: idea in → merged PR out, zero human clicks.**

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

# Verify skeptic-review trigger wiring (REQUIRED for autonomous reviewing):
python3 - <<'PY'
import yaml, os
# Try worker config first, fall back to CLI config
for path in [os.environ.get("AO_CONFIG_PATH", ""), "~/.openclaw_prod/agent-orchestrator.yaml", "~/.openclaw/agent-orchestrator.yaml"]:
    if path and os.path.exists(os.path.expanduser(path)):
        cfg = yaml.safe_load(open(os.path.expanduser(path)))
        print(f"Config: {path}")
        print(((cfg.get("reactions") or {}).get("worker-signals-completion") or {}))
        break
PY

# Verify skeptic-cron is present and running:
gh run list --repo jleechanorg/agent-orchestrator --workflow skeptic-cron.yml --limit 3
```

### 6. Is CR rate-limited?
```bash
gh api repos/jleechanorg/jleechanclaw/issues/comments?per_page=5 | \
  python3 -c "import json,sys; [print(c['user']['login'],c['body'][:100]) for c in json.load(sys.stdin) if 'rate limit' in c['body'].lower()]"
```

### 7. Is draft readiness + `/green` working correctly?
```bash
# Verify current-head CI, mergeability, and current-head /es, /er, /advice artifacts.
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
# A1. Orchestrator session — what is it doing?
tmux capture-pane -t ao-orchestrator -p -S -20 2>/dev/null || echo "ORCHESTRATOR SESSION NOT FOUND"

# A2. Worker session inventory with activity detection (30 lines each)
# Uses ao-session-monitor skill: capture 30 lines, look for Unicode activity indicators
for s in $(tmux list-sessions 2>/dev/null | grep -E "ao-[0-9]|jc-" | cut -d: -f1); do
  echo "=== SESSION: $s ==="
  last=$(tmux capture-pane -t "$s" -p -S -30 2>/dev/null)
  echo "$last" | tail -5
  echo "---"
  # Detect state via activity indicators (✻✶✳✽✾✢)
  activity=$(echo "$last" | grep -oE "[✻✶✳✽✾✢] [A-Za-z]+…[^)]*\)" | tail -1)
  pr=$(echo "$last" | grep -oE "#[0-9]+" | head -1)
  uc=""; echo "$last" | grep -q "uncommitted" && uc="+uncommitted"
  if [ -n "$activity" ]; then
    echo "STATE: WORKING $pr $uc ($activity)"
  elif echo "$last" | grep -qE "Running…|timeout"; then
    echo "STATE: WORKING (shell command) $pr $uc"
  elif echo "$last" | grep -qE "Baked|Sautéed"; then
    echo "STATE: COMPLETED $pr"
  elif echo "$last" | grep -q "queued"; then
    echo "STATE: QUEUED $pr"
  else
    echo "STATE: IDLE $pr $uc"
  fi
  echo ""
done

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

### Stalled PR detection (>1hr gap, not draft-ready + `/green`)

For every open PR, check last commit date and compare to current UTC time. Flag any PR that:
- Has incomplete draft readiness or is not `/green`
- Has >1 hour since the last commit with no visible progress

```bash
# Stall detection — REST API (works even when GraphQL=0)
current_epoch=$(date -u +%s)
echo "=== STALLED PR DETECTION (>1hr gap, not readiness-complete) ==="
for pr_json in $(gh api "repos/jleechanorg/agent-orchestrator/pulls?state=open" --jq '.[] | @base64' 2>/dev/null); do
  pr=$(echo "$pr_json" | base64 -d 2>/dev/null || echo "$pr_json" | base64 -D 2>/dev/null)
  number=$(echo "$pr" | jq -r '.number')
  title=$(echo "$pr" | jq -r '.title[0:60]')
  mergeable=$(echo "$pr" | jq -r '.mergeable_state')
  branch=$(echo "$pr" | jq -r '.head.ref')

  # Get last commit date
  last_commit=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$number/commits" --jq '.[-1].commit.committer.date' 2>/dev/null)
  commit_epoch=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$last_commit" +%s 2>/dev/null || echo 0)
  gap_mins=$(( (current_epoch - commit_epoch) / 60 ))

  # Get review state
  review_state=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$number/reviews" --jq '[.[] | select(.state != "COMMENTED")] | last | .state // "NONE"' 2>/dev/null)

  # Flag if >60 min gap
  if [ "$gap_mins" -gt 60 ]; then
    # Check if worker session exists for this branch
    has_worker="no"
    for s in $(tmux list-sessions 2>/dev/null | grep -E "ao-[0-9]+|jc-[0-9]+" | cut -d: -f1); do
      s_branch=$(tmux capture-pane -t "$s" -p 2>/dev/null | grep -oE "Branch: [^ ]+" | tail -1 | sed 's/Branch: //')
      [ "$s_branch" = "$branch" ] && has_worker="$s" && break
    done
    gap_hrs=$((gap_mins / 60))
    echo "STALLED #$number | ${gap_hrs}h${gap_mins}m | review=$review_state | mergeable=$mergeable | worker=$has_worker | $title"
  fi
done
```

### Zero-Touch PR Measurement

Measure how many merged PRs were truly autonomous. Zero-touch is defined canonically in the `zero-touch` skill (`~/.claude/skills/zero-touch/SKILL.md`): it measures AO's autonomy in *producing* a mergeable-quality PR (no human/terminal intervention before it reached green), not who executes the final merge. If this target repo still has a working auto-merge bot (e.g. `github-actions[bot]` via a skeptic-cron-style gate), `merged_by` is a useful proxy signal for that repo's merge automation — but do not treat "merged_by != github-actions[bot]" as automatically operator-assisted without first confirming whether this repo still has an auto-merge mechanism (it was removed in `$GITHUB_REPOSITORY` by PR #8217 — verify this repo's own status before assuming the same).

```bash
# Zero-touch readiness + merge quality — last 7 days
echo "=== MERGE QUALITY AUDIT (last 7 days) ==="
cutoff=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ)
auto=0; manual=0; total=0
for pr_json in $(gh api "repos/jleechanorg/agent-orchestrator/pulls?state=closed&sort=updated&direction=desc&per_page=50" --jq "[.[] | select(.merged_at != null) | select(.merged_at > \"$cutoff\")] | .[] | @base64" 2>/dev/null); do
  pr=$(echo "$pr_json" | base64 -D 2>/dev/null || echo "$pr_json" | base64 -d 2>/dev/null)
  number=$(echo "$pr" | jq -r '.number')
  title=$(echo "$pr" | jq -r '.title[0:50]')
  merged_by=$(echo "$pr" | jq -r '.merged_by.login')
  total=$((total + 1))
  if [ "$merged_by" = "github-actions[bot]" ]; then
    auto=$((auto + 1))
    echo "  AUTO-MERGED #$number (by $merged_by) $title"
  else
    manual=$((manual + 1))
    echo "  MANUAL #$number (by $merged_by) $title"
  fi
done
echo ""
echo "TOTAL MERGED: $total | AUTO (skeptic-cron): $auto | MANUAL: $manual"
if [ "$total" -gt 0 ]; then
  rate=$((auto * 100 / total))
  echo "ZERO-TOUCH RATE: ${rate}% ($auto/$total auto-merged by skeptic-cron)"
fi
```

### Skeptic-cron correctness spot-check

Pick one APPROVED PR (if any exist) and verify skeptic-cron's gate checks agree with reality:

```bash
echo "=== SKEPTIC-CRON CORRECTNESS SPOT-CHECK ==="
# Find an APPROVED PR
APPROVED_PR=$(gh api "repos/jleechanorg/agent-orchestrator/pulls?state=open" \
  --jq '[.[] | select(.draft == false)] | .[0].number' 2>/dev/null)
if [ -n "$APPROVED_PR" ]; then
  echo "Spot-checking PR #$APPROVED_PR"

  # Gate 3: CR state — must filter to actionable reviews (APPROVED/CHANGES_REQUESTED), not COMMENTED
  CR_ACTIONABLE=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$APPROVED_PR/reviews" \
    --jq '[.[] | select(.user.login == "coderabbitai[bot]") | select(.state == "APPROVED" or .state == "CHANGES_REQUESTED")] | sort_by(.submitted_at) | last | .state // "none"' 2>/dev/null)
  CR_LATEST=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$APPROVED_PR/reviews" \
    --jq '[.[] | select(.user.login == "coderabbitai[bot]")] | sort_by(.submitted_at) | last | .state // "none"' 2>/dev/null)
  if [ "$CR_ACTIONABLE" != "$CR_LATEST" ]; then
    echo "  MISMATCH Gate 3: actionable=$CR_ACTIONABLE vs latest=$CR_LATEST (skeptic-cron uses latest — BUG)"
  else
    echo "  Gate 3 OK: $CR_ACTIONABLE"
  fi

  # Gate 5: Unresolved comments — REST has no isResolved
  REST_COMMENTS=$(gh api "repos/jleechanorg/agent-orchestrator/pulls/$APPROVED_PR/comments" \
    --jq '[.[] | select(.in_reply_to_id == null)] | length' 2>/dev/null)
  GQL_UNRESOLVED=$(gh api graphql -f query='query($owner:String!,$repo:String!,$pr:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$pr){reviewThreads(first:100){nodes{isResolved}}}}}' \
    -f owner="jleechanorg" -f repo="agent-orchestrator" -F pr="$APPROVED_PR" \
    --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length' 2>/dev/null || echo "graphql_failed")
  if [ "$REST_COMMENTS" != "$GQL_UNRESOLVED" ]; then
    echo "  MISMATCH Gate 5: REST root comments=$REST_COMMENTS vs GraphQL unresolved=$GQL_UNRESOLVED (skeptic-cron uses REST — BUG if REST>0)"
  else
    echo "  Gate 5 OK: $GQL_UNRESOLVED unresolved"
  fi

  # Check last skeptic-cron run
  LAST_CRON=$(gh api "repos/jleechanorg/agent-orchestrator/actions/workflows/skeptic-cron.yml/runs?per_page=3" \
    --jq '.workflow_runs[] | "\(.conclusion) \(.created_at[0:16])"' 2>/dev/null)
  echo "  Last skeptic-cron runs: $LAST_CRON"
fi
```

### Merged-PR zombie detection

For every active worker session, check if its associated PR is merged/closed. Workers on merged PRs are zombies burning tokens. **If zombies are found, kill them immediately** — they waste tokens and block worker capacity.

```bash
echo "=== MERGED-PR ZOMBIE DETECTION ==="
for sess in $(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '(ao|jc|wa|wc)-[0-9]+'); do
  pr_num=$(tmux capture-pane -t "$sess" -p 2>/dev/null | grep -oE "PR: #[0-9]+" | head -1 | grep -oE "[0-9]+")
  [ -z "$pr_num" ] && continue
  # Detect repo from session prefix
  case "$sess" in
    ao-*) repo="jleechanorg/agent-orchestrator" ;;
    jc-*) repo="jleechanorg/jleechanclaw" ;;
    wa-*) repo="${GITHUB_REPOSITORY:-$GITHUB_REPOSITORY}"  ;; # set GITHUB_REPOSITORY or hardcode your wa-* repo here
    wc-*) repo="jleechanorg/worldai_claw" ;;
    *) continue ;;
  esac
  merged=$(gh api "repos/$repo/pulls/$pr_num" --jq '.merged' 2>/dev/null)
  if [ "$merged" = "true" ]; then
    echo "  ZOMBIE: $sess on PR #$pr_num ($repo) — PR is MERGED, kill this session"
  fi
done
```

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
For each recently merged PR, check and report:
| PR | merged_by | Draft readiness + `/green` at merge? | Missing proof |
|---|---|---|---|
| #NNN | github-actions[bot] / jleechan2015 | YES/NO | current-head artifacts |

- **Zero-touch** (per the canonical skill) = AO completed draft readiness and `/green` with no human/terminal intervention before that point
- `merged_by=github-actions[bot]` is a useful proxy ONLY on repos that still have a working auto-merge bot — confirm this repo's status first rather than assuming
- Always use the canonical `draft-first-pr`, `pr-green-definition`, and `zero-touch` skills

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
| CR never APPROVED | Rate limited (too many PRs) | Wait for limit reset, or reduce simultaneous PRs |
| Draft checks pass but PR never becomes ready | readiness transition missing | Verify current-head `/es`, `/er`, `/advice` and ready transition |
| `/green` appears to pass but CI is pending | stale or incomplete status evaluation | Use the canonical current-head `/green` query |
| `/tmp/ao-pr-poller.log` missing | **NOT A BUG** — ao-pr-poller is deprecated/removed | Ignore; its absence is correct and expected |
| PRs cycling CR changes_requested | Agent not reading CR comments correctly | Check agento's comment-reading skill |
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

For each worker session:
```bash
tmux capture-pane -t <session> -p -S -5000 | tail -300
```

Extract per-session:
- **Task**: what prose was in the initial spawn?
- **PR produced**: branch + PR number (if any)
- **Outcome**: MERGED / GREEN-AWAITING / OPEN-STALLED / IDLE / MIS-SPAWNED
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
| RC-3 | **Stall-without-escalate** | Worker went idle at a gate (CR, CI, skeptic) without sending `ao send` to orchestrator or posting `/skeptic` | Post `/skeptic` on PR; steer worker with DRIVER mode |
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
| **Stall rate** | OPEN-STALLED / total | <20% |

## Output format

```
## Autonomy Diagnostic — <date>

### System health
- AO lifecycle-worker: RUNNING / STOPPED
- Orchestrator session: FOUND (hash-prefixed name) / NOT FOUND
- Skeptic-review hook: worker-signals-completion auto=true/false, action=X
- Skeptic-cron workflow: RUNNING / FAILING / NOT FOUND
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
