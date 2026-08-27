---
name: automation-completeness
description: "Use when adding automation scripts. Requires a caller (CI/cron/hook); watchdog scripts need launchd plist template + deploy.sh install step."
---

# Automation completeness — scripts must have callers


**Any PR adding an automation script must also add the trigger.** A script with no caller is documentation, not automation.

Red flags (task incomplete if any true): script exists but no CI/cron/hook calls it; only invocation path is manual; PR says "run `./scripts/foo.sh` to verify" with no auto-trigger.

Watchdog/monitoring scripts also need: launchd plist committed to repo + `deploy.sh` step that installs it on every deploy.
