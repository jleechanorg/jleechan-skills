---
name: zero-touch
description: Canonical definition of zero-touch-by-operator for PR autonomy measurement. Use when evaluating, reporting, or labeling PR autonomy status.
---

# Zero-Touch-by-Operator

## Definition

A PR is **zero-touch** when AO (Agent Orchestrator) brought it from creation to merge without any manual intervention from a Claude Code terminal session or human operator.

Specifically:
1. AO spawned the worker session autonomously (via `ao spawn`, lifecycle-worker, or poller)
2. The worker drove the PR to **N-green** (all applicable conditions) without external nudges
3. `skeptic-cron.yml` (or equivalent auto-merge gate) merged the PR

## N-green criteria

Not all PRs need all 7 green conditions. The merge gate requires all **applicable** conditions:

| # | Condition | Always required? |
|---|-----------|-----------------|
| 1 | CI passing | Yes |
| 2 | No merge conflicts | Yes |
| 3 | CodeRabbit APPROVED | Yes (unless CR disabled for repo) |
| 4 | Bugbot clean | Yes (unless Bugbot not configured) |
| 5 | Inline comments resolved | Yes |
| 6 | Evidence review pass | Skippable for docs-only, config-only, chore |
| 7 | Skeptic PASS | Skippable for docs-only, config-only, chore |

A docs-only change passing conditions 1-5 is still zero-touch if AO handled it autonomously.

## What breaks zero-touch

- A Claude Code terminal session (human-operated) pushed fixes to the PR branch
- A human or terminal session posted review comments, approvals, or merge clicks
- A human dismissed a bot review to unblock merge
- A terminal session ran `@coderabbitai approve` or similar to bypass a gate
- A human manually triggered CI re-runs to get past flaky tests

## What does NOT break zero-touch

- Jeffrey asking questions about the PR in Slack (observation, not intervention)
- Bot-to-bot interactions (CR, Bugbot, Skeptic, evidence-review-bot)
- AO workers posting `@coderabbitai approve` or `@coderabbitai all good?` (worker doing its job)
- Jeffrey approving the AO spawn itself (dispatch is expected; execution must be autonomous)

## Measurement — GitHub actor audit

A PR is zero-touch if the only GitHub actors (commits, reviews, comments, merges) are:
- `jleechan2015` (AO agent GitHub identity)
- `github-actions[bot]` (CI, skeptic-cron)
- `coderabbitai[bot]` (code review)
- `cursor[bot]` (Bugbot)

If `$USER` (Jeffrey's personal account) or any other human/terminal identity appears as a PR actor, it's **operator-assisted**.

## KPI

```
zero_touch_rate = (zero-touch merged PRs) / (total merged PRs) * 100
```

Measured weekly. Target: increasing trend.

## Labeling (planned)

`skeptic-cron.yml` should label merged PRs as `zero-touch` or `operator-assisted` based on the actor audit. Not yet implemented — tracked in beads.

## Reference

Full doc with HTML version: `~/.openclaw/docs/ZERO_TOUCH.md` / `ZERO_TOUCH.html`
