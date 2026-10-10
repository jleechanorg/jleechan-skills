---
name: hermes-deploy-pipeline
description: "Enforce the Hermes deploy pipeline — always write to ~/.hermes first, test, then deploy to ~/.hermes_prod. Use whenever creating or modifying launchd jobs, scripts, configs, or any file that needs to run in the Hermes production environment."
when_to_use: "Use when: creating launchd jobs, modifying scripts that run via launchd, adding cron jobs, updating config files, or anything that needs to survive across sessions and be in the prod environment. Also use when the user says 'make this permanent', 'add this to the schedule', 'create a cron job', or 'set this up.'"
arguments:
  - file_path
  - description
argument-hint: "<file_path> [description]"
context: inline
---

# Hermes Deploy Pipeline

## The Rule

**Always write to `~/.hermes` (staging) first. Test. Then deploy to `~/.hermes_prod/` via `scripts/deploy.sh`.**

Going straight to prod or using wrong paths causes:
- Staging/prod drift (untracked changes in prod)
- Git history bypassed (no commit record)
- Broken rollback capability

## The Contract

When adding any file that needs to run permanently in the Hermes environment:

1. **Write to `~/.hermes/`** — not `~/.hermes_prod/`, not `~/.hermes/` (prod symlink), not any ad-hoc path
2. **Test in staging** — run the script/launchd manually, verify it works
3. **Commit to git** — `cd ~/.hermes && git add -A && git commit && git push origin main`
4. **Deploy via pipeline** — `~/.hermes/scripts/deploy.sh`

**⚠️ The "fix already on `origin/main`, deployed is stale" case has a separate recipe.** When the fix you need is already merged to `origin/main` but the deployed file is stale AND staging is on a dirty non-main branch (so `deploy.sh` will die on the uncommitted-changes check), do NOT open a duplicate PR. The user's "commit to main" intent is already satisfied by the existing commit. The right move is the surgical-sync recipe in `references/staging-dirty-surgical-sync.md` (worktree from `origin/main` → `cp` to staging + prod → `launchctl kickstart -kp` to force re-exec). Verified 2026-06-20 against PR #619 / `ai.hermes-watchdog` false-DOWN alert loop.

## File Routing

| File type | Write to | Notes |
|-----------|----------|-------|
| launchd plists | `~/.hermes/launchd/` | Then copy to `~/Library/LaunchAgents/` after deploy |
| Scripts (hermes-managed) | `~/.hermes/scripts/` | Deployed to prod via sync step |
| Cron jobs | Use `cronjob` tool | Registers in hermes_prod's kanban.db directly |
| Config files (prod) | `~/.hermes/config.yaml` | See "Config File Editing" section below — `deploy.sh` does NOT sync `config.yaml` to prod. Manual `cp` + restart required. |
| Config files (prod) | `~/.hermes/config.yaml` (staging) ↔ `~/.hermes_prod/config.yaml` (prod, byte-identical mirrors) | See "Config File Editing" section below — `deploy.sh` does NOT sync `config.yaml` to prod. Manual `cp` + `launchctl kickstart -k` required. As of Hermes v0.13.0 (2026-06-25), there is NO `config.staging.yaml` — older docs that reference it are stale. The user-facing "iteration budget" knob is `agent.max_turns` (line 20), NOT `max_iterations` — see `references/two-config-files-prod-vs-staging.md`. |
| Hermes Agent core files | `~/projects/hermes-agent/` (staging) | Primary write target for `run_agent.py`, `agent/` modules. `projects_other/` is an AO worker mirror, NOT a write target. Deploy syncs staging → prod. |
| Skills | `~/.hermes/skills/` | Deployed via deploy pipeline |
| Skills (project-specific thin pointers) | `~/.hermes/skills/<name>/SKILL.md` | Contains only path to canonical skill in repo + hard-gate reminders. Canonical lives in `.claude/skills/` inside the project repo. See `skill-creator` → "Project-specific skills" section. |
| Skills (wrapper over a bundled skill — binary substitution) | `~/.hermes/skills/<name>/SKILL.md` | Re-exports a bundled skill (e.g. `claude-code`, `codex`) but swaps the **default binary** because the user has a bashrc wrapper that pins provider/env (e.g. `claudem` = `ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic ANTHROPIC_MODEL=MiniMax-M3`). Two-mode structure mirrors the bundled skill; only the binary name changes. Edit the bundled skill in place instead ONLY if you can guarantee no upstream re-deploy will overwrite you; otherwise the wrapper survives a future `git pull`. Worked example 2026-07-24: `skills/claude-code-claudem/SKILL.md` (v1.0.0) re-exports `skills/autonomous-ai-agents/claude-code/SKILL.md` (v2.2.0) with `claudem` as the default binary; live-verified `claudem -p` round-trips to MiniMax-M3 in ~6-8s. |
| SOUL.md `## COMMIT:` sections | `~/.hermes_prod/SOUL.md` AND `~/.hermes/workspace/SOUL.md` (the staging symlink target) | BOTH trees must be updated in the same turn. Runtime loads from `~/.hermes_prod/`; staging is git-tracked. After writing, run `grep -n 'C0B...' ~/.hermes_prod/SOUL.md ~/.hermes/workspace/SOUL.md` to verify the channel ID / rule text matches in both trees (typos here break every future session that fires the trigger). Do NOT auto-run `scripts/deploy.sh` after writing a SOUL.md COMMIT — the user typically wants a chance to review the rule before the gateway restart. (See "SOUL.md COMMIT workflow" below.) |

## Config File Editing

`~/.hermes/config.yaml` is the canonical staging config (gitignored — has tokens baked in). `~/.hermes_prod/config.yaml` is the prod live copy. The `deploy.sh` script does **NOT** sync these — it only does `git pull` + restart + canary. For `config.yaml` changes:

1. Edit `~/.hermes/config.yaml` (staging, source of truth)
2. `cp ~/.hermes/config.yaml ~/.hermes_prod/config.yaml` to sync
3. `diff ~/.hermes/config.yaml ~/.hermes_prod/config.yaml` to verify
4. Restart prod gateway: see "Gateway Restart" below
5. Verify with `python3 -c "from hermes_cli.config import load_config; print(load_config().get('auxiliary', {}).get('vision', {}))"` from a venv that has hermes-agent installed (e.g. `~/.hermes/.venv`)

**Protected vs editable config:** The "no changes without approval" rule in `~/.hermes/AGENTS.md` and `~/.hermes_prod/AGENTS.md` only covers `hermes.json` and `hermes.staging.json` (gateway runtime: `timeoutSeconds`, `maxConcurrent`, `subagents.maxConcurrent`, main model selection). Other sections of `config.yaml` (`auxiliary.*`, `openrouter.*`, `bedrock.*`, `prompt_caching.*`, `compression.*`) are NOT in the protected set and can be edited normally. When in doubt, check `scripts/doctor.sh` — it enforces the protected values and will FAIL on drift.

**⚠️ Iteration-budget confusion (2026-06-25, Hermes v0.13.0).** The user's "iteration budget" maps to `agent.max_turns` at line 20 of `~/.hermes/config.yaml` — NOT `max_iterations` (which is `delegation.max_iterations: 500` at line 348, a subagent fan-out cap), NOT `goals.max_turns: 20` at line 361, and there is NO `config.staging.yaml` in this install (older docs referenced it — stale). The two configs that EXIST are byte-identical mirrors: `~/.hermes/config.yaml` (staging) and `~/.hermes_prod/config.yaml` (prod). Both must be edited together. Diagnostic one-liner before any "bump the budget" task:

```bash
grep -nE "^\s*max_turns:|^\s*max_iterations:" ~/.hermes/config.yaml ~/.hermes_prod/config.yaml
```

