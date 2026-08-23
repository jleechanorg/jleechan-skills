---
name: babysit-ao-pr-loop
version: 1.9.1
description: >
  Recurring cron-tick babysit loop that watches a single AO worker driving a PR
  — observe only, post concise status updates to the originating Slack thread,
  suppress noise via [SILENT] when nothing changed, terminate cleanly on
  terminal PR / missing worker. v1.5.0 (2026-07-13) revises the Skeptic
  merge-ready protocol (Skeptic is RESTORED as launchd cron, do not block on
  it). v1.6.0 (2026-07-13) adds REST JSON parse pitfall + gh_pr_json.py helper.
  v1.7.0 (2026-07-14) adds workflow_dispatch Smoke-Wait 25min timeout pitfall.
  v1.8.0 (2026-07-14) adds three PR #8290 incident learnings (GraphQL field
  divergence, cross-purpose tokens, HEAD-advance-without-redispatch trap).
  v1.9.0 (2026-07-14) adds: REST check-runs endpoint + annotations fallback,
  exact gh-pr-checks valid-field list, robust SLACK_USER_TOKEN awk extraction,
  and points cron prompts at babysit.py poll canonical Phase 0.
  v1.9.1 (2026-07-14) adds explicit ## When to load carve-out for literal-token-watch
  (non-PR) cron tasks; previously this skill auto-loaded from any cron prompt that
  mentioned 'babysit' even when the underlying task had no PR + AO worker pair.
trigger:
  - babysit wa-
  - watch PR <num>
  - tick loop on PR <num>
  - cron job babysitting an AO worker
