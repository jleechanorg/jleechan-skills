---
name: pr-green-definition
description: Canonical /green definition — applicable CI or documented exception + no merge conflicts, verified at current PR HEAD SHA. Quality gates live in pr-lifecycle.
metadata:
  type: policy
---

# PR "Green" Definition (2-Gate, canonical 2026-07-28)

`/green` means exactly TWO gates, both verified at the PR's **current HEAD SHA**:

| # | Gate | Verification |
|---|---|---|
| 1 | **Applicable validation** | Documentation-only: CI NOT REQUIRED with proportionate local validation below. Otherwise every required check passes at HEAD, through CI or the local-equivalent exception for backlogged checks. |
| 2 | **No merge conflicts** | `mergeable == MERGEABLE` (retry while `UNKNOWN`; `CONFLICTING` is a hard FAIL) |

**Nothing else gates `/green`.** Inline-comment resolution (`resolveReviewThread`), the evidence-link gate, the PR-description gate, and the old "6-green" numbering are **not** `/green` gates anymore (operator directive, 2026-07-28). Those quality checks follow the canonical **draft and ready/final phases** in `~/.claude/skills/pr-lifecycle/SKILL.md`; green alone does not establish READY. Apply that owner's applicability (including when `/er` is required by that lifecycle), final `/er` and `/advice` closure, and SHA-binding rule, including justified delta-based reaffirmation — do not restate that chain here, just apply it. Recheck `/green` at the live head and base before stating its verdict.

**CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait, at any phase of the PR lifecycle. Human `MERGE APPROVED` remains the only merge gate.

Merge authorization is unchanged and separate from `/green`: never call `gh pr merge` / `gh api .../merge` without literal `MERGE APPROVED` (case-insensitive) in the human's most recent live message, for `$GITHUB_REPOSITORY`. Reaching `/green` is not merge authorization.

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.

## Documentation-only CI exception

Classify the complete diff at the current PR HEAD by what changed, not by file extension alone. Documentation-only changes do not require CI, triggering/retrying CI, waiting for runners, or the ten-minute backlog threshold. Instruction and skill documentation (including AGENTS.md, CLAUDE.md and SKILL.md) and documentation-only pointer maintenance qualify when no executable or application-runtime behavior changes.

Executable code or embedded automation, application prompts, workflows, schemas, runtime configuration, and mixed diffs containing those changes do not qualify, even inside a Markdown file or docs directory. An agent workflow described in prose is instruction documentation; changing executable hook/script content is not.

Run proportionate local checks for the actual change, such as diff hygiene, link/pointer resolution, or skill metadata validation. Record `Gate 1: CI NOT REQUIRED — documentation-only` with the reviewed SHA, scope, commands and results; never label skipped or unrun CI as passed. Address relevant failures in those local checks. Gate 2, applicable draft and final review/evidence requirements, and merge authorization remain unchanged. This policy does not bypass branch protection or authorize disabling/canceling CI jobs.

## No-CI exception — a check that cannot run is not a check to wait on

When CI **does not exist** for this PR, do not sleep-poll it. Three provable shapes qualify, and each needs its evidence recorded before you skip the wait:

1. **No workflow applies.** No workflow file matches the changed paths (a `paths:` filter excludes this diff), or the repo has no workflow that could run this PR at all.
2. **No runner can host it.** `gh api repos/<owner>/<repo>/actions/runners` reports zero registered runners for the repo, or every available org runner is `busy: true`, so the job can only sit `QUEUED`.
3. **Checks are structurally stuck.** The rollup is `QUEUED`/`PENDING` with no start, and a runner-capacity read explains it — repeatedly, not once.

On any of those, apply the local-equivalent exception immediately — do not wait for the ten-minute backlog threshold, and never substitute a `sleep N` + `gh pr checks` loop for actually running the command. Then record:

```
Gate 1: CI NOT APPLICABLE — <reason: no matching workflow | zero repo runners | runners saturated QUEUED>
  evidence: <command + the output line proving it>
  local equivalent: <the workflow's own command> → <result at SHA>
```

Guardrails that do not move: never label unrun CI as passed, never disable or cancel a job or touch branch protection, never widen this into "skip CI" for a repo whose checks are merely slow or red, and keep Gate 2, applicable review/evidence gates, and merge authorization exactly as they are. A check that has actually started is backlogged CI, not missing CI — that stays under the local-equivalent exception with its own reporting.

## Gate 1 — CI green: verification procedure (when CI applies)

**`gh pr checks` is NOT sufficient** — it can report "pass" from a webhook ping or during GraphQL rate-limit exhaustion while the underlying checks are stale or failing (memory: `feedback_2026-07-11_gh_pr_checks_silent_stale_data_during_graphql_exhaustion.md`). Use the `statusCheckRollup` JSON pattern instead:

```bash
gh pr view N --json statusCheckRollup --jq '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length'
```

`0` (with nothing still pending) → Gate 1 PASS through CI. For backlogged checks, apply the local-equivalent exception below before deciding Gate 1. `statusCheckRollup` is mixed: `StatusContext` rows use `.state`; GitHub Actions `CheckRun` rows use `.conclusion` — never rely on `.state` for Actions rows.

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

## Backlogged CI — local-equivalent Gate 1 evidence

This section applies only when CI is required; documentation-only changes use the exception above immediately.

If a check has been queued/pending for **more than 10 minutes**, run its actual workflow command locally and post proof labeled **"local run — CI still pending/rerunning"** with the command, output, timestamp, and current PR HEAD SHA (PR comment + PR description). Passing local equivalents satisfy Gate 1 for those backlogged checks; identify which checks passed locally and which passed in CI. Report local failures immediately. If an equivalent cannot run locally, that check remains unproven. This exception does not waive failed checks, missing evidence, SHA freshness, Gate 2, or merge authorization.

### Required local-equivalent receipt

Map each substituted job and matrix entry to its actual workflow/reusable-script command, runtime, dependencies, services, flags, non-secret configuration and required artifacts. Run against the current candidate head and actual base; disclose dirty changes with hashes instead of claiming a clean commit. Relevant uncommitted changes cannot establish PASS for the published candidate: commit them through the sole owner and rerun applicable checks, or run against verified identical candidate bytes in isolation. Preserve unrelated dirty work without resetting it; document why it cannot affect the result. Record original start/end timestamps, full relevant output, exit status, source/artifact hashes and environment differences. Put a retrievable sanitized gist URL and the per-job mapping in the PR description, with applicable inline media under the lifecycle evidence rules.

Distinguish CI PASS, local-equivalent PASS, pending, failed and unproven for every required job. A convenient subset, wrong platform, mocked external boundary or unrelated smoke test is not equivalent. Failed CI is not delayed CI; diagnose and resolve it, never substitute a convenient local pass. Hosted-only checks that cannot be reproduced remain unproven. Later contradictory CI reopens readiness. Do not spoof checks, disable protection or cancel jobs to create green; required platform merge protection and separate merge authorization remain intact.

## Related

- `~/.claude/skills/pr-lifecycle/SKILL.md` — applicable draft and ready/final quality gates, separate from `/green`
- `~/.claude/skills/github-cli-reference.md` — REST ↔ GraphQL dual-bucket procedure
