---
name: soak
description: Soak clock protocol — a timed stability test where the clock only counts uptime and a crash is recorded as data, not a reset
---

# Soak clock protocol

A **soak** is a timed stability test. The clock only counts uptime. A crash IS data — record elapsed time, do not reset.

## Why a soak is more than "leave it running and see"

- A 24h soak that ends in a crash is **more valuable** than a 24h soak that doesn't, because the crash tells you the config is unsafe.
- A 24h soak that doesn't crash is **almost worthless** if the longest historical crash interval for the same config is 72h.
- A soak is only meaningful when `elapsed > longest_known_crash_interval` for the same config. Until then, "no crash yet" is consistent with "haven't waited long enough."

## Target-time rules (use the smallest valid number)

| Rule | Why |
|---|---|
| `target_hours >= longest_known_crash_interval` | Otherwise you're not testing what you think |
| `target_hours >= 1.5x current uptime of any passing config` | Otherwise you're not actually testing the change |
| 5 consecutive `target_hours` without a crash | Single-pass is one data point. 5 passes is a trend. |
| Crash-free for `target_hours` + crash-free for `2x target_hours` (long-soak) | Catches latent bugs that take longer to manifest |

## What "the box is up" means

A soak is "in progress" only when ALL of:

1. `uptime_seconds >= (now - soak_started_at).total_seconds()` — kernel didn't reboot
2. `pstore_fingerprint == pstore_fingerprint_at_start` — no new panic dumps
3. The system hasn't lost track of the soak file (the JSON sidecar still exists)

If any of these is false, the soak has FAILED at `elapsed = (now - soak_started_at).total_seconds() - boot_time_seconds`. Record the elapsed time, do not reset.

## State location

- Per-soak JSON: `~/.local/share/soak/<name>.json`
- Watchdog log: `~/.local/share/soak/<name>.log` (one line per `watch` invocation)
- Bead link: bead id stored in the JSON; bead description carries start/target/status

## Bead convention

A soak bead:
- Title: `soak: <name>`
- Type: `task`
- Description: `target=Xh / started=YYYY-MM-DD / longest-known-crash=Yh / config="<description>"`
- Status: `in_progress` while running, `closed` on pass/fail
- Resolution on close: include elapsed-at-fail or elapsed-at-pass

## Watchdog (cron / systemd timer)

Run every 5 min. On each tick:

```bash
for f in ~/.local/share/soak/*.json; do
  soakctl watch "$(basename "$f" .json)"
done
```

`soakctl watch` checks the three "is the box up" conditions, updates the bead status, and appends a log line. Do not silently swallow a failure — surface it.

## Anti-patterns

- **Don't reset the clock on a crash.** A failed soak is the most valuable data. Record elapsed time and start a NEW soak with a different config.
- **Don't compare across configs.** A 72h soak with runners on is not comparable to a 72h soak with runners off. Each config needs its own baseline.
- **Don't trust a single pass.** 5 consecutive passes is the start of a trend. 1 pass is one data point.
- **Don't declare pass before target hours.** `uptime > target_hours` is necessary, not sufficient — also need `pstore_fingerprint unchanged`.
- **Don't run unattended-upgrades during a soak** unless the soak is specifically testing that. Auto-upgrades change the kernel/driver mid-test and invalidate the result.
- **Don't start a soak while pstore has unread dumps.** A crash you haven't analyzed is unknown state; reading them is part of starting the next soak cleanly.

## Pre-soak checklist (run before `soak start`)

1. Read pstore: `sudo cat /var/lib/systemd/pstore/<latest>/*/dmesg.txt` — confirm you've analyzed any prior crash
2. Record pstore fingerprint: `find /var/lib/systemd/pstore -type f | sort | md5sum`
3. Confirm config is what you think: e.g. `systemctl is-enabled jleechanorg-org-runners.service`, `uname -r`, `nvidia-smi --query-gpu=driver_version`
4. Confirm unattended-upgrades is paused OR blacklisted for kernel/nvidia: `grep -E "Package-Blacklist|kernel|nvidia" /etc/apt/apt.conf.d/50unattended-upgrades /etc/apt/apt.conf.d/51*`
5. Pick `target_hours >= max(longest_known_crash, 24)` — explain the choice in the bead description