changelog:
  - 1.9.1 (2026-07-14): Carve-out for literal-token-watch (non-PR) cron tasks. The previous version's `## When to load` block ended at `Do NOT load for: ... dev server or browser session`, which left the obvious "watch this Slack thread for a literal token like `WORKTREE APPROVED`" use case still inside scope. Bug-ref: thread C0AJQ5M0A0Y/1784070882.257369 — `babysit-di[REDACTED_OPENAI_KEY]` cron `18bd680865d9` auto-loaded this skill (because the prompt body mentioned 'babysit' + `conversations.replies`), found no PR + no worker + no `gh pr view` data, and self-cancelled after one tick. The 'babysit armed' claim in the parent thread was false. Fix: extended `## When to load` with an explicit 'Do NOT load for literal-token-watch' paragraph + a pointer to the future `slack-thread-token-watch` sibling skill. Future cron prompts that match the literal-token-watch pattern (regex `^babysit <token name> in thread ts=\\d+\\.\\d+$` or equivalent) MUST NOT pass `--skill babysit-ao-pr-loop` to `hermes cron create`. Verification: `bash scripts/test_babysit_carve_out.py` (TBD; planned but not yet written — at minimum scan all cron prompts for `worktree|disk-?pressure|literal.?token` and assert none of them have `--skill babysit-ao-pr-loop` attached).
  - 1.9.0 (2026-07-14): Four small fixes from the second PR #8290 babysit tick (thread C0AH3RY3DK6/1784030452.318509, post ts 1784070940.086909). (1) REST check-runs endpoint for failure title when check-run output text is null — /repos/OWNER/REPO/commits/<sha>/check-runs?per_page=20 returns full list; when Green Gate check_run output is {title=null, summary=null, text=null, annotations_count=1} the failure title is on /check-runs/<run_id>/annotations and points at path + message + start_line (e.g. .github line 20 "Process completed with exit code 1"). Without that endpoint you only see conclusion=failure with no detail and have to guess at the failing step. (2) Exact valid field list for `gh pr checks --json`: name, state, conclusion, startedAt, completedAt, link, workflow, description, event, bucket ONLY. url, html_url, and many others return Unknown JSON field. Read the available-fields list from the error rather than guessing. conclusion and startedAt ARE valid; do not chase ghosts. (3) Robust SLACK_USER_TOKEN extraction when ~/.profile formats the export with double quotes — the brittle pipeline `grep ... | sed 's/...//' | sed 's/"//g'` leaves a trailing quote and corrupts the token. Use `awk -F'"' '/^export SLACK_USER_TOKEN=/{print $2; exit}' ~/.profile`. Verified mid-tick when the sed pipeline emitted garbage and the curl returned 401; the awk version returned 81-char xoxp-* token. (4) Cron prompts should invoke `babysit.py poll --cron-job-id $CRON_JOB_ID` for Phase 0 (terminal-state probe + auto self-cancel) rather than re-implementing the same logic in the prompt body — re-implementations drift from the canonical helper and skip the --cron-job-id plumbing. Bug-ref: PR #8290 second tick after refresh-head supersession.
  - 1.8.0 (2026-07-14): Three new pitfalls, all from the same PR #8290 babysit tick (thread C0AH3RY3DK6/1784030452.318509). (1) gh pr view --json uses GraphQL camelCase field names (changedFiles, headRefName, mergedAt, mergeable, baseRefName, reviewDecision) NOT snake_case. When GraphQL is rate-limited and the babysit falls back to gh api repos/.../pulls/N, the REST shape IS snake_case. Mixing the two produces Unknown JSON field errors and burns a tool call per miss. (2) Cross-purpose token confusion: SLACK_USER_TOKEN (from ~/.profile per bashrc-profile-xapp-drift-blocks-launchd memory) is a Slack XOX-P user token. It is NOT a GitHub token. Do NOT pipe it to api.github.com (HTTP 401 Bad credentials). For GitHub REST fallback use TOKEN=$(gh auth token). For Slack chat.postMessage fallback use the SLACK_USER_TOKEN grep. (3) HEAD-advance-without-Green-Gate-redispatch trap: when a worker pushes a refresh-head commit, the pull_request-triggered Green Gate re-runs automatically on the new SHA, but any workflow_dispatch Green Gate does NOT auto-re-dispatch, AND the in-flight dispatch runs Smoke Gate Wait step gets CANCELLED by the new SHA supersession. After cancellation, NO Green Gate re-runs on the new SHA for 30+ min until the operator explicitly re-dispatches. Confusing observable pattern: Gates 1-6 PASS, Bugbot PASS, Smoke Gate Wait CANCELLED, parent Green Gate FAIL, but no fresh Green Gate runs. Recipe in references/head-advance-no-green-gate-redispatch.md. Bug-ref PR #8290 c8dbb469 supersedes aff95f87e.
  - "1.7.0 (2026-07-14): New pitfall workflow_dispatch Green Gate Smoke-Wait 25min timeout masquerades as code failure. When a babysit cron re-triggers the Green Gate via workflow_dispatch (typical babysit pattern: gh workflow run green-gate.yml -f pr_number=N -f head_sha=<sha>), the Smoke Gate Wait (Gate 8) step has a hard 25min wait timeout. When the smoke event never lands within 25 min, the wait job is CANCELLED, and the downstream Apply smoke gate result (gate 8) step in the main Green Gate job fails with result=cancelled, smoke_gate=unset. The check then reports as failure in `gh pr checks` even though Gates 1-6 (precheck, Bugbot) all PASSED. This is INFRASTRUCTURE (wait exhaustion), not a code defect — the PR's code is unchanged and the underlying pull_request-triggered Green Gate ran clean. Verified 2026-07-14 babysit tick on PR #8290 ($GITHUB_REPOSITORY, thread C0AH3RY3DK6/1784030452.318509): CodeRabbit explicitly confirmed Confirmed all three failures are timeout/cancellation/self-hosted-runner infrastructure issues, not code defects after investigating the same run. Recipe: (1) when reading `gh pr checks`, distinguish dispatch-run cancellations (conclusion=cancelled on Smoke Gate Wait) from real test failures (concrete failing step with assertion text); (2) check the workflow_dispatch run vs the pull_request-trigger run — they may differ; (3) prefer reading actions/runs?head_sha=<sha> to see ALL runs (some cancelled, some not) rather than the dedup'd pr checks view; (4) post `:hourglass_flowing_sand: PR #N tick HH:MMZ — Gates 1-6 PASS, Gate-8 Smoke wait timed out (25min, workflow_dispatch infra). Skeptic verdict pending.` rather than alarm. Bug-ref: PR #8290 dispatch run 29370026085 — main Green Gate step Apply smoke gate result (gate 8) failed with SMOKE_RESULT=cancelled, SMOKE_GATE=unset."
  - "1.6.0 (2026-07-13): New pitfall REST PR JSON parse fails on raw body field. Supersedes v1.3.0 skeptic is gone protocol. Skeptic verdict now arrives via PR comment (SHA-pinned markers) posted by jleechanorg/dark-factory#281 skeptic_gate_cli.py, dispatched by jleechanorg/jleechanclaw#779's launchd cron. Babysits must NOT post /skeptic (still inert) and must NOT block on the verdict (the launchd cron + AO worker drive that loop). Updated merge-ready protocol: still uses `gh pr checks <N> .conclusion` for gates 1-6, but now also reports (non-blocking) when a skeptic-gate-verdict comment appears. Trigger: Jeffrey 2026-07-13 I dont really wanna install things per repo. Can we have this live in jleechanclaw and use the AO golang reviewer that already exists to redo skeptic."
  - "1.4.0 (2026-07-13): New pitfall Tick-number cadence gated without persistent tick state. Polling crons that suppress Slack noise by posting only on specific tick numbers (e.g. tick #4, #8, #12… every ~20m, with all other ticks silent) MUST persist the counter to a durable file (e.g. /tmp/<job>/.tick_counter). Agent-internal counting breaks across session boundaries (each cron tick is a fresh agent session; the prior session's if tick == 4 never executes). Verified 2026-07-13 on the wa-cookies-poll #8353 watcher cron (thread C0BDEAJH8PK/1783908854.786439): the cron prompt said post only on tick #4, #8, #12, …, no tick state file existed, and the first agent session had to bootstrap /tmp/repro-a1OGXH/.tick_counter=1 ad-hoc. Recipe in references/tick-state-persistence-cron-prompt-2026-07-13.md: (1) the cron prompt MUST name a tick-state path in step 1, (2) the first action of every tick is `TICK=$(($(cat <path>) + 1)); echo $TICK > <path>` BEFORE deciding what to post, (3) terminal-state timeout (e.g. >24 ticks → drop watch) reads the same file. Bug-ref: wa-cookies-poll #8353 cron job 1f0822aae664, first tick 2026-07-12T19:19 PDT had no counter, required ad-hoc bootstrap."
  - "1.3.1 (2026-07-13): Replace obsolete `cronjob action=remove job_id=<id>` self-cancel CLI with the current `hermes cron remove <id>` (and `hermes cron list` for the audit recipe). The old `cronjob` binary is no longer on PATH — `hermes cron --help` lists `remove` (alias `rm,delete`) as the correct subcommand. Affects every babysit prompt template, the audit recipe, and the `cronjob_remove()` helper in `babysit.py`. Bug-ref: 2026-07-13 cron run 781c0e0184d4 (followup #8353) — prompt still templated `cronjob action=remove job_id=$CRON_JOB_ID`; live `hermes cron remove 781c0e0184d4` confirmed the new CLI works (Removed job: followup #8353 /repro fix PR (20m) (781c0e0184d4))."
  - "1.3.0 (2026-07-09): Replace obsolete /skeptic wait with the post-skeptic-deleted green protocol. Skeptic is gone — skeptic-cron.yml workflow deleted from both $GITHUB_REPOSITORY and jleechanorg/.github, ai.hermes.schedule.skeptic-cron.plist removed from ~/Library/LaunchAgents/, ao:skeptic-hourly-report cronjob enabled: false, state: completed. The babysit MUST NOT post /skeptic and MUST NOT wait for a Skeptic verdict — neither will arrive. Judge merge-readiness directly from `gh pr checks <N>`: every gate has `.conclusion` (success / failure / timed_out / skipped / neutral / cancelled) — never `.state`. The two rollups that matter are Green Gate (precheck Gates 1-6) and Smoke Gate Wait (Gate 8). If both pass AND CodeRabbit APPROVED AND Bugbot clean AND mergeable AND no unresolved non-nit review comments → post `✅ PR <N> merge-ready` + flag for MERGE APPROVED. Reference: references/post-skeptic-green-protocol.md. Bug-ref: Slack thread 2026-07-09 — Jeffrey asked Didn't we delete skeptic? while a babysit cron for PR #8290 was still templating awaiting skeptic verdict."
  - "1.2.0 (2026-07-05): Add the executable self-cancel contract — every babysit prompt MUST invoke `babysit.py poll` (or `babysit.py babysit`) with `--cron-job-id $CRON_JOB_ID`. babysit.py gained a `cronjob_remove(job_id)` helper + `--cron-job-id` CLI arg + integration in the `is_pr_terminal` branch. Regression suite `skills/ao-babysit/scripts/test_babysit_self_cancel.py` (11 tests) enforces the contract. Bug-ref: 2026-07-05 thread C0AH3RY3DK6/p1783279995 — even after the v1.1.0 fix landed, babysit cron spam continued because the prompt-level self-cancel clause was unreachable: babysit.py had no way to know its own job_id."
  - "1.1.0 (2026-07-05): Add Phase 0.5 — terminal-state SELF-CANCEL via `cronjob action=remove job_id=$CRON_JOB_ID` (or `launchctl bootout` for launchd-managed babysits). Reference the `babysit-stale-watchdog` companion (every 30 min launchd watchdog at scripts/babysit_stale_watchdog.py) which catches stale babysits even if the in-script check is broken. Document the failure mode the 2026-07-05 babysit-wa-2403-PR7711 leak exposed: 251 polls over 9 days after PR #7711 merged because the original `babysit.py` only recognized 'PR created' as terminal, not 'PR MERGED on GitHub'. Bug-ref: thread C0AH3RY3DK6/p1783240445.370119."
  - "1.0.0 (2026-07-04): Initial authoring (existed on dirty staging branch dev1783194285; first landed on origin/main via cherry-pick of commit 7690435707 in PR replay b2ad00770d)."
