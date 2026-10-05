---
name: agy-dot-coordinator
description: Periodic background launchd agent (macOS) and systemd user timer (Linux) running the Antigravity CLI (agy) to coordinate with the ChatGPT dot assistant, reminding it to prioritize and drive work on its cloud computer environment with stateful debouncing and draft safety.
---

# Antigravity Dot Cloud Coordinator (`agy-dot-coordinator`)

## Purpose
`agy-dot-coordinator` provides a cross-platform background service (macOS `launchd` and Linux `systemd --user`) that periodically invokes the Antigravity CLI (`agy`) to inspect the user's central ChatGPT coordinator ("the dot"). It:
1. Sends a structured message asking what work and goals are currently in flight across all tracks.
2. Reminds the dot to resume any paused or waiting work/goal and keep driving in strict priority order using its cloud computer.
3. Directs the dot to provision and configure its cloud computer with all necessary tools, repositories, dependencies, and test harnesses, and strictly prefer driving execution there.
4. Checks every minute for a reply while the dot is thinking or working, confirms verified delivery, and logs the latest in-flight goals.
5. Uses stateful debouncing and composer draft protection to prevent conversational spam and preserve peer drafts.

---

## Architectural Principles & Invariants

### 1. Dual-Platform Schedulers (Launchd & Systemd)
- **macOS**: Configured as a LaunchAgent (`launchd/ai.gemini.agy-dot-coordinator.plist`) managed via `launchctl`.
- **Linux**: Configured as paired `systemd` user service and timer (`systemd/ai.gemini.agy-dot-coordinator.service` and `systemd/ai.gemini.agy-dot-coordinator.timer`) managed via `systemctl --user`.
- **Unified Installer**: `scripts/install-service.sh` auto-detects macOS vs Linux and delegates to `install-launchagent.sh` or `install-systemd.sh`.

### 2. Single Message Directive: 24h WIP Summary, Active Nudge & Prioritization
- The coordinator dispatches a single structured directive:
  - Requests an explicit summary of all WIP tasks, PRs, and active goals from the last 24 hours across all tracks (PR #, branch/head, status, blockers, and next steps).
  - Nudges the dot firmly to ensure it is actively driving and trying to advance all work rather than waiting passively.
  - Enforces strict prioritization order:
    1) UI redesign (PR 10095), OpenRouter preview/auth (PR 10092), and Single-Turn Level-Up (PR 10097).
    2) Resource PRs (PR 8934, 10107, 10115, 10116, 10128) and Combat/XP bug fixes (PR 9867).
    3) Background campaigns and research tasks.
  - Directs the dot to keep its cloud computer fully provisioned and strictly prefer driving all execution there.

### 3. 1-Minute Reply Polling Loop
- After sending, the worker monitors the conversation, checking every minute (up to 10 minutes) with `dot.sh read` until the dot finishes its response (no longer ending in `Thinking`/`Working`).
- Logs each poll cycle (`[Poll X/10] Dot is actively working on reply...`) and extracts the confirmed reply.

### 4. Stateful Debounce & Staggered 30-Minute Schedule
- Schedulers wake every 30 minutes, staggered by 15 minutes across machines to prevent overlapping checks:
  - **macOS**: At `:00` and `:30` of each hour via `StartCalendarInterval`.
  - **Linux (`jeff-ubuntu`)**: At `:15` and `:45` of each hour via `OnCalendar=*:15,45:00`.
- A 2-hour cooldown (7200 seconds) is enforced in `~/.local/state/ai.gemini.agy-dot-coordinator/state.json`.
- If the dot is actively working (`Thinking`, `Working`, `Searching`), the check-in is skipped.

### 5. Composer Contention & Draft Safety
- `dot.sh` invocations use `DOT_WAIT_SECS=60` and `DOT_RETRY_SECS=15` to avoid hanging when a peer or user draft sits in the composer.
- If an unsubmitted peer draft is present (`DOT_DRAFT_PRESENT`), the worker cleanly logs the busy state and exits 0.
- Delivery verification (`DOT_SENT_VERIFIED`) ensures messages are confirmed in the conversation DOM before updating the last-sent timestamp.

### 6. Concurrency Locking
- Mutual exclusion is enforced via `flock -n` on `/tmp/ai.gemini.agy-dot-coordinator.lock` to prevent overlapping runs.

---

## Component Layout

```
.claude/skills/agy-dot-coordinator/
├── SKILL.md                                           # This guide
├── launchd/
│   └── ai.gemini.agy-dot-coordinator.plist            # macOS launchd plist template (@HOME@ placeholder)
├── systemd/
│   ├── ai.gemini.agy-dot-coordinator.service          # Linux systemd user service (%h / @HOME@ placeholder)
│   └── ai.gemini.agy-dot-coordinator.timer            # Linux systemd user timer (15min cadence)
└── scripts/
    ├── agy-dot-coordinator-wrapper.sh                 # Sourced environment & lock wrapper
    ├── agy-dot-coordinator-worker.sh                  # Gated worker with 1-minute reply polling loop
    ├── install-service.sh                             # Cross-platform installer (macOS & Linux)
    ├── install-launchagent.sh                         # macOS launchctl installer
    └── install-systemd.sh                             # Linux systemctl --user installer
```

---

## Installation & Operations

### Cross-Platform Install
```bash
~/.claude/skills/agy-dot-coordinator/scripts/install-service.sh
```

### Manual Trigger & Status Check
- **Check Status / Elapsed Cooldown**:
  ```bash
  ~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh --status
  ```
- **Dry-Run (Inspect Dot Without Sending)**:
  ```bash
  ~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh --dry-run
  ```
- **Force Immediate Check-in & Reply Polling**:
  ```bash
  ~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh --force
  ```
- **Trigger Scheduler Job**:
  - macOS: `/bin/launchctl kickstart -k "gui/$(id -u)/ai.gemini.agy-dot-coordinator"`
  - Linux: `systemctl --user start ai.gemini.agy-dot-coordinator.service`
- **Inspect Logs**:
  - macOS: `tail -f ~/Library/Logs/ai.gemini.agy-dot-coordinator.log`
  - Linux: `journalctl --user -u ai.gemini.agy-dot-coordinator.service -f`
