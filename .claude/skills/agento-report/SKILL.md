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

Use REST as the primary read path for these listings. REST and GraphQL have
separate quota buckets. Before reporting GitHub/API work blocked, try one
bounded equivalent read through both APIs where the operation permits; see
`github-cli-reference/SKILL.md`. A quota failure for one operation does not
block unrelated AO work.

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

For each open PR number NUM, fetch mergeability, CI, reviews, and comments.
Use REST for the shown reads; if a call is unavailable, try an equivalent
read-only GraphQL query before reporting the data unavailable:

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

# Fetch comment text for model review; never infer severity from words.
gh api "repos/jleechanorg/agent-orchestrator-ts/pulls/NUM/comments" \
  --jq '.[] | {id, user: .user.login, body, path, line, created_at}'
```

### Step 3 — Draft readiness + `/green` per open PR

Use `~/.claude/skills/pr-lifecycle/SKILL.md` and
`~/.claude/skills/pr-green-definition/SKILL.md`. Advisory checks (`Green Gate` and `Cursor Bugbot`) are excluded from gating.

**Status label** (pick worst failing condition):
- Classify each check in order: an incomplete or missing/null `status` is
  `CI_PENDING` regardless of `conclusion`; evaluate `conclusion` only when
  `status == COMPLETED`. A completed null conclusion is `CI_UNKNOWN`, not
  `CI_FAILED` and never a pass. For a `StatusContext`, pending/expected means
  `CI_PENDING`, explicit failure/error means `CI_FAILED`, and missing/unknown
  state means `CI_UNKNOWN`.
- `GREEN` — draft readiness and both `/green` gates pass; green alone does not establish READY, and merge authorization remains separate under `pr-lifecycle`
- `CONFLICT` — mergeable_state is `dirty`
- `CI_PENDING` — any non-advisory check is not complete (`status` is `QUEUED`, `PENDING`, `IN_PROGRESS`, missing, or null), regardless of its conclusion field
- `CI_FAILED` — a non-advisory check is `COMPLETED` and its conclusion is explicitly non-success (`FAILURE`, `CANCELLED`, `SKIPPED`, `NEUTRAL`, `TIMED_OUT`, `ACTION_REQUIRED`); a completed check with a null conclusion is `CI_UNKNOWN`, never silently passed
- `CI_UNKNOWN` — check data is malformed or incomplete in a way not covered by pending/failed; report the exact row and leave Gate 1 unproven
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
- REST is this report's primary API, not an exclusive fallback policy. Before declaring an API read blocked, follow `github-cli-reference/SKILL.md` and try the other read API where equivalent.
- `mergeable_state` from REST: `clean`, `dirty`, `unstable`, `unknown`.
- Zero-touch classification follows `~/.claude/skills/zero-touch/SKILL.md`; title tags are discovery hints, not execution evidence.
- If `ao status` is unavailable, `tmux list-sessions` may confirm that a pane exists, but it does not prove that the worker is working or idle. Use `ao-session-monitor/SKILL.md` to assess state.
- Always display inline report FIRST, then post Slack.
- The Slack post uses MCP, NOT curl.
