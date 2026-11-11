# Specification: Session-to-PR binding for PRW usage attribution

Design and operating notes: [docs/prw-session-binding.md](../prw-session-binding.md).

## 1. Outcome

Token usage from an agent session that declared which PR it is working on is credited to that PR by the PRW metrics collector, labelled as a session-bound inference and kept separate from usage whose request names a PR directly. Three parts deliver it:

1. `scripts/prw_session_binding_hook.py`: a Claude Code / Codex hook that appends at most one JSON line per event to a local ledger (`PRW_BINDING_LEDGER`).
2. `scripts/prw_session_bindings.py`: loads ledgers and answers "which PR was this session bound to at instant T".
3. `scripts/native_usage_collector.py --session-bindings <ledger>`: an opt-in option that gives otherwise unattributed usage records a `convention` attribution from the join.

## 2. Non-goals

- Installing or registering the hook on any host, or adding the option to the scheduled metrics job.
- Backfilling sessions that ran before the hook was installed.
- Dashboard display of session-bound usage (separate PR, branch `feat/prw-web-dashboard`).
- Inferring a PR from branch names, prompt text or repository heuristics.
- Verifying Codex payload field names (no Codex session is run for this change).

## 3. Acceptance criteria

1. The hook records `session_start`, `pr_binding` (only from a successful `gh pr create` whose output carries exactly one PR URL, or a successful `gh pr checkout <full PR URL>` with no other argument or flag; each must be the only command in the line, with no condition, grouping, pipe, redirection, assignment, alias, executable path or substitution; bare numbers, `-R`/`--repo`, `--dry-run` and `--web` record nothing), `branch` (after a simple `git push`, `git switch`, `git checkout`, `git worktree add`) and `stop` events. Coverage is a deliberate lower bound. Read-only `gh pr` commands, failed commands and quoted or heredoc text record nothing.
2. A ledger record holds only schema version, timestamp, runtime, session id, kind, repository, branch, commit, PR and source; never command text, prompts, tool output or paths.
3. Record timestamps keep millisecond precision, so a request issued before a branch switch in the same second stays bound and a request issued just before a binding is not credited to it.
4. The hook always exits 0, prints nothing and writes no record when anything fails.
5. The join returns the latest `pr_binding` at or before T for the session; a later binding replaces it; a `branch` record naming a repository other than the origin recorded with the binding, or a different or unknown branch in that repository (an unknown branch on either side), clears it; repository names compare case-insensitively, so a fork push keeps an upstream binding. Malformed lines and missing files are counted, never raised.
6. With `--session-bindings`, a usage record with no request-level binding and an active session binding gets exactly one attribution `{method: convention, convention_ref: prw-session-binding.v1, basis: hook_session_binding, weight: 1.0}` with a receipt naming the ledger record; request-level bindings take precedence. Collection and normalized-history replay count these records in `session_bound_usage_records`, not `pr_bound_usage_records`. Without the option, collector output is unchanged.
7. `PRW_BINDING_LEDGER` is registered in `docs/portability-env-vars.md`.

## 4. User stories

- As someone reading per-PR token usage, I see usage from a session that checked out or created a PR credited to that PR, labelled as session-bound, so coverage rises without guessing from branch names.
- As an operator, I can install the hook knowing it never blocks or alters an agent session and never stores command text or output.

## 5. Proof plan

- Unit and behavioural tests: `tests/test_prw_session_binding_hook.py`, `tests/test_prw_session_bindings.py`, `tests/test_prw_session_binding_collector.py`, with synthetic fixtures (`acme/app#42`).
- Causal RED/GREEN for criterion 3: a test that fails with second-precision timestamps and passes with millisecond precision.
- Full repository suite at base and head, separating pre-existing failures.
- Real caller: a headless Claude Code session with the hook registered through `--settings`, running `gh pr checkout` and `git switch` in a scratch clone, writing to a scratch ledger; then the collector CLI on a scratch copy of that session's transcript with `--session-bindings`, showing which requests are credited.

## 6. Mock

Exempt: no user interface. The ledger record shape is the mock:

```json
{"v":1,"ts":"2026-11-10T07:20:41.512Z","runtime":"claude","session_id":"<id>","kind":"pr_binding","repo":"acme/app","branch":"feat/x","sha":"<40-hex>","pr":"acme/app#42","source":"gh_pr_checkout"}
```

## 7. Risks

- The ledger names repositories and branches; it stays on the host that wrote it.
- Crediting a whole request to the last declared PR is an inference; a coordinator session that drives several PRs is credited to the one it last created or checked out.
- Codex payload shapes are assumed, not observed.
- A hook that raised or printed could disturb agent sessions; the hook swallows all errors and exits 0.
