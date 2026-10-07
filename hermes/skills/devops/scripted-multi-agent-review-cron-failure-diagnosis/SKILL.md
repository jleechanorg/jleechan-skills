---
name: scripted-multi-agent-review-cron-failure-diagnosis
description: Diagnose "clean sweep" reports from scripted multi-agent review crons (Hermes `bug-hunt-daily.sh`, future siblings in the family — `wa-*-review-*`, `*-nightly-review-*`) when the report's PR/bug/agent-failure counts are all zero but the scan didn't actually happen. Triggers when a daily bug-hunt / nightly-review cron posts a Slack report with all-zero numbers, a sibling report from the same minute surfaces the real failure, a known review CLI was rate-limited / preflight-failed and the cron ran anyway, or the user pastes such a report and asks "is this right?". Classifies into FOUR buckets (PR-discovery suppressed, agent-preflight suppressed, agent-execution suppressed, fail-closed-not-armed), identifies whether the script's FAILURE_WARNING gate masked the failure, and produces the recipe for the next sibling cron. v1.1.0 (2026-07-23) — adds Bucket E for concurrent codex-review processes racing for the same model-list cache; verified on bug-hunt run 20260723_090145.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [bug-hunt, daily-review, multi-agent, cron, failure-diagnosis, debugging, devops, slack-routing, codex-review-race, parallel-cli]
    related_skills: [wa-daily-cron-failure-diagnosis, gh-rate-limit-and-transient-failures, dropped-messages, slack-thread-routing-investigation, dispatch-task, drive-pr-to-green, always-pr-never-local-edit, advice]
---

# Scripted Multi-Agent Review Cron Failure Diagnosis

When a Hermes scripted multi-agent review cron (currently `bug-hunt-daily.sh`, future siblings in the same family) posts a Slack report that **looks like a clean sweep** (PRs reviewed=0, Bugs found=0, Agent failures=0/0), the dispatcher is staring at the script's failure-shape: every layer of the pipeline (PR discovery, agent preflight, agent execution) silently coerces its failure to "zero work done", and the `FAILURE_WARNING` block is gated only on agent-execution failures — not on the upstream gates. The 4-bucket classification below is the diagnostic; the recipe at the end is the durable fix.

This is **distinct from** `wa-daily-cron-failure-diagnosis` (which covers GCP Cloud Run cron jobs for your-project.com with email alerts). This skill covers Hermes-side launchd crons with Slack alerts — different channel, different agent fleet, different failure shape. The two skills share Pitfall 5 ("trust the report's zero count") and Pitfall 8 ("re-verify against live state"); the buckets diverge.

## When this skill fires

- **Slack report arrives:** `*Daily Bug Hunt Report - <TS>*` with `PRs reviewed: 0 / Bugs found: 0 / Agent failures: 0/0`.
- **User pastes such a report:** "is this right?", "this says zero PRs — there should be some", "the daily bug hunt is broken".
- **Sibling-report signal:** a `bug-hunt-<TS>.md` file from the SAME minute has a `## PR Discovery Failure` section, OR a sibling has `Agent failures: N/N` instead of 0/0. Sibling reports at `ls /tmp/hermes/bug_reports/bug-hunt-<same-minute-prefix>*` are the smoking gun.
- **Cron ran but didn't surface what it should have:** the launchd plist (`launchctl print gui/$(id -u)/ai.hermes.schedule.<job>`) shows last exit 0, the log is fresh, but Slack got a zero-result report.

## The five failure buckets — classify BEFORE doing anything

Always classify into ONE of these five buckets before recommending a fix. The bucket determines the recipe.

### Bucket A: PR-discovery suppressed (rate-limit / network / auth)

