---
name: pr-green-definition
description: Canonical /green definition — CI green + no merge conflicts, both verified at current PR HEAD SHA. Quality gates (evidence, review, comment-resolution) live in the draft-first-pr skill, not here.
type: policy
---

# PR "Green" Definition (2-Gate, canonical 2026-07-28)

`/green` means exactly TWO gates, both verified at the PR's **current HEAD SHA**:

| # | Gate | Verification |
|---|---|---|
| 1 | **CI green** | Every CI check at HEAD passes (no FAILURE/ERROR/pending-stale) |
| 2 | **No merge conflicts** | `mergeable == MERGEABLE` (retry while `UNKNOWN`; `CONFLICTING` is a hard FAIL) |

**Nothing else gates `/green`.** Inline-comment resolution (`resolveReviewThread`), the evidence-link gate, the PR-description gate, and the old "6-green" numbering are **not** `/green` gates anymore (operator directive, 2026-07-28). Those quality checks happen in the **draft phase**, before a PR is marked ready for review. The full canonical lifecycle, including when `/er` is required by that lifecycle, and its **SHA-binding rule** (every gate verdict, including `/green`, expires the moment PR HEAD moves and must be re-earned at the new SHA) live in `~/.claude/skills/draft-first-pr/SKILL.md` — do not restate that chain here, just apply it.

**CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait, at any phase of the PR lifecycle. Human `MERGE APPROVED` remains the only merge gate.

Merge authorization is unchanged and separate from `/green`: never call `gh pr merge` / `gh api .../merge` without literal `MERGE APPROVED` (case-insensitive) in the human's most recent live message, for `$GITHUB_REPOSITORY`. Reaching `/green` is not merge authorization.

## Gate 1 — CI green: verification procedure

**`gh pr checks` is NOT sufficient** — it can report "pass" from a webhook ping or during GraphQL rate-limit exhaustion while the underlying checks are stale or failing (memory: `feedback_2026-07-11_gh_pr_checks_silent_stale_data_during_graphql_exhaustion.md`). Use the `statusCheckRollup` JSON pattern instead:

```bash
gh pr view N --json statusCheckRollup --jq '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length'
```

`0` (with nothing still pending) → Gate 1 PASS. `statusCheckRollup` is mixed: `StatusContext` rows use `.state`; GitHub Actions `CheckRun` rows use `.conclusion` — never rely on `.state` for Actions rows.

**Freshness discipline — verify against HEAD, not a stale run:**
- Pull the PR's current head SHA first: `gh pr view N --json headRefOid --jq '.headRefOid'`.
- When reading raw check-runs via `commits/{sha}/check-runs`, use that head SHA, not a cached value from an earlier turn — rerun cycles leave stale check-runs from prior SHAs in the same job-name bucket (memory: `feedback_2026-07-21_check_runs_stale_pickup_across_reruns.md`). Scope to the current run's own job list via `actions/runs/<run_id>/jobs`, not a `max_by(started_at)` dedup across all reruns.
- `gh api .../check-runs` **silently truncates to 30 rows** without `--paginate` — always compare `total_count` to the returned array length before concluding a check "doesn't exist" (memory: `feedback_2026-07-21_gh_api_check_runs_pagination_silent_truncation.md`).
- REST and GraphQL are **separate quota buckets**; `gh api rate_limit` is quota-exempt — check it first, and fall back to the other bucket for the same data before declaring "rate-limited". Full procedure: `~/.claude/skills/github-cli-reference.md`.

## Gate 2 — No merge conflicts: verification procedure

```bash
gh pr view N --json headRefOid,mergeable,mergeStateStatus --jq '.'
```

| Field | Required | If wrong |
|-------|----------|----------|
| `mergeable` | `MERGEABLE` | `UNKNOWN` → wait and re-poll (GitHub is still computing); `CONFLICTING` → hard FAIL, resolve before `/green` |
| `mergeStateStatus` | Informational only | `DIRTY` corroborates a conflict, but non-`CLEAN` states such as `UNSTABLE` may reflect CI rather than conflicts; Gate 2 is decided by `mergeable`. |

**Re-check every time you state a verdict, not once per session.** Mergeability is base-branch-dependent and recomputed asynchronously — a PR can flip from `MERGEABLE` to `CONFLICTING` hours later with zero action on its own branch (an unrelated PR merging to `main` first and touching the same lines is enough). Treat every prior `/green` claim as expired the moment you act on or repeat it: re-fetch, don't recall.

**Merge conflicts are routine, not an escalation event** — resolve them yourself (rebase, take the correct side of a mechanical collision, reapply changes) and report the resolution; escalate only for genuinely ambiguous business logic (see `~/.claude/CLAUDE.md` "Left/right-shift autonomous work").

## Status check — canonical pattern (mandatory)

Always check merge/close state FIRST, before evaluating either gate:

```bash
gh api repos/OWNER/REPO/pulls/N --jq '{state, merged}'
```

If `merged:true` or `state:"closed"`, stop and report — do not evaluate Gates 1/2. `mergeable_state` returns `unknown` for merged PRs, identical to its transient CI-running state, which causes false "blocked" reports on already-merged PRs.

## Slow/stuck CI — stay productive while Gate 1 remains pending

If a CI check is pending or backlogged **>10 minutes past its normal runtime**, do not just wait: run the equivalent test locally now and post proof labeled **"local run — CI still pending/rerunning"** with the exact command, output, timestamp, and git SHA (PR comment + PR description). This is interim proof, never a substitute for the CI check itself finishing green.

## Related

- `~/.claude/skills/draft-first-pr/SKILL.md` — the pre-green quality gates that now live in the draft phase, not in `/green`
- `~/.claude/skills/github-cli-reference.md` — REST ↔ GraphQL dual-bucket procedure
