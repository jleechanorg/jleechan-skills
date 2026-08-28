---
name: agento_report
description: Generate a full agento PR status report — draft readiness, canonical /green, zero-touch rate, inline display, and Slack summary.
type: skill
---

## Purpose

Produce a comprehensive status report for all PRs agento is handling in
`jleechanorg/agent-orchestrator-ts`. Use the canonical draft-first, `/green`,
and zero-touch skills; display inline and post the summary to Slack.

---

## Execution Steps

### Step 1 — Collect open PRs

Use REST (not GraphQL — GraphQL is frequently exhausted):

```bash
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls?state=open&per_page=30&sort=updated" \
  --jq '.[] | "\(.number)\t\(.head.ref)\t\(.title[:60])"'
```

Also collect recently merged (last 24h):
```bash
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls?state=closed&per_page=30&sort=updated&direction=desc" \
  --jq '.[] | select(.merged_at != null) | "\(.number)\t\(.head.ref)\t\(.title[:70])\t\(.merged_at)"'
```
Filter merged ones to last 24h by comparing `.merged_at` timestamp.

### Step 2 — Per-PR data fetch (open PRs)

For each open PR number NUM, fetch mergeability, CI, and reviews via REST:

```bash
# Mergeability (REST returns boolean mergeable + string mergeable_state)
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls/NUM" \
  --jq '{mergeable, mergeable_state}'

# CI checks (canonical statusCheckRollup contract at current HEAD)
gh pr view NUM --json statusCheckRollup \
  --jq '[.statusCheckRollup[] | select(.name != "Green Gate" and .name != "Cursor Bugbot") | {name, status, conclusion, state, typename: .__typename}]'

# Reviews
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls/NUM/reviews" \
  --jq '.[] | {user: .user.login, state}'

# Inline comments (check for High Severity / Critical / Major blockers)
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls/NUM/comments" \
  --jq '[.[] | select(.body | test("High Severity|Critical|Major"))] | length'
```

### Step 3 — Draft readiness + `/green` per open PR

Use `~/.claude/skills/draft-first-pr/SKILL.md` and
`~/.claude/skills/pr-green-definition/SKILL.md`. Advisory checks (`Green Gate` and `Cursor Bugbot`) are excluded from gating.

**Status label** (pick worst failing condition):
- `GREEN` — draft readiness and both `/green` gates pass
- `CONFLICT` — mergeable_state is `dirty`
- `CI_FAILED` — any non-advisory check has non-`SUCCESS` conclusion (`FAILURE`, `CANCELLED`, `SKIPPED`, `NEUTRAL`, `TIMED_OUT`, `ACTION_REQUIRED`, null) or `StatusContext` state != `SUCCESS`
- `CI_PENDING` — any non-advisory check has status != `COMPLETED` (`in_progress`, `queued`, `waiting`, null)
- `DRAFT_NOT_READY` — `/es`, `/er`, or `/advice` is missing at current head

### Step 4 — Zero-touch rate analysis (KEY ADDITION)

**Definition** (from `~/.openclaw/SOUL.md`): Zero-touch-by-operator is measured by the **`[agento]`** prefix in the PR title. A merged PR with `[agento]` prefix means AO produced the work and brought it to merge without operator intervention.

For each merged PR in the window:

```bash
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls?state=closed&per_page=30&sort=updated&direction=desc" \
  --jq '.[] | select(.merged_at != null) | {
    number,
    title: .title[:70],
    merged_at,
    agento: (.title | test("^\\[agento\\]"))
  }'
```

Calculate:
- **Total merged** in window
- **[agento] tagged** (zero-touch)
- **Non-[agento]** (operator-assisted)
- **Zero-touch rate** = agento_count / total_merged * 100

For each non-[agento] PR, note WHY it wasn't zero-touch — common reasons:
- Missing `[agento]` prefix (worker didn't tag it)
- Operator had to fix lint/build errors on main
- Operator manually resolved merge conflicts
- Operator directly pushed code fixes
- CR review required operator comments

### Step 5 — Format and display the report inline

```
## Agento Status Report — YYYY-MM-DD HH:MM

### Summary
- Repo: jleechanorg/agent-orchestrator-ts
- Open PRs: N
- GREEN (ready to merge): N
- Not green: N
- Merged (last 24h): N
- Zero-touch rate (24h): X% (N/M [agento]-tagged of M total merged)

### Open PRs

| PR | Branch | Status | Blockers |
|----|--------|--------|----------|
| [#NUM](URL) title | branch | GREEN/status | blocker details |

### Merged (last 24h)

| PR | Title | Zero-touch? | Notes |
|----|-------|-------------|-------|
| [#NUM](URL) | title | [agento] YES / NO | reason if NO |

### Zero-Touch Analysis
- Rate: X% (N/M)
- Non-zero-touch PRs and why:
  - #NUM: reason (e.g., "operator fixed lint on main before CI could pass")
  - #NUM: reason (e.g., "worker didn't add [agento] prefix")

### AO Sessions
(tmux session count + key worker status)
```

### Step 6 — Post Slack summary via MCP

Post to `#ai-slack-test` (channel ID: `C0AKALZ4CKW`):

```
mcp__slack__conversations_add_message(
  channel_id="C0AKALZ4CKW",
  text="*Agento Status Report — YYYY-MM-DD HH:MM*\n\nRepo: jleechanorg/agent-orchestrator-ts\nOpen: N PRs | GREEN: N | Not green: N\nMerged (24h): N | Zero-touch rate: X%\n\n<per-PR details>"
)
```

---

## Notes

- Scope: `jleechanorg/agent-orchestrator-ts` (not jleechanclaw — that repo is deprecated for AO work).
- Use REST API (`gh api`) not GraphQL (`gh pr view --json`) — GraphQL is frequently exhausted.
- `mergeable_state` from REST: `clean`, `dirty`, `unstable`, `unknown`.
- Zero-touch convention: `[agento]` prefix in PR title (from `~/.openclaw/SOUL.md`).
- If `ao status` is unavailable, use `tmux list-sessions | grep -E 'ao-[0-9]+'` as fallback.
- Always display inline report FIRST, then post Slack.
- The Slack post uses MCP, NOT curl.
