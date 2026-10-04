---
name: agy-dot-coordinator
description: Periodic background launchd agent (macOS) and systemd user timer (Linux) running the Antigravity CLI (agy) to coordinate with the ChatGPT dot assistant, reminding it to prioritize and drive work on its cloud computer environment with stateful debouncing and draft safety.
---

# Antigravity Dot Cloud Coordinator (`agy-dot-coordinator`)

## Purpose
`agy-dot-coordinator` provides a cross-platform background service (macOS `launchd` and Linux `systemd --user`) that periodically invokes the Antigravity CLI (`agy`) to inspect the user's central ChatGPT coordinator ("the dot"). It:
1. Queries the dot about in-flight work and active priorities.
2. Reminds the dot to continually drive work in priority order using its cloud computer environment.
3. Directs the dot to provision and configure its cloud computer with all necessary tools, dependencies, and environment configurations, and strictly prefer driving execution there.
4. Uses stateful debouncing and composer draft protection to prevent conversational spam and preserve peer drafts.

---

## Architectural Principles & Invariants

### 1. Dual-Platform Schedulers (Launchd & Systemd)
- **macOS**: Configured as a LaunchAgent (`launchd/ai.gemini.agy-dot-coordinator.plist`) managed via `launchctl`.
- **Linux**: Configured as paired `systemd` user service and timer (`systemd/ai.gemini.agy-dot-coordinator.service` and `systemd/ai.gemini.agy-dot-coordinator.timer`) managed via `systemctl --user`.
- **Unified Installer**: `scripts/install-service.sh` auto-detects macOS vs Linux and delegates to `install-launchagent.sh` or `install-systemd.sh`.

### 2. Zero-Environment Unit/Plist Principle
- Schedulers contain zero secrets or hardcoded custom PATHs.
- Execution passes through `scripts/agy-dot-coordinator-wrapper.sh`, which sources the user's login shell profile (`~/.bash_profile` on macOS or `~/.bashrc` on Linux) under `set +u` / `set -u`.

### 3. Stateful Debounce & Idle Detection
- Schedulers wake every 15 minutes (`StartInterval: 900` or `OnUnitActiveSec=15min`).
- A 2-hour cooldown (7200 seconds) is enforced in `~/.local/state/ai.gemini.agy-dot-coordinator/state.json`.
- If the dot is actively working (`Thinking`, `Working`, `Searching`), the check-in is skipped.

### 4. Composer Contention & Draft Safety
- `dot.sh` invocations use `DOT_WAIT_SECS=60` and `DOT_RETRY_SECS=15` to avoid hanging when a peer or user draft sits in the composer.
- If an unsubmitted peer draft is present (`DOT_DRAFT_PRESENT`), the worker cleanly logs the busy state and exits 0.
- Delivery verification (`DOT_SENT_VERIFIED`) ensures messages are confirmed in the conversation DOM before updating the last-sent timestamp.

### 5. Concurrency Locking
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
    ├── agy-dot-coordinator-worker.sh                  # Gated worker dispatching agy -p
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
- **Force Immediate Check-in (Bypass Cooldown)**:
  ```bash
  ~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh --force
  ```
- **Trigger Scheduler Job**:
  - macOS: `/bin/launchctl kickstart -k "gui/$(id -u)/ai.gemini.agy-dot-coordinator"`
  - Linux: `systemctl --user start ai.gemini.agy-dot-coordinator.service`
- **Inspect Logs**:
  - macOS: `tail -f ~/Library/Logs/ai.gemini.agy-dot-coordinator.log`
  - Linux: `journalctl --user -u ai.gemini.agy-dot-coordinator.service -f`
