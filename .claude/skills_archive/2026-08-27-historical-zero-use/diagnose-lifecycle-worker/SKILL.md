---
name: diagnose-lifecycle-worker
description: Diagnose and fix AO lifecycle-worker backfill failures (stale worktrees, branch conflicts, claim_failed loops)
---

# Lifecycle-Worker Diagnostic Skill

Use this when `lifecycle.backfill.claim_failed` errors appear in lifecycle-worker logs, or when open PRs have no active sessions and are stalling.

## Step 1 — Confirm lifecycle-worker is running

```bash
pgrep -af "lifecycle-worker"
```

If nothing: lifecycle-worker is not running. Check launchd state:

```bash
launchctl print gui/$(id -u)/com.agentorchestrator.lifecycle-agent-orchestrator 2>&1 | grep "state ="
```

If state ≠ `running`, bootstrap it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.agentorchestrator.lifecycle-agent-orchestrator.plist
```

## Step 2 — Find the lifecycle log

```bash
# Check common log locations
ls ~/.openclaw/logs/ao-lifecycle-*.log 2>/dev/null | tail -5
ls ~/.agent-orchestrator/*/logs/lifecycle-*.log 2>/dev/null | tail -5
```

Tail the most recent log:

```bash
tail -50 ~/.openclaw/logs/ao-lifecycle-<project>.log
```

## Step 3 — Find claim_failed errors

```bash
grep -n "claim_failed\|refusing to fetch\|Session not found" ~/.openclaw/logs/ao-lifecycle-<project>.log | tail -20
```

Extract the error message and branch/worktree path from the output.

## Step 4 — Triage by error type

### Path A: "refusing to fetch into branch" (ghost worktree)

This means a worktree has a branch checked out that the lifecycle-worker is trying to fetch into.

**Identify the worktree and branch:**
```bash
# From the error, note the path and branch name
# e.g.: fatal: refusing to fetch into branch 'refs/heads/feat/foo' checked out at '/path/to/worktree'
```

**Check if the worktree's tmux session is alive:**
```bash
# Extract session name from the worktree path (e.g. ao-123 from /path/to/agent-orchestrator/ao-123)
tmux has-session -t <session-name> 2>/dev/null && echo "ALIVE" || echo "DEAD"
```

**If dead — remove the ghost worktree:**
```bash
# Derive the git repo dir from the worktree path (parent of .git worktrees list entry)
WORKTREE="/path/to/worktree"
GIT_DIR="$(dirname "$WORKTREE")"  # e.g. ~/.worktrees/jleechanclaw

# Remove the ghost worktree (operate from the parent repo, not inside the worktree)
git -C "$GIT_DIR" worktree remove --force "$WORKTREE"
git -C "$GIT_DIR" branch -d <branch-name>   # safe if merged upstream
git -C "$GIT_DIR" branch -D <branch-name>   # force if not yet merged
```

**Verify the fix works:**
```bash
GIT_DIR="$(dirname "/path/to/worktree")"
git -C "$GIT_DIR" fetch --force origin +refs/pull/<PR_NUMBER>/head:<branch-name>
```

### Path B: "Session not found" (orphaned session metadata)

The lifecycle-worker lost track of a session.

**Identify the repo from the log context (look for `project:` in the lifecycle log):**
```bash
grep -n "project:" ~/.openclaw/logs/ao-lifecycle-<project>.log | tail -5
```

**Find orphaned session metadata:**
```bash
ls ~/.agent-orchestrator/*/sessions/archive/ 2>/dev/null | head -20
ls ~/.agent-orchestrator/*/sessions/ 2>/dev/null | head -20
```

**Find orphaned worktrees — always scope to the correct worktreeDir:**
```bash
# Determine worktreeDir for the project from agent-orchestrator.yaml
python3 -c "
import yaml
cfg = yaml.safe_load(open('$HOME/.openclaw/agent-orchestrator.yaml'))
proj = cfg['projects']['<project-name>']
print('worktreeDir:', proj.get('worktreeDir', '~/.worktrees/' + proj.get('name','').lower().replace(' ', '-')))
print('repo:', proj.get('repo'))
"
WORKTREE_DIR="~/.worktrees/jleechanclaw-main"   # substitute from above
git -C "$WORKTREE_DIR" worktree list
```

**Find orphaned worktrees:**
```bash
git worktree list | grep <project-name>
```

If you find a worktree with no corresponding live tmux session, it's orphaned — remove it per Path A.

### Path C: Wrong branch checked out in main repo

If the error path points to the main repo (not a worktree):
```bash
git -C /path/to/repo branch --show-current
```

If it's not `main`:
```bash
git -C /path/to/repo checkout main && git -C /path/to/repo pull --ff-only
```

## Step 5 — Verify lifecycle-worker resumes

```bash
# Watch the log for ~60 seconds after cleanup
tail -f ~/.openclaw/logs/ao-lifecycle-<project>.log
# Press Ctrl+C when done
```

Look for new entries — the lifecycle-worker should resume processing within a few minutes.

## Step 6 — Escalation (3+ consecutive failures)

If the same PR has failed 3+ times after cleanup, something systemic is wrong.

**Send MCP mail alert:**
Use the MCP mail tool (or `mcp__mcp-agent-mail__send_message`):
- `project_key`: "jleechanclaw" (or relevant project)
- `sender_name`: "claude"
- `subject`: "lw-stall: <project> PR #<N>"
- `body_md`: "3+ consecutive `claim_failed` for PR #<N> on <project> after cleanup attempts. Manual intervention required. Last error: `<error snippet>`"

**Alternatively via curl:**
```bash
# Requires: OPENCLAW_SLACK_BOT_TOKEN (from ~/.bashrc) and JLEECHAN_DM_CHANNEL (your DM channel ID)
# Bot token posts as openclaw bot; user token ($SLACK_USER_TOKEN from ~/.profile) posts as $USER
OPENCLAW_SLACK_BOT_TOKEN="${OPENCLAW_SLACK_BOT_TOKEN:-}"  # set in ~/.bashrc
JLEECHAN_DM_CHANNEL="${JLEECHAN_DM_CHANNEL:-}"              # set in ~/.bashrc
curl -s -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer ${OPENCLAW_SLACK_BOT_TOKEN:-$SLACK_USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"channel\": \"${JLEECHAN_DM_CHANNEL:-C0AKALZ4CKW}\", \"text\": \"*[AO Alert]* lifecycle-worker stalled on <project> PR #<N>. 3+ consecutive failures. Manual intervention required.\"}"
```

## Quick Reference: Common Error → Fix Map

| Error substring | Likely cause | Fix |
|---|---|---|
| `refusing to fetch into branch` + worktree path | Ghost worktree | `git worktree remove --force <path>` |
| `refusing to fetch` + main repo path | Main repo on wrong branch | `git checkout main && git pull` |
| `Session not found` | Orphaned session metadata | Find+remove orphaned worktrees |
| `already exists` on worktree add | Duplicate worktree | `git worktree remove --force <path>` then retry |
| Rate limit | gh API exhausted | Wait ~1hr; check `gh api rate_limit` |
