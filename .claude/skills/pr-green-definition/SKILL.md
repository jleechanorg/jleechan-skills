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
| 1 | **Applicable validation** | Documentation-only: CI NOT REQUIRED with proportionate local validation below. Otherwise every required check passes at HEAD, through CI, the documented `CI NOT APPLICABLE` exception, or the local-equivalent exception for backlogged checks. |
| 2 | **No merge conflicts** | `mergeable == MERGEABLE` (retry while `UNKNOWN`; `CONFLICTING` is a hard FAIL) |

**Nothing else gates `/green`.** Inline-comment resolution (`resolveReviewThread`), the evidence-link gate, the PR-description gate and the old "6-green" numbering are **not** `/green` gates (operator directive, 2026-07-28), nor is CodeRabbit/Bugbot feedback: read it and take what is useful, but it is never a gate or a wait at any phase. Those quality checks follow the canonical **draft and ready/final phases** in `~/.claude/skills/pr-lifecycle/SKILL.md`, including its `/er` applicability, final `/er` and `/advice` closure, and SHA-binding rule with justified delta-based reaffirmation; apply that chain rather than restating it. Green alone does not establish READY. Recheck `/green` at the live head and base before stating its verdict.

Merge authorization is separate: follow `~/.codex/AGENTS.md` § Merge safety and the target repository's explicit merge contract. `/green` alone is not merge authorization.

## Retained review integrations

