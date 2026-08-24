---
description: Steer work on $USER's MacBook via SSH (mirrors /linux but targets the MacBook). Auto-detects local-vs-remote and chains to jeff-ubuntu when needed.
type: skill
execution_mode: immediate
---

# /mac [request]

Steer work on $USER's MacBook via SSH.

Read `~/.claude/skills/mac-remote/SKILL.md` then execute the user's request on the MacBook.

The connection is `ssh macbook` (passwordless alias, configured in `~/.ssh/config` — see SKILL.md setup section if not present).

## Auto-detect

- Running locally on the MacBook (uname == Darwin, hostname == jeffreys-macbook-pro) — no SSH needed, execute commands directly.
- Running on jeff-ubuntu or any other machine — SSH into the MacBook first.
- Chained ops (e.g. "install this on Mac and then deploy to jeff-ubuntu") — SSH to MacBook, then chain `ssh jeff-ubuntu` from inside the Mac.

## Cloud Build bastion pre-dispatch probe (Mac only)

Before running any Cloud Build / `/super` dispatch from the MacBook, run:

```bash
bash ~/.hermes/scripts/cloud-build-bastion-watchdog.sh --notify
```

If it exits non-zero, **abort the dispatch** with a clear error and point the operator at:

```bash
bash ~/superpowers-cloud-build-main/skills/cloud-build/scripts/cb-client-setup.sh
# Paste fresh enrollment code at the prompt
```

The watchdog catches silently-rotated host keys and pruned `authorized_keys` before they cause a cryptic mid-dispatch SSH error. The watchdog runs every 12h via launchd (`~/Library/LaunchAgents/ai.hermes.schedule.cloud-build-bastion-watchdog.plist`) so manual pre-dispatch probing is belt-and-suspenders.

Execute the task directly — do not hand commands back to the user to run manually.