**Symptom markers:**
- Sibling report file contains `## PR Discovery Failure` block with a `GraphQL: API rate limit already exceeded for user ID <N>` line, OR an `HTTP 5xx`, OR a `could not resolve host` error.
- The "clean sweep" report's own JSON output files for all agents are **0 bytes** (`bug-hunt-<agent>-<TS>.json` size = 0, `bug-hunt-<agent>-<TS>.err` size = 0). Agents were never started because the script took the `continue` path on `if [ "$PR_COUNT" -eq 0 ]`.
- `gh api user` confirms the rate-limited user ID matches the active token (`gh api user --jq .id` should equal the user ID in the rate-limit message).

**Root cause:** `get_merged_prs "$REPO" 2>/dev/null || echo "[]"` silently coerces a non-zero exit (rate limit, auth failure, network error) to `[]`. The script has no way to distinguish "no PRs merged in the window" from "couldn't even ask".

**Recipe:**
1. Identify which token hit the rate limit (`gh api user --jq .id` vs the user ID in the rate-limit message — should match).
2. Wait for the rate-limit window to pass (GitHub GraphQL resets hourly; REST has its own counter).
3. Manually re-run discovery with `gh pr list --state merged --search "merged:>=<since>"` against each scanned repo.
4. The "fix now" recipe: replace the silent-coercion line with a typed status return (`printf 'ERROR\t%s\t%s\n' "$repo" "$out" >&2; return 1`) and stop coercing to `[]`. The `FAILURE_WARNING` block must surface discovery failures too.

### Bucket B: Agent-preflight suppressed (review CLI missing flags / not installed)

**Symptom markers:**
- `bug-hunt-review-preflight-<TS>.err` contains `ERROR: installed codex CLI lacks supported review mode` or `ERROR: installed codex CLI lacks explicit model selection` or `ERROR: codex CLI not found`.
- The "clean sweep" report has `Agent failures: 0/0` — agents never started because `REVIEW_CLI_AVAILABLE=0` took the `continue` path.
- `codex review --help 2>&1 | grep -q -- '--base'` returns non-zero on this machine.

**Root cause:** `configure_review_cli()` returns 1 when the local `codex` CLI lacks the `--base`/`--model` flags the script requires. The script then skips the agent loop entirely, leaving `AGENT_PIDS=()` empty, so `AGENT_FAILURES` stays 0 (no agents to fail). The `FAILURE_WARNING` block only fires on `ALL_AGENTS_FAILED` (every spawned agent failed), not on "no agents spawned because preflight short-circuited".

**Recipe:**
1. Install or update `codex`: `brew upgrade codex` (or `npm i -g @openai/codex`).
2. Verify flags: `codex review --help 2>&1 | grep -E -- '--(base|model)'` should return non-empty.
3. Verify the model tier per SOUL.md `## COMMIT: subagent model routing (mandatory, 2026-07-14)` — cheapest correct tier for review lanes (mini/haiku-class for pollers/monitors, mid-tier Sonnet/Codex Luna for standard review/evidence lanes).
4. The "fix now" recipe: change `configure_review_cli` to return 0 on missing CLI but still mark a typed `PREFLIGHT_FAILED` status; the loop should set `AGENT_FAILURES=${#AGENTS[@]}` when preflight fails so the warning fires.

### Bucket C: Agent-execution suppressed (spawned but produced 0 bytes / errors)

**Symptom markers:**
- JSON output files exist but are 0 bytes: `bug-hunt-<agent>-<TS>.json size=0`.
- Error files contain `codex: command not found`, `Error: 401`, `Error: 429`, or timeout messages.
- The "clean sweep" report has `Agent failures: N/N` — the warning fires correctly here, but the bug count is still 0 because all agents crashed before producing findings.

**Root cause:** `codex review` was spawned but the underlying model invocation failed (auth, quota, network). The script's `validate_finding_evidence()` correctly rejects empty/malformed output and counts as `AGENT_FAILURES`. **This is the bucket the script handles correctly.** The bug is upstream — quota exhaustion on the chosen tier, transient OAuth expiry, or `codex` binary segfaulting.