Follow [pr-lifecycle's retained review integrations](../pr-lifecycle/SKILL.md#retained-review-integrations) for skill discovery (including on a remote host), `UNAVAILABLE` reporting, quorum and disclosure boundaries.

## Documentation-only CI exception

Classify the complete diff at the current PR HEAD by what changed, not by file extension alone. Documentation-only changes need no CI, CI trigger or retry, runner wait, or ten-minute backlog threshold. Instruction and skill documentation (including AGENTS.md, CLAUDE.md and SKILL.md) and documentation-only pointer maintenance qualify when no executable or application-runtime behavior changes.

Executable code or embedded automation, application prompts, workflows, schemas, runtime configuration, and mixed diffs containing them do not qualify, even inside a Markdown file or docs directory. An agent workflow described in prose is instruction documentation; changing executable hook/script content is not.

Run proportionate local checks for the actual change, such as diff hygiene, link/pointer resolution or skill metadata validation, and address relevant failures. Record `Gate 1: CI NOT REQUIRED — documentation-only` with the reviewed SHA, scope, commands and results; never label skipped or unrun CI as passed. Gate 2, applicable draft and final review/evidence requirements, and merge authorization are unchanged. This policy does not bypass branch protection or authorize disabling or canceling CI jobs.

## No-CI exception — a check that cannot run is not a check to wait on

When CI **does not exist** for this PR, do not sleep-poll it. Three provable shapes qualify, each with its evidence recorded before you skip the wait:

1. **No workflow applies.** A named bounded repository validation evaluates the workflow files and their event/path filters against the changed paths; record the command and actual output. A directory listing or path inspection alone is insufficient. If no bounded validation can establish applicability, Gate 1 stays unproven; do not invent a nonexistent workflow command.
2. **No eligible runner can host it.** Resolve the job's `runs-on` labels and runner group, repository access, and the eligible runner pool (repository, organization or hosted capacity as applicable). A repository self-hosted-runner endpoint alone cannot prove GitHub-hosted or organization-level capacity. Qualifying evidence is zero eligible runners, or repeated observations at separate times showing every eligible runner busy while the check stays `QUEUED` or `PENDING`; one busy snapshot is insufficient.
3. **Checks are structurally stuck.** The rollup is `QUEUED`/`PENDING` with no start, and a runner-capacity read explains it, with all the case 2 requirements (labels, runner group, repository access, eligible pool, repeated observations). A stuck rollup alone is insufficient.

On any of those, apply the local-equivalent exception immediately, without waiting for the ten-minute threshold, and never substitute a `sleep N` + `gh pr checks` loop for running the command. Then record:

```
Gate 1: CI NOT APPLICABLE — <reason: no matching workflow | zero eligible runners | runners saturated QUEUED or PENDING>
  evidence: <command + the output line proving it>
  local equivalent: <workflow command, or bounded repository validation when no workflow applies> → <result at SHA>
  validation/capacity details: <bounded validation result, or timestamped eligibility and queue observations>
```

Fixed guardrails: never label unrun CI as passed; never disable or cancel a job or touch branch protection; never widen this into "skip CI" for a repo whose checks are merely slow or red; keep Gate 2, applicable review/evidence gates and merge authorization unchanged. A check that has actually started is backlogged CI, not missing CI, and stays under the local-equivalent exception with its own reporting.

## Gate 1 — CI green: verification procedure (when CI applies)

**`gh pr checks` is NOT sufficient**: it can report "pass" from a webhook ping or during GraphQL rate-limit exhaustion while the underlying checks are stale or failing (memory: `feedback_2026-07-11_gh_pr_checks_silent_stale_data_during_graphql_exhaustion.md`). Use the `statusCheckRollup` JSON pattern:

```bash
gh pr view N --json statusCheckRollup --jq '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length'
```

`0` (with nothing still pending) → Gate 1 PASS through CI; for backlogged checks, apply the local-equivalent exception below first. `statusCheckRollup` is mixed: `StatusContext` rows use `.state` and GitHub Actions `CheckRun` rows use `.conclusion`; never rely on `.state` for Actions rows.

**Freshness discipline — verify against HEAD, not a stale run:**
- Pull the PR's current head SHA first: `gh pr view N --json headRefOid --jq '.headRefOid'`.
- When reading raw check-runs via `commits/{sha}/check-runs`, use that head SHA, not a value cached from an earlier turn: rerun cycles leave stale check-runs from prior SHAs in the same job-name bucket (memory: `feedback_2026-07-21_check_runs_stale_pickup_across_reruns.md`). Scope to the current run's own job list via `actions/runs/<run_id>/jobs`, not a `max_by(started_at)` dedup across all reruns.
- `gh api .../check-runs` **silently truncates to 30 rows** without `--paginate`; compare `total_count` to the returned array length before concluding a check "doesn't exist" (memory: `feedback_2026-07-21_gh_api_check_runs_pagination_silent_truncation.md`).
- REST and GraphQL are **separate quota buckets**, and `gh api rate_limit` is quota-exempt: check it first, and fall back to the other bucket for the same data before declaring "rate-limited". Full procedure: `~/.claude/skills/github-cli-reference/SKILL.md`.

## Gate 2 — No merge conflicts: verification procedure

```bash
gh pr view N --json headRefOid,mergeable,mergeStateStatus --jq '.'
```

| Field | Required | If wrong |
|-------|----------|----------|
| `mergeable` | `MERGEABLE` | `UNKNOWN` → wait and re-poll (GitHub is still computing); `CONFLICTING` → hard FAIL, resolve before `/green` |
| `mergeStateStatus` | Informational only | `DIRTY` corroborates a conflict, but non-`CLEAN` states such as `UNSTABLE` may reflect CI rather than conflicts; Gate 2 is decided by `mergeable`. |

**Re-check every time you state a verdict, not once per session.** Mergeability depends on the base branch and is recomputed asynchronously: a PR can flip from `MERGEABLE` to `CONFLICTING` hours later with no action on its own branch (an unrelated PR touching the same lines merging first is enough). Treat every prior `/green` claim as expired the moment you act on or repeat it: re-fetch, don't recall.

**Merge conflicts are routine, not an escalation event.** Resolve them yourself (rebase, take the correct side of a mechanical collision, reapply changes) and report the resolution; escalate only for genuinely ambiguous business logic (see `~/.claude/CLAUDE.md` "Left/right-shift autonomous work").

## Status check — canonical pattern (mandatory)

Always check merge/close state FIRST, before evaluating either gate:

```bash
gh api repos/OWNER/REPO/pulls/N --jq '{state, merged}'
```

If `merged:true` or `state:"closed"`, stop and report without evaluating Gates 1/2. `mergeable_state` returns `unknown` for merged PRs, identical to its transient CI-running state, which causes false "blocked" reports on already-merged PRs.

## Backlogged CI — local-equivalent Gate 1 evidence

This section applies only when CI is required; documentation-only changes use the exception above immediately.

If a check has been queued/pending for **more than 10 minutes**, run its actual workflow command locally and post proof labeled **"local run — CI still pending/rerunning"** with the command, output, timestamp and current PR HEAD SHA (PR comment + PR description). Passing local equivalents satisfy Gate 1 for those backlogged checks; identify which checks passed locally and which in CI. Report local failures immediately. A check whose equivalent cannot run locally stays unproven. This exception does not waive failed checks, missing evidence, SHA freshness, Gate 2 or merge authorization.

### Required local-equivalent receipt

Map each substituted job and matrix entry to its actual workflow/reusable-script command, runtime, dependencies, services, flags, non-secret configuration and required artifacts. Run against the current candidate head and actual base; disclose dirty changes with hashes instead of claiming a clean commit. Relevant uncommitted changes cannot establish PASS for the published candidate: commit them through the sole owner and rerun applicable checks, or run against verified identical candidate bytes in isolation. Preserve unrelated dirty work without resetting it and document why it cannot affect the result. Record original start/end timestamps, full relevant output, exit status, source/artifact hashes and environment differences. Put a retrievable sanitized gist URL and the per-job mapping in the PR description, with applicable inline media under the lifecycle evidence rules.

Distinguish CI PASS, local-equivalent PASS, pending, failed and unproven for every required job. A convenient subset, wrong platform, mocked external boundary or unrelated smoke test is not equivalent. Failed CI is not delayed CI: diagnose and resolve it, never substitute a convenient local pass. Hosted-only checks that cannot be reproduced stay unproven, and later contradictory CI reopens readiness. Do not spoof checks, disable protection or cancel jobs to create green; required platform merge protection and separate merge authorization remain intact.

## Related

- `~/.claude/skills/pr-lifecycle/SKILL.md` — applicable draft and ready/final quality gates, separate from `/green`
- `~/.claude/skills/github-cli-reference/SKILL.md` — REST ↔ GraphQL dual-bucket procedure
