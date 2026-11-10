# Session-to-PR binding for PRW metrics

Records which pull request an agent session is working on, so the metrics job can tie the session's token usage to that PR instead of guessing from branch names.

Status: built and unit-tested. **Not installed on any host.** Codex payloads are unverified.

## What it records

`scripts/prw_session_binding_hook.py` reads one hook payload on stdin and appends at most one JSON line to a local ledger.

| Event | Record |
|---|---|
| Session start | `session_start` with repository, branch and commit |
| `gh pr create` whose output has the new PR's URL | `pr_binding` for that PR |
| `gh pr checkout <number or URL>` that did not fail | `pr_binding` for that PR |
| `git push`, `git switch`, `git checkout`, `git worktree add` | `branch` with the branch and commit afterwards |
| Stop, subagent stop | `stop` |

Reading a PR (`gh pr view`, `list`, `checks`, `diff`, comments, reviews) records nothing.

The ledger holds only: schema version, timestamp, runtime, session id, kind, repository, branch, commit, PR and source. It never holds command text, prompts, tool output or paths. It names private repositories and branches, so it stays on the host.

Ledger path: `${PRW_BINDING_LEDGER:-$HOME/.local/share/prw-metrics/bindings/session-bindings.jsonl}`.

The hook always exits 0 and prints nothing. If anything goes wrong it writes no record.

## How usage gets attributed

`scripts/native_usage_collector.py --session-bindings <ledger>` looks up, for each usage record without a request-level binding, the latest `pr_binding` in the same session at or before the record's time. A newer binding replaces it. A switch to a different branch or repository clears it. A bound record gets a `convention` attribution with `convention_ref: prw-session-binding.v1` and a receipt that names the ledger record.

The existing query already totals `convention` attributions per PR (`convention_total_tokens`). The web dashboard export shows them as usage basis `session_binding`.

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

Metrics job: add `--session-bindings "$HOME/.local/share/prw-metrics/bindings/session-bindings.jsonl"` to each `native_usage_collector.py` call in `collect-current.sh`, on each host. Each host reads its own ledger.

The script path above assumes the sync workflow installs it under `~/.claude/scripts/`; use whatever path that workflow actually installs.

## Checking that it works

- The ledger gains a line when a session starts.
- The collector's stats file reports `session_binding_records` and a non-zero `session_bound_usage_records`.
- On the dashboard, "Token usage per PR" coverage rises and drilldowns show "Session recorded as working on this PR".

## What was and was not verified

| Check | Result |
|---|---|
| Hook unit tests (Claude payload shape, 26 cases) | Pass |
| Hook invoked directly with a Claude-shaped `SessionStart` payload in a scratch repository | Wrote a correct record |
| Hook fired by a real Claude Code session | **Not verified.** The building session ran in safe mode, which child sessions inherit and which disables settings-file hooks. Two headless runs completed their command and wrote no records. |
| Hook `session_id` equals the transcript's session id | **Not verified**, for the same reason |
| Codex payload field names; Codex child threads | **Not verified.** No Codex session was run. |
| Join and collector unit tests | See the test modules `tests/test_prw_session_bindings.py` and `tests/test_prw_session_binding_collector.py` |

To run the real-session check outside safe mode:

```bash
S=/path/to/scratch; mkdir -p "$S/repo" && cd "$S/repo" && git init -q && git remote add origin https://github.com/acme/app.git && git commit -q --allow-empty -m init
# settings.json registers the three hooks with PRW_BINDING_LEDGER="$S/ledger.jsonl"
claude -p "Run exactly this one shell command and then stop: git switch -c demo" --settings "$S/settings.json" --model haiku --allowedTools "Bash(git switch:*)" < /dev/null
cat "$S/ledger.jsonl"   # expect session_start, branch, stop with one session_id equal to the transcript's sessionId
```

## Limits

- Only sessions started after install are covered. There is no backfill.
- A coordinator session that drives several PRs is attributed to the PR it last created or checked out. Usage before its first binding stays unattributed.
- Child agents inherit a binding only when they share the parent's session id.
- A PR created outside an agent session produces no binding.
- Crediting a whole request to the bound PR is an inference from the session's last declared PR. It is labelled as session-bound wherever it is shown, separate from requests that name a PR directly.
