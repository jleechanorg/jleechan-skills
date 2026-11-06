# Babysit Cron Audit Recipe (2026-07-02 + 2026-07-05)

Recipe for auditing the babysit cron registry and reaping stale jobs.
Used in the 2026-07-02 audit (11 stale babysits reaped) and the
2026-07-05 babysit-cron-leak post-mortem (2 live leaks reaped).

## The audit (5-step)

```bash
# Step 1: List all babysit-shaped jobs (enabled or not)
cronjob list | jq '.jobs[] | select((.name|test("babysit|wa-[0-9]"; "i")) or
  (.prompt|test("babysit|wa-[0-9]+"; "i"))) |
  {id, name, enabled, state, schedule, last_status}'

# Step 2: Filter to ENABLED babysits only (the live-leak candidates)
cronjob list | jq '.jobs[] | select(.enabled and
  ((.name|test("babysit|wa-[0-9]"; "i")) or
   (.prompt|test("babysit|wa-[0-9]+"; "i"))))'

# Step 3: For each enabled babysit, extract the PR reference from the
# prompt and verify state via gh pr view. The babysit prompt normally
# contains either a `https://github.com/owner/repo/pull/N` URL or a bare
# `PR #N` reference.

# Method A (URL form, exact):
cronjob list | jq -r '.jobs[] | select(.enabled and (.prompt|test("github.com"))) |
  .prompt' | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' | sort -u | while read url; do
    echo "=== $url ==="
    gh pr view "$(echo $url | awk -F/ '{print $NF}')" \
      --repo "$(echo $url | awk -F/ '{print $4"/"$5}')" \
      --json state,mergedAt,closedAt
done

# Method B (bare PR #N, defaults to $GITHUB_REPOSITORY):
cronjob list | jq -r '.jobs[] | select(.enabled and (.prompt|test("PR #"))) |
  .prompt' | grep -oE 'PR #[0-9]+' | sort -u | while read pr; do
    n=$(echo $pr | awk '{print $2}')
    echo "=== $pr ==="
    gh pr view "$n" --repo $GITHUB_REPOSITORY \
      --json state,mergedAt,closedAt
done

# Step 4: For each terminal-state PR, find the cron job ID and reap it.
# Terminal = state=MERGED OR (state=CLOSED AND mergedAt is null)

for id in $(cronjob list | jq -r '.jobs[] | select(.enabled and
  ((.name|test("babysit|wa-[0-9]"; "i")) or
   (.prompt|test("babysit|wa-[0-9]+"; "i")))) | .id'); do
  prompt=$(cronjob list | jq -r ".jobs[] | select(.id==\"$id\") | .prompt")
  # Extract PR ref (URL or bare) and check state
  url=$(echo "$prompt" | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' | head -1)
  if [ -n "$url" ]; then
    pr_n=$(echo "$url" | awk -F/ '{print $NF}')
    pr_repo=$(echo "$url" | awk -F/ '{print $4"/"$5}')
  else
    pr_n=$(echo "$prompt" | grep -oE 'PR #[0-9]+' | head -1 | awk '{print $2}')
    pr_repo="$GITHUB_REPOSITORY"
  fi
  if [ -z "$pr_n" ]; then continue; fi

  state=$(gh pr view "$pr_n" --repo "$pr_repo" --json state -q .state 2>/dev/null)
  echo "$id :: PR #$pr_n ($pr_repo) :: $state"

  if [ "$state" = "MERGED" ] || [ "$state" = "CLOSED" ]; then
    echo "  → REAPING: cronjob action=remove job_id=$id"
    cronjob action=remove job_id="$id"
  fi
done

# Step 5: Verify final state (should be 0 enabled babysits)
cronjob list | jq '.jobs[] | select(.enabled and
  ((.name|test("babysit|wa-[0-9]"; "i")) or
   (.prompt|test("babysit|wa-[0-9]+"; "i"))))' | wc -l
```

## The reaper (one-liner variant)

For a quick clean when the prompt extraction is consistent:

```bash
# Reap all enabled babysits whose target PR is MERGED on $GITHUB_REPOSITORY
for id in $(cronjob list | jq -r '.jobs[] | select(.enabled and
  (.name|test("babysit|wa-[0-9]"; "i"))) | .id'); do
  pr_n=$(cronjob list | jq -r ".jobs[] | select(.id==\"$id\") | .prompt" |
    grep -oE 'PR #[0-9]+' | head -1 | awk '{print $2}')
  [ -z "$pr_n" ] && continue
  state=$(gh pr view "$pr_n" --repo $GITHUB_REPOSITORY --json state -q .state 2>/dev/null)
  if [ "$state" = "MERGED" ] || [ "$state" = "CLOSED" ]; then
    echo "REAPING $id (PR #$pr_n = $state)"
    cronjob action=remove job_id="$id"
  fi
done
```

## Why this recipe (and why it's the safety net for Phase 0.5)

The audit recipe above is the **manual fallback** for the babysit-stale-watchdog launchd job. If the watchdog isn't installed (it requires an operator-side `launchctl load` because it SIGTERMs the gateway if loaded in-session), the audit can be run by hand or via a one-time cron with `--delete-after-run`.

The in-script self-cancel (`ao-babysit/scripts/babysit.py --cron-job-id`)
is the **fast path** — fires on the next tick after the PR reaches
terminal state, no human involvement needed. The watchdog is the
**medium path** — fires every 30 min via launchd. The audit recipe
above is the **slow path** — runs when neither of the other two has
caught a leak.

For a fully leak-free babysit install: install the watchdog + use
Phase 0.5 in every new babysit prompt + run the audit recipe monthly
as belt-and-suspenders.

## Anti-patterns

- ❌ Don't reap a babysit cron whose PR is OPEN or in-progress — even if
  the worker has been silent for hours. The babysit should stay
  enabled until the PR is terminal.
- ❌ Don't disable the watchdog job itself (`ai.hermes.schedule.babysit-stale-watchdog`) — that re-opens the leak class.
- ❌ Don't trust the cron prompt's claim of "PR merged" without
  verifying via `gh pr view --json state` — the prompt was authored
  at PR-open time and may not reflect subsequent events.
- ❌ Don't post a "reaped N babysits" summary to the user's personal
  channel — go to `#ai-general` per `slack-channel-routing-policy` for
  agent-generated audit reports.