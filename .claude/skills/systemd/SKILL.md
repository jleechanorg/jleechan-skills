---
name: systemd
description: "Linux systemd Job Installation Standards — create, install, and manage background systemd user-mode units and timers on Linux"
---

# Linux systemd Job Installation Standards

## Purpose

Linux sibling of `/launchd` (macOS-only). Defines the canonical standards
for creating, installing, and managing background systemd **user-mode**
units + timers on Linux. User mode is the right scope for hermes/dark-factory
jobs because it needs no root, runs in the user's session, and persists
across logout/reboot when `loginctl enable-linger` is on.

> Cross-platform note: a job that must run on BOTH macOS and Linux ships
> paired plist + unit templates (see `daemon/launchd/ai.dark-factory.af-tick.plist.template`
> and `daemon/systemd/ai.dark-factory.daemon.service.template` as the
> precedent). Pick whichever host matches the operator's machine; do not
> introduce a third abstraction layer.

---

## Canonical Design Tenets

### 1. Zero-Environment Unit Principle
- **Do NOT** hardcode environment variables, secret tokens (like `GH_TOKEN`),
  or custom `PATH` entries inside the unit's `[Service]` block as inline
  `Environment=KEY=value` lines. Units are static, hard to update, and leak
  credentials in version control.
- **Instead**, the unit must invoke a wrapper script (`systemd-wrapper.sh`)
  using `/bin/bash`, and secrets come from `EnvironmentFile=` pointing at
  a config file with `0600` perms outside the repo (e.g.
  `~/.config/systemd/user/jleechanbrain-deploy-tokens.conf`).
- A unit may declare non-secret defaults inline (e.g. `HOME=%h`,
  `PATH=/usr/bin:/bin`) but anything credential-bearing goes through the
  wrapper + `EnvironmentFile=`.

### 2. Sourced Shell Profile Sourcing Protocol
The wrapper script MUST source the user's interactive profile
(`~/.bash_profile` or `~/.bashrc`) to inherit all aliases, custom exports,
and PATH updates — the same way `launchd-wrapper.sh` does on macOS.
- Sourcing must be wrapped in `set +u` / `set -u` to prevent aborts from
  unbound optional variables in strict-mode bashrcs.

```bash
if [[ -f ~/.bash_profile ]]; then
  set +u
  source ~/.bash_profile 2>/dev/null || true
  set -u
fi
```

### 3. Graceful Dependency Fallbacks
- Sourced wrapper scripts must actively resolve dynamic credentials (like
  `GH_TOKEN`) at runtime via system commands (e.g. `gh auth token`) when
  `EnvironmentFile=` is empty or the token is missing.
- Use absolute paths for all system binaries (`/bin/systemctl`,
  `/usr/bin/loginctl`, `/usr/bin/id`).
- **Always `UnsetEnvironment=GITHUB_TOKEN GH_TOKEN`** in the unit so the
  keyring auth (via `gh auth login --web` + `gh auth token`) wins over a
  stale shell-exported token. See PR #206 for the rationale; this is
  non-negotiable for jobs that touch `gh api`.

### 4. Clean Re-installation Protocol
- Always execute a clean `systemctl --user disable --now <unit>` before
  re-enabling, to prevent duplicate timers / "Unit already exists" errors.
- After writing the rendered unit, run `systemctl --user daemon-reload`
  before `enable --now`. This is the Linux equivalent of launchd's
  `bootout` + `bootstrap`.

```bash
/bin/systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
/bin/systemctl --user daemon-reload
/bin/systemctl --user enable --now "$UNIT_NAME"
```

- **Never** use the deprecated `systemctl --user reload` for unit
  registration changes. `daemon-reload` is the right call.

---

## The Wrapper Script Template

Every systemd job wrapper script should match the launchd-wrapper standard
so a script that runs under one scheduler runs identically under the other:

```bash
#!/usr/bin/env bash
# systemd-wrapper.sh — bridge script for dark-factory systemd user units.
#
# systemd --user services run with a minimal PATH (/usr/bin:/bin) and no
# sourced shell init. dark-factory tick + audit scripts depend on
# homebrew/conda tooling (br, gh, sqlite3, python3, callpath, jq) and on
# the user's git/SSH configuration. This wrapper sources the user's
# interactive login environment (with set +u / -u guards around the source
# so a strict-mode bashrc doesn't break us) before exec'ing the target
# script.
#
# Usage: systemd-wrapper.sh /absolute/path/to/target.sh [args...]
#
# Conventions:
#   - First arg is the absolute path of the script to run.
#   - All subsequent args are forwarded.
#   - Exit code is the target script's exit code.

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 /absolute/path/to/target.sh [args...]" >&2
    exit 64
fi

TARGET="$1"
shift

if [ ! -x "$TARGET" ]; then
    echo "[systemd-wrapper] target not executable: $TARGET" >&2
    exit 66
fi

# 1. Source user profile with nounset temporarily disabled.
if [[ -f ~/.bash_profile ]]; then
    set +u
    source ~/.bash_profile 2>/dev/null || true
    set -u
fi

# 2. Dynamic credential resolution fallbacks.
if [[ -z "${GH_TOKEN:-}" ]]; then
    GH_TOKEN="$(/usr/bin/env gh auth token 2>/dev/null || true)"
fi
export GH_TOKEN

# 3. Explicit PATH so br / gh / sqlite3 / python3 resolve without the
#    bash_profile source — defensive against minimal PATH= environments.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# 4. Forward to the actual target.
exec "$TARGET" "$@"
```

