---
name: recurring-job-notifications
description: "Wire Gmail + Slack notifications into a recurring launchd/cron job. Use when the user says 'send me a daily email', 'notify me on slack', 'send errors if something went wrong', 'email me the summary', 'ping slack on failure', 'daily recap', 'tag me when something breaks', 'mention me on alert', or any natural-language instruction to add email + Slack delivery to an existing scheduled job. Defaults to ERR-trap failure-only alerts — routine success/no-op posts are noise (Pitfall 11/12); do NOT post routine status updates like 'commited / changed / no changes' to Slack unless the user explicitly asks for them. Covers lib-slack-post.sh, slack_alert() mention prefix, mcp_agent_mail bot identity, channel routing (bot is in #life + #ai-general), gog gmail send, ERR trap firing rules, plus Pitfall 19 (trap ERR doesn't fire on exit 127 — preflight fallback to system python), Pitfall 20 (benign config no-op must return 0), and Pitfall 21 (dead API key surfaces as 402/401)."
when_to_use: "Use when: user asks for email/slack delivery on a launchd or cron job; user says 'notify me', 'daily recap', 'send me a summary', 'email me when X happens', 'alert on errors', 'tag me when X breaks', 'make sure alerts wake me up', 'ping me on Slack failure'; designing a new scheduled job and the user wants both email + slack; debugging a scheduled job whose notifications aren't arriving (silently landing in the channel without waking anyone — see Pitfall 18); deciding which channel to post to for system-generated output. Do NOT use for: one-off Slack posts in an interactive agent session (use mcp__slack__conversations_add_message or the lib-slack-post.sh helper directly); inbound Slack bridge (off per SOUL.md mcp-agent-mail-no-passive-slack-listening); MCP Agent Mail inter-agent messages (different transport)."
context: inline
allowed-tools: terminal, file
---

# Recurring Job Notifications — Gmail + Slack for launchd/cron

## Why this skill exists (six recurring bugs)

Ad-hoc reinvention of the same notification patterns has bitten every new
scheduled job since 2026-06:

