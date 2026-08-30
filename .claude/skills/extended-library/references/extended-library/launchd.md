---
description: Create and install a proper macOS launchd job using the canonical /launchd skill
type: skill
execution_mode: immediate
---

# /launchd

Create and install a macOS launchd job.

Read `~/.claude/skills/launchd/SKILL.md` and execute it.

## What it does

| Step | Action |
|------|--------|
| 1 | Generate a lightweight wrapper script sourcing `~/.bash_profile`/`~/.bashrc` with `set +u` safety |
| 2 | Write a clean, minimal plist file in `~/Library/LaunchAgents/` (calendar or interval trigger) |
| 3 | Reinstall cleanly via `launchctl bootout` then `launchctl bootstrap` |
| 4 | Verify logs and launchd registration status |