**Recipe:**
1. Read the `.err` files: `cat /tmp/hermes/bug_reports/bug-hunt-<agent>-<TS>.err`.
2. Identify the failure class (auth → re-login; quota → switch tier per SOUL.md `subagent model routing`; binary → reinstall).
3. Retry with a different model tier (`BUG_HUNT_REVIEW_MODEL=...`) or different agent fleet.
4. If the underlying cause is quota exhaustion on the cheapest tier, escalate per `ao-spawn-minimax-worker` (mid-tier fallback).

### Bucket D: Fail-closed-not-armed (cron disabled / plist not loaded)

**Symptom markers:**
- `launchctl print gui/$(id -u)/ai.hermes.schedule.bug-hunt-daily` shows `state = not running` and `last exit code = 0` BUT the log mtime is hours/days old.
- `bug-hunt-<TS>.md` files in `/tmp/hermes/bug_reports/` are from older runs; no fresh timestamps.
- `~/.hermes/launchd/ai.hermes.schedule.bug-hunt-daily.plist` exists but `Disabled=true` (canonical example: `ai.hermes.schedule.<job>-watcher.plist` pattern).

**Root cause:** Plist was disabled, never re-enabled after a previous test run, or `KeepAlive{SuccessfulExit=false}` caused launchd to remove it from the run queue. This is NOT a script bug — it's an infra bug. See `dropped-thread-watcher-of-watchers` for the canonical silent-cron-death pattern.

**Recipe:**
1. Check plist state: `plutil -p ~/.hermes/launchd/ai.hermes.schedule.bug-hunt-daily.plist | grep -E 'Disabled|StartInterval|KeepAlive'`.
2. Check launchd state: `launchctl print gui/$(id -u)/ai.hermes.schedule.bug-hunt-daily 2>&1 | head -20`.
3. Re-enable: `launchctl enable gui/$(id -u)/ai.hermes.schedule.bug-hunt-daily && launchctl kickstart -k gui/$(id -u)/ai.hermes.schedule.bug-hunt-daily`.
4. Verify next scheduled run lands and produces a real report.

### Bucket E: Parallel-CLI-process race (concurrent agents hit shared resource lock)

**Symptom markers:**
- PRs were discovered correctly (Bucket A excluded — `TOTAL_PRS > 0` in the log, e.g. `Found 9 merged PRs`).
- Preflight passed (Bucket B excluded — `bug-hunt-review-preflight-<TS>.err` is empty).
- Per-agent output files exist and are **0 bytes**: `bug-hunt-<agent>-<TS>.json size=0`.
- **`bug-hunt-<agent>-<TS>.err` is 0 bytes for SOME lanes but NON-empty for OTHERS** — the discriminating signal. The non-empty err shows the underlying CLI's banner (`OpenAI Codex v0.144.5`, `model: gpt-5.3-codex-spark`, `workdir: ...`) and then a fatal line like `failed to refresh available models: timeout waiting for child process to exit` or `codex_models_manager::manager: failed to refresh available models: ...`.
- The "clean sweep" report has `Agent failures: N/N` where N == number of agents — FAILURE_WARNING fires correctly here.
- `ps aux | grep -E "<cli-binary>"` shows multiple instances of the same CLI binary running concurrently with overlapping start times.

**Root cause:** The script spawns N agents in parallel as background processes from a single bash subshell, all targeting the SAME CLI binary with the SAME model. Each CLI process tries to refresh the local model-list cache on startup; the cache has a single-writer lock and the loser times out. One process wins, the others produce 0-byte output and either swallow the failure to a 0-byte `.err` (race winner ate the error stream) or write the banner + timeout to `.err` before exiting.

