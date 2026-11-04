---
name: github-pr-automation-debug
description: "Diagnose and trace unwanted/automated comments on GitHub PRs to their source. Use when a PR is getting spammed by bot comments, AI automation directives, or cron-triggered messages, and you need to identify which system is responsible and how to disable it."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, PR-automation, debugging, skeptic-cron, codex, launchd]
    related_skills: [github-pr-workflow, github-code-review, hermes-health-check]
---

# GitHub PR Automation Debug

Diagnose and trace unwanted/automated comments on GitHub PRs to their source.

## Trigger

Use this skill when:
- A PR is getting spammed by bot or automation comments
- User says they "disabled the job" but comments keep appearing
- You need to find which system is posting comments as `github-actions[bot]`, a personal account (via PAT), or a GitHub App
- You need to disable or throttle PR automation

## Architecture: Multiple Independent Systems

**Critical pitfall:** Disabling one automation system does NOT disable the others. There are typically 3+ independent systems that can post to PRs:

| System | Posts as | Runs where | Trigger |
|--------|---------|-----------|---------|
| **Skeptic Cron** (GH Actions) | `github-actions[bot]` | GitHub Actions | Schedule (`*/30 * * * *`) |
| **PR Monitor** (Python `jleechanorg_pr_automation`) | Personal account (PAT) | Local launchd or cron | Schedule or on-demand |
| **Codex Connected App** (`chatgpt-codex-connector[bot]`) | `chatgpt-codex-connector[bot]` | External (OpenAI) | Webhook on comment/push |
| **CodeRabbit** (`coderabbitai[bot]`) | `coderabbitai[bot]` | External (CodeRabbit) | Webhook on push/comment |
| **AO Worker sessions** | Personal account or `github-actions[bot]` | Local AO spawn | Manual or cron |

### Operator-PAT daemon in a feedback loop — the comment-storm source (added 2026-07-23, bead $USER-rouf)

A local daemon that posts through the `gh` CLI with the operator's PAT is its
own source of PR comments: its comments appear under the operator's username
with `author_association=MEMBER`, so they look like the operator typed them.

**Why this matters for spam diagnosis:** if a PR has 2,500+ comments that all
share the same body prefix from one operator account, a daemon is in a feedback
loop — NOT a hostile bot, NOT a leaked PAT, NOT CodeRabbit spam. The fix lives in
that daemon's dedup logic, not in GitHub App settings or launchd.

1. Find the loop — pull recent comments and group by body prefix:
   ```bash
   gh api "repos/$REPO/issues/comments?per_page=100&since=$(date -u -v-32H '+%Y-%m-%dT%H:%M:%SZ')&direction=desc&sort=updated" \
     | jq 'group_by(.user.login) | map({user: .[0].user.login, n: length, sample: (.[0].body // "")[0:120]}) | sort_by(-.n) | .[:5]'
   ```
2. If 99% of comments share one body prefix from one user, find the daemon that
   emits that prefix before deciding whether to stop it.
3. Check its dedup key: a key drawn from a per-tick object (a fresh bead or
   session id) never matches. Re-key on a stable identifier (branch, PR number,
   commit SHA) and run the dedup check before the comment is posted.
4. Verify the fix with unit tests against the real state store: happy path,
   regression pin, re-key correctness, cross-key isolation.

## Debugging Steps

### 1. Identify who posted the comment

```bash
# List recent comments and their authors
gh api repos/OWNER/REPO/issues/PR_NUMBER/comments \
  --jq '.[] | {id, user: .user.login, created_at, body: .body[:200]}'
```

**Comment authorship tells you everything:**
- `github-actions[bot]` → GitHub Actions workflow (uses `GITHUB_TOKEN`)
- Personal account (e.g., `jleechan2015`) → Local script with PAT or GitHub App posting on behalf
- `[bot]` suffix → Registered GitHub App or OAuth app

### 2. For `github-actions[bot]` comments: find the workflow

