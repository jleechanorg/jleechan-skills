---
name: agento-report
description: Generate a full agento PR status report — draft readiness, canonical /green, zero-touch rate, inline display, and Slack summary.
type: skill
---

## Purpose

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


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

Use `~/.claude/skills/pr-lifecycle/SKILL.md` and
`~/.claude/skills/pr-green-definition/SKILL.md`. Advisory checks (`Green Gate` and `Cursor Bugbot`) are excluded from gating.

**Status label** (pick worst failing condition):
- `GREEN` — draft readiness and both `/green` gates pass; green alone does not establish READY, and merge authorization remains separate under `pr-lifecycle`
- `CONFLICT` — mergeable_state is `dirty`
- `CI_FAILED` — any non-advisory check has non-`SUCCESS` conclusion (`FAILURE`, `CANCELLED`, `SKIPPED`, `NEUTRAL`, `TIMED_OUT`, `ACTION_REQUIRED`, null) or `StatusContext` state != `SUCCESS`
- `CI_PENDING` — any non-advisory check has status != `COMPLETED` (`in_progress`, `queued`, `waiting`, null)
- `DRAFT_NOT_READY` — an applicable draft gate lacks coverage for the candidate under `pr-lifecycle`; assess earlier-SHA evidence by its delta-and-scope rule rather than requiring a new verdict solely for a new hash

### Step 4 — Zero-touch rate analysis

Use `~/.claude/skills/zero-touch/SKILL.md` for the intervention criteria and
measurement. The `[agento]` title prefix is a discovery hint only, not proof of
zero-touch; its absence does not prove operator assistance.

For every merged PR in the window, inspect spawn provenance, quality-gate receipts and pre-merge intervention history
(commits, reviews, comments and CI actions), using the canonical criteria and exclusions.
Record the supporting evidence links and classify as `YES` (verified zero-touch),
`NO` (verified operator assistance), or `UNKNOWN` (missing or ambiguous evidence).
A shared account or title tag alone does not establish who performed an action.
Do not count merge authorization or the merge action itself as operator assistance;
apply the canonical exclusions rather than inventing new quality or review gates.

Calculate:
- **Total merged** in window
- **Verified zero-touch**, **verified operator-assisted**, and **unknown** counts
- **Zero-touch rate** = verified_zero_touch / total_merged * 100, only when every
  merged PR is classified from evidence and total_merged > 0

Incomplete coverage makes the overall zero-touch rate unknown; report the verified
counts and missing evidence instead of treating unknowns as zero-touch or assisted.
With no merged PRs, report `N/A (no merged PRs)`, not a percentage.
For each `NO`, cite the actual intervention; for each `UNKNOWN`, name the evidence gap.

### Step 5 — Format and display the report inline

```
## Agento Status Report — YYYY-MM-DD HH:MM

### Summary
- Repo: jleechanorg/agent-orchestrator-ts
- Open PRs: N
- GREEN (draft readiness + /green only): N
- Not green: N
- Merged (last 24h): N
- Zero-touch rate (24h): X% / UNKNOWN / N/A (N verified zero-touch, A assisted, U unknown; M total merged)

### Open PRs

| PR | Branch | Status | Blockers |
|----|--------|--------|----------|
| [#NUM](URL) title | branch | GREEN/status | blocker details |

### Merged (last 24h)

| PR | Title | Zero-touch? | Notes |
|----|-------|-------------|-------|
| [#NUM](URL) | title | YES / NO / UNKNOWN | evidence links, intervention or gap |

### Zero-Touch Analysis
- Rate: X% / UNKNOWN / N/A (N verified zero-touch / M total; U unknown)
- Verified operator-assisted PRs and unknowns:
  - #NUM: reason (e.g., "operator fixed lint on main before CI could pass")
  - #NUM: UNKNOWN (e.g., "spawn provenance unavailable")

### AO Sessions
(tmux session count + key worker status)
```

### Step 6 — Post Slack summary via MCP

Post to the user-authorized Slack summary destination (verified channel ID: `<slack-channel>`):

```
mcp__slack__conversations_add_message(
  channel_id="<slack-channel>",
  text="*Agento Status Report — YYYY-MM-DD HH:MM*\n\nRepo: jleechanorg/agent-orchestrator-ts\nOpen: N PRs | GREEN: N | Not green: N\nMerged (24h): N | Zero-touch rate: X% / UNKNOWN / N/A (U unknown)\n\n<per-PR details>"
)
```

---

## Notes

- Scope: `jleechanorg/agent-orchestrator-ts` (not jleechanclaw — that repo is deprecated for AO work).
- Use REST API (`gh api`) not GraphQL (`gh pr view --json`) — GraphQL is frequently exhausted.
- `mergeable_state` from REST: `clean`, `dirty`, `unstable`, `unknown`.
- Zero-touch classification follows `~/.claude/skills/zero-touch/SKILL.md`; title tags are discovery hints, not execution evidence.
- If `ao status` is unavailable, use `tmux list-sessions | grep -E 'ao-[0-9]+'` as fallback.
- Always display inline report FIRST, then post Slack.
- The Slack post uses MCP, NOT curl.
