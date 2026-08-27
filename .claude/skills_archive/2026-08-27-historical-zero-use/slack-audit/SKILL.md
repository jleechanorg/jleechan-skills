---
name: slack-audit
description: "Audit Slack channel threads for untracked work items — checks each thread against GH issues/PRs, reports gaps, and optionally redrives dropped threads by posting a status reply to the channel. Slash command: /slack-audit."
metadata:
  type: skill
---

# /slack-audit

Scan one or more Slack channels for the last N hours, identify threads that contain actionable work items with no corresponding GH issue or PR, and report or redrive them.

## Usage

```
/slack-audit [--channel <#channel|channel_id>] [--hours <N>] [--fix] [--dry-run]
```

- Default channel: `#worldai` (`C0AH3RY3DK6`)
- Default window: `24h`
- `--dry-run` (default): print the gap report, no Slack posts
- `--fix`: post a status reply to each dropped thread and reply-to-channel to surface it

## Subagent strategy (mandatory)

**Always fan out parallel subagents** for independent lookups. Do NOT do GH searches sequentially.

- **Subagent A — Slack fetch**: pull channel history for the time window, parse threads, extract work items
- **Subagent B — GH issues search**: for all extracted items, fan out parallel `gh issue list --search` calls (one per item, all in parallel)
- **Subagent C — GH PR search**: for all extracted items, fan out parallel `gh pr list --search` calls in parallel with subagent B
- **Merge results** in the main agent: join Slack threads with GH tracking results, classify each as TRACKED / COMPLETED / UNTRACKED / NEEDS_REDRIVE

When running `--fix`: fan out parallel Slack posts (one per dropped thread), do not post sequentially.

**Identity:** Always post as the authenticated user ($USER via MCP Slack tool). Never post as a bot user.

## Step-by-step

### 1. Fetch channel history

Use `mcp__slack__conversations_history` for the target channel + time window.

```
mcp__slack__conversations_history(channel_id=<ID>, limit="48h")
```

Parse the CSV result (headers: `MsgID,UserID,UserName,...,Text,Time,...`).

Group messages by `ThreadTs` (empty ThreadTs = root message = its own thread).

### 2. Extract work items

For each thread, identify messages containing actionable intent signals:

| Signal | Examples |
|--------|---------|
| Imperative verb | "fix", "make", "create", "spawn", "investigate", "drive", "open PR", "file issue" |
| PR/issue reference | `github.com/.../pull/N`, `#7NNN`, `/green`, `/es`, `/er` |
| Status question | "what's the status", "is this done", "any update" |
| Explicit work | "AO worker", "dispatch", "bring to green", "/babysit" |

Skip threads that are purely status reports from bots (hermes, coderabbit, etc.) with no human reply.

### 3. Check GH tracking for each work item

For each extracted work item:

1. Search `gh issue list --repo $GITHUB_REPOSITORY --search "<keywords>"` (or `agent-orchestrator` if relevant)
2. Search `gh pr list --repo $GITHUB_REPOSITORY --search "<keywords>"`
3. Check if the thread itself references a PR/issue number that is still open

Classify each thread:

| Status | Meaning |
|--------|---------|
| `TRACKED` | Has open or recently merged GH issue/PR |
| `COMPLETED` | Referenced PR/issue is merged/closed |
| `UNTRACKED` | No GH issue or PR found |
| `NEEDS_REDRIVE` | Has issue/PR but no recent activity (>48h stale) |

### 4. Dry-run report (default)

Print a table:

```
THREAD                          | STATUS      | GH          | LAST ACTIVITY
--------------------------------|-------------|-------------|---------------
keep-logging-in (Jun 14 00:06)  | TRACKED     | #7576 OPEN  | just filed
collapsible filter (Jun 14 19:29)| TRACKED    | #7203 OPEN  | no PR yet
#684 send_message mis-route     | NEEDS_REDRIVE| #684 OPEN  | 20h stale
wiki-ingest campaign skill      | UNTRACKED   | none        | -
RAG optimize-anything           | UNTRACKED   | none        | -
```

### 5. --fix mode: redrive dropped threads

For each `UNTRACKED` or `NEEDS_REDRIVE` thread:

1. **Post a reply in the thread** summarizing what was found (or not found) and what the next step is.
2. **Post a reply-to-channel** so the thread surfaces at the top of #worldai.

Template for untracked item:
```
Following up: this thread has no GH issue or PR yet.
[Summary of what was asked]
Next: [proposed action — file issue / spawn worker / close as resolved]
```

Template for needs-redrive:
```
Re-driving: issue #N / PR #N has had no activity for >48h.
Current state: [open/CI-red/CR-changes-requested]
Next: [specific action]
```

Always use the **user's identity** ($USER via `mcp__slack__conversations_add_message`).
Never use bot tokens for these posts.

### 6. Channels to check by default

| Channel | ID | Purpose |
|---------|-----|---------|
| `#worldai` | `C0AH3RY3DK6` | Main your-project.com work |
| `#jleechanclaw` | `C0AJ3SD5C79` | Hermes/OpenClaw infra work |
| `#agent-orchestrator` | `C0ALSKLU9KM` | AO worker status |

## Existing Hermes scripts (reuse, don't duplicate)

- `~/.hermes/lib/slack_thread_lib.sh` — `slack_post <job> <text> [--channel C] [--force] [--no-thread]`
- `~/.hermes/src/orchestration/slack_catchup.py` — channel history + per-channel cursor state
- `~/.hermes/scripts/slack_history_to_memory.py` — sync Slack history to memory markdown

Use the MCP Slack tool (`mcp__slack__conversations_history`, `mcp__slack__conversations_add_message`) for in-session posting. Use `slack_thread_lib.sh` for cron/automation posting.

## Integration with /learn

After any `--fix` run, call `/learn` to capture:
- Which threads were redriven
- Which were untracked → now have issues filed
- Pattern of what kinds of work commonly fall through

## Notes

- A thread counts as "redriven" only if a reply is actually posted AND the channel root message is bumped (reply-to-channel).
- The dry-run report is the default so you can review before posting.
- Skip threads where the root message is from a cron bot and there are no human replies.
- Skip threads where the only message is a `/repro` or `/green` command that completed (has a bot success reply with a checkmark).