Code default is `90`; current value is `60` (deliberately lowered, not a bug). `doctor.sh` does NOT enforce `max_turns` (only `maxConcurrent`/`timeoutSeconds`/`subagents.maxConcurrent`), so AGENTS.md "no changes without approval" is the only gate. Full recipe + three-knob table + root-cause checklist for "edit didn't stick": `references/two-config-files-prod-vs-staging.md`.

## Gateway Restart (without full deploy)

`deploy.sh` does the full pipeline (pull + restart + canary). For a config-only change you can do the same restart pattern manually:

```bash
DOMAIN="gui/$(id -u)"
LABEL="ai.hermes.prod"
PID="$(launchctl print "${DOMAIN}/${LABEL}" 2>/dev/null | grep '^ *pid' | awk '{print $3}' || true)"
[ -n "$PID" ] && kill -TERM "$PID" 2>/dev/null
# launchd respawns; wait for health
for i in $(seq 1 15); do curl -sf --max-time 3 http://127.0.0.1:8643/health >/dev/null 2>&1 && break; sleep 2; done
curl -sf http://127.0.0.1:8643/health  # expect {"status":"ok","platform":"hermes-agent"}
bash ~/.hermes/scripts/hermes-canary.sh  # confirm bot round-trip
```

Note: `launchctl print` may return empty `pid=` if the job is registered but not currently running. In that case launchd respawns on its own; just wait on the health endpoint.

