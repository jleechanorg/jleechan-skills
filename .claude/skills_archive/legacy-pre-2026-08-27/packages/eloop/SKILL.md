---
name: eloop
description: Autonomous improvement loop for AO + Antigravity — observe, measure, diagnose, fix, repeat. Targets zero-touch rate as quality metric.
type: skill
---

# eloop — Autonomous Self-Improving Loop

**Loop interval**: 10m | **Max duration**: 12h (72 iterations)

## Purpose

Autonomous self-improving loop that observes AO + Antigravity, measures zero-touch rate, diagnoses friction, creates beads for gaps, dispatches fixes via /claw, and records everything.

Invoked via `/loop 10m /eloop` or run manually with `/eloop`.

## System Profile

```
SYSTEM_NAME:        AO + Antigravity
QUALITY_METRIC:     zero-touch rate (autonomous PR merges / total PR merges)
REPOS:              jleechanorg/agent-orchestrator, jleechanorg/worldai_claw
WORKER_PATTERN:     tmux sessions matching (ao|jc|wa|cc|ra|wc)-[0-9]+
IDE_MONITOR:        Antigravity (via /antig skill)
ISSUE_TRACKER:      br (beads, .beads/issues.jsonl)
FINDINGS_LOG:       roadmap/evolve-loop-findings.md
AUTOMATION_CODE:    .github/workflows/skeptic-cron.yml, packages/core/src/lifecycle-manager.ts
HEALTHY_THRESHOLD: 20% (below = chronic problem, triggers code-level diagnosis)
```

## Loop Body (executed every 10 minutes)

### Phase 1: OBSERVE

```bash
# Worker sessions
tmux list-sessions 2>/dev/null | grep -E '(ao|jc|wa|cc|ra|wc)-[0-9]+' || echo "no workers"

# Open PRs across repos
for repo in jleechanorg/agent-orchestrator jleechanorg/worldai_claw; do
  gh api "repos/$repo/pulls?state=open&per_page=10" \
    --jq '.[]|"\(.number) \(.title[:60]) \(.mergeable_state)"' 2>/dev/null
done

# Worker output (last 20 lines)
for sess in $(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '(ao|jc|wa|cc|ra|wc)-[0-9]+'); do
  echo "=== $sess ==="; tmux capture-pane -t "$sess" -p 2>/dev/null | tail -20
done
```

### Phase 2: MEASURE

```bash
# Merged PRs in last 24h — zero-touch rate
gh api 'repos/jleechanorg/agent-orchestrator/pulls?state=closed&per_page=30&sort=updated&direction=desc' \
  --jq '.[] | select(.merged_at != null) | {number, title: .title[:70], autonomous: (.title | test("^\\[agento\\]"))}' \
  2>/dev/null | python3 -c "
import sys, json
merged = [json.loads(l) for l in sys.stdin if l.strip()]
autonomous = sum(1 for m in merged if m['autonomous'])
total = len(merged)
rate = autonomous/max(total,1)*100
print(f'Zero-touch: {autonomous}/{total} = {rate:.1f}%')
" 2>/dev/null || echo "no recent merges"
```

### Phase 3: DIAGNOSE

- Quality metric unchanged AND above 20% AND no new friction → **SKIP to Phase 7**
- Below 20% for 3+ cycles → run Phase 4-6 with code-level diagnosis
- New dead worker or failure → run Phase 4-6
- Worker stuck (same output 3 checks) → kill + respawn

```bash
# Stale in-progress beads
cat .beads/issues.jsonl 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('status') == 'in_progress':
            print(f\"{d['id']} | {d.get('title','')[:60]}\")
    except: pass
" | head -10
```

### Phase 4: PLAN

Run `/nextsteps` for situational assessment. Prioritize:
- P0: Unblock multiple stalled items
- P1: Prevent recurring friction
- P2: Nice-to-have

### Phase 5: RECORD

```bash
# Create beads for new friction
# Append to roadmap/evolve-loop-findings.md
git add roadmap/evolve-loop-findings.md .beads/issues.jsonl 2>/dev/null
git commit -m "docs(evolve): cycle $(date +%Y-%m-%d_%H:%M)" 2>/dev/null || true
```

### Phase 6: FIX

```bash
# Dispatch /claw for actionable beads
# Babysit open PRs — merge if green, fix if failing
# Run /er on items approaching full-green
```

### Phase 7: RECAP

```
## Evolve Loop Cycle — HH:MM
- Zero-touch rate: X% (trend: ↑/↓/→)
- Workers: N alive, N dead, N stuck
- PRs: N open, N merged since last cycle
- Friction: N new points
- Fixes: N dispatched, N direct
- Beads: N created, N updated
```

```bash
touch /tmp/evolve_loop_last_run
```

## Anti-Stall Rules

- GraphQL exhausted → switch to REST immediately
- Session cap hit (>30) → report and defer, don't spawn
- Worker stuck (3x same output) → kill and respawn
- /claw fails twice on same bead → fix directly
- Main repo on wrong branch → `git checkout main` silently
- Build broken on main → fix before dispatching

## Invocation

```bash
/loop 10m /eloop    # Start loop
/eloop              # One cycle manually
```

## Key Files

- `roadmap/evolve-loop-findings.md` — cumulative findings
- `.beads/issues.jsonl` — bead tracker
- `~/.openclaw/SOUL.md` — zero-touch convention ([agento] prefix)
- `~/.openclaw/agent-orchestrator.yaml` — agentRules config
- `novel/` — worker friction narratives