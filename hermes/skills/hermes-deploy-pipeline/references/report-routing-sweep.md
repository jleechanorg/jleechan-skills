# Report-routing sweep — every automated report to `#ai-general`, not `#all-$USER-ai`

Added 2026-07-23 after bead `$USER-yh82`. Class-level recipe for the recurring failure mode where Jeffrey asks "move bug hunt / all reports off this channel to `#ai-general`" and the next run still lands in the original channel because each emitter hardcoded its own Slack destination.

## Trigger phrases

- "move bug hunt / all reports off this channel"
- "stop posting reports to #all-$USER-ai"
- "route report X to #ai-general instead"
- "every automated report should go to #ai-general"
- "why is <report> still landing in #all-$USER-ai"
- "channel default for all system-generated reports should be #ai-general"

## Failure pattern (do NOT just patch one script)

Each report emitter (`bug-hunt-daily.sh`, `stability-report.sh`, `github-intake.sh`, `auto-push-to-main.sh`, `gh-actions-cost-monitor.sh`, `spend-alert-daily.sh`, dropped-thread `ESCALATION_CHANNEL`, hermes-watchdog alert channel, `slack_5b_leak_detector` alert, dropped-thread priority alert — ~10+ emitters across `~/.hermes/scripts/*.sh` and `~/.openclaw/scripts/*.sh`) hardcoded its own Slack destination via a `SLACK_CHANNEL="${…:-C09GRLXF9GR}"` default. The "fix one report" PR (e.g. PR #784 → stability-report only) left the others recurring.

## Two-lane durable fix (apply BOTH every time, never just one)

### Lane 1 — Live launchd env override (immediate containment, before the source PR lands)

When the user complains about a routing lapse and the persistent fix is still in flight, set the relevant env vars on the user's launchd `gui` domain so the live daemons re-route before the next tick. This is `launchctl setenv`, not bash `export`, because launchd launches plists with a stripped env that does not source `.bashrc`.

```bash
# Set the destination env vars on the user's GUI launchd domain.
for kv in \
  BUG_HUNT_SLACK_CHANNEL_ID=C0AJQ5M0A0Y \
  STABILITY_REPORT_CHANNEL=C0AJQ5M0A0Y \
  INTAKE_SLACK_CHANNEL=C0AJQ5M0A0Y \
  DROP_ESCALATION_CHANNEL=C0AJQ5M0A0Y \
  HERMES_OPS_SLACK_CHANNEL=C0AJQ5M0A0Y \
  SLACK_5B_ALERT_CHANNEL=C0AJQ5M0A0Y; do
  launchctl setenv "${kv%=*}" "${kv#*=}"
done

# Verify they stuck.
for k in BUG_HUNT_SLACK_CHANNEL_ID STABILITY_REPORT_CHANNEL \
         INTAKE_SLACK_CHANNEL DROP_ESCALATION_CHANNEL \
         HERMES_OPS_SLACK_CHANNEL SLACK_5B_ALERT_CHANNEL; do
  printf '%s=%s\n' "$k" "$(launchctl getenv "$k")"
done
```

Lane 1 expires whenever the user reboots / logs out (launchd `gui/$UID` env is per-login). It is not a substitute for Lane 2 — it is the immediate containment. Always ship Lane 2 in the same session.

### Lane 2 — Persistent source-of-truth sweep (the durable fix)

Pattern: one AO worker (`ao spawn --agent minimax --harness agy … --model gemini-3.5-flash-high`) on a clean `origin/main` worktree that:

1. Audits every emitter (`rg -nE 'C09GRLXF9GR|SLACK_CHANNEL.*\$\{.*-[}]*C09GRLXF9GR' ~/.hermes/scripts ~/.openclaw/scripts ~/project_jleechanclaw/jleechanclaw/scripts ~/project_openclaw/openclaw/scripts`)
2. Distinguishes report emitters (REWRITE default to C0AJQ5M0A0Y) from monitored-input channels / user-thread sources / fixture files (LEAVE UNCHANGED)
3. Adds a single `lib/slack-report-channel.sh` source-of-truth if appropriate (`SLACK_REPORT_CHANNEL_DEFAULT="${SLACK_REPORT_CHANNEL_DEFAULT:-C0AJQ5M0A0Y}"`) so future emitters import from one location
4. Sweeps tracked launchd templates + installed LaunchAgents
5. Sweeps gateway cron jobs (`hermes cron list` JSON) for `deliver: slack:C09GRLXF9GR`
6. Sweeps env-override files (`~/.bashrc`, `~/.zshrc`, profile snippets) for `C09GRLXF9GR` channel literals
7. Adds regression test under `tests/test_report_routing_defaults.py` that grep-fails the moment any emitter reverts to C09GRLXF9GR
8. Installs the live state, verifies (`launchctl print gui/$(id -u)/<label>`), commits + pushes + opens/updates PR, verifies remote SHA, drives as far green as the repo lane permits

## What stays on C09GRLXF9GR even after the sweep

- Monitored source channels (the script OWNS the channel as an input, not a target — e.g. `slack_5b_leak_detector.sh` watches C0AH3RY3DK6 / C09GRLXF9GR / etc. for output leaks)
- Direct user-originated thread replies (`slack_post --thread-ts <user-msg-ts>` — the post belongs in the originating thread)
- Test fixture .json / .sh mocks that simulate channel IDs
- Watcher `WATCHED_CHANNELS=...` lists where C09GRLXF9GR is the subject of monitoring, not a destination

The regression test under `tests/test_report_routing_defaults.py` must encode these exceptions (source-monitor / direct-thread-reply / fixture file) so future sweeping does not regress by over-correcting.

## Pitfalls

- **Never search-and-replace `C09GRLXF9GR` literally.** That substitution destroys the legitimate "monitored channel" / "user-thread source" uses of the same channel ID. Always run the distinction step BEFORE rewriting.
- **Always set live env (Lane 1) BEFORE Lane 2 starts.** A daily bug hunt at 09:00 PT will fire while the source PR is in flight; Lane 1 ensures today's run routes correctly even if Lane 2 takes a day to merge.
- **The 6 env vars above are not exhaustive.** When the sweep lands new reporters, audit `rg -nE 'SLACK_CHANNEL.*:-C[0-9A-Z]{10}|SLACK_TARGET.*:-C[0-9A-Z]{10}' ~/.hermes/scripts ~/.openclaw/scripts` and add each new variable to Lane 1 + the regression test.
- **Plist templates that hardcode a channel literal** (`<string>C09GRLXF9GR</string>` inside `<key>HERMES_OPS_SLACK_CHANNEL</key>`) MUST be updated in the template file AND have the template re-rendered/installed to the live LaunchAgent. Editing the template alone is invisible to the loaded daemon.
- **`scripts/deploy.sh` Stage 4.5 still does not sync `scripts/`, `launchd/`, or `cron/jobs.json`** (see umbrella §"`scripts/` and `launchd/` trees are NOT in `POLICY_FILES`"). After Lane 2 lands, run `git pull` + the Stage-4.5 + Stage-4.6 sync, then audit each plist / cron job's deployed state via `launchctl print` and `hermes cron list --json`.

## Worked example — 2026-07-23, bead `$USER-yh82`

- Trigger: Slack `C09GRLXF9GR/1784764716.709569` "for the last fucking time move bug hunt and all reports off of this channel and to #ai-general" — third occurrence (memory/briefings/2026-07-16/0804-ea-sweep.md lines 9-11 first recorded the same ask).
- Lane 1: `launchctl setenv` of the 6 env vars listed above. Verified via `launchctl getenv` — every var returned `C0AJQ5M0A0Y`.
- Lane 2: AO session `jc-2048` spawned on `jleechanorg/jleechanclaw` from clean `origin/main` worktree, Mid-tier model tier (Gemini 3.5 Flash High via agy harness verified by direct API call returning `model: MiniMax-M3, text: PONG_M3_OK`). Started sweepting emitters at "Auditing C09GRLXF9GR defaults… (3m 52s)". In-flight as of session end.
- Five-minute progress cron `5c224be1e55c` posts in the originating thread (`deliver: origin`), self-cancels on PR MERGED/CLOSED, never posts Slack canaries.

## Cross-references

- Umbrella: `hermes-deploy-pipeline` → §"Launchd `EnvironmentVariables` and the login-env wrapper pattern" (why `launchctl setenv` matters)
- Umbrella: §"Plist templates that exist but aren't wired into `install-hermes-scheduled-jobs.sh` are silent orphans" (which templates need re-install after edits)
- SOUL.md `## COMMIT: slack-channel-routing-policy` (destination gate policy)
- SOUL.md `## COMMIT: dropped-thread-jeffrey-only-default-removed` (related channel-routing correction)
- Skill `slack-thread-routing-investigation` (5a-5g sub-classes of the same routing-lapse class)
