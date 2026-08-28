---
name: babysit
description: Watch one or more AO worker tmux sessions, classify their state (WORKING/IDLE/QUEUED/DEAD/COMPLETED), auto-remediate known failures (trust TUI, queued prompt), and push-notify on stuck sessions. Reuses ao-session-monitor state detection. Use /babysit to start a monitoring loop on a specific worker, all active workers, or workers matching a PR/branch.
type: skill
---

# /babysit — AO Worker Supervisor

**Primary use:** Watch individual AO worker tmux sessions (e.g., `ao-6312`) and surface/auto-remediate stuck or dead shells. Complements (does not replace) the launchd-managed `ao lifecycle-worker` which handles the system-level reaction loop.

**Full skill content:** `~/.claude/skills/babysit/SKILL.md`

**Aliases:** `/babysit watch <session>`, `/babysit snapshot`, `/babysit watch-all`, `/babysit pr <N>`

**Modes:**
- `/babysit snapshot` — one-shot table of all `ao-*` workers (no loop)
- `/babysit watch <session>` — single worker, 60s poll, auto-dismiss TUI, push-notify on stall/dead
- `/babysit watch-all` — all active workers
- `/babysit pr <PR#>` — resolve PR/branch to session, then watch

**State machine:** WORKING / IDLE / QUEUED / DEAD / STALLED-COMPLETED / TUI-BLOCKED / HAS-WORK-NO-COMMIT

**Auto-remediation policy:** Dismiss agy trust TUI (Enter once, 60s idempotency). Push-notify only on queued/dead/stalled — never auto-respawn, never auto-commit, never auto-send Enter on empty `❯` prompts.

**Do NOT use when:**
- The system-level autonomy chain is broken — use `/auton`
- You want to spawn a worker — use `/ao-worker-dispatch`
- You want a one-shot state check — use `/ao-session-monitor`
- A single worker has a specific error — use `/ao-lifecycle-triage`

**Cross-references:**
- `/babysit-openclaw` — Slack-thread-based, single-shot, different model (openclaw posts to Slack; AO workers use tmux)
- `/ao-session-monitor` — single-pane one-shot (babysit embeds its detection one-liner)
- `/auton` — system-level autonomy diagnostic

**Sentinel layout:** `~/.cache/babysit/${session}.{last_enter,last_notify,last_state,started_at}`

**Hard cap:** 8 workers per watch loop. `--max-min` default 90, hard cap 180 without explicit user approval.
