---
name: pr-green-definition
description: Canonical /green definition — CI green + no merge conflicts, both verified at current PR HEAD SHA. Quality gates (evidence, review, comment-resolution) live in the draft-first-pr skill, not here.
type: policy
---

# PR "Green" Definition (`/green`)

**Redefined 2026-07-28 (operator-directed).** `/green` is exactly **two gates**,
both verified at the current PR HEAD SHA:

| # | Gate | Verification |
|---|---|---|
| 1 | **CI green** | Every CI check at HEAD passes — use the `statusCheckRollup` JSON pattern (see `CLAUDE.md` § "CI status check: use JSON, not grep"): `StatusContext` rows use `.state`; GitHub Actions `CheckRun` rows use `.conclusion`. Never `gh pr checks \| grep`. |
| 2 | **No merge conflicts** | `mergeable == "MERGEABLE"` (retry while `UNKNOWN`; `CONFLICTING` fails the gate). |

**Removed from `/green`** (no longer gates merge-readiness): CodeRabbit/Bugbot
approval, inline-comment-thread resolution (`resolveReviewThread` machinery),
the evidence-link gate, the PR-description gate, and the old "6-green"/"7-green"
checklist numbering. Historical references to "6-green", "6/6 gates", or
"Gate 3–6" elsewhere in this repo's docs/skills/memory describe the **retired**
definition — do not follow them for new work; treat them as stale terminology
pending cleanup.

**CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take
what's useful; never a gate, never a wait, at any phase of the PR lifecycle
(draft or ready-for-review). Human `MERGE APPROVED` remains the only merge gate.

## Where the quality gates went

Those checks did not disappear — they moved to the **draft phase**. PRs are
opened as **DRAFT** and stay draft until:

1. `/es` (evidence standards) passes,
2. `/er` (evidence/code review) passes, and
3. `/advice` approves,

only then does the PR flip to ready-for-review and get driven through the two
`/green` gates above. See the `draft-first-pr` skill for the full draft-phase
lifecycle contract (opening PRs as draft, evidence/review/advice ordering, and
the ready-for-review flip).

**Slow CI never blocks `/green`.** If a check has been running >10 minutes past
its normal runtime, run the equivalent test locally and post proof labeled
"local run — CI still pending" (command + output + timestamp + git SHA) instead
of waiting indefinitely on the runner.

**Merge authorization is separate from `/green` and unchanged.** Even a fully
`/green` PR (both gates pass) requires literal human `MERGE APPROVED` in the
most recent live message before any `gh pr merge` or REST merge call — see this
repo's merge-safety policy. "Drive to `/green`" is never merge authorization by
itself.

## Verification Procedure (Mandatory)

**WARNING: `gh pr checks` is NOT sufficient.** The Green Gate workflow has
historically exited 0 (success) regardless of individual step outcomes, so
`gh pr checks` can show "Green Gate: pass" even when the underlying CI checks
failed, and "CodeRabbit: pass" only means the webhook responded — neither is
evidence of the gates above. Always use the JSON `statusCheckRollup` pattern.

### Gate 1 — CI green

```bash
gh pr view N --repo OWNER/REPO --json statusCheckRollup --jq \
  '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (.state == "FAILURE" or .state == "ERROR")) or (.__typename == "CheckRun" and (.conclusion // "") != "" and (.conclusion | ascii_upcase | (. == "FAILURE" or . == "ERROR" or . == "TIMED_OUT" or . == "ACTION_REQUIRED" or . == "STARTUP_FAILURE" or . == "STALE"))))] | length'
```

Zero-length result = Gate 1 passes. `StatusContext` rows use `.state`;
`CheckRun` (GitHub Actions) rows use `.conclusion` — never rely on `.state` for
Actions rows.

### Gate 2 — No merge conflicts

```bash
gh pr view N --repo OWNER/REPO --json mergeable --jq '.mergeable'
# "MERGEABLE" = pass. "UNKNOWN" = GitHub still computing, retry.
# "CONFLICTING" = fail, resolve conflicts before re-checking.
```

### Always check merge/close state first

```bash
gh api repos/OWNER/REPO/pulls/N --jq '{state, merged}'
# If merged:true or state:"closed" → report and exit. Do NOT check mergeable_state,
# reviews, etc. mergeable_state returns "unknown" for merged PRs too (identical to
# the transient CI-running state) — checking only that field causes loops to
# report "blocked" on already-merged PRs for hours.
```

## PR Freeze Discipline

**Pre-push commit count check**: Before pushing a PR branch, run
`COMMITS=$(git rev-list --count origin/main..HEAD)`. If > 5 commits, warn:
"N commits — squash before final review to avoid CR incremental stall and merge
conflicts."

**Squash before final merge**: Once both `/green` gates pass and the
draft-phase quality gates (`/es`, `/er`, `/advice`) are done, squash all commits
into ONE before pushing:

```bash
git reset --soft origin/main
git commit -m "feat(scope): concise single-commit message"
git push --force-with-lease
```

Then merge with explicit human authorization (`gh pr merge N --squash --admin`)
— see this repo's merge-safety policy for the required approval phrase.

**Why**: 16-commit PR #412 took 5 review rounds. CR treats squashed commits as
"already reviewed" and refuses re-review. 1-commit squash merged in one shot.

**Never use `git commit --no-edit`** after a merge conflict — it steals
origin/main's commit message. Always provide an explicit squash commit message.

**Admin merge** (when CR is in an incremental stall during the draft phase):
`gh pr merge N --squash --admin --subject "feat(scope): message"`. Verify
`gh api repos/OWNER/REPO --jq .permissions.admin` first. Still requires literal
human `MERGE APPROVED`.

**Export PR admin merge**: For `jleechanorg/claude-commands` export PRs (title
contains "Export"), when `cr-loop-guard.sh` returns `skip` AND CR state is
`CHANGES_REQUESTED` on acknowledged design limitations (not code bugs), treat
the PR as merge-ready during the draft-phase review.

## Docs-only non-prod merge exception

A docs-only, non-production PR (touching only `docs/`, `.claude/`, `.codex/`,
`.cursor/`, `AGENTS.md`, `CLAUDE.md`-style files) may skip the draft-phase
evidence/video requirements per the operator's 2026-07-28 grant — eligibility
test and scope for this exception live in the repo's evidence-standards skill
(`.claude/skills/evidence-standards.md`); the two `/green` gates above still
apply unchanged.

---

**Historical note**: this skill formerly defined a "6-green" (previously
"7-green") numbered-gate checklist — CI, no-conflicts, CodeRabbit APPROVED,
Bugbot clean, comments resolved, evidence review — as the single merge-readiness
bar. That checklist was retired 2026-07-28 in favor of the 2-gate `/green` +
draft-phase model above. The Skeptic/Gate-7 removal that preceded this
redefinition is tracked in bead `rev-p0cc4`.
