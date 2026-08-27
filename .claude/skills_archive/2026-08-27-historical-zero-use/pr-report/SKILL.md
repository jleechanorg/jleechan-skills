---
name: pr-report
description: This skill should be used when the user asks for a PR report, PR audit, PR delta analysis, /pr-report, or wants per-PR summary with delta files/lines. Generates a structured report for one or more open PRs covering purpose, files changed, +/− line counts, /code-standards + /thermo review findings, /ponytail simplification opportunities, file-overlap combination candidates, and /green status per pr-green-definition. Output: machine-readable JSONL + human-readable markdown. Read-only by default; can apply simplifications if user opts in.
---

# /pr-report — Per-PR Delta Audit & Quality Review

Use when the user invokes `/pr-report [<PR#s>]` or asks for a structured audit of one or more open pull requests. The skill defines the methodology, lane protocol, model routing, and output format. The Claude command at `~/.claude/commands/pr-report.md` dispatches the work.

## Inputs

- **PR#s** (space-separated) — defaults to all open prompt PRs in the repo if omitted. Resolved via `gh pr list --state open --json number,title,headRefName,files --limit 100`.
- **Repo** — defaults to current `git remote get-url origin | sed ...` derivation; can be overridden.
- **`--apply`** (optional) — when set, the audit may apply non-destructive simplifications (extract shared rules, add unit tests). Default = read-only.
- **`--push`** (optional) — when set, write the human-readable report to `~/roadmap/<repo-name>-pr-report-YYYY-MM-DD.md` and push to the roadmap repo. Default = local-only.
- **`--baseline`** (optional, default `origin/main`) — the merge-base to diff against for delta stats.

## Methodology (4 lanes, parallel)

The Claude command spawns one Sonnet sidekick teammate per the `/sidekick` skill. The sidekick fans out 4 anonymous lanes per the `/swarm` rules. **All lanes set `model:` explicitly** per CLAUDE.md "Subagent model routing":

| Lane | Model | Job |
|---|---|---|
| **A — per-PR delta stats** | `haiku` (mechanical) | title, purpose 1-paragraph, base/head SHA, files-changed count + list, +lines, -lines, net, top 3 files by lines added |
| **B — /code-standards + /thermo review** | `sonnet` (review) | for PRs >50 lines added OR >3 files changed: prompt consistency with `$PROJECT_ROOT/prompts/AGENTS.md` (setting-agnostic, no banned entities, generic placeholders, no meta-commentary, no version history), repetition/mirroring (`shared/` candidate), redundant phrasing, anti-patterns |
| **C — /ponytail simplification analysis** | `sonnet` (review) | per-prompt-PR ponytail ladder: (1) does the rule need to exist at all, (2) duplicate elsewhere, (3) one-liner possible, (4) move to `shared/`, (5) minimum text |
| **D — combination analysis** | `haiku` (mechanical) | file-level overlap matrix across all PRs in scope, cluster PRs that touch same files, propose merge candidates |

## Output

- **Machine-readable**: `/tmp/pr_report.jsonl` — one JSONL line per PR with `{pr, title, purpose, files, additions, deletions, net, top_files, review_findings, simplifications, combination_candidates}`
- **Human-readable**: `/tmp/pr_report.md` — per-PR table + review findings + simplification recommendations + combination candidates + suggested merge order
- **Optional push**: when `--push` is set, copy `pr_report.md` to `~/roadmap/<repo>-pr-report-YYYY-MM-DD.md` and push to the roadmap repo (commit message includes the date + the repo name).

## Lane protocol (per lane)

1. **Lane A** (haiku): mechanical `gh api` calls only. No file modifications. Append to `/tmp/pr_report.jsonl`.
2. **Lane B** (sonnet): read-only diff inspection via `gh pr diff <N>`. Output structured findings to `/tmp/pr_report.jsonl`. Cite file:line for every claim.
3. **Lane C** (sonnet): read-only prompt-rule inspection. Cite `$PROJECT_ROOT/prompts/AGENTS.md` rule number for every anti-pattern. Output to `/tmp/pr_report.jsonl`.
4. **Lane D** (haiku): file-overlap matrix via `gh pr view <N> --json files`. Output to `/tmp/pr_report.jsonl`.

After all 4 lanes complete, the sidekick synthesizes `/tmp/pr_report.md` and surfaces to the main session.

## /green integration

For each PR, also compute the canonical 2-gate `/green` status (per `pr-green-definition` skill):

```bash
gate1=$(gh pr view N --json statusCheckRollup --jq '[.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length')
gate2=$(gh pr view N --json mergeable --jq '.mergeable')
```

- `gate1 == 0` AND `gate2 == "MERGEABLE"` → `MERGE_READY`
- `gate1 == 0` AND `gate2 == "UNKNOWN"` → `PENDING` (re-poll)
- `gate1 == 0` AND `gate2 == "CONFLICTING"` → `BLOCKED_CONFLICT`
- `gate1 > 0` → `BLOCKED_CI` (real test failure)
- Otherwise → `BLOCKED`

Green Gate and Cursor Bugbot checks are advisory and excluded from Gate 1; CodeRabbit/Bugbot feedback is advisory across all phases (per `draft-first-pr` + `pr-green-definition` skills).

## Conventions

- **Read-only by default.** `--apply` is the explicit opt-in.
- **No `gh pr merge`** — user issues `MERGE APPROVED` separately.
- **Cost-route** — haiku for mechanical stats, sonnet for review/narrative. No top-tier (opus/fable) unless user explicitly requests.
- **Max 4 parallel lanes** (per `/swarm` rule 4 — bursts kill, ramps don't).
- **Sidekick durability**: STATE.md at `$CLAUDE_STATE_DIR/<repo-slug>/sidekick/pr-report-<date>/STATE.md`; resumption bead P1.

## Example

```
/pr-report                    # audit all open prompt PRs
/pr-report 8564 8628 8443     # audit specific PRs
/pr-report --apply --push     # audit + apply simplifications + push to roadmap repo
```

## Related skills

- `/code-standards` — code/PR review standards
- `/thermo` (`thermo-nuclear-code-quality-review`) — strict structural audit
- `/ponytail` — lazy senior dev ladder
- `/pr-green-definition` — canonical 2-gate /green status check
- `/draft-first-pr` — PR lifecycle (draft → /es → /er → /advice → /green)
- `/sidekick` — durable Sonnet teammate wrapper
- `/swarm` — multi-agent orchestration playbook
- `/e` — cost-aware model routing