---
name: draft-first-pr
description: Lifecycle contract for opening PRs, driving them green, and fixing CI. Triggers on: opening a PR, driving a PR to green, fixing CI on a PR, /green, /es, /er, /advice on a PR.
type: policy
---

# Draft-First PR Policy

**Every new PR is opened as DRAFT** (`gh pr create --draft`) and stays draft until quality is proven. Flipping to ready-for-review is a deliberate, gated action — not a side effect of pushing code.

## Canonical lifecycle (operator-approved 2026-07-29)

This is the full state machine — every other file (`pr-green-definition`, `/green`, `CLAUDE.md`, `AGENTS.md`) points here rather than restating it:

```
DRAFT
  → /es PASS @ SHA
  → /er PASS @ SHA (non-documentation PRs only)
  → /advice APPROVED @ SHA
  → mark ready (gh pr ready <N>)
  → /green: CI green + no merge conflicts, BOTH verified @ current HEAD SHA
  → separate merge authorization: explicit human "MERGE APPROVED" (case-insensitive)
    in the most recent live user message
```

Each arrow is a gate, not a formality — do not skip ahead, and do not treat an earlier gate's pass as still valid once HEAD has moved (see "SHA-binding rule" below).

## Draft-phase gates (in order)

While a PR is draft, run these in sequence — do not skip ahead:

1. **`/es`** — evidence bundle passes (real evidence per `~/.claude/skills/evidence-standards/SKILL.md` + repo-specific extensions), verified at the PR's current HEAD SHA.
2. **`/er`** — for every PR except the documentation-only class below, evidence review verdict is PASS (not PARTIAL/FAIL/INCONCLUSIVE), verified at the same current HEAD SHA — re-run if `/es` was earned at an older SHA.
3. **`/advice`** — second-opinion approval on the change itself (`APPROVED at <SHA>` / `NOT APPROVED at <SHA>` / `WITHHELD at <SHA>` — see `~/.claude/skills/advice/SKILL.md`), bound to the same current HEAD SHA. `WITHHELD` does not satisfy the draft gate.

Only after every applicable gate passes **at the same current SHA**: flip the PR from draft to ready-for-review (`gh pr ready <N>`).

### Documentation-only exception

After `/es`, classify the complete `origin/main...HEAD` changed-path set. A PR
is documentation-only only when every changed path is one of:

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/**`

For that class, do not run `/er`. Record `/er: NOT REQUIRED —
documentation-only (<changed paths>)` on the PR, then continue directly to
`/advice`. Documentation-only PRs still require `/es` and `/advice` at the
current SHA, followed by `/green` and separate merge authorization.

This is an exact allowlist, not a file-extension heuristic. Changes under
`.claude/**`, `.codex/**`, `.github/**`, prompts, tests, scripts, configuration,
schemas, or source code do not qualify even when the file is Markdown. Any
mixed diff uses the normal `/er` gate.

## SHA-binding rule (critical — applies to every gate in this chain)

`/es`, `/er`, `/advice`, and `/green` gate verdicts are each earned **at a specific commit SHA** — none of the production-gate verdicts carry forward across a HEAD move. If a new commit lands after a verdict (a nit fix, a rebase, a CI-requested change), that verdict is **STALE** and must be re-earned — or explicitly re-affirmed at the new SHA — before it counts toward the next gate in the chain.

**This is a verdict-binding rule, not an automatic evidence-capture rule.** Apply
the evidence-staleness tolerance in `evidence-standards`: a docs, tests,
skills, ordinary PR-policy, or other non-behavioral HEAD change does not
require a fresh production-evidence run. The reviewer may re-affirm `/es` at
the new SHA after documenting the non-production diff. A production behavior
change still requires fresh evidence, then fresh SHA-bound `/es`, `/er`, and
`/advice` verdicts.

The verdict rule applies uniformly:

- A stale `/es` PASS does not justify running `/er` against it when `/er` is required.
- A stale `/er` PASS does not justify running `/advice` against it when `/er` is required.
- A stale `/advice` APPROVED does not justify marking the PR ready.
- A stale `/green` does not justify reporting merge-readiness.

Before trusting any prior verdict, compare the SHA it was stamped with against the PR's live head: `gh pr view <N> --json headRefOid --jq '.headRefOid'`. Any mismatch means re-run that gate — never carry a verdict forward on memory.

## Ready phase — drive `/green`

Once ready-for-review, drive `/green` per `~/.claude/skills/pr-green-definition/SKILL.md` (2-gate CI+mergeable definition, SHA-bound) — do not restate the gate mechanics here.

Do NOT burn CI cycles chasing green on an unproven draft — that's what starved capacity before this policy. Get through every applicable draft gate first, *then* spend CI budget on the 2-gate `/green` loop.

## Slow CI — never block-wait

If CI is running more than ~10 minutes past its normal runtime for the check in question: run the equivalent tests locally NOW and post proof labeled **"local run — CI still pending"** (exact command, output, timestamp, git SHA). Do not treat polling/waiting as the primary strategy; Gate 1 remains pending until remote CI itself resolves successfully.

## Rationale

Long-open PRs that skipped straight to chasing CI green (e.g. the level-up auto-PR class) were starved by CI contention — CI capacity is a shared resource, not a private queue. The `ci-value-audit-v2` findings (`green-gate` workflow: 341 hr/wk consumed, 50.7% cancel rate pre-[#8637](https://github.com/$GITHUB_REPOSITORY/pull/8637)) show that driving unproven work through full CI repeatedly is the dominant cost driver. Gating quality (`/es`, `/er` when required, and `/advice`) in draft — before CI spend — front-loads correctness and back-loads CI cost only onto PRs already known-good.

## CodeRabbit/Bugbot — optional advisory reviewers

Neither draft-phase gate above nor `/green` includes CodeRabbit or Bugbot approval. **CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait, at any phase.

## Merge authorization — unchanged

Merge still requires the literal phrase `MERGE APPROVED` (case-insensitive) from the human in the most recent live message, scoped per-repo per existing policy (e.g. `$GITHUB_REPOSITORY`). Nothing in this skill changes that gate.