> **Why this exists in addition to bash_profile sourcing**: bash_profile may
> not exist on a fresh Linux box (`bash` is not the default login shell on
> many distros). The explicit `PATH=` line + `gh auth token` fallback makes
> the wrapper work even with zero user customization. The launchd-wrapper
> pattern intentionally leaves bash_profile sourcing to launchd-wrapper.sh
> on macOS; on Linux we do it in the same wrapper because the default shell
> init files are less predictable.

---

## Service Unit Template

Keep the unit minimal. It should only declare runtime type, working
directory, the wrapper script, and logging targets — never inline secrets:

```ini
[Unit]
Description=Dark Factory <job-name>
Documentation=https://github.com/jleechanorg/dark-factory
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=@REPO@
ExecStart=/bin/bash @HOME@/.hermes/scripts/systemd-wrapper.sh @REPO@/daemon/<job>.sh
# Strip shell-exported GitHub tokens so keyring auth wins (PR #206).
UnsetEnvironment=GITHUB_TOKEN GH_TOKEN
# Pulls in HERMES_SLACK_BOT_TOKEN etc. from the file at 0600; the leading
# `-` makes the file optional — unit starts even if it doesn't exist yet.
EnvironmentFile=-@HOME@/.config/systemd/user/jleechanbrain-deploy-tokens.conf
# Cap runtime so a stuck process can't pin the unit forever.
TimeoutStartSec=600
# Do NOT set Restart= for Type=oneshot timers — the timer fires it again
# on its own cadence. Restart=on-failure would re-run inside the same
# OnCalendar slot, violating the launchd ThrottleInterval contract that
# the macOS twin plist already documents.
StandardOutput=append:@HOME@/Library/Logs/dark-factory/<job>.log
StandardError=append:@HOME@/Library/Logs/dark-factory/<job>.err.log

[Install]
WantedBy=default.target
```

For **long-running services** (not timer-fired oneshots) — the precedent is
`daemon/systemd/ai.dark-factory.daemon.service.template`:

```ini
[Service]
Type=notify
NotifyAccess=main
WorkingDirectory=@REPO@
ExecStart=@REPO@/daemon/target/release/daemon
Restart=on-failure
RestartSec=10s
WatchdogSec=7200s
KillSignal=SIGINT
TimeoutStopSec=30s
Environment=HOME=@HOME@
Environment=PATH=@HOME@/.local/bin:@HOME@/.cargo/bin:/usr/bin:/bin
StandardOutput=append:@HOME@/Library/Logs/dark-factory/rust-daemon.out.log
StandardError=append:@HOME@/Library/Logs/dark-factory/rust-daemon.err.log
```

---

## Timer Unit Template

systemd timers are **separate** from the service they fire (vs launchd's
single-plist model). The timer unit declares cadence; the service unit
declares what runs. Wire them via `Unit=<service-name>.service` in the
timer:

```ini
[Unit]
Description=Schedule <job-name>.service daily at 03:00 local
# Mirrors the launchd plist `ai.dark-factory.<job>` cadence. 03:00 chosen
# because it's a maintenance window, not urgent.

[Timer]
# Daily at 03:00:00 local time. Use `*-*-* HH:MM:00` form for fixed times,
# `OnCalendar=daily` shorthand for midnight UTC (NOT what you want — UTC
# drift breaks the "03:00 local" assumption).
OnCalendar=*-*-* 03:00:00
# Catch up missed runs (e.g. machine was asleep at fire time).
Persistent=true
Unit=<job-name>.service
# Randomized delay so multiple timers set to the same minute don't
# thunder-herd; defaults to 0 if unset.
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
```