**For non-gateway launchd jobs (e.g. `ai.hermes.watchdog`) the restart is different.** `launchctl bootout` on a running job fails with `Boot-out failed: 3: No such process`, and `bootstrap` after that fails with `Bootstrap failed: 5: Input/output error`. The safe nudge for an already-registered, currently-not-running job is `launchctl kickstart -kp gui/$(id -u)/<label>` — it re-execs the script on the next interval (or immediately, depending on the job's `StartInterval`). See `references/staging-dirty-surgical-sync.md` for the full recipe.

## Provider Attribution Headers (OpenRouter / Vercel AI Gateway)

If a user reports "why is my OpenRouter dashboard showing my app name and URL on every call?" — this is by design. The auxiliary client (`projects_other/hermes-agent/agent/auxiliary_client.py`) hardcodes attribution headers for OpenRouter and Vercel AI Gateway:

```python
# OpenRouter
_OR_HEADERS_BASE = {
    "HTTP-Referer": "https://hermes-agent.nousresearch.com",
    "X-Title": "Hermes Agent",
    "X-OpenRouter-Categories": "productivity,cli-agent",
}
# Vercel AI Gateway
_AI_GATEWAY_HEADERS = {
    "HTTP-Referer": "https://hermes-agent.nousresearch.com",
    "X-Title": "Hermes Agent",
    "User-Agent": f"HermesAgent/{_HERMES_VERSION}",
}
```

OpenRouter reads `X-Title` for the App column and `HTTP-Referer` for the Referer column. The "Subject" column in OpenRouter's dashboard is the first user-message text of the call — so prompts like "Favicon for google" or "Favicon for https://hermes-agent.nousresearch.com/" appear verbatim. See `references/openrouter-attribution-headers.md` for the full diagnostic recipe (favicon auto-captioning, vision_analyze default model, why Gemini 3 Flash appears in the dashboard).

## Launchd Job Lifecycle

```
Write plist → ~/.hermes/launchd/<name>.plist
       ↓
Test: launchctl load ~/Library/LaunchAgents/<name>.plist
       ↓ (if works)
Commit + push to origin main
       ↓
deploy.sh → syncs to ~/.hermes_prod/
       ↓
Load in prod: launchctl load ~/Library/LaunchAgents/<name>.plist
```

**launchd plist location**: Always `~/Library/LaunchAgents/` for user-level agents. `~/.hermes/launchd/` holds the canonical source; deploy syncs to prod.

### Launchd `EnvironmentVariables` and the login-env wrapper pattern (added 2026-07-09)

launchd launches plists with a **stripped PATH** (`/usr/bin:/bin:/usr/sbin:/sbin`) and **no `.bashrc` sourced**. Any command the daemon needs that lives outside that default — `br` at `~/.cargo/bin/br`, `gh` at `/opt/homebrew/bin/gh`, `sqlite3` if not in the system path, etc. — will silently fail with `FileNotFoundError: [Errno 2] No such file or directory: '<tool>'` and exit 1. The launchd `state = not running, last exit code = 0` then hides the crash behind KeepAlive=true's restart loop: the daemon churns every StartInterval, every tick dies at the same line, and the user sees a stale-looking log.

**Two patterns fix this — pick the one the plist already uses:**

**(A) `EnvironmentVariables` block in the plist** (recommended for new plists). Add a `<key>EnvironmentVariables</key><dict>` block with the keys the daemon needs:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>$HOME/.cargo/bin:$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    <key>HERMES_SLACK_BOT_TOKEN</key>
    <string>[REDACTED_SLACK_TOKEN]</string>
    <key>FACTORY_SLACK_CHANNEL_ID</key>
    <string>C0REPLACEMEWITHCHANNELID</string>
</dict>
```

**(B) `launchd-wrapper.sh` indirection** (existing pattern in dark-factory's `ai.dark-factory.af-tick.plist`). The plist invokes a wrapper script that sources `~/.bashrc` (or `~/.zshrc`) before exec'ing the actual tick script. This is **less secure for secrets** (bashrc typically contains tokens) but gives the daemon the full user PATH including all installed CLIs. The wrapper exists at `daemon/launchd/launchd-wrapper.sh` in dark-factory; copy the pattern, do not bypass it with `EnvironmentVariables` if the repo already standardizes on the wrapper.

**For secrets / channel IDs, ALWAYS use placeholder substitution — never commit real tokens.** Pattern:

1. Plist template (committed to repo) has `@VAR@` placeholders: `<string>@HERMES_SLACK_BOT_TOKEN@</string>`.
2. `install-launchagents.sh` (or equivalent installer) reads the real value from `~/.bashrc` / 1Password CLI / `op read op://Vault/Item/field` and substitutes before `launchctl bootstrap`.
3. CI / pre-commit guard rejects commits that contain `xoxb-` or `C0[A-Z0-9]{10}` literals in `.plist` or `.plist.template` files.

**Diagnostic when the daemon exits 1 every tick** (verified 2026-07-09, dark-factory /af):

```bash
launchctl print gui/$(id -u)/<label> | grep -E "state|last exit"
# state = running, last exit code = 1, runs = 1748  → tick is crashing every cycle

tail -50 ~/Library/Logs/<service>.err.log
# FileNotFoundError: 'br'  → PATH is stripped, env vars not injected
# FileNotFoundError: 'sqlite3'  → same, but for a different tool
# The python traceback will point to the subprocess.run() call that tried
# to shell out to the missing tool.
```

If you see this pattern: open the plist template, add the `EnvironmentVariables` block OR ensure the plist invokes a `launchd-wrapper.sh` that sources `~/.bashrc`. Do NOT just symlink `br` into `/usr/local/bin` — that hides the underlying deployment-environment bug and bites the next daemon that needs a different binary.

**Fail-soft notification pattern** (also added 2026-07-09, dark-factory `libnotify-slack.sh`): daemon scripts that post to Slack should gate every notification on `slack_capable` returning 1 (both `HERMES_SLACK_BOT_TOKEN` and `FACTORY_SLACK_CHANNEL_ID` set). When unset, the helper no-ops silently so the daemon runs in environments without Slack without breaking the tick loop. Pattern:

```bash
if [ "$(slack_capable)" != "1" ]; then return 0; fi
# only reach the curl chat.postMessage call when both vars are present
```

This is the opposite of "crash loud on missing creds" — for *notifications*, silent no-op is correct; for *dispatch*, fail-loud is correct. Pick the right default per call site. Full recipe + the dark-factory `daemon/scripts/libnotify-slack.sh` template at `references/launchd-env-injection-and-wrapper.md`.

## Deploy Script Flags (verified 2026-06-25 via `deploy.sh --help`)

```bash
~/.hermes/scripts/deploy.sh              # full deploy (git pull + Stage 4.5 policy sync + Stage 4.6 skills sync + restart + canary + Stage 5.5b drift WARN)
~/.hermes/scripts/deploy.sh --skip-pull  # skip git pull on ~/.hermes/ (already updated locally)
~/.hermes/scripts/deploy.sh --skip-restart  # skip gateway restart, run canary only
~/.hermes/scripts/deploy.sh --no-sync    # skip BOTH Stage 4.5 (policy file sync) AND Stage 4.6 (skills sync); runs canary + restart only
```

**Stage summary (verified 2026-06-25, post-Stage-4.6):**

| Stage | Purpose | Skippable? |
|-------|---------|------------|
| 2 | `git pull` on `~/.hermes/` | `--skip-pull` |
| 4.5 | Policy-file sync (CLAUDE.md/SOUL.md/TOOLS.md/HEARTBEAT.md) staging → prod | `--no-sync` |
| **4.6** | **Skills sync (skills/ tree, add-only rsync -c) staging → prod (NEW 2026-06-25)** | **`--no-sync`** |
| 4 | Gateway restart | `--skip-restart` |
| 5.5 | Policy-file drift warning (non-blocking) | `--skip-restart` (only) |
| **5.5b** | **Skills drift warning (non-blocking, NEW 2026-06-25)** | **`--skip-restart` (only)** |
| 5.6 | Cron jobs + launchd plist drift warning | `--skip-restart` (only) |
| 5 | Canary (LLM round-trip) | `--skip-restart` (only) |

**The `--system hermes`, `--skip-push`, and `--prod-only` flags referenced in older memory entries DO NOT EXIST** — verified 2026-06-25 when I tried `--system hermes` and got `Unknown argument`. If you see those flags in memory or prior session transcripts, they are stale — use `--help` to verify what's actually supported. The script's actual contract is "git pull + sync policy files + sync skills + restart + canary," NOT a parameter-driven system selector.

## Anti-Patterns

- ❌ Writing directly to `~/.hermes_prod/` as primary action
- ❌ **Writing skills directly to `~/.hermes_prod/skills/<name>/SKILL.md` with `skill_manage(action='patch'|'edit')`** without first writing the same change to `~/.hermes/skills/<name>/SKILL.md` (added 2026-06-23). The `skill_manage` tool writes to whichever path you pass — it does NOT auto-stage. The user catches this every session ("why do you keep forgetting this studd"). The right sequence: (a) write to STAGING first (`~/.hermes/skills/<name>/SKILL.md`), (b) `cp -p ~/.hermes/skills/<name>/SKILL.md ~/.hermes_prod/skills/<name>/SKILL.md` to deploy, (c) `cd ~/.hermes && git add skills/<name>/SKILL.md && git commit && git push origin main` to record in git history. The "I wrote to prod because the running agent reads from prod" justification is **wrong** — the running agent reads from prod, so the manual `cp` step in (b) makes it visible in one extra shell call. Do NOT skip staging "to save time." The skillify cost is the same; the audit trail is the difference.
- ❌ Creating launchd plist in `~/Library/LaunchAgents/` first, then trying to "sync back"
- ❌ Bypassing git commit before deploy
- ❌ Running `deploy.sh` without first verifying staging works
- ❌ Writing agent code to `projects_other/` (the prod fork at `$HOME/projects_other/hermes-agent/`) as the primary development path — this puts work in the deploy target instead of staging. **The correct path is `~/projects/hermes-agent/`** (the git-tracked staging checkout). `projects_other` is a mirror/fork for AO workers, not a write target.

- ⚠️ **Known orphan: `ai.hermes-staging` plist.** This launchd job (`~/Library/LaunchAgents/ai.hermes-staging.plist`) is NOT managed by `install-launchagents.sh` and has a different label than the repo template (`ai.smartclaw.hermes-staging`). Jeffrey wants it disabled. If you find it running, stop it with `launchctl bootout gui/$(id -u)/ai.hermes-staging` + `launchctl disable gui/$(id -u)/ai.hermes-staging`. Do NOT just rename to `.plist.disabled` — it gets re-created by setup/reconfigure.
- ⚠️ **In single-dir mode, `~/.hermes` IS `~/.hermes_prod` — manual `cp` is a no-op (verified 2026-07-20).** When `scripts/deploy.sh` prints `[single-dir] Canonical repo and runtime are both $HOME/.hermes; no policy copy needed.` (and the same for skills), it means the two paths resolve to the same directory on this machine — writing a file to `~/.hermes/skills/<name>/SKILL.md` IS already writing to prod. `cp -p ~/.hermes/... ~/.hermes_prod/...` will print "files are identical (not copied)". Verified against `wiki-campaign-daily-ingest.sh` + `download_campaign.py` + `SKILL.md` rollout on 2026-07-20: all three files byte-identical between staging and prod after a single `git push origin main` — no second `cp` step needed. The SOP "write to staging then `cp -p` to prod" still applies when staging and prod are SEPARATE paths, but the verification step (`diff -q`) is the way to tell which mode you're in. Don't waste a tool call doing `cp` in single-dir mode.
- ⚠️ **Hermes Agent core-file editing (run_agent.py, model_tools.py, etc.):** The canonical staging path for Hermes Agent edits is `~/projects/hermes-agent/run_agent.py`. The prod path `~/.hermes_prod/` receives updates via the deploy pipeline only. All `run_agent.py` patching must be done in staging first.
- ⚠️ **SOUL.md `## COMMIT:` for source-channel scoping (channel → repo) is now a documented class (added 2026-06-26).** The `slack-channel-routing-policy` COMMIT (line 385) governs **destination** routing (where system-generated traffic goes). The new class is **source** scoping: a SOUL.md `## COMMIT:` that says "when a session is bound to Slack channel `C…`, treat all messages from that channel as scoped to repo `OWNER/REPO` and auto-load the matching skill set." Verified instances:
  - `slack-channel-agentf-maps-to-local-agentf` (line 343) — `C…` (agentf channel) → `agentf` skill / `jleechanorg/agent-orchestrator-ts` family
  - `slack-channel-c0bdeajh8pk-is-worldarchitect-repo` (line 489) — `C0BDEAJH8PK` (`#worldai-bugs` in workspace `T09FXQ4LCQP`) → `worldarchitect` skill / `$GITHUB_REPOSITORY`
  Recipe for new instances: copy the second COMMIT, swap (a) the channel ID + workspace, (b) the repo, (c) the auto-loaded skill name, (d) the date. Trigger must list the channel ID AND the `#name` AND common short-aliases ("worldai", "this channel", "the worldai channel") so future sessions match regardless of how the user phrases it. **Do NOT scope a channel to a repo the user did not name in the same message** — the rule fires on every message in the channel, so a misnamed repo propagates to all future sessions. Always confirm the repo with the user before adding the COMMIT. Companion pattern for *destination* routing: `slack-channel-routing-policy`; for *agent per channel* (different model/tools per channel): populate `slack.channel_prompts.<channel_id>` in `config.yaml` with a per-channel `system_prompt`.

- ⚠️ **The right `deploy.sh` flag combo for a SOUL.md-only change is `--skip-pull --skip-restart` (added 2026-06-26).** The SOUL.md file-routing table row says "Do NOT auto-run `scripts/deploy.sh`" because the user typically wants a review window — but when the user IS asking you to deploy (e.g., "save this in soul md and apply it now"), the right flag combo is:
  ```bash
  ~/.hermes/scripts/deploy.sh --skip-pull --skip-restart
  ```
  This runs Stage 4.5 (policy-file sync: CLAUDE.md + SOUL.md + TOOLS.md + HEARTBEAT.md) + Stage 4.6 (skills sync) + Stage 5 (canary) + Stage 5.5/5.5b/5.6 (drift warnings). It skips the `git pull` (the change is already local) and the gateway restart (a restart is not required for SOUL.md to take effect on the next session-start, and the running gateway has the old rules loaded). **Verify the sync landed:** `diff -q ~/.hermes/workspace/SOUL.md ~/.hermes_prod/SOUL.md` must return 0; `grep -c '^## COMMIT:'` must be the same in both files. **Banned combos (verified 2026-06-26):** `--system hermes` (unknown argument — `deploy.sh --help` shows the actual flag set); `--skip-push` (also does not exist); `--prod-only` (also does not exist). The only real flags are `--skip-pull`, `--skip-restart`, and `--no-sync`. Always `deploy.sh --help` first if you're uncertain.

- ⚠️ **Script-default `*_DIR` can silently disagree with the plist-installed override.** When a launchd-managed script defines a default path (e.g. `BUG_REPORTS_DIR=/tmp/openclaw/bug_reports` at the top of `scripts/bug-hunt-daily.sh`) AND is launched by a plist that either (a) injects an override via `EnvironmentVariables` or (b) is a sibling plist with its own override, the two paths can silently disagree if either side is updated without the other. Observed 2026-07-15 in `~/.hermes_prod/launchd/ai.hermes.schedule.bug-hunt-9am.plist` + `~/.openclaw/launchd/ai.openclaw.schedule.bug-hunt-9am.plist`: BOTH labels enabled, BOTH firing Mon-Fri 09:00, EACH writing to its own `BUG_REPORTS_DIR` (`/tmp/hermes/bug_reports/` vs `/tmp/openclaw/bug_reports/`). User looked at the script's defined dir, found nothing, concluded the script never ran — when in fact the run completed and the report landed in the OTHER tree.

  **Three-step diagnostic** — when a launchd-managed script's output dir looks empty:
  1. `launchctl print gui/$(id -u) | grep -iE '<script-keyword>'` — confirm how many enabled labels match (1 vs 2 is the tell)
  2. `grep -nE 'DIR=|REPORTS_DIR=|LOG_FILE=' scripts/<name>.sh | head -10` — find the script's default path
  3. `find / -name '<expected-output-pattern>' -mtime -2 2>/dev/null` — locate where the output ACTUALLY landed

  **Fix layers**:
  1. Pick ONE canonical `*_DIR` per script and align all plists to it. The canonical choice is whichever path is referenced in the script's own default — that is what `set -u` + `set -o pipefail` users will see in their scripts.
  2. Disable the duplicate plist (`launchctl disable gui/$(id -u)/<sibling-label>` + `launchctl bootout gui/$(id -u)/<sibling-label>`) so the script runs exactly once per trigger.
  3. If the script must run multiple times (e.g. once from hermes + once from openclaw for cross-stack validation), make the report filename include the source label so the two reports don't collide.

  **Verified bug-ref** — 2026-07-15, `bug-hunt-daily.sh` run at 09:00 PT. User flagged "0 bugs is odd" → agent probed `tail -120 ~/.hermes/logs/bug-hunt-daily.log` → found `[WARN] hermes agent unavailable` triple → inspected per-agent `bug-hunt-*.err` files in the wrong dir → pivoted to `find /tmp -name '*20260715*'` → discovered actual reports at `/tmp/hermes/bug_reports/`. Total diagnostic time: ~6 tool calls before the path-drift root cause was found. See `devops/slack-thread-routing-investigation/references/2026-07-15-fabrication-class.md` §"Shape C" for the full transcript.

- ⚠️ **Plist templates that exist but aren't wired into `install-hermes-scheduled-jobs.sh` are silent orphans (added 2026-07-20).** `launchd/` holds 46+ `.plist.template` files, but `~/.hermes/scripts/install-hermes-scheduled-jobs.sh` is an enumeration (`grep -E 'thread-followup|slack-thread-roadmap-report'` etc.), not a directory walk. If you author a new `scripts/<name>.sh` + `launchd/<name>.plist.template` pair but DON'T add the template to the install script's enumeration list, the plist is silently orphaned — no `launchctl load` ever fires, no `launchctl list` row exists, and the cron LOOKS fine on disk (`bash -n` clean) but never runs. Verified bug-ref 2026-07-20, thread `C0AH3RY3DK6/p1784548844.491489`: `thread-reply-nudge.sh` + `thread-reply-nudge.plist.template` both intact, but the install script's enum block did not include them; the orphan let the 2026-07-20 Daily Dice Audit FAIL sit unanswered for 9h. Diagnostic 3-step (works for any "this cron looks fine but never fires"):
    1. `launchctl list | grep <label>` — empty? orphan.
    2. `grep -nE '<name>|<label>' ~/.hermes/scripts/install-hermes-scheduled-jobs.sh` — empty? install script doesn't know about the template.
    3. `DRY_RUN=1 bash ~/.hermes/scripts/<name>.sh` — clean dry-run output? the script itself is fine; the bug is upstream.
    Fix BOTH in the same turn: (a) add the template to `install-hermes-scheduled-jobs.sh`'s enum, (b) `launchctl load -w ~/Library/LaunchAgents/<name>.plist` to bring it live now. The next deploy/worktree-refresh will silently drop the plist again if only (b) was done. See `dropped-messages` skill → "orphaned plist" section for the full playbook + bead `rev-fvv22`.

- ⚠️ **`scripts/` and `launchd/` trees are NOT in `POLICY_FILES` (added 2026-07-20, escalation of the Stage 4.5/4.6 gap).** Per the "Still open" line in the `references/policy-files-skill-sync-gap.md` block below, **`scripts/`, `launchd/`, `cron/jobs.json`, and `.claude/commands/` are still NOT auto-synced by `deploy.sh`.** That means two failure modes that are easy to confuse but require DIFFERENT fixes:
    - (A) "Skill works locally after `skill_manage` write but prod still has stale copy" → Stage 4.6 will fix on next `deploy.sh` run. Tracked in skill-sync-gap reference.
    - (B) "Plist template + script committed, plist NOT loaded in prod" → orphan class above, requires `install-hermes-scheduled-jobs.sh` patch + manual `launchctl load`. **Stage 4.6 / deploy.sh does NOT fix this** because there is no prod-side plist to sync TO; the plist was never generated.

    Whenever a new `.sh` + `.plist.template` pair ships, ALSO amend `install-hermes-scheduled-jobs.sh`'s enumeration in the same PR, OR explicitly document that the plist will be loaded out-of-band. `scripts/deploy.sh` Stage 4.5 only synced the 4 files in `POLICY_FILES=(CLAUDE.md SOUL.md TOOLS.md HEARTBEAT.md)`. **`~/.hermes/skills/` and `~/.hermes/skills/RESOLVER.md` were not on the list.** Prior to 2026-06-25, every skillify pass had to either (a) add `skills/` (or `skills/RESOLVER.md`) to `POLICY_FILES`, (b) rsync the skill directory in a custom Stage 4.5 step, or (c) document a manual `cp` step in the closure summary. Same drift class as the `config.yaml` non-sync rule below, but the canonical-file list was shorter so the gap bit more often. **Fixed on 2026-06-25** by adding **Stage 4.6 (Skills Sync)** and **Stage 5.5b (Skills Drift Warning)** to `deploy.sh`. Stage 4.6 uses `rsync -a -c` with add-only semantics (NO `--delete` — prod has 166 hub-installed skills not in the staging git repo) and excludes runtime-only artifacts (`__pycache__/`, `.usage.json`, `.curator_backups/`). Companion upstream fix in [jleechanorg/hermes-agent PR #34](https://github.com/jleechanorg/hermes-agent/pull/34) pinned `SKILLS_DIR` to `~/.hermes/skills/` so prod-profile `skill_manage` writes also go to git first. See `references/policy-files-skill-sync-gap.md` for the full decision matrix + closed status + 354-vs-188 prod-vs-staging skill count audit. **Still open:** the same shape (add a Stage 4.7/4.8 or widen POLICY_FILES) for `scripts/`, `launchd/`, `cron/jobs.json`, and `.claude/commands/`. Skillify rollouts that touch those directories still need manual `cp` in the same turn.

- ⚠️ **`.claude/commands/` is also NOT in `POLICY_FILES`.** Same class as the
  RESOLVER.md gap above: a new slash command at `~/.hermes/.claude/commands/<name>.md`
  does NOT get synced to `~/.hermes_prod/.claude/commands/` by `deploy.sh`.
  The slash-command discovery path in SOUL.md resolves to whichever tree the
  gateway actually loads from at runtime (prod). So if you only add the file
  to staging, `/<name>` will not be invocable until you also `cp -p
  ~/.hermes/.claude/commands/<name>.md ~/.hermes_prod/.claude/commands/`.
  Verified 2026-06-20: `/finish` + `/auto` slash command rollout (PR
  `3f5adb80f5`) — staging had the files after the push to origin/main, but
  the prod `.claude/commands/` dir only got them via explicit `cp -p` BEFORE
  the deploy. Without that step, the gateway would have served 404 on
  `/finish` and `/auto` until the next prod restart cycle.

- ⚠️ **`workspace/` is in `.gitignore` but `workspace/SOUL.md` IS tracked on
  origin/main** (with `!workspace/README.md` exception for the dir). The
  working-tree diff for the tracked SOUL.md will be silently invisible to
  `git status` / `git add` unless you use `git add -f workspace/SOUL.md`.
  This bites when editing the runtime SOUL.md in the staging checkout:
  - Symptom: `git status` does not show `workspace/SOUL.md` as modified even
    after editing it; `git add workspace/SOUL.md` errors with "ignored by
    one of your .gitignore files" but the file IS in `git ls-files`.
  - Fix: `git add -f workspace/SOUL.md` (force-add overrides gitignore for
    tracked files). Confirmed at commit `3f5adb80f5` (jleechanclaw, 2026-06-20).

- ⚠️ **`jleechanclaw` self-merge flow uses feature-branch push to `main`**
  (different from your-project.com's AO worker PR flow). On jleechanclaw,
  Jeffrey merges by pushing a fresh `feat/<name>` branch to `main` directly
  (not by opening a PR for human review). Branch protection on `main`:
  - Force-push is REJECTED with `GH013: Cannot force-push to this branch`.
    Implication: `git commit --amend` AFTER the initial push to `main`
    cannot be force-pushed; you must either (a) squash into the original
    commit before pushing, (b) drop the amend and live with the original
    commit, or (c) accept that the additional change will land on a
    follow-up branch. Verified 2026-06-20: the RESOLVER.md amendment
    (`c90d4bbd9d`) had to be reverted to keep staging in sync with
    `origin/main`'s `3f5adb80f5`.
  - Non-fast-forward pushes are rejected — you must rebase or use
    worktree-from-`origin/main` per `.cursor/rules/pr-branch-from-main.mdc`
    rule #4. The auto-commit-pending branch was 2 commits behind with
    regen-only changes (`docs/context/SYSTEM_SNAPSHOT.md` + `gateway_state.json`
    timestamps) that conflict non-trivially. **The right move was NOT to
    rebase; it was `git worktree add ~/.worktrees/<feat> -b feat/<name>
    origin/main`**, then apply changes on the fresh branch tip.

## ⚠️ Skills Discovery — `skill_manage` writes to whichever path you pass (added 2026-06-23)

When updating an existing skill via `skill_manage(action='patch'|'edit')`, the tool writes to the **absolute path you pass** in the tool call — it does NOT auto-stage to `~/.hermes/skills/` first. If you pass `~/.hermes_prod/skills/<name>/SKILL.md`, the change lands in prod directly, bypassing staging. The user catches this every session because the running gateway loads from prod (so the change IS visible) but the git history in `~/.hermes` is missing it (so a future deploy drift-audit will flag the gap).

**Right sequence for any skill update:**

1. Read the skill via `skill_view(name='<name>')` — returns the prod-loaded version (what the running gateway sees).
2. Edit `~/.hermes/skills/<name>/SKILL.md` (STAGING) — use `skill_manage` with the staging path, OR `terminal` to write directly.
3. `cp -p ~/.hermes/skills/<name>/SKILL.md ~/.hermes_prod/skills/<name>/SKILL.md` — make the change live in prod (1 shell call).
4. `cd ~/.hermes && git add skills/<name>/SKILL.md && git commit -m "[Auto] <brief description>" && git push origin main` — record in git history.

If you accidentally wrote to `~/.hermes_prod/skills/<name>/SKILL.md` first: `cp -p ~/.hermes_prod/skills/<name>/SKILL.md ~/.hermes/skills/<name>/SKILL.md` to back-fill staging, then continue from step 4. The cost is the same; the audit trail is preserved.

**Why this isn't already enforced:** the `skill_manage` tool is a generic file-write primitive — it doesn't know which tree is staging vs prod, and it doesn't know the user's deploy-pipeline preferences. The skill author must remember to pass the staging path. This anti-pattern is the most common cause of "why do you keep forgetting this studd" frustration.

## ⚠️ Slash command AND RESOLVER.md AND SOUL.md `## COMMIT:` are three
  separate wiring points** for a new trigger phrase or slash command. Missing
  any one breaks the auto-fire path:
  1. **`.claude/commands/<name>.md`** — for explicit `/name <arg>` invocations
     (resolved by SOUL.md "Slash Command Discovery" rule order:
     `.claude/commands/<name>.md` → `~/.claude/commands/<name>.md` →
     `~/.claude/skills/<name>/SKILL.md`).
  2. **`~/.hermes_prod/skills/RESOLVER.md`** — for natural-language phrase
     matching. The resolver is loaded by the gateway at startup; the prod
     copy is the runtime source of truth (staging has its own RESOLVER.md
     via `git ls-files`, but they drift if not synced).
  3. **`~/.hermes_prod/SOUL.md` `## COMMIT: <name>`** Trigger line — for
     trigger phrases that should fire the skill automatically based on
     session-init scan. RESOLVER.md alone is not enough; the SOUL.md
     COMMIT is what guarantees the skill loads on every session, not just
     when a user types the exact phrase.
  Verified 2026-06-20: adding "finish the job" to the finish-the-job skill
  initially only wired RESOLVER.md (and the slash command file), so the
  literal phrase did NOT auto-fire on session-init. Adding it to the SOUL.md
  `## COMMIT: finish-the-job` Trigger line closed the gap.

- ⚠️ **Hermes self-mods in a heavily-dirty live checkout: use a fresh `origin/main` worktree (added 2026-07-22).** When `~/.hermes/` is the live production checkout (no `~/.hermes_prod` separation) AND it carries dozens of unrelated uncommitted/staged files from prior sessions, do NOT work directly in it. Every `git checkout -B <branch>` from the dirty HEAD carries that noise onto the PR head, which is precisely the pollution class the SOUL.md `pr-clean-branch-from-main-no-history-bloat` and `never-push-onto-someone-elses-pr-head` commits guard against. The right move is identical to the staging-dirty recipe: `git worktree add ~/.worktrees/<repo>/<purpose> -b <new-branch> origin/main`, commit + push + open PR from there, leave the live checkout untouched. Verified 2026-07-22, PR [#790](https://github.com/jleechanorg/jleechanclaw/pull/790) on `scripts/cron-backup-sync.sh`: live checkout had 80+ unrelated dirty files; used `git worktree add ~/.worktrees/jleechanclaw/cron-backup-no-routine-slack -b fix/cron-backup-no-routine-slack origin/main` to keep the PR at 2 files / 19+ / 21-. The `references/staging-dirty-surgical-sync.md` recipe is for single-file fixes already on `origin/main`; this pattern is for **new commits on a fresh branch** when the live checkout is dirty. Cross-reference the AO spawn retry failure mode (`Internal server error INTERNAL_ERROR` from a healthy daemon, 2026-07-22 same session) — instead of retrying the spawn, pivot to the inline worktree + push + open PR pathway.

- ⚠️ **Wrapper skill over a bundled binary: edit the bundled skill, NOT the wrapper, when the source-of-truth is upstream (added 2026-07-24).** When you have a wrapper skill (e.g. `claude-code-claudem` re-exports bundled `claude-code`) and the bundled skill gets an upstream update (a new flag, a new mode, a new gotcha), the durable move is to (a) re-read the bundled skill via `skill_view` (or the symlinked `~/.hermes/skills/autonomous-ai-agents/<name>/SKILL.md` if skill_view is wedged), (b) port the new content into the wrapper's "What the bundled skill now says" section, (c) leave a pointer in the wrapper noting the upstream version it was last reconciled against. Do NOT silently diverge from upstream — the wrapper's value is "I track the canonical skill + I swap the binary"; if it stops tracking, it becomes a stale fork. Verified 2026-07-24: `claude-code-claudem` v1.0.0 notes it re-exports `claude-code` v2.2.0; when `claude-code` ships v2.3.0, the wrapper needs a sync commit in the same PR cycle.

- ⚠️ **Verify every CLI flag in a launchd-driven script actually exists in the installed CLI — before shipping (added 2026-07-21, cron-backup-sync.sh `--json` regression).** When a `~/.hermes/scripts/*.sh` calls a CLI with a flag the author assumed existed (e.g. `hermes cron list --json`), and the flag does NOT exist, argparse rejects it, the script's `$(...) || true` fallback silently swallows the failure, the parser computes an empty result, and any shell variables interpolated into Slack/email/log messages fall back to literal `?` placeholders. The launchd job still appears healthy (exit 0, log file generated, message delivered) — so the bug can persist for weeks without anyone noticing. **Verified case (2026-07-15 → 2026-07-21)**: every Mon-Fri 08:25 PT post to `#ai-general` said `Cron Backup: no changes. Total: ? jobs (? enabled).` for 6 days before the user spotted it scrolling back through chat. **Fix layers**:
  1. **Before deploy**: run `hermes <subcmd> --help` and confirm every distinct `(subcommand, flag)` pair the script uses appears in the help text. If a flag is missing, the script is broken — drop the flag, parse the default output, or pin the CLI version. Never assume a flag exists from convention (`--json`, `--quiet`, `--no-color` are NOT universal).
  2. **Defensive fallback discipline**: shell variables that land in user-facing messages MUST be real numbers/strings. `TOTAL=$(... || echo "?")` is the anti-pattern — the `?` SILENTLY survives into production. The right pattern is `TOTAL=$(... 2>/dev/null) || { log "ERROR"; exit 1; }` (fail loud) or `TOTAL=${TOTAL:-0}` (explicit empty default), never a sentinel string.
  3. **Ship a regression test** in `tests/test_<script>.py` with three layers: (a) CLI flag assertion (process returns 0 when flag present, non-zero + "unrecognized" when absent), (b) parser row count cross-checks against the CLI's authoritative count (e.g. `hermes cron status` "12 active"), (c) grep the script source for literal `?` placeholders in templates. Reference test at `tests/test_cron_backup_sync.py` (commit [996be8cf81](https://github.com/jleechanorg/jleechanclaw/commit/996be8cf81)).
  4. **Smoke-test in launchd conditions** before adding the script to a plist: `env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/bash ~/.hermes/scripts/<name>.sh` (no `.bashrc`, stripped PATH — exactly what launchd gives the daemon).

  Full recipe + 4 pre-deploy checks + test-shell template at `references/cli-flag-verification-pre-deploy.md`. Companion to `references/launchd-env-injection-and-wrapper.md` (PATH-stripping failure mode) and `references/staging-dirty-surgical-sync.md` (deployed-stale failure mode). The three references cover the three distinct launchd-script failure modes: this one = "script is wrong as written", the env-wrapper = "script needs CLIs launchd can't find", surgical-sync = "fixed on origin/main but deployed file is stale".

- ⚠️ **Watcher/parser scripts in `~/.hermes_prod/scripts/` are silent-failure drift magnets.** A script like `wa_daily_test_watcher.sh` parses the body of an email generated by another script (e.g., `testing_mcp/infra/send_report_email.py`). When the *sender* changes its template (e.g., `=== Scenarios: 6/8 passed` → `=== Results: 6/8 passed`), the watcher's regex stops matching, the post falls through to a hardcoded fallback like `"(could not parse failed scenario list from email body)"`, and the Slack alert loses all signal. **The only visible symptom is "the alert is vague," not "the deploy broke"** — so this class of drift can persist for days without anyone noticing the underlying template change. **Whenever you touch a sender's template, audit the receiver's regex in both `~/.hermes/scripts/` AND `~/.hermes_prod/scripts/`.** Conversely, whenever a Slack alert shows a generic `"(could not parse...)"` / `"(no data found)"` / `"(unknown status)"` fallback, suspect staging/prod watcher-drift before assuming the upstream system broke. See `worldarchitect` skill → `references/daily-cron-test-investigation.md` §9 for the worked example (2026-06-18, `wa_daily_test_watcher.sh`).

- ⚠️ **Missing `lib/<helper>.sh` causes `slack_post` and other sourced helpers to silently no-op.** When a script `source`s a lib file (e.g. `slack_thread_lib.sh` for `slack_post`, or `token-probes.sh` for token checks) and the lib file is missing from the deployed `lib/` dir, the `source` fails with "No such file or directory" and the helper is undefined. The script's `|| log "..."` fallback logs a non-zero return but the alert never reaches the user. The user sees "no alert" instead of "alert failed." **Symptom to grep for in launchd job logs:** `lib/<helper>.sh: No such file or directory` on a `source` line. The fix is the surgical-sync in `references/staging-dirty-surgical-sync.md` — copy the missing lib files from the worktree to BOTH `~/.hermes/lib/` AND `~/.hermes_prod/lib/`. Verified 2026-06-20: `ai.hermes-watchdog` was firing "prod gateway DOWN" alerts via `slack_post` but the post never reached Slack because `~/.hermes/lib/slack_thread_lib.sh` was missing. The alert channel was the only signal that the watchdog was running; once `slack_post` broke, the watchdog was effectively invisible.

- ⚠️ **Verify the API key is live BEFORE flipping `model.default` / `model.provider` in `config.yaml`.** The `model.*` block in `config.yaml` controls the inference provider the gateway uses for ALL outbound LLM calls. A flip to `anthropic/claude-opus-4-7` (or any new provider) without a working API key in `~/.bashrc` or the provider's env var will brick the gateway the next time it processes a request — no key = 401/auth-failed, every channel/agent dies, the user has to revert manually.

  **Pre-flight (do this BEFORE writing `config.yaml`):**

  ```bash
  # 1. Confirm the key exists AND is uncommented
  grep -E "^export (ANTHROPIC_API_KEY|<PROVIDER>_API_KEY)=" ~/.bashrc
  # If line is commented (# export ...) — STOP. Do not flip model.

  # 2. Confirm the key is the right format (Anthropic = [REDACTED_OPENAI_KEY])
  echo "${ANTHROPIC_API_KEY:0:7}"  # expect: sk-ant-
  ```

  **Bug-ref:** 2026-06-20 — user asked "switch the model to opus." I edited `~/.hermes/config.yaml` to set `model.default: claude-opus-4-7` + `model.provider: anthropic` and made a backup (`config.yaml.bak.preopus`). On the *next* step of the pre-flight (checking the key), I found `ANTHROPIC_API_KEY` was commented out in `~/.bashrc` with a comment: `# Commented out to use Claude Code subscription instead of API credits`. Direct Anthropic API would have burned credits the user explicitly avoided. I reverted immediately via `cp config.yaml.bak.preopus config.yaml` and surfaced the question to the user instead of letting the change go to `deploy.sh`. The user actually meant "use the `claude-code` provider (subscription, no cost)" — a different model path that would have silently failed too.

  **Lesson:** the AGENTS.md "no config changes without approval" rule applies here too. When the user says "switch the model to X" without naming a provider, treat the request as having two halves: (1) the model name, (2) the provider route. Both must be confirmed live before any `config.yaml` write. If only the model is named, ask which provider path — don't guess. The user *intentionally* chose Claude Code subscription routing (the comment in `~/.bashrc` makes that explicit), and silently moving to direct API would have violated an explicit user preference.

  **Always run the pre-flight and make a backup BEFORE any `config.yaml` model change, even when the user gives explicit approval.** The pre-flight is cheap (2 grep + 1 echo); the rollback is cheap (one `cp`); the failure mode of "skip pre-flight, brick the gateway" is expensive (full gateway restart + manual recovery).

## Proof Before Claim

When asked "is it working?", the answer must include raw terminal output showing:
- `launchctl list | grep <name>` — job is loaded (exit 0, not error)
- Manual test run of the script — clean output
- `git log --oneline -1` — committed to git

Not:
- "It should work"
- "The commands were run"
- Summary descriptions of expected behavior

## Skills Discovery

Before writing any new file, check if a relevant skill exists in `~/.hermes_prod/skills/`:
- `launchd-job-authoring` — for creating launchd plists
- `skillify` — for making new workflows permanent
- `hermes-agent` — for configuring Hermes itself

If none exist, build the file, then offer to skillify the pattern.

## Commit Message Convention

For deploy pipeline commits:
```
[Auto] <brief description>

- <file 1>: what changed
- <file 2>: what changed
```

Example:
```
[Auto] Add auto-push launchd jobs for llm-wiki and user-scope

- scripts/auto-push-to-main.sh: reusable push-to-main script with codex --yolo fallback
- launchd: plists for llm-wiki and user-scope, 30-min interval
```

## Support Files

- `references/circuit-breaker.md` — live diagnostic commands, state transitions, and config for the circuit breaker failover system.
- `swap-hermes-provider` (skill) — when the user asks to add / remove / replace a model provider in Hermes' config. Covers all six touch-points in `~/.hermes/config.yaml` + `~/.hermes/scripts/launchd-env-wrapper.sh` + the prod mirror, plus the `hermes config set` vs Python-edit workaround for the `patch`-tool security guard on `config.yaml`. Worked example at `references/rm-opencode-go-glm51.md`. The old `references/opencode-go-glm51.md` file here was the same provider's reference, removed 2026-07-16 when the `opencode-go/glm-5.1` provider was deleted from the live config.
- `references/exportcommands-runbook.md` — `/exportcommands` workflow: export `~/.claude/` dirs to `jleechanorg/claude-commands`. Covers prerequisites, timeout (≥300s), content filters, union merge logic, and pitfalls (must run from git repo root).
- `references/openrouter-attribution-headers.md` — why every auxiliary call shows up in the OpenRouter dashboard as "App: Hermes Agent", why "Favicon for X" prompts appear, and the vision_analyze auto-captioning flow. Diagnostic recipe for any future "why is Hermes using X via OpenRouter" question.
- [`references/actual-deploy-state-2026-06-09.md`](references/actual-deploy-state-2026-06-09.md) — read this before assuming `scripts/deploy.sh` exists. Documents the actual manual-cp sync procedure (the umbrella SKILL.md references a deploy.sh that doesn't exist), the staging/prod drift observed, and the cmux-send-submit rollout as a worked example. **Critical if you hit "I changed the skill but the running agent doesn't see it"** — 90% chance it's staging/prod drift, not the change being wrong.
- [`references/actual-deploy-state-2026-06-23.md`](references/actual-deploy-state-2026-06-23.md) — **read this FIRST** before the 2026-06-09 baseline. Updates the deploy state as of the #682 bring-to-green: `deploy.sh` now EXISTS at `~/.hermes/scripts/deploy.sh` AND `~/.hermes_prod/scripts/deploy.sh` (verified). SOUL.md runtime path is `~/.hermes_prod/workspace/SOUL.md` (NOT `~/.openclaw/SOUL.md` as the 2026-06-09 doc said). The deploy-pipeline POLICY_FILES gap is unchanged: `deploy.sh` Stage 4.5 only syncs 4 files (CLAUDE.md, SOUL.md, TOOLS.md, HEARTBEAT.md); skills/scripts/launchd/ROADMAP all require manual `cp` or a custom Stage 4.5 step. Includes a staging/prod SOUL.md drift incident from 2026-06-23 (the `never-hallucinate-no-new-content` COMMIT block was in staging but not prod) and a 3-question staging/prod sanity check to run before claiming "deployed."
- `references/actual-deploy-state-2026-06-09.md` — **read this before assuming `scripts/deploy.sh` exists**. It documents the actual manual-cp sync procedure as of 2026-06-09 (the umbrella SKILL.md references a deploy.sh that doesn't exist), the staging/prod drift observed, and the worked example of the cmux-send-submit rollout. **Critical if you hit "I changed the skill but the running agent doesn't see it"** — 90% chance it's staging/prod drift, not the change being wrong.
- `references/deploy-script-port-drift-pitfall.md` — **the "Gateway did not come up on port 8643 within 30s" message is a known false negative** when `scripts/deploy.sh` hard-codes `PROD_PORT=8643` but `~/.hermes_prod/config.yaml` actually says `port: 8642`. Includes the 3-step "is the gateway actually up?" recipe (`grep config.yaml` → `lsof` → `curl`) and the `launchctl print` pid-extraction pitfall that can leave the old gateway un-killed. Read this whenever a deploy reports failure at the port-canary stage.
- `references/find-actually-running-source.md` — **read this BEFORE answering "is the fix live?" or "deploy it"**. Documents the 3-place Hermes source layout (`~/.hermes/` staging, `~/.hermes_prod/` runtime state, `~/projects_other/hermes-agent/` pip-installed editable — the one that actually serves requests). Includes a 5-step copy-pasteable probe (`which hermes` → `ps aux` → `pip3 show` → `pip3 show -f` → `cd ... && git log`) and a `git diff` recipe to confirm a squashed fix is content-equivalent to its upstream PR merge. Closes the 2026-06-13 gap where the umbrella's "write to `~/.hermes/`" rule silently mis-targeted Hermes Agent core code.
- `references/policy-files-skill-sync-gap.md` — **read this before any skillify pass that creates files outside `POLICY_FILES=(CLAUDE.md SOUL.md TOOLS.md HEARTBEAT.md)`**. Documents the `skills/` + `scripts/` + `launchd/` + `skills/RESOLVER.md` non-sync gap in `deploy.sh` Stage 4.5, the manual `cp` workaround, and the rsync-vs-widen-POLICY_FILES decision matrix. Worked example: finish-the-job skillify (2026-06-19) — Stage 4.5 fired, matched all 4 files, no skill sync; manual cp after canary flake. Cross-linked from `skillify` → "Anti-Pattern: Deploy.sh POLICY_FILES Gap".
- `references/jleechanclaw-slash-command-rollout.md` — **read this before adding a slash command or trigger phrase to jleechanclaw**. End-to-end recipe for the three wiring points (`.claude/commands/` + RESOLVER.md + SOUL.md `## COMMIT:`), the jleechanclaw self-merge flow (feat-branch push to main, no human-review PR), the `auto/commit-pending` rebase trap, the 10-item pre-deploy audit, the post-push local-drift sequence, and the canary false-negatives. Verified 2026-06-20 against PR `3f5adb80f5` (`/finish` + `/auto` + "finish the job" trigger).
- `references/staging-dirty-surgical-sync.md` — **read this when the fix is already on `origin/main` but the deployed file is stale, AND `~/.hermes/` staging is on a dirty non-main branch so `deploy.sh` will die**. Covers the 4-step diagnostic (origin/main has it? deployed file has it? live process shows it?) and the surgical-sync recipe (worktree from `origin/main` → `cp` to staging + prod → `launchctl kickstart` to force re-exec). Includes the "no new PR when the fix is already on main" judgment rule, the `kickstart -kp` vs `bootout`+`bootstrap` gotcha, the "missing `lib/` file → silent `slack_post` failure" diagnostic, and the 2026-06-20 worked example (PR #619 already-merged fix deployed to fix the watchdog false-DOWN alert loop).
- `references/staging-dirty-quarantine-stash.md` — **read this when the source-of-truth clone has UNRELATED dirty files (from prior sessions) AND you need to open a NEW clean single-file PR.** Sister recipe to `staging-dirty-surgical-sync.md`: covers the 3-step quarantine (`git stash push -u -m "STASH pre-<purpose>"` → clean worktree from `origin/main` → recover stash later via Option A/B/C). Includes the 2026-07-21 worked example (27 unrelated dirty files stashed so SOUL.md compression PR #789 landed as 1 file / +89 / −83).
- `references/soul-compression-contract.md` — **read this when the user asks to compress / trim / reduce `~/.hermes/workspace/SOUL.md`** (e.g. "compress the soul MD maybe 30%", "it's too long"). Recurring class with prior history (commit `6e2470345c` trim to fit 48,660-char limit, PR #789 105KB → 73KB). Covers the 4 invariants (commit count / trigger count / action count must be unchanged pre/post), the "rewrite the 10–15 longest blocks" strategy, the `tests/test_soul_compression.py` contract test, and the 3-place write (worktree + live staging + live prod).
- `references/two-config-files-prod-vs-staging.md` — **read this before any "change the iteration budget" / "bump max_turns" task.** Documents the actual knob (`agent.max_turns` line 20), the three confusable knobs (`max_iterations` for delegation, `goals.max_turns` for goal mode), the byte-identical mirror relationship between staging and prod configs (Hermes v0.13.0+ — `config.staging.yaml` no longer exists), the running binary path (`/opt/homebrew/bin/hermes` v0.13.0 at `$HOME/projects_other/hermes-agent/`), the AGENTS.md-vs-doctor.sh enforcement boundary, and the 5-step root-cause checklist for "my edit didn't stick."
- [`references/staging-dirty-new-skill-mirror.md`](references/staging-dirty-new-skill-mirror.md) — **read this when you just committed + pushed a new skill to `origin/main` but `deploy.sh` Stage 2 aborts on UNRELATED dirty files in `~/.hermes/`**. The sibling recipe to `staging-dirty-surgical-sync.md` for the **new-skill-directory** case (not a single-file fix). Covers the 5-step manual mirror (rsync skill + surgical RESOLVER.md section append + Stage 5 health check without a full deploy), the 7-line closure summary you owe the user, the "when NOT to use this recipe" list, and the 2026-06-23 worked example (test-tui-claude-feature-via-cmux pushed while the user's pre-deploy snapshot for the Tuesday 3pm PT window was in flight).
- [`references/cli-flag-verification-pre-deploy.md`](references/cli-flag-verification-pre-deploy.md) — **read this BEFORE adding a `scripts/*.sh` + `launchd/*.plist.template` pair, or BEFORE deploying an updated launchd-driven script.** The "script is wrong as written" failure mode: argparse rejects a non-existent CLI flag (e.g. `hermes cron list --json`), the script's `|| true` fallback silently swallows it, shell vars interpolate as `?` placeholders into Slack messages, and the launchd job posts broken messages for weeks before anyone notices. 4 pre-deploy checks (flag-exists-in-help → dry-run parser → smoke-test under launchd PATH → regression test pinning contract) + test-shell template that locks the CLI flag + parser row count + template-no-`?`-placeholders contract. Verified 2026-07-21 against the `cron-backup-sync.sh` "Total: ? jobs (? enabled)." bug that ran 6 days before being noticed.
- [`references/report-routing-sweep.md`](references/report-routing-sweep.md) — **read this whenever the user says "move report X (or all reports) off #all-$USER-ai to #ai-general" or any equivalent routing-lapse complaint.** Two-lane recipe: (1) **Lane 1 — live launchd env override** via `launchctl setenv` on the 6 report-routing vars (BUG_HUNT_SLACK_CHANNEL_ID, STABILITY_REPORT_CHANNEL, INTAKE_SLACK_CHANNEL, DROP_ESCALATION_CHANNEL, HERMES_OPS_SLACK_CHANNEL, SLACK_5B_ALERT_CHANNEL) so today's tick routes correctly before the source PR lands; (2) **Lane 2 — persistent source-of-truth sweep** dispatched as one `ao spawn --agent minimax` worker on a clean `origin/main` worktree (Mid-tier model tier preferred; verified worked with `--harness agy --model gemini-3.8-flash-high`) that audits `rg -nE 'C09GRLXF9GR|SLACK_CHANNEL.*\$\{.*-[}]*C09GRLXF9GR' scripts/ launchd/ cron/jobs.json`, distinguishes report emitters from monitored-input / direct-thread / fixture uses, adds a regression test that grep-fails on any emitter reverting, commits + pushes + opens/updates a clean PR. Trigger phrases: "move bug hunt / all reports off this channel", "stop posting reports to #all-$USER-ai", "why is <report> still landing in #all-$USER-ai". Verified 2026-07-23, bead `$USER-yh82`, third recurrence (memory/briefings/2026-07-16 records the prior two).

## Quick Reference

```bash
# Write staging
write_file content "..." to "~/.hermes/launchd/ai.hermes.schedule.example.plist"

# Test
launchctl load ~/Library/LaunchAgents/<name>.plist

# Commit + push
cd ~/.hermes && git add -A && git commit && git push origin main

# Deploy
~/.hermes/scripts/deploy.sh

# Surgical sync (when staging is dirty but fix is on origin/main — see references/staging-dirty-surgical-sync.md)
git worktree add ~/.worktrees/<repo>-fix-<purpose> -b fix/<purpose> origin/main
cp -p <file> ~/.hermes/<file> && cp -p <file> ~/.hermes_prod/<file>
launchctl kickstart -kp gui/$(id -u)/<label>
```