```bash
# List all workflows (including disabled)
gh api repos/OWNER/REPO/actions/workflows --jq '.workflows[] | {id, name, state, path}'

# Check recent runs of the suspect workflow
gh run list --repo OWNER/REPO --workflow=WORKFLOW_ID -L 5 \
  --json databaseId,status,conclusion,createdAt,event
```

**Common spam sources in jleechanorg:**
- `skeptic-cron.yml` → Posts `SKEPTIC_CRON_TRIGGER` every 30 min
- `skeptic-gate.yml` → Posts verdicts on PR checks
- `green-gate.yml` → Posts gate check results
- `pr-agent-trigger.yml` → Posts agent directives

### 3. For personal-account comments: find the local process

```bash
# Check running launchd agents
launchctl list | grep -i "pr\|monitor\|autom\|codex"

# Check process list
ps aux | grep -i "pr_monitor\|pr-automation\|jleechanorg-pr"

# Check local logs for the pr-monitor
tail -50 ~/Library/Logs/${PROJECT_NAME:-your-project}-automation/pr-monitor.err.log
tail -20 ~/Library/Logs/${PROJECT_NAME:-your-project}-automation/pr-monitor.out.log

# Check launchd plist files
ls ~/Library/LaunchAgents/ | grep -i "pr\|monitor\|autom"
```

**Key log location:** `~/Library/Logs/${PROJECT_NAME:-your-project}-automation/pr-monitor.err.log`
Look for lines like `✅ Posted Codex support comment on PR #N` — this confirms local pr-monitor activity.

### 4. For bot/app comments: check the app installation

```bash
# Check installed GitHub Apps on the repo
gh api repos/OWNER/REPO/installation --jq '.' 2>/dev/null || echo "No installation data accessible"
```

Bot comments come from external services (CodeRabbit, Codex, Copilot) configured as GitHub Apps. These respond to webhooks and are controlled from their own dashboards, not from repo settings.

### 5. Check crontab and hermes cron

```bash
# System/user crontab
crontab -l | grep -i "pr\|monitor\|autom\|codex"

# Hermes cron jobs
cat ~/.hermes/cron/jobs.json | python3 -m json.tool

# Hermes cron (if applicable)
hermes cron list 2>/dev/null
```

## Disabling Automation

### Disable a GitHub Actions workflow

```bash
gh workflow disable WORKFLOW_ID --repo OWNER/REPO
# Example: gh workflow disable 253141151 --repo $GITHUB_REPOSITORY
```

### Disable a local launchd agent

```bash
# 1. Bootout the agent
launchctl bootout gui/$(id -u)/LABEL_NAME

# 2. Kill any currently-running process
pkill -f "PATTERN"  # e.g., pkill -f "jleechanorg_pr_monitor"

# 3. Rename the plist so launchd can't auto-restart it
mv ~/Library/LaunchAgents/LABEL_NAME.plist ~/Library/LaunchAgents/LABEL_NAME.plist.disabled

# Full example for pr-monitor:
launchctl bootout gui/$(id -u)/ai.worldarchitect.pr-automation.pr-monitor
pkill -f "jleechanorg_pr_monitor"
mv ~/Library/LaunchAgents/ai.worldarchitect.pr-automation.pr-monitor.plist \
   ~/Library/LaunchAgents/ai.worldarchitect.pr-automation.pr-monitor.plist.disabled
```

**Critical pitfalls:**
- `launchctl list` may show `state = not running` but the process can STILL be active (invoked by a different path or still finishing). Always check `ps aux` AND the log files to confirm.
- Just running `launchctl bootout` is NOT sufficient — rename the `.plist` to `.plist.disabled` to prevent auto-restart on next login.
- There may be **multiple launchd agents** for the same function. In the `jleechanorg` stack, the pr-automation package installs at least 5 agents: `pr-monitor`, `fixpr`, `fix-comment`, `comment-validation`, and `codex-api`. Check all of them:
  ```bash
  ls ~/Library/LaunchAgents/ | grep "worldarchitect.pr-automation"
  ```

### Disable an external bot (CodeRabbit, Codex, etc.)

These are typically GitHub App installations controlled from the app's dashboard or repo Settings → Integrations. You cannot disable them from the CLI — the user must do it from the GitHub web UI.

