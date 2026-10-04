---
name: zero-touch
description: Canonical definition of zero-touch-by-operator for PR autonomy measurement. Use when evaluating, reporting, or labeling PR autonomy status.
---

# Zero-Touch-by-Operator

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


## Definition

A PR is **zero-touch** when AO (Agent Orchestrator) produced a PR that completed
the draft-first quality sequence and reached `/green` without manual
intervention from a Claude Code terminal session or human operator. Canonical
definitions live in `draft-first-pr` and `pr-green-definition`.

This repo requires explicit human `MERGE APPROVED` authorization before any
merge (see this repo's merge-safety policy) — that authorization step, and the
`gh pr merge` command it triggers, are **not** by themselves a zero-touch
violation. The metric measures AO's autonomy in *producing* a mergeable-quality
PR, not who executes the final merge click. (Prior to
[PR #8217](https://github.com/$GITHUB_REPOSITORY/pull/8217), condition
#3 required `skeptic-cron.yml` to have auto-merged the PR; that gate and its
auto-merge mechanism no longer exist in this repo, so this condition is retired
rather than left permanently unsatisfiable.)

Specifically:
1. AO spawned the worker session autonomously (via `ao spawn`, lifecycle-worker, or poller)
2. The worker completed `/es`, `/er`, and `/advice`, then reached `/green`, without external nudges
3. No human/terminal session pushed commits, resolved comments, fixed CI, or posted reviews on the PR branch before it reached that state

## Quality-complete criteria

Use `~/.claude/skills/draft-first-pr/SKILL.md` for the draft-phase sequence and
`~/.claude/skills/pr-green-definition/SKILL.md` for the two `/green` gates.
CodeRabbit and Bugbot are advisory and do not determine zero-touch status.
Repo evidence exceptions still apply where the evidence standards permit them.

## What breaks zero-touch

- A Claude Code terminal session (human-operated) pushed fixes to the PR branch
- A human or terminal session posted review comments or approvals
- A human dismissed a bot review to unblock merge
- A terminal session ran `@coderabbitai approve` or similar to bypass a gate
- A human manually triggered CI re-runs to get past flaky tests

**Not counted as breaking zero-touch:** the mandatory `MERGE APPROVED` human
authorization and the merge command itself — every PR in this repo requires
this regardless of how autonomously it was produced.

## What does NOT break zero-touch

- Jeffrey asking questions about the PR in Slack (observation, not intervention)
- Bot-to-bot interactions (CR, Bugbot, Skeptic, evidence-review-bot)
- AO workers posting `@coderabbitai approve` or `@coderabbitai all good?` (worker doing its job)
- Jeffrey approving the AO spawn itself (dispatch is expected; execution must be autonomous)

## Measurement — GitHub actor audit

A PR is zero-touch if, **up to the point of the merge action**, the only GitHub
actors (commits, reviews, comments) are:
- `jleechan2015` (AO agent GitHub identity)
- `github-actions[bot]` (CI)
- `coderabbitai[bot]` (code review)
- `cursor[bot]` (Bugbot)

**The merge action itself is excluded from this audit.** Since PR #8217 removed
the auto-merge mechanism, every merge in this repo is executed by a human-facing
session under explicit `MERGE APPROVED` authorization — the merge event is not a
zero-touch signal one way or the other. Only audit actions that happened *before*
the merge command.

If `$USER` (Jeffrey's personal account) or any other human/terminal identity
appears as a commit author, reviewer, or commenter before the merge, it's
**operator-assisted**.

## KPI

```
zero_touch_rate = (zero-touch merged PRs) / (total merged PRs) * 100
```

Measured weekly. Target: increasing trend.

## Labeling (planned)

Previously planned to run via `skeptic-cron.yml`; that workflow no longer exists
(removed by PR #8217). Labeling mechanism TBD — not yet implemented, tracked in beads.

## Reference

(No external doc currently exists — this SKILL.md is the sole source of truth.
A prior reference to `~/.openclaw/docs/ZERO_TOUCH.md`/`.html` pointed to files
that do not exist on disk; removed rather than left as a dead link.)
