---
description: Steer work on $USER's Ubuntu machine (jeff-ubuntu) via SSH (mirrors /extended-library:mac but targets the Linux box). Auto-detects local-vs-remote and chains via the MacBook when needed.
type: execution
execution_mode: immediate
---

# /linux [request]

Steer work on jeff-ubuntu (LAN-only Ubuntu 24.04 box at 192.168.254.128) via SSH.

Read `~/.claude/skills/linux-remote/SKILL.md` then execute the user's request on jeff-ubuntu.

The connection is `ssh jeff-ubuntu` (passwordless alias, configured in `~/.ssh/config` — see SKILL.md setup section if not present).

## Auto-detect

- Running locally on jeff-ubuntu (uname == Linux, hostname/IP matches the box) — no SSH needed, execute commands directly.
- Running on the MacBook or any other machine — SSH into jeff-ubuntu first via the passwordless `jeff-ubuntu` alias.
- Chained ops (e.g. "do X on jeff-ubuntu then ship from the MacBook") — SSH to jeff-ubuntu, then chain `ssh macbook` from inside the Linux box. Note: Linux → MacBook SSH requires the MacBook-side alias or user/pass context, so this direction is rarer than MacBook → jeff-ubuntu.

Execute the task directly — do not hand commands back to the user to run manually.
