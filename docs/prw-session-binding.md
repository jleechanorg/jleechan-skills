# Session-to-PR binding for PRW metrics

Records which pull request an agent session is working on, so the metrics job can tie the session's token usage to that PR instead of guessing from branch names.

Status: built, unit-tested and exercised by a real headless Claude Code session. **Not installed on any host.** Codex payloads are unverified.

Specification: [docs/specs/prw-session-binding-spec.md](specs/prw-session-binding-spec.md).

## What it records

`scripts/prw_session_binding_hook.py` reads one hook payload on stdin and appends at most one JSON line to a local ledger.

| Event | Record |
|---|---|
| Session start | `session_start` with repository, branch and commit |
| `gh pr create` whose output has exactly one PR URL | `pr_binding` for that URL's PR |
| Exactly `gh pr checkout <full PR URL>`, with no other argument or flag, that did not fail | `pr_binding` for that URL's PR |
| `git push`, `git switch`, `git checkout`, `git worktree add`, optionally with a literal `git -C <dir>` | `branch` with the branch and commit afterwards |
| Stop, subagent stop | `stop` |

Coverage is a deliberate lower bound. Each row counts only as one simple command: literally `gh pr ...` or `git ...` with nothing else in the line apart from a trailing `;`, no condition, grouping, pipe, redirection, assignment, alias, executable path or `$(...)`/backtick substitution. A PR is bound only from a fully qualified `github.com/<owner>/<repo>/pull/<N>` URL. A bare number, `-R`/`--repo`, `gh repo set-default`, fork remotes, `gh pr checkout` with any flag (`--detach`, `--help`, `-b`), `gh pr create --dry-run`/`--web`/`--help` and every other form record nothing, so the hook never guesses which repository gh resolved. Reading a PR (`gh pr view`, `list`, `checks`, `diff`, comments, reviews) records nothing.

The ledger holds only: schema version, timestamp, runtime, session id, kind, repository, branch, commit, PR and source. It never holds command text, prompts, tool output or paths. It names private repositories and branches, so it stays on the host.

Ledger path: `${PRW_BINDING_LEDGER:-$HOME/.local/share/prw-metrics/bindings/session-bindings.jsonl}`.

The hook always exits 0 and prints nothing. If anything goes wrong it writes no record.

## How usage gets attributed

`scripts/native_usage_collector.py --session-bindings <ledger>` looks up, for each usage record without a request-level binding, the latest `pr_binding` in the same session at or before the record's time. A newer binding replaces it. A switch to a different branch, or to a repository other than the checkout's origin when the binding was made, clears it (repository names compare case-insensitively). So does any branch record in that repository when the branch is unknown on either side, such as a detached HEAD or a binding recorded without a branch. A bound record gets a `convention` attribution with `convention_ref: prw-session-binding.v1` and a receipt that names the ledger record.

Ledger timestamps have millisecond precision, so the request that issues a branch switch stays bound to the PR it was working on.

The existing query already totals `convention` attributions per PR (`convention_total_tokens`). Showing them on the web dashboard as usage basis `session_binding` belongs to a separate change (branch `feat/prw-web-dashboard`).

## Installing (not done; needs the repository's review and sync workflow)

Claude Code, in the user `settings.json` hooks:

```json
{
  "SessionStart": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/scripts/prw_session_binding_hook.py --runtime claude"}]}],
  "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 ~/.claude/scripts/prw_session_binding_hook.py --runtime claude"}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/scripts/prw_session_binding_hook.py --runtime claude"}]}]
}
```

Codex, in `hooks.json`: the same three events with `--runtime codex`. Do this only after capturing one real Codex `PostToolUse` payload and confirming the field names the hook reads.

Metrics job: add `--session-bindings "$HOME/.local/share/prw-metrics/bindings/session-bindings.jsonl"` to each `native_usage_collector.py` call in the host's scheduled metrics job (this repository does not ship that job; find it with `grep -r native_usage_collector` in the host's scheduler or wrapper scripts), on each host. Each host reads its own ledger.

The script path above assumes the sync workflow installs it under `~/.claude/scripts/`; use whatever path that workflow actually installs.

## Checking that it works

- The ledger gains a line when a session starts.
- The collector's stats file reports `session_binding_records` and a non-zero `session_bound_usage_records`.
- Once the dashboard change lands, "Token usage per PR" coverage rises and drilldowns show "Session recorded as working on this PR".

## What was and was not verified

| Check | Result |
|---|---|
| Hook unit tests (Claude payload shape) | Pass |
| Hook invoked directly with a Claude-shaped `SessionStart` payload in a scratch repository | Wrote a correct record |
| Hook fired by a real Claude Code session | Pass at `b478e0db` (the narrowed hook; the later exact-form change only rejects more checkout forms): a headless `claude -p --settings` session running `gh pr checkout 787`, a checkout of a nonexistent PR URL, `gh pr checkout <URL of 787>`, `cd . && git switch demo-e2e` and `git switch demo-e2e` wrote `session_start`, one `pr_binding` for the URL checkout only, one `branch` for the plain switch only, and `stop`. The bare number, the failed checkout and the compound switch wrote nothing. An earlier run at `efab4368` (before the narrowing) is superseded. Launch it with that session's `CLAUDECODE` and `CLAUDE_CODE_*` variables unset. |
| Hook `session_id` equals the transcript's session id | Pass in both runs: every ledger line carries the session id of the transcript file |
| Collector on that session's transcript with `--session-bindings` | Pass for the `efab4368` run only (not repeated for the narrowed hook; since then the collector is unchanged and the join changed only to count out-of-range timestamps as malformed): the request issued while bound was credited to the PR; requests before the checkout and after the switch were not |
| Codex payload field names; Codex child threads | **Not verified.** No Codex session was run. |
| Join and collector unit tests | See the test modules `tests/test_prw_session_bindings.py` and `tests/test_prw_session_binding_collector.py` |

To repeat the real-session check:

```bash
S=/path/to/scratch; mkdir -p "$S/repo" && cd "$S/repo" && git init -q && git remote add origin https://github.com/acme/app.git && git commit -q --allow-empty -m init
# settings.json registers the three hooks with PRW_BINDING_LEDGER="$S/ledger.jsonl"
env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT claude -p "Run exactly this one shell command and then stop: git switch -c demo" --settings "$S/settings.json" --model haiku --allowedTools "Bash(git switch:*)" < /dev/null
cat "$S/ledger.jsonl"   # expect session_start, branch, stop with one session_id equal to the transcript's sessionId
```

## Limits

- Only sessions started after install are covered. There is no backfill.
- A coordinator session that drives several PRs is attributed to the PR it last created or checked out. Usage before its first binding stays unattributed.
- Child agents inherit a binding only when they share the parent's session id.
- A PR created outside an agent session produces no binding.
- Most real binding commands are not recorded: `gh pr checkout <number>`, `git push ... && gh pr create`, `cd x && gh pr checkout ...`. Only the simple forms above count.
- A branch change the hook does not record (a compound or unmodelled `git switch`) does not clear an earlier binding; the session stays credited to that PR until its next recorded binding or branch record.
- The ledger is append-only with no rotation or size cap.
- Crediting a whole request to the bound PR is an inference from the session's last declared PR. It is labelled as session-bound wherever it is shown, separate from requests that name a PR directly.
