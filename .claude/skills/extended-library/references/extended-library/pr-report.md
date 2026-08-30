# /pr-report — Per-PR Delta Audit & Quality Review

Generate a structured report for one or more open pull requests. For full methodology, lane protocol, model routing, output format, and conventions see the skill at `~/.claude/skills/pr-report/SKILL.md`.

## Usage

```
/pr-report [<PR#s>...] [--apply] [--push] [--baseline=<ref>]
```

## Flags

- `<PR#s>...` — space-separated PR numbers. Omit to audit all open prompt PRs in the repo (default heuristic: PRs with `prompts` or `prompt` or `directive` in title).
- `--apply` — apply non-destructive simplifications (extract shared rules, add unit tests). Default = read-only.
- `--push` — write `~/roadmap/<repo>-pr-report-YYYY-MM-DD.md` and push to the roadmap repo.
- `--baseline=<ref>` — base ref for delta stats. Default `origin/main`.

## Examples

```
/pr-report                            # audit all open prompt PRs, local-only
/pr-report 8564 8628 8443             # audit specific PRs
/pr-report --apply                    # audit + apply simplifications
/pr-report --apply --push              # audit + apply + push to roadmap
/pr-report --baseline=main            # custom baseline
```

## Execution

This command is a wrapper around the `pr-report` skill. The main session:

1. Resolves target PRs (`gh pr list --state open`).
2. Computes `MERGE_READY` per `pr-green-definition` (gate1=0 + mergeable=MERGEABLE).
3. Spawns one Sonnet sidekick teammate (per `/sidekick` skill) with the sidekick's lanes protocol documented in the skill.
4. Sidekick fans out 4 anonymous lanes (A=haiku stats, B=sonnet standards+thermo, C=sonnet ponytail, D=haiku combination).
5. Sidekick compiles `/tmp/pr_report.jsonl` + `/tmp/pr_report.md` and surfaces to main session.
6. Main session optionally pushes the markdown to `~/roadmap/<repo>-pr-report-YYYY-MM-DD.md`.

## Hard rules

- **Read-only by default** — `--apply` is the explicit opt-in for simplifications.
- **No `gh pr merge`** — user issues `MERGE APPROVED` separately.
- **No push to main** — only to feature branches (rebase) and to the roadmap repo (report write).
- **Model routing explicit** — every spawned `Agent()` must set `model:` per CLAUDE.md "Subagent model routing".
- **Max 4 parallel lanes** — bursts kill, ramps don't (per `/swarm` rule 4).

## Skill file

`~/.claude/skills/pr-report/SKILL.md`