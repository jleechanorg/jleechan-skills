---
description: Check PR green status — CI green + no merge conflicts, both verified at current PR HEAD SHA. Quality gates (evidence, review, comments) belong to the draft phase, not /green.
type: verification
execution_mode: immediate
---

# /green — PR Green Status Check (2-Gate)

**Canonical definition (2026-07-28):** `/green` = exactly two gates, both at the PR's current HEAD SHA. Full rationale and stale-data caveats: `~/.claude/skills/pr-green-definition/SKILL.md`.

| Gate | Check |
|------|-------|
| 1 | CI green — every check at HEAD passes |
| 2 | No merge conflicts — `mergeable == MERGEABLE` |

Nothing else gates `/green`. Comment-thread resolution and evidence-link/PR-description gates are draft-phase quality checks (`~/.claude/skills/draft-first-pr/SKILL.md`), not `/green` gates. **CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait, at any phase. Reaching `/green` is NOT merge authorization — merging still requires literal `MERGE APPROVED` from the human in the most recent live message.

**SHA-binding:** `/green`'s two gates, like every gate in the full lifecycle (`/es` → `/er` → `/advice` → mark ready → `/green` → merge authorization), are only valid at the exact HEAD SHA they were checked against — a new commit invalidates a prior `/green` verdict. Full lifecycle and the SHA-binding rule: `~/.claude/skills/draft-first-pr/SKILL.md`.

## EXECUTION INSTRUCTIONS

When invoked as `/green <PR#>` or `/green` (auto-detect from current branch):

### Step 1 — Resolve PR + verify not merged/closed

```bash
PR=<N or auto-detected via: gh pr list --head "$(git branch --show-current)" --json number --jq '.[0].number'>
gh pr view "$PR" --json number,headRefName,headRefOid --jq '.'
gh api repos/OWNER/REPO/pulls/"$PR" --jq '{state, merged}'
```

If `merged:true` or `state:"closed"` → report and STOP. Do not evaluate Gates 1/2.

### Step 2 — Gate 1: CI green

```bash
gh pr view "$PR" --json statusCheckRollup --jq '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length'
```

`0`, with no checks still `PENDING`/`IN_PROGRESS` → Gate 1 PASS. Any non-zero, or checks still running → Gate 1 FAIL/PENDING.

If a check has been pending/running **>10 min past its normal runtime**: run the equivalent test locally now, post "local run — CI still pending/rerunning" proof (command + output + timestamp + SHA) to the PR, and keep Gate 1 as PENDING (not PASS) until CI itself resolves.

Never use `gh pr checks | grep` — it can show stale "pass" during GraphQL rate-limit exhaustion. Never trust `.state` for GitHub Actions `CheckRun` rows (use `.conclusion`).

### Step 3 — Gate 2: no merge conflicts

```bash
gh pr view "$PR" --json headRefOid,mergeable,mergeStateStatus --jq '.'
```

- `mergeable == "MERGEABLE"` → Gate 2 PASS. Report `mergeStateStatus` as context only; non-`CLEAN` states can reflect CI rather than conflicts.
- `mergeable == "UNKNOWN"` → re-poll (GitHub still computing), do not report FAIL yet
- `mergeable == "CONFLICTING"` → Gate 2 FAIL. Resolve it yourself (rebase, correct side of a mechanical collision, reapply changes) — do not stop and ask unless the conflict is genuinely ambiguous business logic.

**Re-run this check immediately before every verdict you state** — mergeability is recomputed asynchronously and can flip hours later with zero action on this branch.

### Step 4 — Report verdict

```
## /green Status: PR #N (HEAD <sha>)

| Gate | Status | Detail |
|------|--------|--------|
| 1. CI green | PASS/FAIL/PENDING | <checks summary> |
| 2. No conflicts | PASS/FAIL | mergeable=<value> mergeStateStatus=<value> |

**Verdict: GREEN / NOT-GREEN** (as of <SHA> @ <UTC timestamp>)
```

- **GREEN** only when both gates show direct PASS evidence pulled just now — never from memory of an earlier check.
- **NOT-GREEN** — state which gate(s) failed and why, plus the fix-it action taken (or needed).

GREEN is not merge authorization. Report readiness and stop; merging requires literal `MERGE APPROVED` from the human.

### Where the quality gates went

Evidence (`/es`), review (`/er`), and second-opinion (`/advice`) checks now run in the **draft phase**, before a PR flips from draft to ready-for-review. See `~/.claude/skills/draft-first-pr/SKILL.md`. `/green` no longer waits on or reports these.

## Where this rule lives

- `~/.claude/skills/pr-green-definition/SKILL.md` — canonical 2-gate definition, stale-data mechanics
- `~/.claude/skills/draft-first-pr/SKILL.md` — draft-phase quality gates (`/es`, `/er`, `/advice`)
- `~/.claude/skills/github-cli-reference.md` — REST ↔ GraphQL dual-bucket procedure