For **sub-minute polling** (Linux-only vs launchd's `StartInterval=N`):

```ini
[Timer]
OnBootSec=60
OnUnitActiveSec=60
# Don't use both — pick the cadence shape that matches the job.
```

`StartCalendarInterval` (launchd) ⇄ `OnCalendar` (systemd) cheat-sheet:

| launchd | systemd |
|---|---|
| `<integer>240</integer>` (StartInterval) | `OnUnitActiveSec=240` |
| `<key>Hour</key><integer>3</integer>` | `OnCalendar=*-*-* 03:00:00` |
| `<key>Minute</key><integer>0</integer>` | (folded into OnCalendar) |
| `<key>Weekday</key><integer>1</integer>` | `OnCalendar=Mon *-*-* 00:00:00` |
| `<key>ThrottleInterval</key><integer>60</integer>` | (use `Restart=` policy on the service instead) |
| `<key>KeepAlive</key><true/>` | `WantedBy=default.target` + `Restart=always` |
| `<key>RunAtLoad</key><true/>` | `[Install] WantedBy=default.target` |

---

## 6-Step Installation Checklist

1. Write the target script (the worker) under `daemon/scripts/<job>.sh`.
2. Write the sourced wrapper script (`systemd-wrapper.sh`) to
   `~/.hermes/scripts/systemd-wrapper.sh` and `chmod 0755` it.
3. Write the minimal unit template files using `@HOME@` / `@REPO@`
   placeholders (not hardcoded paths), commit them under
   `daemon/systemd/<unit>.service.template` and
   `daemon/systemd/<unit>.timer.template`.
4. **Commit the templates to the owning repo.** A unit with no repo template
   is orphaned — cleanup scripts cannot find or remove it. This step is
   mandatory before install (same rule as `/launchd` step 4).
5. Ensure linger is on so user services survive logout/reboot:
   `loginctl enable-linger $USER` (one-time; idempotent).
6. Render the template(s), write to `~/.config/systemd/user/<unit>`,
   `systemctl --user daemon-reload`, then `enable --now` (timer only —
   `enable --now` on the service alone does not start the cadence).
   Verify with `systemctl --user list-timers --no-pager | grep <job>`.

> **Why step 5 is mandatory on Linux**: macOS launchd starts agents on
> demand regardless of session state. systemd --user services stop when the
> user logs out *unless* `linger=yes` is set for the user. Without linger,
> a daily timer that fires at 03:00 will simply never fire on a headless
> box where no one is logged in at 03:00.

---

## Existing patterns to mirror

| Pattern | Precedent | Notes |
|---|---|---|
| Daily 03:00 audit timer | `~/.config/systemd/user/jleechanclaw-slack-thread-auto-park.{timer,service}` | Best template for a G10–G13 audit timer |
| Sub-minute polling | `~/.config/systemd/user/dark-factory-merge-guard.{timer,service}` | `OnUnitActiveSec=60s` for the 60s merge-guard sweep |
| Long-running daemon | `daemon/systemd/ai.dark-factory.daemon.service.template` | `Type=notify` + `WatchdogSec=7200` — the right shape when the job isn't timer-fired |
| Installer | `daemon/systemd/install-systemd-user.sh` | `--dry-run`, `--render-only`, `--uninstall` flags; expands `@HOME@`/`@REPO@`; verifies linger |
| Wrapper | `daemon/launchd/launchd-wrapper.sh` | Linux twin lives at `~/.hermes/scripts/systemd-wrapper.sh` |

---

## Common pitfalls

- **Forgot `--user`**: `systemctl enable foo.service` without `--user`
  tries to write to `/etc/systemd/system/` and fails on a non-root shell.
  Always `systemctl --user` for hermes/dark-factory jobs.
- **Forgetting `daemon-reload`**: editing a unit file and re-enabling
  without `daemon-reload` keeps the old unit in effect. Always reload
  between edits.
- **`Type=oneshot` + `Restart=on-failure`**: triggers re-run inside the
  same OnCalendar slot, breaking the cadence contract. Either pick
  `Type=simple` + `Restart=` (long-running) or `Type=oneshot` + `Restart=no`
  (timer-fired).
- **`OnCalendar=daily`**: shorthand for `*-*-* 00:00:00` **UTC**, not local
  time. Almost always wrong for "every day at 03:00 my time." Use
  `*-*-* 03:00:00` for explicit local time.
- **PATH not set in unit**: `--user` services inherit the user's
  `~/.config/environment.d/*.conf` on some distros but not others. The
  wrapper script's explicit `export PATH=...` line is the only
  cross-distro guarantee.
- **Linger off**: timer silently never fires on a headless box. Run
  `loginctl show-user $USER -p Linger --value` and expect `yes`.

---

## Verification

```bash
# Linger on?
loginctl show-user "$USER" -p Linger --value     # must print "yes"

# Timer registered + next-fire time correct?
systemctl --user list-timers --no-pager | grep <job>

# Last run succeeded?
systemctl --user status <job>.service --no-pager

# Manual fire (debug only)
systemctl --user start <job>.service
journalctl --user -u <job>.service -n 50

# Wrapper is sourcing bash_profile correctly?
bash -x ~/.hermes/scripts/systemd-wrapper.sh /bin/true   # trace it
```

---

## Related

- `/launchd` — macOS twin; same tenets, different scheduler
- `daemon/systemd/install-systemd-user.sh` — canonical installer for the
  dark-factory daemon service; pair it with sibling templates when adding
  new units (e.g. `ai.dark-factory.fe-audit.{service,timer}.template`)
- `~/.claude/CLAUDE.md` "Credentials and authentication" — never store
  tokens in `.env`; `EnvironmentFile=` pointing at 0600 files outside the
  repo is the Linux equivalent