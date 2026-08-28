---
name: launchd
description: Create, install, and operate reliable macOS launchd jobs with safe environment handling.
---

# macOS launchd Job Installation Standards

## Purpose
This skill defines the canonical standards for creating, installing, and managing background launchd agents on macOS. Sourcing interactive environments under launchd is notoriously tricky; this skill ensures that jobs execute reliably in the exact same environment as an interactive terminal.

---

## Canonical Design Tenets

### 1. Zero-Environment Plist Principle
- **Do NOT** hardcode environment variables, secret tokens (like `GH_TOKEN`), or custom paths inside the plist `<key>EnvironmentVariables</key>` block. Plists are static, hard to update, and leak credentials in version control.
- **Instead**, the plist must execute a lightweight wrapper bash script using the system shell (`/bin/bash`).

### 2. Sourced Shell Profile Sourcing Protocol
The wrapper script MUST source the user's interactive profile (`~/.bash_profile` or `~/.bashrc`) to inherit all aliases, custom exports, and PATH updates.
- Sourcing must be wrapped in `set +u` / `set -u` to prevent launchd aborts from unbound optional variables.
```bash
if [[ -f ~/.bash_profile ]]; then
  set +u
  source ~/.bash_profile 2>/dev/null || true
  set -u
fi
```

### 3. Graceful Dependency Fallbacks
- Sourced wrapper scripts must actively resolve dynamic credentials (like `GH_TOKEN`) at runtime via system commands (e.g. `gh auth token`) to ensure the agent never crashes due to expired or missing static exports.
- Use absolute paths for all system binaries (`/bin/launchctl`, `/usr/bin/id`, `/usr/bin/install`).

### 4. Clean Re-installation Protocol
- Always execute a clean `bootout` of the existing agent before bootstrapping the new one to prevent duplicate registrations or "Service already exists" launchctl errors.
```bash
/bin/launchctl bootout "gui/$(/usr/bin/id -u)/${LABEL}" 2>/dev/null || true
/bin/launchctl bootstrap "gui/$(/usr/bin/id -u)" "${PLIST_DST}"
```
- **Never** use the deprecated `launchctl load` or `launchctl unload` commands.

---

## The Wrapper Script Template

Every launchd job wrapper script should match the following standard:

```bash
#!/usr/bin/env bash
# com.user.job-wrapper.sh — Auto-generated launchd wrapper
set -euo pipefail

# 1. Source user profile with nounset temporarily disabled to avoid interactive-var crashes
if [[ -f ~/.bash_profile ]]; then
  set +u
  source ~/.bash_profile 2>/dev/null || true
  set -u
fi

# 2. Dynamic credential resolution fallbacks
if [[ -z "${GH_TOKEN:-}" ]]; then
  GH_TOKEN="$(/usr/bin/env gh auth token 2>/dev/null || true)"
fi
export GH_TOKEN

# 3. Standard execution logs
LOG_PREFIX="[job-name]"
echo "$LOG_PREFIX Starting job at $(date)"

# 4. Invoke target command with full environment
exec "$@"
```

---

## Plist Template

Keep the plist minimal. It should only define scheduling and logging targets:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.hermes.schedule.job-name</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>@HOME@/.hermes/scripts/job-wrapper.sh</string>
    <string>arg1</string>
    <string>arg2</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>2</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>@HOME@/Library/Logs/ai.hermes.schedule.job-name.log</string>
  <key>StandardErrorPath</key>
  <string>@HOME@/Library/Logs/ai.hermes.schedule.job-name.error.log</string>
  <key>WorkingDirectory</key>
  <string>@HOME@/.hermes</string>
</dict>
</plist>
```

---

## 6-Step Installation Checklist
1. Write the target script (the worker).
2. Write the sourced wrapper script.
3. Write the minimal plist template file **using `@HOME@` placeholders** (not hardcoded paths).
4. **Commit the template to the owning repo** (e.g. `~/.hermes/launchd/<label>.plist`, `~/.config/mcp-daemon/`). A plist with no repo template is orphaned — cleanup scripts cannot find or remove it. This step is mandatory before install.
5. Execute `launchctl bootout` on any existing registration first.
6. Bootstrap the rendered plist (with `@HOME@` substituted to `$HOME`) and verify with `launchctl list | grep <label>`.

> **Why step 4 is mandatory**: In 2026-06-09, `launchd/ai.hermes.prod.plist` was never committed. `install-launchagents.sh` gates orphan-plist cleanup on that template existing — so `ai.hermes.gateway.plist` (orphan) survived every deploy for months.
