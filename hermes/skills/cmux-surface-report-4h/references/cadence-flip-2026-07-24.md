# 2026-07-24 cadence flip: every-4h → daily 08:00 PT

This is the session-specific reference for the user request *"Make this a daily report only at 8am"* in Slack thread `C0AJQ5M0A0Y / p1784891379.012009`. The SKILL.md carries the new contract; this file is the verbatim transcript of what shipped, what tripped, and how the live plist was forced to match.

## What changed

- `launchd/com.$USER.cmux-surface-report-4h.plist.template` — six `StartCalendarInterval` entries collapsed to one (`Hour=8 Minute=0`)
- `scripts/cmux-surface-report-4h.sh` — Slack header `cmux Surface Report (4h)` → `(Daily)`; stale "hermes cron create every 4h" example comment deleted
- `scripts/cmux-surface-report-4h-wrapper.sh` — `ThrottleInterval=14400` → `60` (no more "natural cadence" rationale)
- `skills/cmux-surface-report-4h/SKILL.md` — version bump 1.2.0 → 1.3.0, "Daily" everywhere, LLM-cron twin framing removed
- `skills/RESOLVER.md` — added `cmux daily report` / `daily cmux check` triggers; legacy `cmux 4h report` / `4h cmux check` retained
- `~/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist` — re-rendered from the new template, `bootout`/`bootstrap`-reloaded so launchd's cache picked up the new schedule in the SAME session

PR: [jleechanorg/jleechanclaw#799](https://github.com/jleechanorg/jleechanclaw/pull/799)
Heads: `83f3891564db1804801275f90b76813313db3172` (1st commit + post-CodeRabbit fix)
5 files, +26 / −62 lines.

## Live rendered plist reload gate (verbatim, copy-pasteable)

```bash
PLIST="$HOME/Library/LaunchAgents/com.$USER.cmux-surface-report-4h.plist"
LABEL="com.$USER.cmux-surface-report-4h"
DOMAIN="gui/$(id -u)"
plutil -lint "$PLIST"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL"
launchctl print "$DOMAIN/$LABEL" | egrep '"Hour"|"Minute"|state ='
plutil -extract StartCalendarInterval json -o - "$PLIST"
```

After reload on this session:

```
plutil StartCalendarInterval → [{"Hour":8,"Minute":0}]
launchctl print                → "Hour" => 8, "Minute" => 0, state=not running (will fire at next 08:00 PT)
```

## Codex Spark usage-limit retry (verbatim)

First `ao spawn --harness codex --branch fix/cmux-report-daily-8am` returned `spawned session jleechanclaw-19 (idle)` but the worker immediately logged:

```
■ You've hit your usage limit for GPT-5.3-Codex-Spark. Switch to another model now,
  or try again at Jul 29th, 2026 4:22 PM.
```

It never edited anything. Recovery recipe that worked:

```bash
ao session kill jleechanclaw-19
# Preserve the brief verbatim
cat > /tmp/cmux-daily-8am-AO-TASK-BRIEF.md <<'EOF'
Make this a daily report only at 8am
... (full preserved user text + memory expansion) ...
EOF
GH_TOKEN_VAL="$(gh auth token)"
env -i HOME="$HOME" USER="$USER" \
  PATH="$HOME/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" \
  GH_TOKEN="$GH_TOKEN_VAL" AO_BOT_GH_TOKEN="$GH_TOKEN_VAL" \
  bash -c 'exec $HOME/bin/ao spawn --project jleechanclaw --issue $USER-zes1 --name cmux-daily-8am --branch fix/cmux-report-daily-8am --harness agy --prompt "..."'
# Spawn jleechanclaw-20 with --harness agy (defaults to gemini-3.5-flash-high, mid-tier)
```

The second worker took ~6 minutes to commit, push, open PR #799, then took the Green Gate FAIL steer from the `ci-failed` reaction, fixed the stale 4h cron comment in scripts/cmux-surface-report-4h.sh, and pushed `83f3891564`. No top-tier model was needed for this class of work.

## Cron-duplicate audit (verbatim)

Before changing the schedule, confirmed only ONE scheduler was active:

```bash
hermes cron list 2>/dev/null | egrep -i 'cmux.*surface|surface.*cmux'
# → none
launchctl list | grep cmux
# → -   0       -1      com.$USER.cmux-surface-report-4h  (the LaunchAgent)
ls "$HOME/Library/LaunchAgents/" | egrep 'cmux-surface'
# → com.$USER.cmux-surface-report-4h.plist (one file)
```

The skill's historical "LLM-cron twin" framing in the v1.2 SKILL.md turned out to be stale documentation — there was never an active Hermes cron job for this report. The fix updated the doc instead of disabling a non-existent cron.

## Tests that passed

```bash
bash skills/cmux-surface-report-4h/tests/test-classify.sh
# Tests passed: 51, Tests failed: 0

bash tests/test_cmux_surface_report_notify_skip.sh
# PASSED: 11 test(s)

sed "s|@HOME@|$HOME|g; s|@HERMES_EXTRA_PATH@||g" \
  launchd/com.$USER.cmux-surface-report-4h.plist.template | plutil -lint -
# OK
```

## What did NOT happen

- Did not delete the `cmux-surface-report-4h` filename/label — kept it intact to avoid migration risk. The user-visible surface is the Slack header and the firing cadence; both were updated.
- Did not remove the script's `cmux-surface-report-4h` filename — same reason.
- Did not merge PR #799. The user decides merge.
- Did not rename the skill — directory name `cmux-surface-report-4h/` is unchanged for the same migration-safety reason.

## Open follow-up

Bead `$USER-w7yd` records the skillify-completeness audit finding (score 0/9 — missing Output Format section, deterministic scripts dir, Python unit/integration tests, resolver heading triggers, routing-eval.jsonl, check_resolvable.py, E2E test). The bead exists but is **not blocking** — this schedule change shipped correctly; the skill hardening is a separate, follow-up PR.

Bead `$USER-zes1` closed with reason "Live daily 08:00 schedule verified; durable source pushed in PR #799."