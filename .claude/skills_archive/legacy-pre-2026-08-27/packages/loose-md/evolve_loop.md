---
name: evolve_loop
description: Generic autonomous improvement loop — observe, measure, diagnose, fix, repeat. System-agnostic framework; configure a system profile to target any repo/agent/IDE ecosystem.
type: skill
---

## Purpose

Autonomous self-improving loop that observes a target system, measures its quality metric, diagnoses friction, creates beads for gaps, dispatches fixes, and records everything. Runs via `/loop 10m /eloop` for max 12 hours.

---

## System Profile (configure per target system)

The loop is driven by a **system profile** — a set of parameters that describe what to observe and how to measure health. The default profile targets AO + Antigravity.

```
SYSTEM_NAME:        AO + Antigravity
QUALITY_METRIC:     [agento] zero-touch rate (autonomous PR merges / total PR merges)
REPOS:              jleechanorg/agent-orchestrator, jleechanorg/worldai_claw, jleechanorg/jleechanclaw
WORKER_PATTERN:     tmux sessions matching (ao|jc|wa|cc|ra|wc)-[0-9]+
IDE_MONITOR:        Antigravity (via /antig skill)
ISSUE_TRACKER:      br (beads, .beads/issues.jsonl)
FINDINGS_LOG:       roadmap/evolve-loop-findings.md
AUTOMATION_CODE:    .github/workflows/skeptic-cron.yml, packages/core/src/lifecycle-manager.ts, ~/.openclaw/agent-orchestrator.yaml
HEALTHY_THRESHOLD:  20% (below = chronic problem, triggers code-level diagnosis)
```

To apply this loop to a different system, replace the profile values. The 7 phases work unchanged.

---

## Adaptive Behavior — NOT Every Phase Every Cycle

This loop is problem-driven:
- **Healthy cycle** (~30s): Observe → Measure → Recap "all good, waiting"
- **Problem cycle** (~5min): Observe → Measure → Diagnose → Plan → Record → Fix → Recap

Decision tree after Phase 2 (Measure):
- Quality metric unchanged AND above HEALTHY_THRESHOLD AND no new friction AND all workers alive → SKIP to Phase 7 (Recap)
- Quality metric below HEALTHY_THRESHOLD for 3+ consecutive cycles → run Phase 3-6 with code-level diagnosis
- New dead worker or new failure → run Phase 3-6
- Worker stuck (same output 3 checks) → kill + respawn, skip full diagnosis
- Build broken on main → fix immediately

---

## Loop Body (executed every 10 minutes)

### Phase 1: OBSERVE — System State Snapshot

**1a. Check external IDE/agent** (if IDE_MONITOR configured):
- Invoke the IDE monitor skill (e.g., `/antig` for Antigravity)
- Check liveness, scan for blocking dialogs, steer if idle + open work exists

**1b. Check worker sessions** — for each repo in REPOS:
```bash
# List active worker sessions
tmux list-sessions 2>/dev/null | grep -E '<WORKER_PATTERN>'

# Open work items per repo
for repo in <REPOS>; do
  gh api "repos/$repo/pulls?state=open&per_page=20" \
    --jq '.[]|"\(.number) \(.head.ref) \(.mergeable_state)"' 2>/dev/null
done
```

**1c. Read worker conversations** — capture last 30 lines from each active session. Look for:
- Stuck patterns (same output for 10+ min)
- Error loops (repeated failures)
- Waiting for input
- Context exhaustion (>80%)

```bash
for sess in $(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '<WORKER_PATTERN>'); do
  echo "=== $sess ==="
  tmux capture-pane -t "$sess" -p 2>/dev/null | tail -30
done
```

**1d. Zombie sweep** — kill workers burning tokens on already-closed work:
```bash
for sess in $(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '<WORKER_PATTERN>'); do
  # Determine repo from session name pattern
  # Check if associated work item (PR/issue) is closed/merged
  # If yes: kill session
  tmux kill-session -t "$sess" 2>/dev/null
done
```

**1e. Read friction narratives** — check for recent entries in any friction log (e.g., `novel/`, `docs/novel/`):
```bash
find novel/ docs/novel/ -name '*.md' -newer /tmp/evolve_loop_last_run 2>/dev/null
```

### Phase 2: MEASURE — Quality Metric

Calculate the system's QUALITY_METRIC. For AO + Antigravity, this is [agento] zero-touch rate:

```bash
# Merged work items in last 24h — what fraction were fully autonomous?
gh api 'repos/<PRIMARY_REPO>/pulls?state=closed&per_page=30&sort=updated&direction=desc' \
  --jq '.[] | select(.merged_at != null and .merged_at > "<YESTERDAY_ISO>") |
    {number, title: .title[:70], autonomous: (.title | test("^\\[agento\\]"))}'
```

