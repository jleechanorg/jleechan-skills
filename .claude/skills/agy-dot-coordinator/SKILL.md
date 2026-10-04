---
name: agy-dot-coordinator
description: Periodic background launchd agent running the Antigravity CLI (agy) to coordinate with the ChatGPT dot assistant, reminding it to prioritize and drive work on its cloud computer environment with stateful debouncing and draft safety.
---

# Antigravity Dot Cloud Coordinator (`agy-dot-coordinator`)

## Purpose
`agy-dot-coordinator` provides an autonomous macOS `launchd` background agent that periodically invokes the Antigravity CLI (`agy`) to inspect the user's central ChatGPT coordinator ("the dot"). It:
1. Queries the dot about in-flight work and active priorities.
2. Reminds the dot to continually drive work in priority order using its cloud computer environment.
3. Directs the dot to provision and configure its cloud computer with all necessary tools, dependencies, and environment configurations, and strictly prefer driving execution there.
4. Uses stateful debouncing and composer draft protection to prevent conversational spam and preserve peer drafts.

---

## Architectural Principles & Invariants

### 1. Zero-Environment Plist Principle
- The launchd plist template contains no secrets, tokens, or custom environment variables.
- The plist executes `/bin/bash` with the canonical sourced wrapper script `scripts/agy-dot-coordinator-wrapper.sh`.

### 2. Sourced Shell Profile Protocol
- The wrapper script sources the user's interactive profile (`~/.bash_profile`) under `set +u` / `set -u` so that `PATH` (including `~/.local/bin`, NVM Node, and Aside CLI) is available under launchd without TTY crashes.
- Never sources `~/.zshrc` from `/bin/bash`.

### 3. Stateful Debounce & Idle Detection
- Launchd wakes every 15 minutes (`StartInterval: 900`).
- To prevent spamming 96 messages per day into the dot's conversation, the worker evaluates `~/.local/state/ai.gemini.agy-dot-coordinator/state.json`.
- A 2-hour cooldown (7200 seconds) is enforced between reminders. If the dot is actively working (`Thinking`, `Working`, `Searching`), the check-in is skipped.

### 4. Composer Contention & Draft Safety
- Child calls to `dot.sh` use `DOT_WAIT_SECS=60` and `DOT_RETRY_SECS=15` to prevent hanging on peer drafts.
- If an unsubmitted peer draft is present in the composer (`DOT_DRAFT_PRESENT`), `agy` gracefully logs the busy state and exits 0 to avoid crash loops.
- Delivery verification (`DOT_SENT_VERIFIED`) ensures messages are confirmed in the conversation DOM before updating the last-sent timestamp.

### 5. Concurrency Locking
- Mutual exclusion is enforced via `flock -n` on `/tmp/ai.gemini.agy-dot-coordinator.lock` to prevent overlapping runs if a tick runs long.

---

## Component Layout

```
.claude/skills/agy-dot-coordinator/
├── SKILL.md                                           # This guide
├── launchd/
│   └── ai.gemini.agy-dot-coordinator.plist            # Plist template with @HOME@ placeholder
└── scripts/
    ├── agy-dot-coordinator-wrapper.sh                 # Sourced environment & lock wrapper
    ├── agy-dot-coordinator-worker.sh                  # Gated worker dispatching agy -p
    └── install-launchagent.sh                         # Canonical launchd installer script
```

---

## Installation & Lifecycle

### Quick Install
To install or update the LaunchAgent:
```bash
~/.claude/skills/agy-dot-coordinator/scripts/install-launchagent.sh
```
This script:
1. Renders `launchd/ai.gemini.agy-dot-coordinator.plist` to `~/Library/LaunchAgents/ai.gemini.agy-dot-coordinator.plist` substituting `@HOME@`.
2. Cleanly boots out any existing registration (`/bin/launchctl bootout`).
3. Bootstraps the agent into the user GUI domain (`/bin/launchctl bootstrap`).
4. Verifies registration with `launchctl list | grep ai.gemini.agy-dot-coordinator`.

### Operational Commands & Inspection
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
- **Manual Launchd Kickstart**:
  ```bash
  /bin/launchctl kickstart -k "gui/$(id -u)/ai.gemini.agy-dot-coordinator"
  ```
- **View Live Logs**:
  ```bash
  tail -f ~/Library/Logs/ai.gemini.agy-dot-coordinator.log
  tail -f ~/Library/Logs/ai.gemini.agy-dot-coordinator.error.log
  ```

### Uninstallation
```bash
/bin/launchctl bootout "gui/$(id -u)/ai.gemini.agy-dot-coordinator" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/ai.gemini.agy-dot-coordinator.plist"
rm -f /tmp/ai.gemini.agy-dot-coordinator.lock
```