---

# babysit-ao-pr-loop

A scheduled cron job ticks every N minutes on a single PR + AO worker pair. Each tick observes (does NOT modify or push) and posts a concise status update to a pre-known Slack thread. The loop is finite — it must terminate cleanly when the work is done, and stay quiet when nothing changed.

## When to load

- A scheduled cron job is targeting a single PR + worker session (e.g. `babysit wa-2403 on PR #7711`).
- A user asks you to "watch PR N", "tick loop on PR N", or "babysit worker wa-NNNN".
- You are inheriting an existing babysit loop mid-life and need to keep its cadence without re-creating its contract.

Do NOT load for: one-shot `agento_report` aggregations (use `agento_report`), PR bring-to-green interactive loops (use `drive-pr-to-green` / `finish-the-job`), full-time babysitting of a launched dev server or browser session (different domain).

**Do NOT load for "watch this Slack thread for a literal token" tasks** — that is a *different* skill pattern (literal-substring scan on `conversations.replies`, optional destructive action on match, otherwise silence). This skill assumes the work being babysat is a single PR + AO worker pair; if there is no PR, no worker, and no PR number in scope, every Phase-0 check (`gh pr view`, `ao session ls`) is undefined and the tick exits without ever loading the literal-substring matcher. Bug-ref: 2026-07-14 thread C0AJQ5M0A0Y/1784070882.257369 — `babysit-di[REDACTED_OPENAI_KEY]` cron `18bd680865d9` auto-loaded this skill instead of running its actual literal-token watch logic, self-cancelled after one tick, and the "babysit armed" claim in the parent thread became a false assurance. Future literal-token-watch crons must (a) NOT pre-load this skill, and (b) inline the literal-substring scan + df/deleted-worktree deletion logic in the prompt body without re-using Phase 0/0.5/1-3 of this contract. Draft sibling skill `slack-thread-token-watch` lives at `~/.hermes/skills/devops/slack-thread-token-watch/SKILL.md` (or rename once landed).

## Skeptic merge-ready protocol (v1.5.0 — replaces v1.3.0)

