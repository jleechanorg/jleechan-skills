---
name: pr-green-definition
description: Canonical /green definition — applicable CI or documented exception + no merge conflicts, verified at current PR HEAD SHA. Quality gates live in pr-lifecycle.
metadata:
  type: policy
---

# PR "Green" Definition (2-Gate, canonical 2026-07-28)

`/green` has exactly two gates, both bound to the PR's current `headRefOid`:

| # | Gate | Verification |
|---|---|---|
| 1 | **Applicable validation** | Documentation-only: `CI NOT REQUIRED` with proportionate local validation. Otherwise every required check passes at HEAD through CI, a documented `CI NOT APPLICABLE` exception, or the local-equivalent exception for backlogged checks. |
| 2 | **No merge conflicts** | `mergeable == MERGEABLE` (`UNKNOWN` may be re-polled; `CONFLICTING` is a hard FAIL). |

Nothing else gates `/green`: inline-comment, evidence-link and PR-description checks, old "6-green" numbering, CodeRabbit and Bugbot are not gates or waits. Stages, reviewer routes/quorum, evidence applicability/publication, SHA reuse, and runtime/visual/bundle requirements belong to [`pr-lifecycle`](../pr-lifecycle/SKILL.md); follow its claim/risk applicability instead of duplicating those manuals here. Pure instruction Markdown is not automatically runtime/visual/bundle-required or exempt solely by line count. Known relevant mechanical failures remain failures; skipped or neutral checks never become passes. Green alone does not establish READY.

Merge authorization is separate: follow `~/.codex/AGENTS.md` § Merge safety and the target repository's explicit merge contract.

## Retained review integrations

Follow [pr-lifecycle's retained review integrations](../pr-lifecycle/SKILL.md#retained-review-integrations) for discovery, `UNAVAILABLE` reporting, quorum and disclosure boundaries.

## Documentation-only CI exception

Classify the complete current-head diff by actual effects, not file extension or line count. Instruction/skill documentation, documentation-only pointer maintenance, and files including `AGENTS.md`, `CLAUDE.md` and `SKILL.md` qualify only when no executable or application-runtime behavior changes; they need no CI trigger/retry, runner wait or backlog threshold. Embedded code, automation, prompts, workflows, schemas, runtime configuration and mixed diffs do not qualify merely because they are Markdown. Run proportionate local checks (diff hygiene, link/pointer resolution or metadata validation) and record `Gate 1: CI NOT REQUIRED — documentation-only` with SHA, scope, commands and results. Never call skipped/unrun CI passed; Gate 2, lifecycle review/evidence requirements and merge authorization remain separate.

## No-CI exception — a check that cannot run is not a check to wait on

Do not sleep-poll absent CI. `CI NOT APPLICABLE` requires bounded proof of one case: no workflow matches the changed paths; zero eligible runners; repeated observations show every eligible runner busy while the check remains `QUEUED`/`PENDING`; or a no-start rollup is explained by that same capacity evidence. Resolve workflow filters, labels, runner group, repository access and eligible pool as applicable; a directory listing, one busy snapshot or a stuck rollup alone is insufficient. Otherwise Gate 1 stays unproven.

For a qualifying case, run the actual workflow command (or bounded repository validation when no workflow applies) immediately and record:

```
Gate 1: CI NOT APPLICABLE — <no matching workflow | zero eligible runners | runners saturated QUEUED or PENDING>
  evidence: <bounded command + proving output>
  local equivalent: <workflow command or bounded validation> → <result at SHA>
  validation/capacity details: <result or timestamped eligibility/queue observations>
```

Never call unrun CI passed, disable/cancel jobs or touch branch protection, and do not use this exception for merely slow or failed CI. A started check is backlogged CI and follows the local-equivalent rule below.

## Gate 1 — CI verification at the fresh head

Check close/merge state first (`gh api repos/OWNER/REPO/pulls/N --jq '{state, merged}'`), then read the current head and complete `statusCheckRollup`; `gh pr checks` is only a summary, never proof. The rollup includes legacy `StatusContext` and Actions `CheckRun` rows:

```bash
gh pr view N --json headRefOid,statusCheckRollup --jq '[.statusCheckRollup[] | if .__typename == "StatusContext" then {name:(.context // ""), kind:"legacy-context", state:(.state // "" | ascii_upcase), conclusion:null} elif .__typename == "CheckRun" then {name:(.name // ""), kind:"check-run", state:(.status // "" | ascii_upcase), conclusion:(.conclusion // "" | ascii_upcase)} else {name:"", kind:(.__typename // ""), state:"", conclusion:""} end]'
```

`StatusContext` is the legacy context shape; `CheckRun` uses `status` and `conclusion`. Bucket required results as `PASS` only for legacy `SUCCESS` or completed `CheckRun`/`SUCCESS`; `PENDING` while incomplete; `FAIL` for a completed non-success; and `UNPROVEN` for missing/unknown or non-applicable evidence. Skipped or neutral results are never `PASS`, including optional checks; CodeRabbit/Bugbot never gate. Fix known required mechanical failures. Re-read the current head for every verdict; raw check-run reads use that SHA, the current run's jobs and pagination, with REST/GraphQL fallback per `../github-cli-reference/SKILL.md` before claiming unavailable.

## Gate 2 — no merge conflicts at that same head

```bash
gh pr view N --json headRefOid,mergeable,mergeStateStatus --jq '.'
```

`mergeable` must be `MERGEABLE`; re-poll `UNKNOWN` and resolve `CONFLICTING`. `mergeStateStatus` is informational (`DIRTY` corroborates conflict; other non-`CLEAN` values can reflect CI). Re-check whenever stating a verdict because base-branch changes can recompute mergeability.

## Backlogged CI — local-equivalent Gate 1 evidence

For a required check queued/pending more than 10 minutes, run its actual workflow command locally and report `local run — CI still pending/rerunning` with command, output, timestamp and current head SHA. Map each substituted job and matrix entry to its workflow command, runtime, dependencies, services, flags, configuration and artifacts; record base/head, dirty-state hashes, timestamps, exit status, source/artifact hashes and environment differences. Distinguish CI PASS, local-equivalent PASS, pending, failed and unproven per job; a convenient subset, wrong platform, mock boundary or non-reproducible hosted check is not equivalent and stays unproven. This does not waive failures, freshness, Gate 2, lifecycle evidence or merge authorization.

## Related

- `../pr-lifecycle/SKILL.md` — canonical lifecycle, stages and review/evidence applicability
- `../github-cli-reference/SKILL.md` — REST ↔ GraphQL dual-bucket procedure
