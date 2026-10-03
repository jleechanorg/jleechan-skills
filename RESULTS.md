# ci-queue-trim — safe optimization RESULTS

Branch: `codex/ci-queue-throughput-20261003`
Base: `c42b5d49` (last commit: `codex/gpt-6: track installed CI queue audit tool for safe optimization`)

## What changed

| File | Change |
|---|---|
| `.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py` | Added supersede + audit_incomplete semantics, event-specific comparison, pre-cancel refresh, `--superseded-only` mode, explicit `PROTECTED_WORKFLOWS` allowlist |
| `.claude/skills/ci-queue-trim/SKILL.md` | Documented the three pitfalls (deceptive `updatedAt`, superseded `run.headSha`, lookup failure), event semantics, `--superseded-only`, pre-cancel refresh, `deploy` branch added, fuzzy-heuristic note, `committedDate` ≠ push time |
| `.claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py` | 20 focused offline regression tests across 6 scenarios |

## Audit semantics (what the script now enforces)

- **Supersede**: `pull_request` / `pull_request_target` runs are cancelled when `run.headSha` ≠ `PR.head.sha`; `push` runs are cancelled when `run.headSha` ≠ branch HEAD SHA.
- **Merge ref / fork identity**: Fork PRs are compared against the base repo's `PR.head.sha` (the merge ref), never the run's fork-side SHA.
- **merge_group & unknown events**: never receive the generic stale-head comparison; unknown events are kept with `audit_incomplete=True`.
- **Lookup failure**: PR / commit / per-run detail lookup failure keeps the run with `audit_incomplete=True`. The run's age is **never** substituted for a missing head-commit age.
- **Reusable / deploy-style workflows**: kept via the **explicit** `PROTECTED_WORKFLOWS` allowlist or the `workflow_call` event — fuzzy substring matching is rejected on purpose.
- **`deploy` branch**: added to `PROTECTED_BRANCHES`.
- **Pre-cancel refresh**: `refresh_before_cancel()` re-fetches every candidate's run status, event, workflow name, and PR/branch head SHA. Any state that moved on since the audit drops the candidate before mutation.
- **`--superseded-only`**: dormancy is skipped; only runs whose head SHA is proven obsolete (or whose PR is already MERGED/CLOSED) are cancelled. Suitable for first-time operators.

## Test results

```
$ python3 -m pytest .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py -v
============================== 20 passed in 0.06s ==============================
```

Coverage:

| Scenario | Tests |
|---|---|
| Superseded vs current head (pull_request / push / MERGED) | 4 |
| Event semantics (merge_group, unknown, fork SHA) | 3 |
| Lookup failures (PR missing, commit date missing, run metadata missing) | 3 |
| Pre-cancel refresh (status change, head advance, workflow protection) | 3 |
| Protection (deploy branch, reusable event, explicit allowlist, fuzzy-name negative) | 4 |
| `--superseded-only` mode (dormant-current kept, proven-superseded cancelled, MERGED-PR cancelled) | 3 |

## Doc corrections

- `committedDate` is the author's commit timestamp, not the push time. Push time can be later; the doc now states this explicitly.
- `reusable` workflow protection is by event (`workflow_call`) or by exact-match in `PROTECTED_WORKFLOWS`, not by name substring.
- `deploy` is a protected branch.

## Operator safety constraints observed

- No live cancellations executed in this lane.
- No installed-file changes (`~/.claude/...`) — only this repo's copy.
- No `.env` / secrets reads, no `git add -A`, no merges, no force pushes.
- Commit on the existing `codex/ci-queue-throughput-20261003` branch; push (non-force) after this commit.

## Out-of-scope follow-ups

- Live deploy / canary run on `jleechanorg/worldarchitect.ai` from Linux and Mac (root to perform after the seed lands).
- Populate `PROTECTED_WORKFLOWS` for any specific deploy / reusable filenames the operator wants protected (currently empty by default).