---
name: spend-alert-bridge
description: Diagnose why a Spend Alert (GitHub Actions MTD/7-day breach, MCP Agent Mail relay, #worldai-alerts C0BCVG4F560) was missed. Use when user asks "why didn't you reply to the spend alert?", the alert didn't reach Slack, or MCP Agent Mail surfaces a spend alert in session context without a corresponding reply.
---

# Spend Alert Reply Bridge

## Failure pattern

The `spend-alert-daily.sh` launchd script posts a Slack alert to `#worldai-alerts` (C0BCVG4F560) when GitHub Actions daily Δ or 7-day rolling exceeds its threshold. The user sees this alert re-routed to their session context via **MCP Agent Mail** (a separate relay process, `com.mcp.agent.mail`, PID ~1151), but **nothing in the dropped-thread-watcher pipeline watches Agent Mail**. Combined result: the alert appears in human-facing chat but there is no hook that pings me to reply in-thread.

**Three distinct failure modes, all recurring:**

### Mode A — bridge delivery is fine, the SPEND ITSELF is the runaway (most common, 2026-07-23+)

The script posts correctly, the alert lands in #worldai-alerts, MCP Agent Mail relays it. But the user still gets a "why is spend $X" message because the alert numbers are real and trace to a runaway workflow. The bridge isn't broken — the cost is real.

**Important nuance:** the script's "MTD delta" is NOT a true daily-spend metric. GH's billing API returns monthly buckets only (`date == "2026-07-01T00:00:00Z"` for all of July). The script subtracts two snapshots taken 24h apart to estimate daily burn — this conflates real-time burn with billing-API lag. When the API finalizes a batch overnight, the next morning's delta will spike without any real new spend.

### Mode A.1 — comment-router-style runaway (workflow-level noise, low minutes)

The first instinct: look at which workflow fired thousands of times. The 2026-07-23
incident was initially diagnosed as a `comment-router.yml` runaway (5,566 issue_comment
runs/32h, all `conclusion=skipped`). The comment-router's `if:` correctly skipped
each one, but the workflow_run event still registered.

This is real but **usually a SYMPTOM, not the cause.** The actual 5,566 comments
were being posted by a **different process** — see Mode A.2.

### Mode A.2 — upstream spam loop posting to issue_comment (most common runaway source, 2026-07-23+)

**The recurring shape that has actually been driving the spend spikes:**

- An **upstream automation** (typically a local daemon posting with the operator's PAT) posts the same comment to 1-3 PRs every ~1h as part of a feedback loop
- Each `issue_comment` event fires `comment-router.yml` once, which correctly skips at the job level
- The workflow_run count in the GH Actions `runs` API balloons to thousands, polluting metrics and (in the daemon's case) triggering more downstream side effects
- The spend delta is mostly billing-API lag from finalized batches, not real new minutes

**2026-07-23 incident (bead $USER-rouf):**
- 3 PRs getting hammered: `your-project.com#8428` (1,791 posts), `#8420` (1,773), `#8421` (1,770)
- Total: 5,334 same-prefix daemon comments in 32h on these 3 PRs alone (vs ~6,000/48h for ALL of `comment-router` traffic)
- Root cause: the daemon posted the comment BEFORE its dedup check ran, AND the dedup key used a per-tick id (a fresh bead id every tick) instead of the stable branch
- Fix: re-key dedup on the branch name AND move the dedup check before the comment write
- Full detail: `references/comment-router-runaway-2026-07-23.md`

**Diagnostic recipe when `comment-router` is the noise source:**

```bash
# 1. Pull the actual comment bodies (not the workflow runs — the comments are upstream)
REPO="$GITHUB_REPOSITORY"
# NOTE: the `since` query param is ignored for `repos/<repo>/issues/comments` —
# paginate with `sort=created&direction=desc` and filter the timestamp in-process.
gh api "repos/$REPO/issues/comments?per_page=100&direction=desc&sort=updated" \
  | jq -r '.[] | "\(.user.login)\t\(.author_association)\t\((.body // "")[0:80])"'

# 2. Group by author_association + author login + body prefix
# 99% of "noisy" comments will share a body prefix from one automation
gh api "repos/$REPO/issues/comments?per_page=100&direction=desc&sort=updated" \
  | jq 'group_by(.author_association) | map({aa: .[0].author_association, n: length})'

# 3. Find the source — likely a local daemon, a GitHub Actions bot, or a cron
```

**Once the source automation is identified, fix it at its own repo — BUT FIRST verify any claimed fix actually landed:**

```bash
cd <source-repo>
FIX_SHA=<fix-commit>
git merge-base --is-ancestor "$FIX_SHA" origin/main && echo "merged" || echo "NOT MERGED"
# If NOT merged, the daemon is still running buggy code: merge the fix, rebuild,
# and restart its launchd job. `launchctl bootout` is a stopgap, not a fix.
# ALWAYS verify the fix is on main BEFORE telling the user "fix is shipped".
```

**Why this matters:** fixing `comment-router.yml` (the downstream consumer) does NOT
stop the spend alert. The fix lives at the source — the daemon that posts the comments
in the first place. The comment-router's job-level `if:` is already correct; it just
gets hit thousands of times because the upstream daemon is in a loop.

### Mode B — `set -u` crash in `spend-alert-daily.sh` (2026-07-16, RESOLVED)

`log_warn "$1"` aborts on unbound variable when called with no arg during `slack_post`'s stderr pipe under `set -euo pipefail`. The script terminates before `slack_post` ever fires. Fix landed — `log_warn "${1:-}"` (and same for `log`, `log_error`) per PR in `jleechanorg/jleechanclaw`. If you see this in `tail -40` of the log, the fix has regressed.

## Three independent root causes (one per mode)

| # | Mode | Cause | Fix |
|---|------|-------|-----|
| 1 | A.1 | `comment-router.yml` (PR #8354–#8355) was supposed to consolidate 4 issue_comment workflows, but its `on: issue_comment` trigger fires on EVERY comment, and the `if:` guard skips 99%+ of them. The fix only consolidated workflows; it didn't reduce trigger volume. | Add `if: github.event.comment.author_association == 'OWNER'` to the `on: issue_comment` trigger; cap `concurrency` (N=5). **BUT** verify this isn't a downstream symptom of an upstream spam loop first (see A.2). |
| 2 | A.2 | **Upstream daemon loop** posts the same comment to 1-3 PRs every ~1h. Its dedup key was a per-tick id (fresh bead every tick → never matches) AND the comment posted BEFORE the dedup check ran. | (a) Move the dedup check BEFORE the comment write AND re-key dedup on the branch name (stable across ticks). (b) **VERIFY the fix commit is on main HEAD before claiming the fix is shipped** — `git merge-base --is-ancestor $FIX_SHA HEAD`. |
| 3 | B | `set -u` in `spend-alert-daily.sh` aborts on `log_warn "$1"` when called with no arg | `log_warn "${1:-}"` everywhere, OR remove `-u` from the script's `set` line. |

The bot identity **is** a member of `C0BCVG4F560` (verified 2026-07-23 via `conversations.info` returning `is_member=true` for the bot token fetched from `~/.bashrc HERMES_SLACK_BOT_TOKEN`). The standalone bot token from `HERMES_SLACK_BOT_TOKEN` posts reliably; the scoped MCP identity in this session may report `is_member=false` because it's a different bot identity — don't conflate the two.

## Recovery action when user reports a missed Spend Alert

1. `cat $HOME/.hermes/logs/spend-alert-daily.log | tail -40` — confirm whether the last run completed the Slack post or crashed on the `set -u` line. **If it completed, the alert is in the channel — you're in Mode A (real cost spike), not Mode B (bridge broken).**
2. `jq . $HOME/.hermes/state/spend-alert-state.json` — check the rolling deltas match what the user reported. If `gh_delta` jumped 3x+ over baseline (e.g. $61 vs typical $15), the runway is the cause, not a billing error.
3. `curl -fsS -H "Authorization: Bearer $(bash -c 'source ~/.bashrc; echo $HERMES_SLACK_BOT_TOKEN')" "https://slack.com/api/conversations.history?channel=C0BCVG4F560&limit=5"` — confirm whether the alert landed in #worldai-alerts. **This is the right verification** — `mcp__slack__conversations_replies` may falsely report `not_in_channel` for the scoped identity.
4. **If alert NOT posted (crash / silent failure):** post a manual ack to #worldai-alerts using the bot token (which IS a member) — reply with the same breach numbers so the channel has the missing record.
5. **If alert IS posted (Mode A — the common case):** reply in-thread with the diagnosis. The user wants to know WHY the spend jumped, not whether the bridge worked. Skip directly to the runaway audit below.
6. **Runaway audit (Mode A only):** identify the repo and workflow driving the billable minutes. The pattern in 2026-07-23 was a `comment-router.yml` symptom + an upstream daemon cause — see step 7.
7. **Upstream spam check (Mode A.2 — the most common real cause as of 2026-07-23):** before concluding the comment-router is the runaway, check who is actually posting the comments. If 99% of the `issue_comment` events have one of a small set of body prefixes (e.g. one daemon's escalation prefix), the comment-router is the victim, not the cause. The fix lives in the source that posts the comments. See Mode A.2 in the failure pattern above for the recipe.
8. **Verify the fix is actually live before claiming resolution.** If the alleged fix is a commit on a branch, run `git -C <repo> merge-base --is-ancestor <fix-sha> HEAD`. If the result is "NOT MERGED", the daemon is still running buggy code. Either merge the branch or stop claiming the fix is shipped. (On 2026-07-24 a fix left unmerged on a branch produced a second spend spike identical to the first.)

## Verification commands

```bash
# Step 1: script log + state
tail -40 $HOME/.hermes/logs/spend-alert-daily.log
jq . $HOME/.hermes/state/spend-alert-state.json

# Step 2: channel membership & recent posts
TOK=$(bash -c 'source ~/.bashrc; echo $HERMES_SLACK_BOT_TOKEN')
curl -fsS -H "Authorization: Bearer $TOK" \
     "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200" \
  | jq '.channels[] | select(.id=="C0BCVG4F560")'

# Step 3: identify the cost-driver repo
gh api "orgs/jleechanorg/settings/billing/usage" --paginate \
  | jq '[.usageItems[]? | select(.product == "actions") | select(.date == "2026-07-01T00:00:00Z")] | sort_by(-.netAmount)'

# Step 4: identify the runaway workflow in that repo (last 32h)
# NOTE: `created=>` query param is treated as equality, not greater-than.
# Use `sort=created&direction=desc` and walk pages manually until the
# oldest run's `created_at` < SINCE.
REPO="jleechanorg/<repo>"
python3 ./scripts/gh-cost-audit.py   # see scripts/ dir
```

## Prevention — durable fix shape

- **Mode B (script crash):** `scripts/spend-alert-daily.sh`: change `log_warn "$1"` to `log_warn "${1:-}"` (and same for `log`, `log_error`), OR remove `-u` from the script's `set` line. Pair with `scripts/tests/test_spend_alert_idempotent.py` (or similar) so the crash mode is regression-tested. **Status 2026-07-23: fix is in place; no crash observed today.**
- **Mode A (runaway workflow):** the recurring shape is `comment-router.yml` patterns — workflows that listen to high-volume `issue_comment` events and use a job-level `if:` guard. The job guard short-circuits before billable minutes, but the workflow still registers an event. Mitigations:
  - Add `if:` at the **workflow/job level** that filters by `author_association`, comment body prefix, and `issue.pull_request` BEFORE the runner is allocated
  - Set `concurrency` group to a tight key (`comment-router-${{ github.event.comment.id }}` is already present in this file — verify it)
  - Audit who posts comments at 174/hr — likely a bot loop or external webhook source
  - For the long term, consider an org-wide CODEOWNERS + workflow-level `if: contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)` guard
- **Mode A.2 (upstream daemon runaway):** the recurring shape is a dedup key that uses a fresh-per-tick value (e.g. `bead_id`) instead of a stable identifier (e.g. `head_ref_name`). Mitigations:
  - All dedup keys must be drawn from STABLE identifiers (branch name, PR number, commit SHA) — never from objects that get re-created every tick
  - The dedup check must run BEFORE the SCM write (`comment_external`, `gh api repos/.../issues/.../comments`) — otherwise the write is never suppressed even if the dedup would have matched
  - Add a `cfg.escalation_refire_secs` cooldown (default 3600s) so re-emission is bounded even if the dedup logic has a bug
  - **Every fix commit must be verified as on the deployment branch before declaring "fix shipped"** — `git merge-base --is-ancestor <fix-sha> <deployment-branch>`. A commit on a fix branch is not a fix until that branch is merged into main AND the daemon is rebuilt AND the running launchd job is restarted.

## Pitfalls

- **The bridge is usually NOT broken** when a Spend Alert appears in session context. MCP Agent Mail relays everything from #worldai-alerts into the session — that's working as designed. Spend the first 30 seconds confirming the Slack post landed, then pivot to the cost driver. Don't waste a turn fixing a non-broken bridge.
- **"Fix is in PR #N" ≠ "fix is shipped".** The skill recipes (and older incidents) often cite a PR number or branch name as if the fix is live. **ALWAYS verify with `git merge-base --is-ancestor <fix-sha> HEAD`** before claiming the fix is merged. The 2026-07-24 incident was caused by trusting a previous skill's stated fix location without re-verifying.
- **The `created=>` query param on `gh api repos/<repo>/actions/runs` is treated as EQUALITY, not greater-than.** It returns 0 hits even when plenty of runs exist after the date. Use `sort=created&direction=desc` + manual pagination instead.
- **`/actions/runs/{id}/timing` returns `billable: {}` for completed runs.** The billable field is reserved for in-progress / queued runs. To approximate cost, use `updated_at - created_at` to compute wall-clock minutes and multiply by the runner type's $/min rate. The `gh-actions-cost-monitor.sh` script does this with `COST_PER_MINUTE=0.002` (Linux self-hosted rate).
- **`gh-api` `repos/<repo>/issues/comments` ignores the `since` query parameter.** The `since` field on the comment-schema response is also undefined. To filter comments to a time window, paginate (sort=created + direction=desc) and filter by `created_at` in-process.
- **The `runs` API sees `run_duration_ms` as 0/null for skipped runs** even if the workflow allocated a runner. Use `runs.total_count` to gauge trigger volume, not minutes.
- **Don't trust `run_duration_ms` field** — it returns `null` or `0` for `skipped` runs, even if the workflow was allocated a runner. Use `updated_at - created_at` to get the real wall-clock time per run.
- Don't assume `is_member=False` from `mcp__slack__conversations_replies` is global to the bot — it's per-identity. The `HERMES_SLACK_BOT_TOKEN` env may resolve to a different bot identity than the one bound to the live Slack MCP server. Use `conversations.history` with the bot token to verify, not `conversations_replies` from the scoped MCP.
- **Don't trust a `bead_id` as a dedup key.** Per-tick fresh objects (new bead IDs, new session IDs) make the ledger never match. Use stable identifiers (branch name, PR number, commit SHA) for dedup keys.
- Don't post the user's reply via `mcp__slack__conversations_add_message` from this session context — it's the wrong identity. Use `chat.postMessage` with the bot token from `~/.bashrc`.
- **GH billing API returns monthly buckets only** — `date == "2026-07-01T00:00:00Z"` is the entire month, not a day. Don't try to slice it by day; you'll see empty results. The script's `gh_delta` is a 24h-difference between two MTD snapshots, NOT a true daily-spend figure.
- The Agent Mail relay is **in addition to**, not a replacement for, the Slack post. Don't "fix" by silencing the cron — fix the crash and keep both channels.
- **A "skipped" workflow run still counts.** `conclusion=skipped` means 0 billable minutes, but the workflow_run event is registered. If a workflow fires 5,000+ times in 32h, the `runs` API is polluted even if no minutes are billed. Use the runs API for diagnosing trigger volume, not the billing API.
- **Comment-router noise is usually a SYMPTOM, not the cause.** When `comment-router.yml` fires 5,000+ times/32h on `issue_comment`, the first instinct is to harden the workflow (add author_association guard, lower concurrency). That fixes the symptom but misses the cause: an upstream automation (typically a PAT-driven daemon) is in a feedback loop posting the same comment to 1-3 PRs every ~1h. Pull the actual comment bodies via `repos/<repo>/issues/comments?per_page=100&direction=desc&sort=updated` and group by `user.login` + `body` prefix BEFORE proposing a workflow fix. If 99% of comments come from one automation with one body prefix, the fix lives at that automation, not at the comment-router. See Mode A.2 for the fix.

## Companion skills / files

- `references/comment-router-runaway-2026-07-23.md` — original 2026-07-23 incident detail
- `scripts/gh-cost-audit.py` — runs/workflow volume audit helper (32h window, per-workflow breakdown with skip counts)
- `scripts/comment-audit.py` — issue_comments audit helper (per-author, per-prefix, per-hour breakdown for time-windowed analysis)