**v1.3.0 (2026-07-09) said: "Skeptic is gone, stop waiting for it."** That advice is **partially obsolete** as of 2026-07-13. Skeptic is RESTORED as a launchd-managed cron ([jleechanorg/jleechanclaw#779](https://github.com/jleechanorg/jleechanclaw/pull/779)) but the per-repo GHA workflow is permanently gone. Updated rules:

| Aspect | v1.3.0 (2026-07-09) | v1.5.0 (2026-07-13) |
|---|---|---|
| Should the babysit post `/skeptic`? | No, the bot will never respond | **No, still inert** |
| Should the babysit BLOCK waiting for a Skeptic verdict? | No, that wait will never resolve | **Only watch for it as a non-blocking event** — if the launchd cron has dispatched (visible as `skeptic-gate-verdict` comment + `skeptic-cron-trigger-${SHA}` marker), the verdict may appear in 5-30 min. Don't block; report it when it lands. |
| Should the babysit read `gh pr checks .conclusion`? | Yes | **Yes — still required.** Gates 1-6 must all pass before the launchd cron dispatches the review at all. |
| Should the babysit merge? | No, requires human `MERGE APPROVED` | **No, still requires `MERGE APPROVED`** unless `SKEPTIC_AUTO_MERGE=true` is set on the launchd cron env. |
| Should the babysit detect "skeptic is running"? | N/A | **Yes — if a `<!-- skeptic-gate-verdict -->` comment exists for the current SHA but verdict is FAIL, post a single-line notice and ask user to `/advice` the verdict** |

**If the PR has been 6-green for >30 min with no skeptic verdict yet**, post a one-liner: "PR #N 6-green ≥30 min, no skeptic verdict — launchd cron should dispatch soon. If no verdict in 1h, manually run `bash scripts/skeptic_auto_merge.py --repo OWNER/REPO --pr N`."

For the full Skeptic architecture + restoration history, see `references/post-skeptic-green-protocol.md` (rewritten for v1.5.0).

## The contract (each tick)

Each tick has exactly five phases. Do them in this order, every tick:

### Phase 0 — Pre-flight (early-exit; run BEFORE composing any output)

> **v1.9.0 update:** instead of re-implementing the terminal-state probe inline in the cron prompt, prefer invoking the canonical helper:
>
> ```bash
> python3 ~/.hermes/skills/ao-babysit/scripts/babysit.py poll \
>     --session "$SESSION_ID" \
>     --slack-channel "$CHANNEL" \
>     --slack-thread-ts "$THREAD_TS" \
>     --task-summary "$TASK_SUMMARY" \
>     --cron-job-id "$CRON_JOB_ID"
> ```
>
> `babysit.py poll` already wires Phase 0 (GraphQL rate-limit + REST fallback, terminal state probe, double-closeout suppression) + Phase 0.5 (executable self-cancel via `hermes cron remove <id>`). Re-implementing Phase 0 in the prompt body duplicates logic and drifts from the canonical fix over time. Use the helper unless the cron explicitly needs raw control.

When the prompt *does* re-implement Phase 0 (because `babysit.py` is unavailable or the cron needs raw data), the manual recipe is:

Run these three checks. If ANY short-circuits the loop, do NOT post, do NOT nudge — produce the single suppression token or the single terminal message and exit.

1. **Is the work already done?**
   ```bash
   gh pr view <PR> --repo <OWNER>/<REPO> --json state,mergedAt,closedAt 2>&1
   ```
   - `state == "MERGED"` → terminal: post ONE single-line final message to the thread (e.g. `✅ PR <N> merged on <mergedAt>. Loop closing.`) and exit. Do not run subsequent ticks.
   - `state == "CLOSED"` (not merged) → terminal: post ONE escalation asking the user whether to keep the loop alive or stop it (your call: which is more useful here is up to the operator, but default to "stop, ask user"). Do not re-tick on your own.

   ⚠️ **Pitfall — GraphQL rate-limit silently blocks Phase 0.** `gh pr view --json ...` uses the GitHub GraphQL endpoint, which shares a separate 5000/hr counter from the REST core. When that counter is exhausted, `gh pr view` returns `GraphQL: API rate limit already exceeded for user ID <id>.` and the babysit appears to have no terminal-state data — but the PR may already be MERGED. **Do not wait for the GraphQL counter to reset.** Fall back to REST + curl using `gh auth token` (works even when `gh auth status` shows a secondary-account warning). Reference the full rate-limit fallback recipe at `references/graphql-rate-limit-rest-fallback.md`. Quick check + REST read of PR metadata:
   ```bash
   TOKEN=$(gh auth token 2>/dev/null)
   curl -fsS -H "Authorization: token $TOKEN" "https://api.github.com/rate_limit" \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['resources']; \
         print(f\"core={d['core']['remaining']}/5000 graphql={d['graphql']['remaining']}/5000\")"
   # If core > 0 and graphql == 0:
   curl -fsS -H "Authorization: token $TOKEN" \
     "https://api.github.com/repos/<OWNER>/<REPO>/pulls/<PR>" \
     | python3 -c "import sys,json; d=json.load(sys.stdin); \
         print(f\"state={d['state']} merged={d['merged']} merged_at={d['merged_at']}\")"
   ```
   This is the exact path that unblocked the 2026-07-11 PR-review-status babysit when every `gh pr view` returned rate-limit and GraphQL reset was 12 min away.
2. **Is the worker session still alive?**
   ```bash
   ao session ls 2>&1 | grep -E "wa-<id>|<session_label>"
   ```
   - If the worker is gone AND the PR is not yet merged → terminal: post ONE final message noting the worker died, worker session no longer in `ao session ls`, and the loop is closing pending operator direction. Do not auto-respawn.
   - If the worker is gone AND the PR is already merged → terminal: post ONE final message acknowledging both ends and exit.
3. **Did anything actually change since the last tick?**
   - Compare current `git log origin/<base>..HEAD --since="<last_tick_ts>" --oneline` to the last-tick reading. If empty AND no new commit lands on `origin/<branch>` AND no new `ao` state change AND no CI rerun finished → suppress the full status update. Reply with the literal token `HEARTBEAT_OK` (the cron playbook contract) — do NOT post to Slack. If the cron also says "if absolutely nothing new, reply [SILENT]" and you have an empty commit delta AND no in-thread message is required → reply exactly `[SILENT]` per the cron playbook SILENT contract.

   ⚠️ **Pitfall — duplicate closeouts.** A common failure mode is two consecutive babysit ticks each independently noticing "work is done" and each posting a full closeout. After the FIRST tick posts the terminal message, every subsequent tick MUST short-circuit at Phase 0 step 1 even if `mergedAt` was already reported. Do not "refresh" a closeout. The first tick owns the close; subsequent ticks own silence.

### Phase 0.5 — SELF-CANCEL on terminal state (added 2026-07-05, v1.1.0)

After posting the terminal closeout in Phase 0 step 1 or step 2, the cron MUST also remove itself so no further ticks fire. The 2026-07-05 babysit-wa-2403-PR7711 incident exposed the failure mode: the cron reported MERGED every tick for 9+ days but never called `cronjob action=remove` on itself, producing 251 polls of duplicate closeouts to the same Slack thread.

**Mandatory self-cancel clause** — every babysit cron prompt MUST include this verbatim (the agent prompt, not just the skill):

```
After posting the Phase 0 terminal closeout, immediately call:
  hermes cron remove $CRON_JOB_ID
```

Invoked as:

```
python3 ~/.hermes/skills/ao-babysit/scripts/babysit.py poll \
    --session "$SESSION_ID" \
    --slack-channel "$CHANNEL" \
    --slack-thread-ts "$THREAD_TS" \
    --ta[REDACTED_OPENAI_KEY] "$TASK_SUMMARY" \
    --cron-job-id "$CRON_JOB_ID"
```

Without `--cron-job-id`, the script cannot self-cancel and the cron leaks past terminal-state.

> **CLI rename (v1.3.1, 2026-07-13):** the older `cronjob action=remove job_id=$CRON_JOB_ID` form is obsolete. `cronjob` is no longer on PATH; the current CLI is `hermes cron` with subcommands `{list, create, edit, pause, resume, run, remove, status, tick}`. Prompts that still template the old form will fail with `FileNotFoundError` in `babysit.py cronjob_remove()` and the cron will leak until the watchdog catches it (≤30 min).

**Regression contract:** `skills/ao-babysit/scripts/test_babysit_self_cancel.py` enforces the executable side — that `babysit.py` defines `cronjob_remove()`, exposes `--cron-job-id` on both subcommands, and `poll()` invokes `cronjob_remove(cron_job_id)` in the terminal-PR branch. 11/11 tests pass; any future regression to babysit.py that drops the self-cancel plumbing fails the suite.

**Companion watchdog:** `~/.hermes/skills/babysit-stale-watchdog/SKILL.md`
ships a launchd plist (`ai.hermes.schedule.babysit-stale-watchdog`)
that runs every 30 min and disables any babysit cron whose referenced
PR is MERGED/CLOSED, even if the in-script Phase 0.5 self-cancel is
broken, missing, or running against an old prompt version. The
watchdog is the safety net; the in-script Phase 0.5 is the fast path.
Both layers are required.

**Audit recipe** for existing babysit crons that pre-date Phase 0.5
(the v1.0.0 babysit cron registry may have un-self-cancelled jobs):

```bash
hermes cron list | jq '.jobs[] | select(.enabled and (.name|test("babysit|wa-[0-9]")))'
# For each match: gh pr view <PR-ref> --json state,mergedAt
# If MERGED or CLOSED, run: hermes cron remove <id>
```

### Phase 1 — Observe (only if Phase 0 did NOT early-exit)

Run these and only these. Do NOT modify code; do NOT push; do NOT amend commits; do NOT call `ao send` or `git commit`.

1. **`git log origin/<base>..HEAD --oneline`** — what has the worker committed?
2. **`git status`** — any uncommitted work? (Untracked artifacts in the worktree like `.beads/.write.lock`, `specs/skeptic-report.json`, `ADVERSARIAL_REVIEW_*.md` are NORMAL residue from prior ticks, not new work. Do not flag them as "uncommitted work" unless they are fresh files on the fix-related paths.)
3. **`ao session ls | grep <session>`** — worker state (`working` / `pr_open` / `spawning` / `killed`).
4. **`gh pr view <PR> --repo <OWNER>/<REPO> --json headRefName,state,mergeable,commits,mergedAt`** — PR state.
5. **`gh pr checks <PR> --repo <OWNER>/<REPO>`** — CI state (only if Phase 0 didn't early-exit AND worker has pushed since last tick).
6. **`git log origin/<base>..HEAD --stat`** — only if there are new commits this tick.

Run these as a single parallel fan-out of `terminal` calls to keep ticks fast. NOT serial.

> **v1.9.0 additions (REST check-run observation, when GraphQL `gh pr checks` returns no useful detail):**
>
> 7. **(Optional, only when check-run `conclusion=failure` and `gh pr checks` did not surface the failing step)** — fetch the full check-run list and pull annotations:
>    ```bash
>    TOKEN=$(gh auth token 2>/dev/null)
>    curl -fsS -H "Authorization: token $TOKEN" \
>      "https://api.github.com/repos/<OWNER>/<REPO>/commits/<HEAD_SHA>/check-runs?per_page=20" \
>      > /tmp/checks.json
>    python3 -c "import json; d=json.load(open('/tmp/checks.json')); \
>        [print(f\"{c['name'][:60]:60s} {c['status']}/{c.get('conclusion')} started={c['started_at']}\") \
>         for c in d['check_runs']]"
>    ```
>    When a check-run returns `{title=null, summary=null, text=null, annotations_count=1}` (Green Gate commonly does this — the parent job's own output is opaque), the failing file/line/message is on the **annotations** sub-resource:
>    ```bash
>    curl -fsS -H "Authorization: token $TOKEN" \
>      "https://api.github.com/repos/<OWNER>/<REPO>/check-runs/<CHECK_RUN_ID>/annotations" \
>      | python3 -c "import sys,json; [print(f\"  {a['path']}:{a.get('start_line','?')} ({a['annotation_level']}) {a['message']}\") \
>                        for a in json.load(sys.stdin)]"
>    ```
>    Verified on PR #8290 second tick (2026-07-14): `Green Gate` check-run 87222745926 had `text=null` and surfaced a single annotation pointing at `.github` line 20 "Process completed with exit code 1." Without the annotations fetch there was no detail to communicate.
>
> 8. **`gh pr checks --json` field list — exact (v1.9.0)** — the only accepted field names are:
>    `name, state, conclusion, startedAt, completedAt, link, workflow, description, event, bucket`.
>    `url`, `html_url`, `bucket` (as in `check_suite`), and many others return `Unknown JSON field: "<name>"\nAvailable fields: <full list>`. Read the available-fields list from the error rather than guessing. `conclusion` and `startedAt` ARE valid; do not chase ghosts.

### Phase 2 — Decide nudges (only if Phase 0 didn't early-exit AND state has changed)

- If worker has NOT pushed in 30+ min AND state is still `spawning` or `working` → call `ao send <session> "STATUS?"` (the canonical nudge). Wait, do not inline-Enter; the manual Enter is the cron-playbook convention. After nudging, post a one-line note in the thread: `Nudged wa-NNNN at HH:MMZ — no push in N min.`
- If CI is red → summarize the failing check name + run URL in one line. Do not propose fixes; do not edit code. The babysit does not fix.
- If worker pushed new commits since last tick → summarize what landed (commit count + headline + one-line behavior delta), then run `gh pr checks` and post a 1-line green/red summary.
- If state == `pr_open` AND CI fully green AND reviewer-ready (no unresolved CodeRabbit CHANGES_REQUESTED, no Bugbot error-severity comments, mergeable=true) → the PR is **merge-ready**. Post `✅ PR <N> merge-ready — Green Gate ✓, Smoke Gate ✓, CodeRabbit ✓, Bugbot ✓, mergeable=true` to the babysit thread and flag for human `MERGE APPROVED`. Do NOT post `/skeptic` — that workflow is deleted (see `references/post-skeptic-green-protocol.md`).

### Phase 3 — Post the status update to the Slack thread (only if Phase 0 didn't early-exit)

Use the cron-deliverable template. Post ONE message per tick. Keep it under 12 lines.

```
:large_green_circle: _PR <N> babysit tick — HH:MMZ_
  • Worker state: <ao_session_state> | Branch: <branch> | HEAD: <short_sha>
  • Activity since last tick: <commit count> commits, headlines: <h1>; <h2>; ...
    OR "no new commits in <N> min"
  • CI: :white_check_mark: green OR :x: <failing check name> (<run_url>) OR :hourglass: pending
  • Reviewers: CodeRabbit <approve|request-changes|pending>; Bugbot <clean|errors|skipping>
  • Action taken this tick: <nudge / status-only / none>
  • Next checkpoint: <merge-ready / awaiting CI / awaiting CR / awaiting user>
```

If the worker has gone silent for a full 30 min window with no commits and no state change → reply `HEARTBEAT_OK` and DO NOT POST to Slack. This is the cron playbook's silence contract.

If the cron delivery instructions say "respond with exactly [SILENT]" AND there is genuinely nothing to report AND no nudge needed → reply exactly `[SILENT]` per that contract.

> **v1.9.0 — SLACK_USER_TOKEN extraction (only when XOX-P fallback path is taken, i.e. `mcp__slack__conversations_add_message` is unavailable or the bot is in a different workspace from the channel).** `~/.profile` formats the export as `export SLACK_USER_TOKEN="xoxp-..."` with **double quotes** around the value. The brittle pipeline `grep ... | sed 's/^export SLACK_USER_TOKEN=//' | sed 's/"//g'` produces garbage (verified mid-tick — `1 matches` / `1 mat` artifact, followed by 401 from chat.postMessage). Use the quote-aware form:
>
> ```bash
> TOK=$(awk -F'"' '/^export SLACK_USER_TOKEN=/{print $2; exit}' ~/.profile)
> wc -c <<<"$TOK"  # sanity: should be ~80-90 chars for an xoxp-* token
> curl -fsS -X POST "https://slack.com/api/chat.postMessage" \
>   -H "Authorization: Bearer $TOK" \
>   -H 'Content-Type: application/json; charset=utf-8' \
>   -d '{"channel":"<CHAN>","thread_ts":"<TS>","text":"<msg>"}'
> ```
>
> If the file uses single quotes instead, switch the awk delimiter to `awk -F"'"` and print `$2`. The `~/.bashrc` source is wrong (per `bashrc-profile-xapp-drift-blocks-launchd` memory); always read `~/.profile`.

## Termination rules (loop closure)

When ANY of these are true, the loop is done:

1. PR state is `MERGED` (Phase 0 catches this).
2. PR state is `CLOSED` without merge, AND the operator has confirmed to stop.
3. Worker session is gone from `ao session ls`, AND the operator has confirmed to stop.
4. The cron schedule itself has been disabled (e.g. one-time cron fired + `--delete-after-run` completed).
5. The PR has been open > N days (configurable, default 14) with no movement AND no recent owner action → ask the operator.

When terminating:
- Post ONE final summary to the thread.
- Disable or self-delete the cron (one-time crons with `--delete-after-run` handle this automatically).
- If the cron is launchd-managed and meant to keep ticking, set `Disabled=true` in the plist template and `launchctl bootout gui/$(id -u)/<label>`.

## Anti-patterns (do NOT do)

- ❌ Reposting the same closeout message every tick after the work is done. **One tick owns the close; later ticks own silence.**
- ❌ Posting to Slack when nothing changed and the playbook says `HEARTBEAT_OK` / `[SILENT]`. Noise is worse than silence — the human inbox is the precious resource.
- ❌ Inlining `Enter` after `ao send "STATUS?"`. The cron-playbook convention is the literal newline-less stream; the worker ITSELF consumes the manual Enter as a session-input boundary.
- ❌ Editing code, even to fix a CI red. The babysit is observe-only. Drive-to-green goes to `drive-pr-to-green` or `finish-the-job`, which is a different loop.
- ❌ Auto-respawning the worker when it disappears. The operator decides.
- ❌ Treating untracked worktree files (`.beads/.write.lock`, `specs/*.json`, `ADVERSARIAL_REVIEW_*.md`) as "uncommitted work" — they are harness residue from prior ticks, not the fix's scope.
- ❌ Post-merge commits on the branch tip are NOT the babysit's problem. Drift accumulated after `mergedAt` belongs to a different audit; ignore it for status purposes.
- ❌ **Re-introducing a per-repo `.github/workflows/skeptic-cron.yml` (v1.5.0, 2026-07-13).** The launchd cron at jleechanorg/jleechanclaw#779 is the canonical Skeptic dispatch + auto-merge mechanism. Adding a per-repo workflow file is a regression to the 2026-07-09 deletion and re-creates the runner-queue incident from your-project.com bead `rev-z3zus`. See `references/post-skeptic-green-protocol.md` for the audit recipe.
- ❌ **Posting `/skeptic` to a PR (still forbidden post-restore, v1.5.0).** The `/skeptic` slash comment trigger is inert — verdicts are auto-posted by `dark-factory/runner/skeptic_gate_cli.py`, never in response to a PR comment.
- ❌ **Tick-number cadence gated without persistent tick state (added 2026-07-13, v1.4.0, wa-cookies-poll #8353).** When a polling cron's prompt says "post only on tick #4, #8, #12, #16, #20, #24, #28, #32 (every ~20m)" and the cron is recurring (e.g. `every 5m`, repeat 1/99999), the agent has no way to know its own tick number — every cron tick is a fresh agent session, the prior session's `if tick == 4` branch never executes, and tick state held in the prompt's running context evaporates between ticks. Verified 2026-07-13 on `wa-cookies-poll #8353` (cron `1f0822aae664`, thread C0BDEAJH8PK/1783908854.786439): the cron prompt templated "post a single line on tick #4, #8, #12, …", no `.tick_counter` file existed, and the first agent session had to bootstrap `/tmp/repro-a1OGXH/.tick_counter=1` ad-hoc on the cron prompt's first action. The recipe: (1) every tick-cadence cron prompt MUST name a durable tick-state path in step 1 (`STATE=/tmp/<job>/.tick_counter; mkdir -p "$(dirname "$STATE")"`), (2) the first action of every tick is `TICK=$(($(cat "$STATE" 2>/dev/null || echo 0) + 1)); echo "$TICK" > "$STATE"` BEFORE deciding what to post, (3) terminal-state conditions (e.g. "if TICK > 24 → post timeout") read the same file, (4) on terminal-self-cancel, the file should also be removed so a re-spawn starts clean at tick 0. Companion reference: `references/tick-state-persistence-cron-prompt-2026-07-13.md` with the full template block, the bootstrap recipe, and the cross-session-boundary rationale.
- ❌ **REST PR JSON parse fails on raw body field (added 2026-07-13, v1.6.0, PR #779 state check in C0BDEAJH8PK/p1783980995.978159).** When `gh pr view --json` is rate-limited (per `references/graphql-rate-limit-rest-fallback.md`) the natural fallback is `curl /repos/OWNER/REPO/pulls/N | python3 -c "json.load(...)"`. GitHub's response embeds the PR `body` field with literal LF/CR bytes when the description is multi-paragraph Markdown, and Python stdlib `json.loads` rejects those with `json.decoder.JSONDecodeError: Invalid control character at: line N column M (char K)`. Plain `json.loads(raw, strict=False)` does NOT help — `strict=False` is for legacy reasons, not control-char tolerance. The recipe: pipe the response through `gh_safe_json_loads()` (ships at `scripts/gh_pr_json.py`) which pre-escapes every byte in `\x00-\x1f` except `\t`/`\n`/`\r` (which it also escapes, since GitHub does not pre-escape them), then calls `json.loads` on the result. For cron prompts: `STATE=$(curl -fsS -H "Authorization: token $(gh auth token)" "https://api.github.com/repos/${OWNER}/${REPO}/pulls/${PR}" | python3 ~/.hermes/skills/devops/babysit-ao-pr-loop/scripts/gh_pr_json.py --state-only)` returns just `open` / `closed`. Companion reference: `references/rest-pr-json-parse-pitfall.md` with the root-cause writeup, the inline `python3 -c` regex fallback, and the combined rate-limit + parse failure recipe.
- ❌ **workflow_dispatch Green Gate Smoke-Wait 25min timeout masquerades as code failure (added 2026-07-14, v1.7.0, PR #8290 babysit thread C0AH3RY3DK6/1784030452.318509).** When a babysit cron re-triggers the Green Gate via `workflow_dispatch` (the typical babysit pattern: `gh workflow run green-gate.yml -f pr_number=N -f head_sha=<sha>`), the `Smoke Gate Wait (Gate 8)` step has a **hard 25-min wait timeout**. If the upstream smoke event never lands within that window, the wait job is **cancelled** and the downstream `Apply smoke gate result (gate 8)` step in the main Green Gate job fails with `SMOKE_RESULT=cancelled, SMOKE_GATE=unset`. The check then reports as `failure` in `gh pr checks` even though Gates 1-6 (Green Gate Precheck, Bugbot Gate Wait) all PASSED. This is INFRASTRUCTURE (wait exhaustion, not test assertion failure), not a code defect — the PR's code is unchanged and the underlying `pull_request`-triggered Green Gate has separate behavior. The diagnostic recipe: (1) on every `failure` conclusion, fetch the run via `gh api repos/OWNER/REPO/actions/runs/<run_id>/jobs` and look at the FAILED STEP name — if it's `Apply smoke gate result (gate 8)`, check the `Smoke Gate Wait (Gate 8)` job's conclusion (`cancelled` vs `failure`); `cancelled` ⇒ infra wait exhaustion, `failure` ⇒ real test failure; (2) check the run's `event` field — `workflow_dispatch` runs are babysit re-triggers and have the 25-min wait cap, `pull_request` runs do not; (3) prefer `gh api repos/OWNER/REPO/actions/runs?head_sha=<sha>` to see ALL runs (some cancelled, some not) instead of the dedup'd `gh pr checks` view which collapses duplicates. Post format when infra: `:hourglass_flowing_sand: PR #N tick HH:MMZ — Gates 1-6 PASS, Gate-8 Smoke wait timed out (25min, workflow_dispatch infra). Skeptic verdict pending.` — NOT `:x: Gate-8 failed` which would alarm the operator. Companion reference: `references/workflow-dispatch-smoke-wait-pitfall.md`.
- ❌ **Re-implementing Phase 0 inline instead of calling `babysit.py poll --cron-job-id` (added 2026-07-14, v1.9.0, PR #8290 thread C0AH3RY3DK6/1784030452.318509).** Cron prompts that include a full hand-rolled Phase 0 (rate-limit probe → REST curl → awk token → post closeout) duplicate logic that already exists in `babysit.py poll`. The duplication drifts as `babysit.py` gains new terminal-state conditions, new rate-limit counters, or new self-cancel CLIs (e.g. the v1.3.1 rename). Use `babysit.py poll` directly — it already handles GraphQL rate-limit + REST fallback, terminal-state probe, double-closeout suppression, and self-cancel via `--cron-job-id`. Reserve hand-rolled Phase 0 for cron prompts that need raw access to the PR/commits/HTTP responses (e.g. the bring-to-green inline loop). See Phase 0 callout above for the canonical invocation line.

## Tool usage notes

- Use `terminal` for `git`, `gh`, `ao` — fan-out parallel, not serial. A tick should not take more than 6 sequential tool calls.
- Use `mcp__slack__conversations_add_message` for thread replies. The cron invocation will pre-populate `channel_id` + `thread_ts`; verify before posting (per `slack-reply-inherit-thread-ts`).
- Use `mcp__slack__conversations_replies` once per tick if you need to confirm whether earlier ticks already posted a closeout.
- Do NOT use `mcp__slack__conversations_history` in full — paging through the channel is wasteful and may surface unrelated threads. The thread is the unit of work.

## Verification

Before posting the first tick of a new babysit loop, confirm:

- The cron is correctly delivering to the channel + thread configured by the operator. (The cron prompt usually specifies these.)
- The branch name + base branch + PR number are correct. (`gh pr view <N> --json headRefName,baseRefName`.)
- The worker session id is correct. (`ao session ls | grep <pattern>`.)
- If you inherit a mid-loop babysit, READ THE LAST 3 THREAD REPLIES before posting — if a recent tick already announced completion, post `[SILENT]` (do NOT duplicate the closeout).

## Support files

- `references/mid-loop-handoff.md` — pattern for inheriting a babysit loop from a previous session and confirming the thread state before posting.
- `references/cron-prompt-anatomy.md` — anatomy of a babysit cron task prompt (channel, thread_ts, branch, PR, worker session, beat) and how to extract them safely.
- `references/post-skeptic-green-protocol.md` — **v1.5.0 Skeptic merge-ready protocol** (Skeptic is RESTORED as launchd cron). Replaces the obsolete v1.3.0 "Skeptic is gone" protocol. Documents the launchd cron architecture (jleechanorg/jleechanclaw#779), the dark-factory SHA-bound reviewer (PR #281), the AO Go reviewer adapter (agent-orchestrator-golang), and the audit recipe for verifying Skeptic is restored (and in the right shape).
- `references/tick-state-persistence-cron-prompt-2026-07-13.md` — **v1.4.0 recipe for tick-cadence polling crons**. Why "post on tick #4, #8, #12…" silently fails without a persistent counter; the `STATE=/tmp/<job>/.tick_counter` + `TICK=$(($(cat "$STATE" 2>/dev/null || echo 0) + 1))` recipe; the "IF (( TICK % N == 0 ))" gate; the timeout-cleanup step. Use when authoring any cron prompt that gates Slack posting on a tick-number cadence.
- `references/graphql-rate-limit-rest-fallback.md` — **rate-limit fallback for Phase 0** (added 2026-07-11). When `gh pr view --json ...` returns `GraphQL: API rate limit already exceeded`, do NOT wait an hour — REST core is usually still near-full. Contains 5 REST recipes (PR metadata, issue comments, inline review comments, file contents via base64, repo issues), the counter-detection snippet, the `gh auth token` vs `gh auth status` pitfall, and the secondary-rate-limit Retry-After warning.
- `references/rest-pr-json-parse-pitfall.md` — **REST PR JSON parse pitfall** (added v1.6.0, 2026-07-13). The natural Phase 0 sibling to the GraphQL fallback above: `curl /repos/.../pulls/N` succeeds (REST core is fine) but `python3 -c "json.load(...)"` crashes on the multi-paragraph PR `body` field. Why `strict=False` does NOT help, drop-in helper, inline regex workaround, combined rate-limit + parse failure recipe. Verified in the PR #779 state-check cron (`C0BDEAJH8PK/p1783980995.978159`).
- `references/workflow-dispatch-smoke-wait-pitfall.md` — **workflow_dispatch Green Gate Smoke-Wait 25min timeout pitfall** (added v1.7.0, 2026-07-14). When the babysit cron re-triggers Green Gate via `workflow_dispatch` (the typical babysit pattern), the `Smoke Gate Wait (Gate 8)` step has a hard 25-min wait timeout that CANCELS the run when no smoke event lands. The downstream step fails with `SMOKE_GATE=unset` and the rollup reports `failure` — but this is INFRASTRUCTURE, not a code defect. Diagnostic recipe: distinguish `conclusion=cancelled` (wait exhaustion) from `conclusion=failure` (real test failure) on the Smoke Gate Wait job; check the `event` field (`workflow_dispatch` vs `pull_request`). Post format with reassurance tone instead of `:x:` alarm. Verified in the PR #8290 babysit thread (`C0AH3RY3DK6/1784030452.318509`).
- `references/head-advance-no-green-gate-redispatch.md` — **v1.8.0 trap** (added 2026-07-14). When a worker pushes a refresh-head commit superseding the babysit's last-known SHA, the in-flight `workflow_dispatch` Green Gate's Smoke Gate Wait gets CANCELLED and the parent Green Gate runs to `failure` without anything obviously wrong; the `pull_request`-triggered Green Gate may auto-fire but separately may not. The confusable observable pattern (Gates 1-6 PASS, Bugbot PASS, Smoke Gate Wait CANCELLED, parent Green Gate FAIL, no new Green Gate run) is diagnostic — wait 30 min and look for a fresh `pull_request`-triggered Green Gate before declaring infra-broken. If none appears, the operator must explicitly re-dispatch. Verified PR #8290 supersession `aff95f87e → c8dbb469`.
- `references/check-run-observation-endpoints.md` — **v1.9.0 endpoint recipe** (added 2026-07-14). REST `/repos/OWNER/REPO/commits/<sha>/check-runs?per_page=20` returns the full check-run list (`name`, `status`, `conclusion`, `started_at`, `completed_at`, `app`, `check_suite`, `output`). When the parent check-run output has `title=null, summary=null, text=null, annotations_count>0`, the failing detail is on `/check-runs/<id>/annotations` (path, start_line, message, annotation_level). Also documents the exact `gh pr checks --json` valid field list and the brittle-vs-robust SLACK_USER_TOKEN extraction. This is the REST counterpart to the GraphQL `gh pr checks` view, used when GraphQL is rate-limited or when the parent check summary is opaque. To author after v1.9.0 ships.
- `scripts/gh_pr_json.py` — **drop-in helper** (added v1.6.0, 2026-07-13). Provides `gh_safe_json_loads(raw)` (Python module form) + `python3 gh_pr_json.py [--state-only|--summary|--json] <token> <owner/repo> <pr>` (CLI form). Default summary output: `PR #779 [jleechanorg/jleechanclaw] state=open mergeable=True additions=1153 deletions=0 files=5 merged=False`. Drop the `--state-only` form into any cron prompt's Phase 0 terminal-state probe.
