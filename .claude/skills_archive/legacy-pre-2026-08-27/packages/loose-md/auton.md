# Autonomy Diagnostic Skill

## Purpose

When invoked, diagnose WHY the jleechanclaw + AO system is NOT autonomously driving PRs to 6 green and merged. The system is supposed to do this without human intervention — if it isn't, something is broken.

## Read first (mandatory before answering)

1. `~/.openclaw/CLAUDE.md` — repo goals, PR green definition, autonomy target
2. `~/.codex/AGENTS.md` — agent policies
3. `~/.openclaw/agent-orchestrator.yaml` — AO project config (worktreeDir, backfillAllPRs, notifiers, reactions)
4. `~/.openclaw/SOUL.md` — openclaw decision-making policy

**NOTE: ao-pr-poller is DEPRECATED and removed. Do NOT check for it or report its absence as a problem.**

## The system's intended behavior

```
AO lifecycle-worker (every ~5 min via launchd)
  ↓ detects non-green PR (backfillAllPRs: true)
  ↓ spawns agento session (ao spawn --claim-pr)
  ↓ agento: reads comments, fixes code, pushes
  ↓ agento: posts @coderabbitai all good?
  ↓ agento: runs /er evidence review
  ↓ CI passes, CR APPROVED, Bugbot neutral, comments resolved
  ↓ approved-and-green reaction fires → auto-merge (auto: true, action: auto-merge)
```

**Key config to verify**: `~/.openclaw/agent-orchestrator.yaml` must have:
```yaml
reactions:
  approved-and-green:
    auto: true
    action: auto-merge
```
If `auto: false` or missing — that is the merge executor gap.

**Full autonomy means: idea in → merged PR out, zero human clicks.**

## Diagnostic questions (answer each with evidence)

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

# Also verify auto-merge config (REQUIRED for autonomous merging):
grep -A3 "approved-and-green" ~/.openclaw/agent-orchestrator.yaml | grep -E "auto:|action:"
# Expected: auto: true, action: auto-merge
```

### 6. Is CR rate-limited?
```bash
gh api repos/jleechanorg/jleechanclaw/issues/comments?per_page=5 | \
  python3 -c "import json,sys; [print(c['user']['login'],c['body'][:100]) for c in json.load(sys.stdin) if 'rate limit' in c['body'].lower()]"
```

### 7. Is the 6-green check working correctly?
```bash
PYTHONPATH=~/.openclaw/src python3 -m orchestration.merge_gate jleechanorg jleechanclaw <PR_NUM> --json
```

### 8. Is the stray-worktree bug blocking spawns?
```bash
git -C ~/.openclaw worktree list | grep -v "~/.openclaw\b\|~/.worktrees"
# Any /private/tmp/ or unexpected paths = stray worktree blocking new spawns
```

## Common failure modes

| Symptom | Root cause | Fix |
|---|---|---|
| Sessions spawn but die immediately | `--claim-pr` fails (stray worktree) | `git worktree prune`, clear stale paths |
| Sessions alive but no pushes | Agent hits rate limit or auth failure | Check agent logs, re-auth |
| CR never APPROVED | Rate limited (too many PRs) | Wait for limit reset, or reduce simultaneous PRs |
| 6-green check passes but no merge | auto-merge config missing or `auto: false` | Verify `approved-and-green: auto: true, action: auto-merge` in `~/.openclaw/agent-orchestrator.yaml` |
| `/tmp/ao-pr-poller.log` missing | **NOT A BUG** — ao-pr-poller is deprecated/removed | Ignore; its absence is correct and expected |
| PRs cycling CR changes_requested | Agent not reading CR comments correctly | Check agento's comment-reading skill |
| Spawned sessions are idle shells | `is_agent_alive_in_session` returns false | Check openclaw gateway is running on port 18789 |

## Output format

```
## Autonomy Diagnostic — <date>

### System health
- AO lifecycle-worker: RUNNING / STOPPED
- Orchestrator session: FOUND (hash-prefixed name) / NOT FOUND
- Auto-merge config: approved-and-green auto=true/false, action=X
- Active sessions: N (M with live agents)
- Open PRs: N total, N non-green

### Per-PR status
| PR | Non-green reason | Session | Session state |
|---|---|---|---|
| #NNN | <reason from log> | jc-NNN | alive/zombie/none |

### Root cause
<Primary reason the system is not progressing PRs autonomously>

### Recommended fix
<Concrete next step>
```