For each **non-autonomous** merged item, determine WHY:
- Missing prefix/tag (tagging gap) → bead if no existing bead
- Operator had to fix directly → bead for root cause
- Manual conflict resolution → bead for conflict pattern
- Review required operator action → bead for review automation gap

### Phase 3: DIAGNOSE — Root Cause Analysis

**3a.** Run `/harness` on each new friction point.

**3b.** Check existing beads — don't duplicate:
```bash
br list --open 2>/dev/null | head -30
```

**3c. Stale bead detection** — in_progress beads with no active worker are zombies:
```bash
cat .beads/issues.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('status') == 'in_progress':
            print(f\"{d['id']} | {d.get('title','')[:60]}\")
    except: pass
" 2>/dev/null
```

**3d. Automation code audit** (when quality metric chronically below HEALTHY_THRESHOLD):
Read AUTOMATION_CODE files — look for bugs in the pipeline vs what the healthy definition requires. Log specific bugs.

### Phase 4: PLAN — Next Steps

Run `/nextsteps` — situational assessment and roadmap update.

Prioritize fixes by impact on quality metric:
- P0: Fixes that unblock multiple stalled items
- P1: Fixes that prevent recurring friction patterns
- P2: Nice-to-have improvements

### Phase 5: RECORD — Findings + Push

**5a.** Create/update beads for each new friction point:
```bash
br create --priority P1 --title "..." --body "..." 2>/dev/null
```

**5b.** Append findings to FINDINGS_LOG:
```markdown
## YYYY-MM-DD HH:MM cycle

### Quality metric: X% (N/M)
### New friction points: [list]
### Fixes dispatched: [list]
### Beads created: [list]
```

**5c.** Push to origin:
```bash
git add <FINDINGS_LOG> .beads/issues.jsonl
git commit -m "docs(evolve): cycle YYYY-MM-DD HH:MM — quality X%, N friction points"
git push origin main
```

### Phase 6: FIX — Dispatch Workers

**6a.** Use `/claw` for each actionable bead:
```bash
/claw "Fix <bead-id>: <description>.

After implementing:
1. Run /er on the PR evidence bundle
2. Ensure system's green definition (all gates pass)
3. Run /learn to capture reusable patterns"
```

**6b.** Babysit open work items — for each item without a live worker:
- If CI failing → dispatch worker to fix
- If review CHANGES_REQUESTED → dispatch worker to address + re-request review
- If evidence gate failing → run `/er` inline
- If all gates green → merge immediately

**6c.** Run `/er` on items approaching full-green — validate evidence NOW, don't wait for a worker.

**6d.** If `/claw` fails (rate limit, session cap):
- Fall back to manual worktree + `claude --dangerously-skip-permissions` in tmux
- Or fix directly if small (config change, rules edit)
- Record the failure in a bead

**6e. Pre-merge gate check** (MANDATORY before ANY merge):
```bash
# Check all system green conditions before merging
# NEVER merge a work item that fails this check
# If not green: dispatch worker to fix — do not merge to show progress
```

### Phase 7: RECAP — Cycle Summary

```
## Evolve Loop Cycle — HH:MM
- Quality metric: X% (trend: ↑/↓/→)
- Workers: N alive, N dead, N stuck
- Open items: N open, N closed since last cycle
- Friction: N new points found
- Fixes: N dispatched, N direct
- Beads: N created, N updated
- Findings: pushed to FINDINGS_LOG
```

Touch timestamp:
```bash
touch /tmp/evolve_loop_last_run
```

---

## Invocation

```bash
# Start the loop
/loop 10m /eloop

# One cycle manually
/eloop

# With IDE monitor
/loop 10m /eloop and /antig — monitor worldai_claw Antigravity conversation (PIL Allow scan, steer agent, merge PRs at 7-green)
```

---

## Anti-Stall Rules

- If GraphQL is exhausted, switch to REST immediately — never sleep-retry
- If session cap is hit (>30), do not spawn — report and defer
- If a worker is stuck (same output 3 consecutive checks), kill and respawn
- If `/claw` fails twice on the same bead, fix directly
- If main repo is on wrong branch, fix it silently (`git checkout main`)
- If build is broken on main, fix it before dispatching workers

## Key Files (AO + Antigravity profile)

- `roadmap/evolve-loop-findings.md` — cumulative findings log
- `.beads/issues.jsonl` — bead tracker
- `~/.openclaw/SOUL.md` — zero-touch convention ([agento] prefix)
- `~/.openclaw/agent-orchestrator.yaml` — agentRules config
- `novel/` — worker friction narratives