1. `slack_post_message "$chan" "$text" | tee -a log` swallows the function's
   return code (tee's status wins). Slack posts silently fail and the script logs
   "Slack notification sent". Always capture rc with `$?`.
2. `find -newermt @<epoch>` is GNU-only — macOS BSD find silently returns 0 matches,
   so any change-detector relying on it reports "no changes" after a real ingest.
3. `[[ -z "$X" ]] && X=0` returns non-zero when X is non-empty (the `&&`
   short-circuits to the false branch). With `set -e` or an ERR trap, this
   becomes a false-positive "failed" alarm every run.
4. mcp_agent_mail bot is **NOT** in #ai-general but **IS** in #life and
   #all-$USER-ai. Verify with `conversations.info` before posting.
5. Hardcoding a Slack channel in a script + committing it kills re-targetability.
   Use `SLACK_CHANNEL=...` env var with a sensible default.
6. **A routine status post is noise, not a feature.** A scheduled job that
   cheerfully posts "Cron Backup: changed (not committed). Total: 26 jobs." every
   weekday morning is doing exactly what the user did NOT ask for — filling
   their inbox with non-actionable summaries. The default for *new* jobs in
   this environment should be Slack-silent on success / no-op / routine
   change. Use ERR-trap failure alerts as the only Slack path. Verified
   2026-07-22, thread C0AJQ5M0A0Y/1784734483.171289, on
   `scripts/cron-backup-sync.sh`. User pushback: "we dont need a slack alert
   for it i think". Fix landed as PR
   [#790](https://github.com/jleechanorg/jleechanclaw/pull/790) — dropped the
   `do_slack` function and the three routine branches, kept local completion
   log + regression test asserting Slack transport cannot return.

## Quick wiring (copy-paste skeleton)

For a new launchd-driven job that needs to email + Slack on success and error,
copy this skeleton and replace `<JOB_NAME>` and the markers:

```bash
#!/bin/bash
# <JOB_NAME> — short description of what runs

set -u                                  # NOTE: do NOT use `set -e`; rely on ERR trap

WIKI_DIR="$HOME/llm_wiki"               # or whatever the job touches
LOG="$HOME/Library/Logs/<JOB_NAME>.log"

# Notification config — all overridable via env var so deployments can re-target
GMAIL_TO="${GMAIL_TO:-$USER@gmail.com}"
GMAIL_ACCOUNT="${GMAIL_ACCOUNT:-$USER@gmail.com}"
# Default to #life (C0AMM2B4319) — same convention as gmail-daily-recap.sh and
# the mcp_agent_mail bot IS a member. See "Channel choice" below for why.
SLACK_CHANNEL="${SLACK_CHANNEL:-C0AMM2B4319}"
LIB_SLACK_POST="$HOME/.hermes/scripts/lib-slack-post.sh"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# Capture ingest/work counters from your Python script's output — adjust
# parser to your script's print format. The download_campaign.py example
# parses lines like "Downloaded: 12" / "Skipped: 232" / "Errors: 0" / "=== Done (..., 135 real users)".
INGEST_OUT=$(mktemp)
"$PYTHON" "$SCRIPT" ... 2>&1 | tee -a "$LOG" "$INGEST_OUT" >/dev/null || true
INGEST_EXIT=${PIPESTATUS[0]}
INGEST_DOWNLOADED=$(grep -E "^Downloaded:" "$INGEST_OUT" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d ' ' || echo 0)
# ... same for SKIPPED, ERRORS, USERS_SCANNED ...

# Generic notify() helper — sends both Slack + Gmail. Returns 0 even on
# individual-channel failures so a broken notifier can't turn a green run red.
notify() {
    local subject="$1" slack_text="$2" gmail_body_file="${3:-}"
    # Slack — capture rc explicitly (do NOT pipe through tee; that masks failures)
    if [[ -x "$LIB_SLACK_POST" ]] || [[ -r "$LIB_SLACK_POST" ]]; then
        source "$LIB_SLACK_POST"
        local slack_output slack_rc
        slack_output=$(slack_post_message "$SLACK_CHANNEL" "$slack_text" 2>&1)
        slack_rc=$?
        echo "$slack_output" | tee -a "$LOG" >/dev/null
        if [[ $slack_rc -eq 0 ]]; then
            log "Slack notification sent (channel $SLACK_CHANNEL)"
        else
            log "WARN: Slack notification failed (rc=$slack_rc) — see $LOG"
        fi
    fi
    # Gmail — gog, best-effort
    if command -v gog >/dev/null 2>&1; then
        local body_arg=()
        if [[ -n "$gmail_body_file" && -s "$gmail_body_file" ]]; then
            body_arg=(--body-file "$gmail_body_file")
        else
            body_arg=(--body "$slack_text")
        fi
        if gog gmail send --account "$GMAIL_ACCOUNT" --to "$GMAIL_TO" \
            --subject "$subject" --no-input "${body_arg[@]}" >/dev/null 2>&1; then
            log "Gmail notification sent (to $GMAIL_TO)"
        else
            log "WARN: Gmail notification failed — see $LOG"
        fi
    fi
    return 0
}

# Error notifier — fires from the ERR trap. Log tail + manual retry command.
notify_error() {
    local err_msg="$1"
    local subject="[Hermes] <JOB_NAME> FAILED — $(date '+%Y-%m-%d')"
    local slack_text
    slack_text=$(cat <<EOF
:red_circle: *<JOB_NAME> — FAILED*
${err_msg}

*Last log tail:* (see \`$LOG\` for full)
\`\`\`
$(tail -8 "$LOG" 2>/dev/null | sed 's/^/  /')
\`\`\`
*Recourse:* \`bash $HOME/.hermes/scripts/<JOB_NAME>.sh\` to retry manually.
EOF
)
    local gmail_body
    gmail_body=$(cat <<EOF
<JOB_NAME> FAILED at $(date '+%Y-%m-%d %H:%M:%S')

${err_msg}

Last log lines:
$(tail -8 "$LOG" 2>/dev/null)

To retry manually:
  bash $HOME/.hermes/scripts/<JOB_NAME>.sh
EOF
)
    notify "$subject" "$slack_text" <<<"$gmail_body"
}

# Success / no-op notifier — same notify() helper, different body shape.
notify_success() {
    local subject="[Hermes] <JOB_NAME> — $(date '+%Y-%m-%d')"
    # Build slack_text + gmail_body from your script's counters
    # (Downloaded/Skipped/Errors/Users/Added/Modified + sample new items).
    local slack_text gmail_body
    slack_text=$(cat <<EOF
:clipboard: *<JOB_NAME> — $(date '+%Y-%m-%d')*
:white_check_mark: Pushed commit \`${PUSH_SHA:0:7}\` → \`${PUSH_BEFORE_SHA:0:7}\`

*Users scanned:* ${INGEST_USERS_SCANNED}
*Campaigns downloaded (new):* ${INGEST_DOWNLOADED}
*Wiki files added:* ${ADDED}
EOF
)
    gmail_body=$(cat <<EOF
<JOB_NAME> — $(date '+%Y-%m-%d')

Users scanned: ${INGEST_USERS_SCANNED}
Campaigns downloaded: ${INGEST_DOWNLOADED}
EOF
)
    notify "$subject" "$slack_text" <<<"$gmail_body"
}

# ERR trap fires on any non-zero command exit (incl. early failures)
on_error() {
    local exit_code=$? line=${BASH_LINENO[0]}
    log "TRAP: exit ${exit_code} at line ${line}"
    notify_error "exit ${exit_code} at line ${line}" || true
    exit $exit_code
}
trap 'on_error' ERR
trap 'on_error' INT TERM

# === YOUR ACTUAL WORK GOES HERE ===

# At every successful exit point:
notify_success || true
log "=== <JOB_NAME> Complete ==="
exit 0
```

## Channel choice — where to post

Verified 2026-07-20: the mcp_agent_mail bot (`B0A3MS7G08P`, app `A0A3WSV6BM1`,
Slack user `U0A4G7LDJ4R`) has these memberships:

| Channel | ID | Bot is member? |
|---|---|---|
| #life | C0AMM2B4319 | ✓ yes |
| #all-$USER-ai | C09GRLXF9GR | ✓ yes |
| #ai-general | C0AJQ5M0A0Y | ✓ yes (re-invited 2026-07-14) |

SOUL.md `slack-channel-routing-policy` says system-generated cron output goes to
home channel (#ai-general). As of 2026-07-28 the bot IS a member of #ai-general,
so the **default channel for new recurring jobs is `C0AJQ5M0A0Y`**. The legacy
"default to #life because the bot can't post to #ai-general" carve-out is
**retired**; any script still defaulting to `C0AMM2B4319` is stale. PR
[#807](https://github.com/jleechanorg/jleechanclaw/pull/807)
(wiki-campaign-daily-ingest) demonstrates the migration.

- **Quick path (default, 2026-07-28+)**: post to **#ai-general** (`C0AJQ5M0A0Y`)
  — the canonical home channel per SOUL.md; bot is a member; no setup needed.
  Use `SLACK_CHANNEL="${SLACK_CHANNEL:-C0AJQ5M0A0Y}"`.
- **Override for a specific target**: `SLACK_CHANNEL=C0XXX bash <script>`
  (any channel the bot is in — `#life`, `#all-$USER-ai`, `#ai-general`,
  etc.).
- **Re-invite the bot to another channel** via the `slack-mcp-mail-bot-reinstall`
  skill §6 (Aside-driven `slack.getClient()` recipe) before changing the
  default for a NEW channel.
- **Operator-attributed fallback** (added 2026-07-27, verified on
  executive-assistant morning sweep to #ai-general C0AJQ5M0A0Y):
  when a *user-initiated* delivery target is #ai-general (or any
  channel the bot isn't in) and the user wants the message to land
  RIGHT NOW without a bot-reinstall round trip, fall back to the
  `SLACK_MCP_XOXP_TOKEN` (xoxp user token) via direct curl. The
  message posts as **`$USER` (user identity), not as the Hermes
  bot** — say so in the body if the recipient might wonder. This is
  the path SOUL.md `slack-cross-workspace-fallback-xoxp` COMMIT
  codifies for "iteration budget exhausted + bot can't post" — and
  it's the right move for cron-driven briefings where the user has
  *explicitly* requested a target channel and the bot isn't a
  member there. Token source: `bash ~/.hermes/scripts/launchd-env-wrapper.sh`
  → exports `SLACK_MCP_XOXP_TOKEN`. The xoxp token is a *user* token,
  not a bot token — `conversations.info?channel=C0AJQ5M0A0Y`
  returns `is_member: true` for `U09GH5BR3QU` ($USER) where the
  bot returns `not_in_channel`.

Verify with `conversations.info` before picking:
```bash
TOK=$(bash -c 'source ~/.bashrc 2>/dev/null; echo -n "${HERMES_SLACK_BOT_TOKEN:-}"')
curl -s -H "Authorization: Bearer ${TOK}" "https://slack.com/api/conversations.info?channel=$CHAN" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('is_member:', d.get('channel',{}).get('is_member'))"
```

## Gmail transport — `gog` is the path

`gog` (gogcli) v0.10.0 is the canonical email-sending CLI in this environment.
It is already used by `gmail-daily-recap.sh`. The exact incantation:

```bash
gog gmail send \
    --account "$GMAIL_ACCOUNT" \
    --to "$GMAIL_TO" \
    --subject "$subject" \
    --no-input \
    --body-file "$body_file"   # or --body "$text" for short bodies
```

`-no-input` is mandatory in launchd/non-interactive contexts (no TTY to prompt).
Credentials live in gog's own store, NOT in bashrc — works under launchd's empty
env as long as `HOME` is set.

Verify it landed via `gog gmail search "subject:wiki-campaign-daily-ingest newer_than:2h"`.

## The `tee` swallow — bash return-code gotcha

This bug shipped and was caught on 2026-07-20 in `wiki-campaign-daily-ingest.sh`:

```bash
# WRONG — tee's exit code wins; slack_post_message's rc is lost
if slack_post_message "$CHAN" "$TEXT" 2>&1 | tee -a "$LOG"; then
    log "sent"      # fires even when Slack returned not_in_channel
fi
```

```bash
# RIGHT — capture rc before the pipe
local slack_output slack_rc
slack_output=$(slack_post_message "$CHAN" "$TEXT" 2>&1)
slack_rc=$?
echo "$slack_output" | tee -a "$LOG" >/dev/null
if [[ $slack_rc -eq 0 ]]; then log "sent"; else log "WARN: rc=$slack_rc"; fi
```

This bites ANY helper function that prints to stdout when called inside an `if`
guard with `| tee`. Always capture `$?` explicitly when the helper is allowed
to fail.

## ERR trap false positive — the `[[ -z X ]] && X=0` pattern

Another bug shipped 2026-07-20:

```bash
# WRONG — returns non-zero when X is non-empty (&& short-circuits to false branch)
for v in A B C; do
    eval "[[ -z \"\${$v}\" ]] && $v=0"   # ERR trap fires here on every populated X
done
```

```bash
# RIGHT — explicit if/then assignment, never evaluates to non-zero
for v in A B C; do
    eval "val=\${$v}"
    val=$(printf '%s' "$val" | tr -cd '0-9')
    if [[ -z "$val" ]]; then val=0; fi
    eval "$v=$val"
done
```

Same shape with `grep | awk '{print $2}'` — guard against empty input.

## The `find -newermt @<epoch>` trap (already in download-campaign pitfall #9)

GNU find: `find /path -newermt @1784583090` (epoch seconds).
macOS BSD find: silently returns 0 matches for `@<epoch>` syntax — your script
will say "no changes" after writing a dozen new files.

Fix: store both. Use the human-readable form for `find`:
```bash
RUN_START_TIME=$(stat -f %m "$MARKER")
RUN_START_DATE=$(date -r "$RUN_START_TIME" '+%Y-%m-%d %H:%M:%S')
find "$DIR" -name "*.md" -newermt "$RUN_START_DATE"  # works on both BSD and GNU
```

## What "send errors if something went wrong" requires

Use `trap 'on_error' ERR` (NOT `set -e` — they're different; `set -e` skips the
trap on some commands). The trap must:
1. Capture the exit code AND the line number (`BASH_LINENO[0]`).
2. Call `notify_error` with the context (NOT rely on the script's main log —
   it might be lost mid-trap).
3. `exit` with the original code AFTER notifying (so launchd sees non-zero and
   can flag the run).

For run-once schedules (StartCalendarInterval fires once a day), an unhandled
failure is invisible — the next day's run silently overwrites the failed log.
The ERR trap is the only thing that pages Jeffrey.

**Trap blind spot — `trap ERR` does NOT fire on exit 127** (added 2026-07-28,
verified on `scripts/wiki-campaign-daily-ingest.sh` 2026-07-24 09:00 cron).
When bash tries to exec a nonexistent binary (`$PYTHON
$HOME/your-project.com/.venv/bin/python: No such file or directory`),
the shell aborts the script with exit 127 BEFORE the ERR trap ever runs.
`trap 'on_error' ERR` only catches commands bash actually executed; a
`command not found` from `execve()` short-circuits the whole interpreter.

Symptom: cron log shows a clean `ERROR: batch ingest exited with status 127`
followed by `=== Wiki Campaign Daily Ingest Complete ===` if the script also
guards `|| true` around the failing call, OR the script just dies mid-line
with zero Slack/Gmail/anything. Gmail-only fallback is the only operator
signal, and only if the script's outer flow continues past the abort.

**Mitigation — binary preflight block BEFORE the first exec call.** Add a
precheck that explicitly tests `$BIN` (or `[[ -L $BIN ]] && [[ ! -e $(readlink
$BIN) ]]` for symlinks) before any `$BIN` invocation:

```bash
if [[ -L "$PYTHON" ]]; then
    py_target=$(readlink "$PYTHON" 2>/dev/null || echo "")
    if [[ -z "$py_target" ]] || [[ ! -e "$py_target" ]]; then
        # Auto-recover if a candidate python is reachable
        py_basename=$(basename "$py_target")
        candidate=$(command -v "$py_basename" 2>/dev/null || command -v python3 2>/dev/null || echo "")
        if [[ -n "$candidate" ]] && [[ -e "$candidate" ]]; then
            ln -sf "$candidate" "$PYTHON"   # relink and continue
        else
            notify_error "venv python symlink broken: $PYTHON -> '$py_target' (no candidate python found — recreate with 'python3 -m venv $WORLDAI_REPO/.venv')" || true
            exit 127
        fi
    fi
elif [[ ! -x "$PYTHON" ]]; then
    # Try to bootstrap from scratch, then exit cleanly if no recovery.
    notify_error "venv python missing or not executable: $PYTHON — recreate with 'python3 -m venv $WORLDAI_REPO/.venv' or relink to a system python" || true
    exit 127
fi
```

Three properties that matter:
- The precheck runs BEFORE the first `$BIN` invocation so the failure is
  detected before `execve()` aborts the script.
- It calls `notify_error()` directly (not the ERR trap) so the alert goes out
  even though the trap would never have fired.
- It includes a remediation hint in the alert body so the operator knows
  what to fix without reading the log.

For venv python specifically, the script that owns the broken `$PYTHON` is
the right place for the fix — but the **contract that any recurring job MUST
have a preflight for every binary it execs** belongs here.

**Diagnostic for already-broken crons**: when a cron has failed silently,
inspect the log for `No such file or directory` lines under the script's
expected `$BIN` paths, then check the binary exists (or the symlink target
exists). A blank log with no output AT ALL is a stronger signal — the
script aborted before `log()` ever wrote its first timestamped line, which
means a preflight is needed.

## Pitfalls (this list IS the skill — review before writing a new job)

1. **`slack_post_message | tee` masks failures** — always capture `$?` after
   `$()` command substitution, never inside a `|` pipeline.
2. **Bot membership is real** — verify with `conversations.info` before posting.
   The bot is in #life, #all-$USER-ai; NOT in #ai-general (needs re-invite
   via `slack-mcp-mail-bot-reinstall` skill §6).
3. **macOS BSD find does not support `find -newermt @<epoch>`** — silently
   returns 0 matches. Use a `date -r +'%Y-%m-%d %H:%M:%S'` string instead.
4. **`[[ -z "$X" ]] && X=0` returns non-zero when X is non-empty** — wrong pattern
   for "default to 0 if empty". Use explicit `if/then`.
5. **`set -e` + `trap ERR` is fragile** — pick one (trap is more flexible). When
   using trap, use `|| true` on lines you intentionally let fail (so the trap
   doesn't fire spuriously).
6. **gog requires `HOME`** even though it's not on the env-passthrough list in
   the plist — launchd always exports HOME by default. If you copy a plist from
   a job that omitted HOME, gog silently uses an empty config path and fails
   with `no credentials`.
7. **gog credentials live in `~/Library/Application Support/gogcli/`** — they
   are NOT in `~/.bashrc`. The launchd plist does not need to pass any token.
8. **`lib-slack-post.sh` `slack__resolve_token()` sources `~/.bashrc`** if the
   plist doesn't pre-export `HERMES_SLACK_BOT_TOKEN`. That works because
   bashrc ~line 951 has the export. If you ever clear that line, every
   recurring job's Slack posts silently break — fix: re-export in the plist's
   `EnvironmentVariables` dict.
9. **Default Slack-on-no-op is anti-noise policy now obsolete** — the daily
   recap style of always-posting (success/no-op/error) is appropriate for
   jobs where the user explicitly asked for a daily summary (e.g. the
   `gmail-daily-recap.sh` shape). It is NOT the right default for "the cron
   ran and produced a backup" jobs. See Pitfall 11 below.
10. **`PUSH_BEFORE_SHA` capture** — record `git rev-parse origin/main` BEFORE
    the push so the notification can show the SHA delta (`abc1234 → def5678`).
    After the push, `HEAD` is the new SHA but the "from" state is lost.
11. **Routine status posts are noise, not a feature** (added 2026-07-22).
    A scheduled job that Slack-posts on every successful run — committed /
    changed / no changes — buries real alerts. The verified pattern when
    the user says "we dont need a slack alert for it" is: keep the local log
    line, keep the backup/git commit, REMOVE the `do_slack` function and
    every Slack branch from the script, and add a regression test that
    forbids the Slack transport from returning to the file. The ERR-trap
    failure alert remains; routine posture becomes "git history + local
    log line". PR
    [#790](https://github.com/jleechanorg/jleechanclaw/pull/790) is the
    canonical worked example (script went from 154 lines to 134 lines,
    dropped the Slack transport entirely, kept the `log "Done. ..."`
    line as the user-facing report).
12. **When the user pushes back on Slack noise, don't ask, just remove the
    transport** (added 2026-07-22). "i think" is consent, not a question.
    Drop `chat.postMessage`, drop `do_slack`, drop the inline `Cron Backup:
    ...` template strings, drop the `SLACK_REVIEW_CHANNEL_ID` fallback, drop
    the `curl` block. Anything left over creates a future regression risk
    and another daily noise post.

13. **Backfilling a "missed day" for a script that hardcodes `TODAY=$(date)`
    (added 2026-07-22)**. When the user says "the GH Actions cost report
    for July 21 didn't fire" and you want to re-run the script for that
    specific day, do NOT edit the script or pass `TODAY=2026-07-21` env
    (most scripts overwrite with `TODAY=$(date -u '+%Y-%m-%d')` on line 1,
    before any env override can stick). The cleanest backfill is a PATH
    stub: write `/tmp/jl-stubs/date` that returns the target date for the
    specific `+format` flag and forwards everything else to `/bin/date`,
    then run the script with `PATH="/tmp/jl-stubs:$PATH"` prepended.
    Verified recipe (2026-07-22, GH Actions Cost Monitor backfill for
    2026-07-21):
    ```bash
    mkdir -p /tmp/jl-stubs && cat > /tmp/jl-stubs/date <<'EOF'
    #!/bin/bash
    # Stub date that returns 2026-07-21 for `-u +%Y-%m-%d` calls only.
    # Forwards everything else to /bin/date.
    if [[ "$1" == "-u" && "$2" == "+%Y-%m-%d" ]]; then
        echo "2026-07-21"
        exit 0
    fi
    exec /bin/date "$@"
    EOF
    chmod +x /tmp/jl-stubs/date
    # Run script with stub on PATH (place first to override /opt/homebrew/bin/date).
    PATH="/tmp/jl-stubs:$PATH" $HOME/.hermes/scripts/gh-actions-cost-monitor.sh
    # Cleanup after — stub only applies to scripts in the same PATH subtree.
    rm -rf /tmp/jl-stubs
    ```
    Why this works: bash resolves `date` via `PATH` lookup at the moment
    the script runs `$(date -u '+%Y-%m-%d')`. Prepending `/tmp/jl-stubs`
    to PATH intercepts that call before `/opt/homebrew/bin/date` /
    `/bin/date` ever sees it. No edit to the script, no env-overwrite
    race, fully reversible.

    **Watch for `gh api` rate-limit burns** — the backfill re-runs the
    full multi-repo scan with `--paginate`. For 3 repos × 24h of data,
    expect ~500-1000 paginated calls = roughly 80% of the user-level
    secondary rate-limit budget. If the script uses `set -euo pipefail`
    and aborts on `jq: parse error: Unfinished JSON term at EOF` after
    the rate limit hits, you'll get a partial backfill (2/3 repos).
    Re-run only the failed repo after a 60-90 min cooldown, or fall back
    to billing-API cost data if the user just needs the dollar figure.

14. **A failed backfill is still a fix, even partial** (added 2026-07-22).
    When the script aborts mid-way through a backfill, ship the partial
    numbers you DID get, label the missing slice explicitly, and post
    the rate-limit cooldown ETA — do NOT silently retry in a tight loop
    (that extends the rate-limit window per `gh-rate-limit-and-transient-failures`).
    "jleechanclaw: $0.13, worldai_claw: $0.42, your-project.com: rate-limited,
    retry in ~60 min" is a usable answer; "$X.XX total" fabricated from
    per-day averages is a fabrication (per SOUL.md `proof-before-claim`).

15. **Multi-worker fan-out scripts must distinguish "no input" from
    "agent failed"** (added 2026-07-22, verified on
    `scripts/bug-hunt-daily.sh` Daily Bug Hunt Report 20260722_162942).
    Scheduled scripts that call N independent LLM/CLI workers and aggregate
    their output face a 4-state outcome grid, not a 2-state (success/fail)
    one. States:
      - (a) **discovery failed** — upstream data source (e.g. `gh pr list`)
        errored, so the workers received an empty input list. Not the
        workers' fault; do NOT report "agent failures".
      - (b) **legitimate empty input** — discovery returned zero items.
        Workers should NOT be spawned; report "no input" truthfully.
      - (c) **worker failed** — workers ran, produced no/bad output. Count
        as agent failures.
      - (d) **worker succeeded** — workers ran, returned findings. Count
        normally.
    The three anti-patterns that collapse these states together:
      - `gh pr list ... 2>/dev/null || echo "[]"` — turns a GraphQL rate
        limit into a fake "0 PRs merged", which then becomes
        "no bugs found → clean sweep" downstream. **Fix**: capture stderr
        to a discovery-error file, return non-zero on `gh` failure, branch
        on that exit code BEFORE the worker-spawn loop.
      - Spawning N workers when input is empty and reporting the empty
        results as "agent failures". **Fix**: skip the spawn loop when
        the input list is empty (and was actually fetched cleanly); the
        report should say "0 PRs to review" — not "3/3 agents failed".
      - Counting prose output as "0 findings" because the worker didn't
        wrap it in a JSON fence. **Fix**: if the output file is non-JSON,
        count it as a worker failure (state c), NOT as state d with zero
        findings. Always validate with `jq empty` before counting.
    The fail-closed summary: if state (a) fires, post `:warning: discovery
    failed — 0 PRs reviewed, no workers spawned, see <err>`; if (b)
    fires, post a clean "0 PRs in window" line; only states (c)/(d)
    should ever produce the "agent failures: N/M" line. Verified on the
    2026-07-22 bug-hunt report — Slack post said `3/3 agents failed` when
    the truthful statement was `0 PRs reviewed because gh rate-limited,
    no workers spawned`. PR (in flight, jleechanclaw session
    `jleechanclaw-13`) restores all four states as a single source of
    truth in the bug-hunt report template.

16. **Multi-worker scripts must not pretend multiple labels are multiple
    models** (added 2026-07-22, same incident). If the script routes
    `--label claude` / `--label codex` / `--label minimax` through a
    single CLI binary that always picks the same underlying model,
    the report's "Agents deployed: claude codex minimax" line is a
    fabrication. **Fix**: probe model identity per worker before
    declaring "agents deployed: N"; if all workers resolved to the same
    model, the report must say "agents deployed: codex (×3, identical)"
    or similar — and the script should fail closed if it cannot
    instantiate the named agents. Verified: all three error logs from
    20260722_162942 showed `model: gpt-5.3-codex-spark` despite
    `Agents deployed: claude codex minimax` in the Slack summary.

17. **Workers receiving empty input should reply `[]`, not prose**
    (added 2026-07-22). Even after the script stops spawning workers on
    empty input, the LLM worker prompt template should include the
    explicit instruction: "If the supplied PR list is empty, return
    exactly `[]` (a JSON array with no elements) wrapped in a single
    markdown code fence — do NOT write a prose explanation." Verified
    on the same incident: workers received `[]`, returned prose
    ("No merged PRs were provided to review..."), and the script's
    fence extractor produced empty output files → counted as failures.
    Even with the upstream fix, the prompt should be defensive.

18. **Silent parser failure + `set -euo pipefail` + `git commit` of
    garbage data is the recurring-job footgun** (added 2026-07-26,
    verified on `scripts/cron-backup-sync.sh` 2026-07-24 08:25 PT run
    that committed `ef5f285f87` `+4/-367` = *deleted* 367 lines of the
    backup JSONL). Three things line up to produce this bug:
    - **Parser crash swallowed by `2>/dev/null`** — the python heredoc
      that parses `hermes cron list --all` had a `+ sched_str +` shell-
      evaluation error (literal text in the error log: `+ sched_str +
      : command not found`). The `2>/dev/null` mask on the python
      substitution hides the stderr and the script treats the parser
      as having "returned empty" instead of "errored".
    - **Silent fallback to empty shell** — the post-parse guard writes
      `CRON_JOBS='{"jobs": [], "total": 0}'` instead of aborting. This
      is correct behavior for a *clean empty parse*, but indistinguishable
      from a *crash that returned empty*.
    - **Empty state still commits** — the commit branch runs
      `git add "$BACKUP_JSON" "$BACKUP_MD" && git commit` regardless of
      whether `CRON_JOBS` is empty or non-empty, because the `CHANGED=1`
      flag is set by `diff -q` when the empty shell differs from the
      prior `.bak` file. Net result: `chore: refresh cron backup`
      commits an empty JSONL, deletes all 26 prior jobs, and posts
      `Cron Backup: changed (not committed). Total: 0 jobs.` to Slack.
      The Slack post then *looks like* an action item ("not committed"
      implies something to fix), but the actual bug already shipped
      to `origin/main` via the commit step.
    - **`COMMIT_SHA: unbound variable` from `set -u` + conditional
      init** — the script only initializes `COMMIT_SHA=""` *inside*
      the `if [[ $CHANGED -eq 1 ]]; then ... fi` block. When the
      diff branch fires but `git commit` is skipped (no changes to
      commit), `COMMIT_SHA` stays unset; with `set -euo pipefail`
      the post-block Slack branches that reference
      `if [[ -n "$COMMIT_SHA" ]]` then trigger `unbound variable`.
    **The fix is four guards, in priority order:**
    - **Refuse to write empty state.** After the parse-or-fallback
      step, check `[[ $(jq '.total' "$BACKUP_JSON") -ge 1 ]]` (or
      python `len(...)`); if zero AND the prior `.bak` was non-empty,
      exit 1 with a log line + Slack ERR-trap alert. An empty backup
      after a non-empty one is NEVER a valid state.
    - **Always init `COMMIT_SHA=""` at the top of the script**, before
      any branch that may skip init. With `set -u`, every variable
      referenced in a later branch must be guaranteed-set in the same
      flow or at script top.
    - **Refuse to commit when the diff is whitespace-only or the
      `jobs` list went from N to 0.** Either: (a) compare the parsed
      job count, not the byte-diff of the JSONL; or (b) wrap the
      `git add && git commit` in a `if [[ $TOTAL -ge 1 ]] || ...
      then` guard so an empty state never produces a commit.
    - **Make the post-block branch read COMMIT_SHA from a single
      source-of-truth.** Use one if/elif/else chain with `COMMIT_SHA`
      resolved once at the top, not a tree of nested conditionals
      that can leave it unset.
    **Bug-ref**: 2026-07-24 08:25 PT, `scripts/cron-backup-sync.sh`
    committed `ef5f285f87` (`+4/-367`) of an empty `{"jobs":[],
    "total":0}` JSONL, then posted `Cron Backup: changed (not
    committed). Total: 0 jobs.` to `#ai-general`. The Slack post
    looked actionable but the bad commit had already shipped. The
    2026-07-24 10:37 PT fix `1c06096bdc` ("descriptive Slack message
    with semantic diff") addressed the message format but did NOT
    add the four guards above. Companion followup filed as
    `br create` (no PR yet — gated on the (a)/(b) reply from
    `C0AJQ5M0A0Y/1784906714.446409`).

19. **`trap ERR` does NOT fire on exit 127 from a missing binary**
    (added 2026-07-29, verified on `scripts/orchestration_slack_catchup_daily.sh`
    `ai.hermes.schedule.slack-digest-rollup` 2026-07-16 → 2026-07-29,
    13 days of silent failure). When the interpreter tries to exec a
    nonexistent file, the kernel's `execve()` aborts the whole script
    BEFORE bash consults the ERR trap. Result: the log shows only the
    launcher-orchestrated error message (often nothing), and the launchd
    job's exit code reflects whatever the launcher printed, NOT the
    script-level `trap`. This is the same shape as Pitfall 18 in
    `wiki-campaign-daily-ingest-silent-venv-failure-2026-07-28.md` —
    see that reference for the full preflight recipe.

    **The simplest durable fix** (verified 2026-07-29): when the script
    uses a venv python and the venv has been deleted, do NOT try to
    rebuild the venv — that's expensive and noisy. Instead, fall back
    to a known-good system python in priority order:
    ```bash
    VENV_PY="$HERMES_HOME/.venv/bin/python3"
    if [[ ! -x "$VENV_PY" ]]; then
      err "venv python missing at $VENV_PY"
      for candidate in \
          "$HOME/.local/orch-venv/bin/python3" \
          "$HOME/.local/bin/python3" \
          "/opt/homebrew/bin/python3" \
          "/usr/bin/python3"; do
        if [[ -x "$candidate" ]]; then
          err "falling back to system python: $candidate"
          VENV_PY="$candidate"
          break
        fi
      done
      [[ ! -x "$VENV_PY" ]] && { err "no usable python found"; exit 1; }
    fi
    ```
    The `err` lines make the fallback visible in launchd stderr, but the
    script continues — the daily job is more important than venv purity.
    This pattern is the right call when the script's Python module is
    stdlib-only (verify with `grep -E '^(from|import)' <module>.py` —
    if every import resolves to the stdlib, system python works).

20. **A "config no-op" path must return 0, not 1** (added 2026-07-29,
    verified on `slack_catchup.py` "No channels to scan"). When the
    script's main() encounters a benign config condition — empty channel
    list, missing config file, no items in the watch window — the
    return code MUST be 0 so the launchd ERR-trap doesn't treat it as a
    failure. The launcher comment claimed rc=0, but the actual python
    was returning rc=1; the launcher was tagging every run as an error
    in stderr even though "no channels to scan" is a normal config state.

    **The two-part fix** (mirror these in every cron script):
    1. **Python side**: return `0` with a `{"ok": false, "benign": true}`
       JSON body so the launcher's `pipe` can grep for `benign` and
       downgrade. Never return `1` for a config-driven no-op.
    2. **Launcher side**: if the launcher's existing comment claims
       rc=0 for some condition, AND the python module returns rc≠0 for
       that same condition, the comment is a lie. **Trust the python
       return code over the comment.** The first time you find this
       mismatch, fix BOTH sides in one commit so future readers can't
       get confused.

    **Diagnostic**: `tail -50 ~/.hermes/logs/<job>.err | grep -E 'rc=[1-9]'`
    over 7+ days. If you see the SAME rc=1 every tick but the stdout
    body says `{"ok": false, "benign": true}`, that's this pitfall.
    The launcher comment probably lies about rc semantics.

21. **A dead API key surfaces as `402 Insufficient credits` / `401
    User not found` indistinguishably** (added 2026-07-29, verified on
    `OPENROUTER_API_KEY` in `~/.hermes/.env` and `~/.hermes_prod/.env`).
    When a vendor API key is rotated, expired, or the workspace is
    deleted, the vendor's error response is shaped to look like a quota
    problem ("Insufficient credits. Add more at <vendor>/settings/credits")
    even when the underlying cause is "user/key not found". This bites
    every cron that calls that vendor — the ERR-trap fires, the Slack
    alert fires, the alert body says "vendor out of credits" but the
    actual problem is the key.

    **Two-step probe (run both before declaring "vendor out of credits"):**
    ```bash
    # 1. Pull the key from the env file the script actually reads
    KEY=$(grep -E '^VENDOR_API_KEY=' ~/.hermes/.env | cut -d= -f2)
    # 2. Probe the vendor's auth endpoint (most have one)
    curl -sS --max-time 10 -H "Authorization: Bearer $KEY" \
      https://vendor.example.com/api/v1/auth/key
    # - 200 OK with usage/limit → key works, vendor truly out of credits
    # - 401 "User not found" → key is dead; need replacement from operator
    # - 401 "Invalid API key" → key was rotated; need new key
    # - 403 / 429 → rate-limit or scope; different fix
    ```
    **Never trust a "vendor out of credits" message in a Slack alert
    without probing the auth endpoint first.** The probe takes 10s and
    saves the operator a wild-goose-chase.

    **Why this isn't self-fixable**: API keys are credentials; the
    agent cannot fabricate one. The fix path is always "ask the
    operator for a new key, drop it into the right env file, restart the
    gateway/job". Do NOT attempt to bypass by routing through a
    different provider or generating a test key — that hardens into a
    policy violation.

    **Companion**: if a Slack thread relays "cron X failed: 402
    Insufficient credits" from a bot identity this session cannot
    control (`hermes_pc` or similar foreign instances), treat it as
    external telemetry. The job ID is NOT in this gateway's cron DB.
    Fix only the underlying cause (the dead key); don't try to "stop"
    the foreign cron since this session has no handle on it. Verified
    on the 2026-07-29 `dbbbf6a173b5` `slack-digest` failure relay.

## Related skills & references

- `~/.hermes/scripts/lib-slack-post.sh` — the canonical Slack helper
  (`slack_post_message`, `slack_post_daily_anchor`, `slack__resolve_token`).
  Read this before reinventing Slack-posting logic.
- `~/.hermes/scripts/gmail-daily-recap.sh` — closest existing example: daily
  cron that posts a Gmail recap to Slack on weekdays 8am. ~150 lines,
  excellent reference.
- `~/.hermes/scripts/wiki-campaign-daily-ingest.sh` — fully wired example
  with both success + error notifiers, ERR trap, and SHA-delta notifications.
  ~400 lines as of 2026-07-20.
- `slack-mcp-mail-bot-reinstall` skill — re-invite the bot to a new channel,
  fix scope gaps. Required if you want to post to #ai-general.
- `download-campaign` skill — has Pitfall #9 (the `find -newermt @<epoch>`
  bug) and a `references/multi-user-batch-rollout-2026-07-20.md` session note
  covering the full wiring.
- `references/wiki-campaign-daily-notifications-2026-07-20.md` (this skill's
  attached notes) — full transcript of the wiring pass that surfaced these
  bugs.
- `references/cron-backup-no-routine-slack-2026-07-22.md` — the inverse
    pass: user pushes back on routine Slack noise, transport is deleted
    entirely, regression test added. Worked example for "stop posting this"
    requests.
- `references/cron-backup-silent-empty-jsonl-commit-2026-07-26.md` —
    companion to the above: silent parser crash (`+ sched_str +` shell-
    eval + `COMMIT_SHA: unbound variable`) writes an empty JSONL to
    `CRON_JOBS_BACKUP.json`, commits it as `chore: refresh cron backup`
    (verified `ef5f285f87` `+4/-367` deletes 367 lines), then posts
    `Cron Backup: changed (not committed). Total: 0 jobs.` which looks
    like an action item but the bad commit already shipped. Four-step
    guard recipe (refuse empty state, init COMMIT_SHA at top, refuse
    empty commit, single-source-of-truth branch). The (a)/(b) followup
    PR is gated on the user reply in `C0AJQ5M0A0Y/1784906714.446409`.
- `references/bug-hunt-daily-fail-closed-2026-07-22.md` — the 4-state
  grid for multi-worker fan-out scripts: discovery-failed vs empty-input
  vs partial-failure vs all-green. Worked example for "the report said
  3/3 failed but really 0 workers should have spawned" bugs. Verified
  on `scripts/bug-hunt-daily.sh` Daily Bug Hunt Report 20260722_162942.
- `references/slack-alert-mention-contract-2026-07-24.md` — the
  tag-or-it-doesn't-notify contract. Why plain `slack_post` text-only
  posts silently land in the channel without waking anyone, the
  `slack_alert()` wrapper (prepends `<@USERID>` + prefix glyph), the
  probe-vs-alert distinction (don't tag routine "still alive" probes),
  the mock-curl e2e test pattern (SLACK_POST_CURL stub that captures
  `-d` payload from args, not stdin), and the 9-script migration
  transcript. Verified on PR
  [#801](https://github.com/jleechanorg/jleechanclaw/pull/801)
  (commit `e056be86b8` on branch `feat/alert-jh-mentions`).
  Uses `tests/test_slack_alert_mentions.sh` (17 contract checks) and
  `tests/test_slack_alert_e2e.sh` (live Slack post verifying both
  mention tokens in the payload).
- `references/wiki-campaign-daily-ingest-silent-venv-failure-2026-07-28.md` —
  companion to the silent-empty-JSONL incident: the `trap ERR` blind
  spot (does NOT fire on exit 127 from a missing binary), the venv
  preflight recipe (detect dangling symlinks, auto-recover via system
  python, fire notify_error() with remediation hint), the TDD test
  pattern for cron notification contracts (red-green proof captured
  pre-fix, 6/6 deterministic across reruns post-fix), and the three
  test-harness subtleties (`export -f` doesn't override script-defined
  functions; `log()` writes to stdout via tee; `LOG=...` is hardcoded).
  Verified on PR
  [#807](https://github.com/jleechanorg/jleechanclaw/pull/807)
  (3 targeted fixes, 2 files / +339/-16). When a cron delivers only a
  Gmail recap and no Slack ping, this is the diagnostic checklist.

## Tests

No automated tests for this skill — it's a wiring pattern, not a runtime
library. Manual verification checklist for any new wired job:

- [ ] Success path: `bash <script>` with a forced change (touch a file, delete
      a page) → check Slack channel has new bot message + check Gmail for
      matching subject + correct sender (`$USER@gmail.com`).
- [ ] No-op path: run with no actual work to do → check Slack + Gmail both
      still arrive (so the cron-still-alive signal works).
- [ ] Error path: rename the working script to break it → check Slack +
      Gmail both arrive with `FAILED` subject and log tail.
- [ ] `bash -n <script>` passes.
- [ ] `shellcheck -S warning <script>` only has SC2155 (declare-and-assign)
      warnings, no SC1036/SC1072/SC1073 parse errors.
- [ ] `launchctl print gui/$(id -u)/<plist-label>` shows `state = not
      running` and `last exit code = 0` after one successful run.
- [ ] `tee | $?` capture pattern used, NOT bare `| tee` (verify by grep).
- **Noise audit (added 2026-07-22)**: if this job is a routine posture
      job (backup, sync, refresh, snapshot) rather than a user-asked-for
      summary, confirm it does NOT post Slack on healthy runs. Concretely:
      `rg -n 'chat.postMessage|do_slack' <script>` should return zero hits,
      and the smoke test should show zero non-failure Slack posts in the
      past 24 hours of `~/.hermes/logs/cron-backup/slack-*.log`. If the user
      has not explicitly asked for success/no-op Slack on this job, default
      to ERR-trap-only.
- **Tag-or-it-doesn't-notify contract (added 2026-07-24)**: for any
      alert path that should wake the user, the wire payload sent to
      Slack must contain `<@USERID>` mention tokens. Bash scripts using
      `slack_thread_lib.sh` should call `slack_alert` (not `slack_post`).
      Python alert helpers should call `_slack_alert` (not `_slack_post`).
      Inline-curl paths must manually prepend the mention line. Audit
      with: `grep -nE '<@U09GH5BR3QU>|<@U0AEZC7RX1Q>' <script>` — FAILURE
      paths should show matches; probe/OK/digest paths should NOT (Pitfall
      19). End-to-end verify with the `tests/test_slack_alert_e2e.sh`
      pattern (Pitfall 23).
- **Probe/OK paths must NOT tag** (added 2026-07-24). A wrapper like
      `gw_message_send` in `monitor-agent.sh` is called by BOTH
      alert paths ("prod gateway DOWN") AND periodic probes ("Monitor
      check started" every 15 min). If you migrate the wrapper to
      `slack_alert`, you'll ping Jeffrey + Hermes every 15 min. Fix:
      keep `slack_alert` for the alert path, add a sibling
      `gw_probe_message_send` that uses `slack_post` (no tag). Or set
      `HERMES_ALERT_SILENT=1` on the probe path. The judgment: tag
      only when the message carries actionable information the user
      needs to react to. Routine "still alive" probes are noise.
- **Direct-curl fallbacks also need mentions** (added 2026-07-24).
      Scripts that bypass the lib with inline `curl chat.postMessage`
      (e.g. `monitor-agent.sh`'s `send_report_to_slack` "hermes-alert"
      branch that fires when the gateway itself is down) need to
      manually prepend `<@U09GH5BR3QU> <@U0AEZC7RX1Q>\n:rotating_light:\n`
      to the message body before the curl. The `slack_alert` wrapper
      isn't an option here because the lib can't be sourced when the
      gateway is down. The custom prefix is the difference between
      "alert silently landed" and "page went out".
- **Override knobs for slack_alert** (added 2026-07-24). The lib
      accepts three env vars: `HERMES_ALERT_TARGETS` (space-separated
      raw user IDs; default `<@U09GH5BR3QU> <@U0AEZC7RX1Q>`),
      `HERMES_ALERT_PREFIX` (default `:rotating_light:`), and
      `HERMES_ALERT_SILENT=1` (forces plain `slack_post` semantics).
      Use `HERMES_ALERT_SILENT` in scripts that post a series of
      related messages where only the first should tag (e.g. an
      initial "ALERT" followed by "RECOVERED" follow-ups — the
      follow-up should not double-tag). Use `HERMES_ALERT_TARGETS` in
      incident bridge scripts where the primary on-call is someone
      other than the default.
- **Always grep for the actual `<@USERID>` mention token, not the
      string \"$USER\" or \"hermes\"** (added 2026-07-24). A naive
      audit (`grep $USER <script>`) matches a hundred false
      positives — the literal token rarely appears in the script,
      while the word "$USER" appears in log paths, comments,
      sensitive-key patterns, etc. The mention-token regex is the
      only audit that maps to Slack's actual notification behavior.
      Use: `grep -nE '<@U09GH5BR3QU>|<@U0AEZC7RX1Q>' <script>` and
      `rg -l '<@U09GH5BR3QU>|<@U0AEZC7RX1Q>' $HOME/.hermes/scripts/`.
- **Test slack_alert end-to-end with a mock-curl wrapper, not stdin
      redirection** (added 2026-07-24). The lib's `SLACK_POST_CURL`
      override passes the payload via `-d "$payload"` argument, NOT
      via stdin. A mock that reads stdin will see empty content and
      capture nothing. Stub pattern:
      ```bash
      cat > /tmp/slack-alert-e2e/mock-curl.sh <<'EOF'
      #!/usr/bin/env bash
      PAYLOAD=""
      while [[ $# -gt 0 ]]; do
          case "$1" in
              -d|--data|--data-binary|--data-raw) PAYLOAD="$2"; shift 2 ;;
              *) shift ;;
          esac
      done
      echo "$PAYLOAD" > /tmp/slack-alert-e2e/last-payload.json
      curl -sS --fail ... -d "$PAYLOAD"  # forward to real Slack
      EOF
      chmod +x /tmp/slack-alert-e2e/mock-curl.sh
      SLACK_POST_CURL=/tmp/slack-alert-e2e/mock-curl.sh \
      bash tests/test_slack_alert_e2e.sh
      ```
      Then assert `grep -q '<@U09GH5BR3QU>' /tmp/slack-alert-e2e/last-payload.json`
      and similarly for the Hermes mention. The mock-curl can forward
      to real Slack (so the e2e test proves both "payload contains
      mentions" AND "Slack actually accepted it").

## Recipes

### Recipe: TDD contract tests for cron notification scripts

Use this recipe when wiring a new recurring job (or fixing a notification
contract violation like the wiki-campaign-daily-ingest 2026-07-24 silent
abort). The test runs against the actual script in a sandboxed `HOME`, so
the same control flow that launchd invokes is exercised — without making
real Slack/Gmail calls. Three contracts to assert, in priority order:

1. **Channel routing** — the script's `SLACK_CHANNEL` default is the
   canonical home channel (e.g. `C0AJQ5M0A0Y`), and any override respects
   `SLACK_CHANNEL` env var. Test:
   ```bash
   DEFAULT_SLACK=$(grep -E '^SLACK_CHANNEL=' "$SCRIPT" | head -1 \
     | sed -E 's/.*\$\{SLACK_CHANNEL:-([^}]+)\}.*/\1/')
   if [[ "$DEFAULT_SLACK" != "C0AJQ5M0A0Y" ]]; then bad "..."; fi
   ```
2. **Failure-path tagging** — `notify_error()` interpolates both
   `<@U09GH5BR3QU>` and `<@U0AEZC7RX1Q>` on the alert body. The script
   typically references them as `${SLACK_OPERATOR_ID}` / `${SLACK_HERMES_BOT_ID}`,
   so the test asserts both the variable declarations AND their
   interpolation in the `notify_error()` heredoc. Companion negative:
   `build_success_summary()` MUST NOT tag (USER_PROFILE rule:
   tag-only-on-failure-paths).
3. **Binary preflight fires before exec** — run the script with the
   expected `$BIN` path pointed at a guaranteed-missing file AND
   `HOME="$TMPD"`. Inspect the log file the script wrote to (NOT stdout;
   `log()` does `echo ... | tee -a "$LOG"` which goes to stdout via `tee`,
   so redirect `>/dev/null 2>&1`). The log must contain a "venv python
   missing" or equivalent diagnostic AND a remediation hint.

**Sandboxing recipe** — the script has hardcoded `$HOME/Library/Logs/...`
in its `LOG=` line (NOT `${LOG:-...}`), so you cannot override `LOG` via
env. Instead, override `HOME` to a tmpdir and inspect the log at the path
the script derives from `$HOME`:

```bash
TMPLOG="$TMPD/Library/Logs/<job-name>.log"
HOME="$TMPD" \
PYTHON="/nonexistent/pythonXYZ-$(date +%s)" \
SLACK_CHANNEL="C0AJQ5M0A0Y" \
GOOGLE_APPLICATION_CREDENTIALS="/dev/null" \
WORLDAI_DEV_MODE=true \
bash "$SCRIPT" >/dev/null 2>&1 || true
# Now assert against $TMPLOG
```

The `WORLDAI_DEV_MODE=true` / `GOOGLE_APPLICATION_CREDENTIALS=/dev/null`
overrides prevent the script from making real Firestore/Google calls. The
`>/dev/null 2>&1` is required because `log()` writes to stdout via `tee`
AND the log file; capturing either one eats the other.

**Why this works even without stubbing `notify()`** — the script's
`notify()` calls `slack_post_message` which is sourced from
`$HOME/.hermes/scripts/lib-slack-post.sh`. If `$HOME` is a tmpdir, the
script logs `WARN: $LIB_SLACK_POST not found — skipping Slack notification`
and the notify() call returns 0. The Slack TEXT was constructed in
`notify_error()` before that fallback, so the failure is recoverable: you
verify the wiring (text construction, variable interpolation, channel
default) by inspecting the script source AND by running it with broken
inputs and checking the log. You don't need to stub `notify()`.

**Worked example**: `scripts/tests/test_wiki_campaign_daily_ingest_notifications.sh`
(241 lines, 6 contract assertions, deterministic across 3 reruns). Added in
PR #807 (2026-07-28). The TDD trail:
- RED proof: 3/3 FAIL pre-fix — Slack targets `#life`, no operator tag,
  silent `No such file or directory` on missing venv.
- After the 3 targeted code fixes: 6/6 PASS (3 contracts × 2 assertions
  each), deterministic, no flake.

The verdict for a new recurring job: write the contract tests BEFORE the
script is wired. If the test pattern is right, you get RED for every
notification contract violation on day one and never have to debug silent
cron failures again.

### Recipe: migrate an existing alert script to slack_alert

Before (silent — text-only posts do not notify):
```bash
slack_post "my-job" "Hermes prod gateway DOWN port 8643" \
    --channel "$ALERT_CHANNEL" --force
```

After (tags Jeffrey + Hermes):
```bash
slack_alert "my-job" "Hermes prod gateway DOWN port 8643" \
    --channel "$ALERT_CHANNEL" --force
```

For Python scripts with a private `_slack_post` helper, add a
parallel `_slack_alert` and migrate FAILURE paths:
```python
DEFAULT_ALERT_TARGETS = ("U09GH5BR3QU", "U0AEZC7RX1Q")

def _slack_alert(channel: str, text: str) -> None:
    targets_raw = os.environ.get("HERMES_ALERT_TARGETS", "").strip()
    ids = targets_raw.split() if targets_raw else list(DEFAULT_ALERT_TARGETS)
    mentions = " ".join(f"<@{uid}>" for uid in ids)
    prefix = os.environ.get("HERMES_ALERT_PREFIX", ":rotating_light:")
    _slack_post(channel, f"{mentions}\n{prefix}\n{text}")
```

For inline-curl paths that bypass the lib (gateway-down scenarios):
```bash
prefixed="<@U09GH5BR3QU> <@U0AEZC7RX1Q>
:rotating_light:
${msg}"
payload=$(jq -nc --arg ch "$CHAN" --arg txt "$prefixed" \
    '{channel: $ch, text: $txt}')
curl -sS -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer ***" \
    -H "Content-Type: application/json" \
    -d "$payload"
```

### Recipe: SKILL.md / SOUL.md contract when user asks "tag me on alerts"

When the user says "tag me / Hermes / @-mention me / make sure I
get notified / wake me up / page me" in the context of alerts, the
deliverable is:

1. A `slack_alert()` (or `_slack_alert` in Python) helper that
   prepends `<@USERID>` mentions on failure paths.
2. Migration of every alert-sending script in the repo to use it on
   the failure path. Tag stays OFF on probe / OK / digest paths.
3. A contract test that verifies the actual payload sent to Slack
   contains both mentions (the e2e test pattern in this skill).
4. Live proof: post a test alert to a non-operator channel
   (`#ai-slack-test` C0AKALZ4CKW is the standing test channel),
   verify the Slack API response shows `ok=true` and the response
   shape renders the mentions as live user links. Save the test
   ts+channel so the user can click through.

The shipped deliverables (files changed + PR link) ARE the proof —
"Ran a test" without a tracked PR/commit is not durable.