This was confirmed in the 2026-07-23 09:01 PT bug-hunt run: three concurrent `codex review -c "model=\"gpt-5.3-codex-spark\"" -` processes from `bug-hunt-daily.sh:230-238`. `bug-hunt-claude-20260723_090145.{json,err}` and `bug-hunt-codex-20260723_090145.{json,err}` were both 0 bytes. `bug-hunt-minimax-20260723_090145.json` was 0 bytes; `bug-hunt-minimax-20260723_090145.err` contained the actual Codex banner + `codex_models_manager::manager: failed to refresh available models: timeout waiting for child process to exit`. All three agents used the SAME `gpt-5.3-codex-spark` model — the labels `claude`/`codex`/`minimax` were cosmetic, all three were the same Codex CLI invocation.

**Recipe:**
1. **Detect: count err-files-with-content vs total.** `for f in /tmp/hermes/bug_reports/bug-hunt-*-<TS>.err; do echo "$f $(stat -f%z "$f") bytes"; done`. Mix of 0-byte and non-zero = Bucket E.
2. **Stop spawning the same CLI in parallel.** Two durable fixes, pick one:
   - **Switch to per-agent CLIs** (the canonical fix in PR #792): `hermes -z -m <model>` per agent label where each label maps to a DIFFERENT CLI (`claude` → Claude Code, `gemini` → Gemini CLI, `minimax` → minimax Anthropic-API shim). Each CLI has its own model-list cache, no contention.
   - **Serialize the agents**: change the bash loop from `&` backgrounding to `wait` after each spawn. Loses parallelism but eliminates the race.
3. **Surface the race in the report.** Add a per-agent stderr-capture guard that copies non-empty `.err` content into the `## Results` section BEFORE the FAILURE_WARNING block, so a single-line `codex_models_manager::manager: failed to refresh available models: timeout waiting for child process to exit` shows up in Slack instead of being swallowed.
4. **Add a regression test** that monkey-patches the agent spawn to return the timeout error string and asserts the report's `## Results` section contains the literal `failed to refresh available models`.

**Related skill for the canonical fix:** the durable fix lives in `jleechanorg/jleechanclaw` PR #792 (`fix/durable-bug-hunt-harness`, MERGEABLE, CodeRabbit APPROVED, blocked only by Gate 3 stale state + Gate 5 unresolved comment as of 2026-07-23). Reference: `references/2026-07-23-bug-hunt-codex-review-race.md`.

## The 7-step investigation protocol (always run in order)

### Step 1 — Read the report file the bot posted

```bash
cat /tmp/hermes/bug_reports/bug-hunt-<TS>.md
```

Capture: PRs reviewed, Bugs found, Agent failures. If all three are zero, suspect suppression (Buckets A/B/C/D).

### Step 2 — List sibling reports from the same minute

```bash
ls -la /tmp/hermes/bug_reports/bug-hunt-<same-minute-prefix>*
```

If you see ≥2 reports from the same minute, **the cron ran more than once** and one of them likely surfaced the real failure. Sibling reports are the smoking gun — Bucket A/B always leaves a sibling that reports correctly.

### Step 3 — Inspect per-agent JSON output + .err files

```bash
for f in /tmp/hermes/bug_reports/bug-hunt-{claude,codex,gemini,minimax}-<TS>.{json,err}; do
  echo "=== $f ($(stat -f%z "$f" 2>/dev/null) bytes) ==="
  [ -s "$f" ] && head -c 500 "$f"
  echo
done
```

Empty JSON + empty err = Bucket A or D (agents never spawned). Empty JSON + non-empty err = Bucket C (agents spawned, failed). **Mixed empty-JSON-and-err across agents = Bucket E (parallel-CLI-process race)** — see Bucket E's symptom markers; the lane that captured the banner-then-timeout is the one that lost the model-list cache lock. Preflight .err present = Bucket B.

### Step 4 — Re-derive the ground truth

```bash
gh api graphql -f query='query {
  a: repository(owner:"jleechanorg",name:"jleechanclaw"){ pullRequests(first:25, states:[MERGED], orderBy:{field:UPDATED_AT, direction:DESC}){ nodes{ number, title, mergedAt } } }
  b: repository(owner:"jleechanorg",name:"your-project.com"){ pullRequests(first:25, states:[MERGED], orderBy:{field:UPDATED_AT, direction:DESC}){ nodes{ number, title, mergedAt } } }
  c: repository(owner:"jleechanorg",name:"ai_universe"){ pullRequests(first:15, states:[MERGED], orderBy:{field:UPDATED_AT, direction:DESC}){ nodes{ number, title, mergedAt } } }
  d: repository(owner:"jleechanorg",name:"beads"){ pullRequests(first:15, states:[MERGED], orderBy:{field:UPDATED_AT, direction:DESC}){ nodes{ number, title, mergedAt } } }
}' | jq -r '.data | to_entries[] | .key as $alias | .value.pullRequests.nodes[] | select(.mergedAt >= "2026-07-20T00:00:00Z") | "\($alias)#\(.number) \(.title)"'
```

(Adjust `<TS>` and `mergedAt >= "<since>"` to the actual window.) This is the live ground truth; the report is the suspect. **Compare counts.** Mismatch = Bucket A.

### Step 5 — Classify into one of the four buckets

Apply the markers from each bucket section above. Buckets can compound (e.g. Bucket A on first repo → all subsequent repos loop returns `[]` → no agents → clean sweep). When in doubt, start with Bucket A — it is the most common and the most silent.

### Step 6 — Identify the right fix surface

| Bucket | Right fix surface |
|---|---|
| A | `~/.hermes/scripts/bug-hunt-daily.sh` lines 112-114, 137, 405-416 — replace silent `[]` coercion; broaden FAILURE_WARNING gate |
| B | `~/.hermes/scripts/bug-hunt-daily.sh` `configure_review_cli()` — surface preflight failure in FAILURE_WARNING |
| C | Quota/auth/tier — outside script. Apply SOUL.md `subagent model routing` + retry with `BUG_HUNT_REVIEW_MODEL` |
| D | launchd plist — `~/.hermes/launchd/ai.hermes.schedule.bug-hunt-daily.plist` + `launchctl enable`/`kickstart` |
| E | Switch to per-agent CLIs (e.g. `hermes -z -m <model>` per label) OR serialize the spawn loop; surface the cached timeout in the report |

### Step 7 — Produce a named end-state

Per `diagnosis-requires-followthrough-or-handoff`, every diagnosis must end with one of:

1. **"apply now"** — fix is ≤10 lines, single-file, reversible (e.g. broaden FAILURE_WARNING gate). Apply inline in same turn. Reply: "Diagnosis complete. Applied the fix inline — <summary + file:line + verification>."

2. **"dispatch now"** — multi-file or needs PR (the script fix + pytest). `ao spawn` with a one-line brief OR `bring-to-green` babysit cron. Reply: "Diagnosis complete. Dispatched <worker> on branch <branch> with the recipe."

3. **"hand off explicitly"** — fix is destructive/expensive (data migration, schema, billing, prod deploy) OR user has been upset by auto-fixes. Paste exact 3-5 line shell block + offer to dispatch. Reply: "Diagnosis complete. NOT applying because <reason>. To finish: <shell block>."

Bare "Investigate" / "look at this report" (no `/a`, `/finish`, `/auto`) means **diagnose-then-hand-off**: do NOT auto-dispatch. Reply with the diagnosis + end-state ask.

## Pitfalls

### Pitfall 1: Trusting the "clean sweep" report's zero counts

The script's three zero counts (PRs=0, Bugs=0, Agent failures=0/0) are all three independently suppressible by upstream failures. Always run Step 2 (sibling reports) and Step 4 (re-derive ground truth) before believing any of the three. The 2026-07-22 case: zero counts on the main report, sibling at the same minute had `## PR Discovery Failure` with the rate-limit message verbatim, and Step 4 found 8 merged PRs the bot should have reviewed.

### Pitfall 2: Diagnosing the report's surface format instead of the script's pipeline

The user often asks "is this report formatted right?" — that's the wrong question. The format is fine; the content is suppressed. Pivot to the pipeline: PR discovery → agent preflight → agent execution → report generation. Each stage has a silent-failure path; identify which one is firing in this run.

### Pitfall 3: Skipping the launchd state check (Bucket D) on first encounter

If `bug-hunt-<TS>.md` files are stale (no fresh timestamps in the last 24h), check the launchd plist state FIRST. No amount of script debugging helps if the cron isn't running. `launchctl print gui/$(id -u)/ai.hermes.schedule.bug-hunt-daily 2>&1 | grep -E 'state|last exit'` is the 5-second check.

### Pitfall 4: Reporting "all three agents failed" when the actual cause was preflight

The "clean sweep" report with `Agent failures: 0/0` often masks a preflight failure (Bucket B). The script's FAILURE_WARNING gate only fires on `AGENT_FAILURES == ${#AGENTS[@]}` (every spawned agent failed), not on `REVIEW_CLI_AVAILABLE == 0` (no agents spawned because preflight short-circuited). Read the preflight .err file before declaring "agents failed".

### Pitfall 5: Trusting prior-session conclusions about cron health

EA sweeps (e.g. `memory/briefings/YYYY-MM-DD/<time>-ea-sweep.md`) often cite "bug-hunt cron is healthy" or "no PRs to review" from brief-time telemetry. Re-derive live per Step 4. The same "session-of-record drift" bug that `wa-daily-cron-failure-diagnosis` Pitfall 10 catches for daily-cron telemetry applies here.

### Pitfall 6: Reading the bot's Slack-token vs the user's GitHub-token

The Slack post lands under the bot's identity (XOX-B). The GitHub `gh pr list` rate-limit is on the user's GitHub token (XOX-P for the user, or `GITHUB_TOKEN` for the bot identity). When triaging rate-limit errors, the user ID in the message is the GitHub user (`gh api user --jq .id`), not the Slack user. They're different credentials.

### Pitfall 7: Posting the diagnostic to the wrong Slack thread

Per SOUL.md `slack-reply-inherit-thread-ts` + `slack-channel-routing-policy`, the diagnostic reply belongs in the originating thread (the bug-hunt report thread) — NOT a home-channel orphan. The report itself is the durable artifact; if you reply home-channel instead of in-thread, the user will treat the home-channel post as "your reply" and re-ask in-thread. Always verify `ThreadTs == <correct_ts>` on the verification call (`conversations.replies`).

### Pitfall 8: Auto-dispatching on bare "is this right?"

`no-confirmation-gate`: bare "is this right?" / "look at this report" / "the bug hunt is broken" are NOT dispatch commands. Only `/a`, `/fullrun`, `/finish`, `/auto`, `/f`, `/fin` bypass the confirmation gate. If the user's message is bare, diagnose and name the end-state — let the user invoke the dispatch command. Posting "Should I spawn an AO worker? Y/N" is a SOUL.md violation.

### Pitfall 9: Skipping the "named end-state" — finishing with "want me to fix?"

Every diagnostic reply must end with ONE of: "apply now" / "dispatch now" / "hand off" named explicitly. A reply ending with "Want me to ...?" or "Should I ...?" is a SOUL.md `no-pick-one-menus` violation. The user explicitly opted into autonomous execution by building this skill family, but a structured diagnosis with a named handoff lets them pick precisely.

### Pitfall 11: Treating a mixed empty/non-empty `.err` pattern as Bucket C only

The Bucket C markers say "empty JSON + non-empty err = Bucket C". When ALL lanes show that pattern, it's Bucket C. But when the pattern is mixed (some lanes 0-byte err, some non-empty err, ALL lanes 0-byte JSON), it's Bucket E — a parallel-CLI-process race where the cache-lock winner ate its error stream and the loser(s) got the timeout. The single signal that disambiguates Bucket C from Bucket E is **which CLI** is in the `.err` file. If every non-empty `.err` file shows the SAME CLI banner and the SAME model — and the script's TASK_PROMPT was sent to N distinct labels that all resolved to the same CLI/model — it's Bucket E, not C. The "fix CLI" recipe in Bucket C won't help; the fix is "stop running this CLI N times in parallel" (Bucket E recipe).

A subtler pitfall inside this one: the cosmetic agent labels (`claude`/`codex`/`minimax`) often DO NOT correspond to distinct CLI binaries. When the script dispatches via a single `codex review -c "model=\"…\""` for all three labels, the labels are cosmetic and all three agents are the same Codex CLI. The bug-hunt run 20260723_090145 had labels `claude`/`codex`/`minimax` and a single banner `OpenAI Codex v0.144.5 / model: gpt-5.3-codex-spark` in the surviving `.err`. Diagnosing this as "claude and codex failed but minimax worked" is wrong — minimax didn't work either; it just produced a non-empty `.err` before the timeout.

### Pitfall 10: Including a recipe without proof

Per SOUL.md `proof-before-claim`, the diagnostic reply must include raw terminal output proving the classification — sibling report contents, `.err` file lines, `gh api` output for the re-derivation. A "Bucket A" classification with no `cat` output of the sibling report's `## PR Discovery Failure` section is unprovable and is a SOUL.md `fabricated proof` violation.

## Reference and cross-links

- `references/2026-07-22-bug-hunt-rate-limit-suppression.md` — session-specific evidence: the three sibling reports from `16:40:07`, `16:40:09`, `16:40:11` PT; the GraphQL rate-limit message verbatim; the script's lines 112-114, 137, 405-416 trace; the 8 PRs the bot failed to review; the durable-fix recipe for the script + pytest.
- `references/2026-07-23-bug-hunt-codex-review-race.md` — session-specific evidence for Bucket E: three parallel `codex review` processes racing for the same model-list cache; one lane captured the banner + `codex_models_manager::manager: failed to refresh available models: timeout waiting for child process to exit`, the other two produced 0-byte `.err`; the cosmetic agent labels all resolved to the same CLI; in-flight durable fix is `jleechanorg/jleechanclaw#792` (`fix/durable-bug-hunt-harness`).
- `~/.hermes/skills/worldarchitect/wa-daily-cron-failure-diagnosis/SKILL.md` — sibling skill for GCP-cron failures (4-bucket classification pattern shared, but different cron family).
- `~/.hermes/skills/devops/gh-rate-limit-and-transient-failures/SKILL.md` — the GraphQL rate-limit-and-recovery playbook that Bucket A relies on.
- `~/.hermes/skills/dropped-messages/SKILL.md` — Bucket D detection (silent launchd death).
- `~/.hermes/skills/devops/slack-thread-routing-investigation/SKILL.md` — Pitfall 7 (wrong-thread post) recovery.
- `~/.hermes/skills/hermes-imports/dispatch-task/SKILL.md` — AO worker dispatch mechanics for the "dispatch now" end-state.
- `~/.claude/skills/drive-pr-to-green/SKILL.md` — for driving the resulting PR through to merge.
- `~/.claude/skills/advice/SKILL.md` — for `/advice` second-opinion on the script fix.
- `~/.cursor/rules/pr-hyperlink.mdc` — for the PR-hyperlink rule when reporting the missed PR list to the user.
- `~/.hermes/scripts/bug-hunt-daily.sh` — the script under diagnosis; lines 112-114 (silent coercion), 137 (`|| echo "[]"`), 405-416 (FAILURE_WARNING gate).

## One-line summary

**Treat every "clean sweep" report as suspect until proven otherwise — sibling reports in the same minute and live `gh api` re-derivation are the two smoking guns. Classify into A/B/C/D/E (E = parallel-CLI-process race: mixed empty/non-empty `.err` across lanes, all targeting the same CLI/model), fix the right surface, name the end-state explicitly.**