### Disable skeptic-cron trigger comments (without disabling the workflow)

If you want skeptic-cron to keep running (for 7-green checks) but stop posting trigger comments, modify `skeptic-cron-reusable.yml` to skip the comment-posting step. This requires a PR to the `agent-orchestrator` repo.

## Pitfalls

1. **"Disabled" ≠ "Stopped"**: A workflow may be `disabled_manually` but a local script with PAT continues posting. Always check ALL sources. The `codex-api` plist was disabled months ago but `pr-monitor` (same package, separate agent) kept posting.
2. **`launchctl list` can be misleading**: An agent showing `state = not running` may have been running earlier (check logs). More importantly, the process may have been started by a cron job, manual invocation, or parent script — not via launchd. Always check `ps aux` and log files.
3. **Multiple launchd agents for the same function**: There may be separate agents under `ai.hermes.*`, `ai.hermes.*`, and `ai.worldarchitect.*` namespaces. The `jleechanorg_pr_automation` package installs at least 5: `pr-monitor`, `fixpr`, `fix-comment`, `comment-validation`, and `codex-api`. Disabling one does NOT disable the others.
4. **SKEPTIC_CRON_TRIGGER → chain reaction**: The skeptic-cron posts `SKEPTIC_CRON_TRIGGER`, then CodeRabbit responds to `@coderabbitai` mentions, then Codex responds to the trigger, creating an automation cascade that spams the PR.
5. **Comment timestamp vs log timestamp**: PR comment timestamps are UTC. Local log timestamps are usually local time (PDT/PST). Subtract 7 hours to compare.
6. **PAT comments look like user comments**: Comments posted by a local script using a personal access token appear under the user's GitHub username, NOT under a bot account. The only way to distinguish is timing correlation with local logs. Match `✅ Posted Codex support comment on PR #N` in `pr-monitor.err.log` to the `[AI automation]` comment on GitHub.
7. **Hostname collision in launchd**: The 7-green monitor has TWO identical plist agents: `ai.hermes.schedule.pr-monitor-worldai` (Hermes) and `ai.hermes.schedule.pr-monitor-worldai` (Hermes). Both run `ao7green-pr-monitor.sh` and both are read-only (do NOT post comments). Don't disable these when trying to stop comment spam — they only check PR status.
8. **Same-prefix operator-account comment floods are not user spam** (added 2026-07-23, bead $USER-rouf). If a PR has 2,000+ comments from the operator account (`author_association=MEMBER`) all sharing one body prefix, a PAT-driven daemon is in a feedback loop — the operator did NOT actually type 2,000 comments. Rotating the PAT or revoking the GitHub App are the WRONG fixes. Fix the daemon's dedup: post only after the dedup check, and key it on a stable identifier (branch, PR number), not a per-tick id.

## Quick Reference: jleechanorg PR Automation Stack

| Component | Label | Type | Location |
|-----------|-------|------|----------|
| Skeptic Cron | `ai.hermes.schedule.pr-monitor-worldai` | 7-green monitor (read-only) | Hermes launchd |
| PR Monitor (Python) | `ai.worldarchitect.pr-automation.pr-monitor` | `[AI automation]` comment poster | Local launchd + crontab |
| Skeptic Cron (GHA) | `skeptic-cron.yml` | `SKEPTIC_CRON_TRIGGER` posts | GitHub Actions |
| Skeptic Cron Reusable | `agent-orchestrator/.github/workflows/skeptic-cron-reusable.yml` | Comment + verdict logic | GitHub Actions (reusable) |
| Codex Connected App | `chatgpt-codex-connector[bot]` | Responds to triggers | External (OpenAI) |
| CodeRabbit | `coderabbitai[bot]` | Responds to `@coderabbitai` | External (CodeRabbit) |

## References

- **`references/jleechanorg-automation-topology.md`** — Full topology map of PR automation systems in the jleechanorg org: local launchd agents, their labels, log paths, Python package versions, GitHub Actions workflow IDs and states, and the comment cascade chain.