---
name: mac-remote
description: "Steer work on $USER's MacBook via SSH. Use when asked to run commands, install software, check services, or manage files on the MacBook from jeff-ubuntu or another machine. Auto-detects whether running locally on MacBook (no SSH) or remotely (SSH into MacBook first)."
---

# Mac Remote — MacBook SSH Steering

Mirror of `/linux` (jeff-ubuntu), but targeting the MacBook. Runs from any machine that can reach the MacBook's SSH port.

## Connection

| Field | Value |
|---|---|
| **Host alias (recommended)** | `macbook` (after `~/.ssh/config` setup below) |
| **Hostname (LAN)** | `jeffreys-macbook-pro.local` or `192.168.254.199` |
| **Hostname (Tailscale)** | `100.67.70.24` (works off-LAN via Tailscale) |
| **User** | `$USER` |
| **Key (from MacBook)** | `~/.ssh/id_jeff_ubuntu` (same key used by jeff-ubuntu's reverse direction) |
| **SSH port** | 22 (default) |
| **OS** | macOS 14+ (Sonoma/Sequoia), aarch64 |

## Off-LAN fallback: Tailscale, then Slack

If `ssh macbook` times out or is refused (off home LAN, or the LAN link is just down), use the dedicated Tailscale alias instead — proven working 2026-09-16/17, including a double-hop from jeff-ubuntu with the LAN link fully down:

```bash
ssh macbook-ts '<command>'
```

`macbook-ts` is a real `~/.ssh/config` stanza on the SSHing machine (same `IdentityFile` as the LAN alias) — no manual `-i`/IP lookup needed, it's a drop-in replacement for `macbook` in every command in this skill. `ssh macbook` does **not** fail over automatically; try the LAN alias first, fall to `-ts` on failure. Re-verify with `tailscale status | grep macbook` if it ever seems dead.

If both the LAN alias and `macbook-ts` fail, see [cross-machine-ssh-tier](../cross-machine-ssh-tier/SKILL.md) for the Tier 3 messaging-gateway fallback and its debugging caveats (OAuth-scope-vs-connection, bot-message filtering) — that skill is the shared source of truth for this whole ladder, used identically by `linux-remote`, `linux-mirror`, and `mac-mirror`.

## Detect local-vs-remote automatically

Before SSHing, check if you're already on the MacBook:

```bash
if [[ "$(uname -s)" == "Darwin" && "$(hostname -s)" == "jeffreys-macbook-pro" ]]; then
  echo "local MacBook — no SSH needed"
else
  ssh macbook '...'  # remote
fi
```

Or simpler — try `uname -s` to detect. On MacBook locally, `Darwin`; on jeff-ubuntu, `Linux`; on GitHub Actions ubuntu-latest, `Linux`.

## Setup on a remote machine (one-time, e.g. on jeff-ubuntu)

```bash
# 1. Generate an SSH key on the remote machine (if none exists)
ssh-keygen -t ed25519 -f ~/.ssh/id_macbook -N ""

# 2. Copy the public key to MacBook's authorized_keys
ssh-copy-id -i ~/.ssh/id_macbook.pub $USER@192.168.254.199
# (prompts for $USER's MacBook password once)

# 3. Add the macbook alias to ~/.ssh/config
cat >> ~/.ssh/config <<'EOF'

Host macbook
    HostName 192.168.254.199
    User $USER
    IdentityFile ~/.ssh/id_macbook
    StrictHostKeyChecking no
EOF
```

## How to run commands

Once the alias is set up, use `ssh macbook '<command>'` for one-liners:

```bash
ssh macbook 'launchctl list | grep ezgha'                            # check launchd
ssh macbook 'brew list | grep ez-gh-actions'                         # check Homebrew installs
ssh macbook 'cat ~/Library/Logs/ezgha-launchd-stderr.log | tail -20' # tail launchd logs
ssh macbook 'ls -la ~/.local/share/worldarchitect-runners/'          # runtime mirror
```

For multi-line scripts, use heredoc:

```bash
ssh macbook 'bash -s' << 'EOF'
brew update
brew install ez-gh-actions
ls -la /opt/homebrew/bin/ezgha
EOF
```

## sudo with known password

```bash
expect -c "
spawn ssh macbook sudo <command>
expect {
  \"password\" { send \"<password>\r\"; exp_continue }
  eof
}
"

# OR pipe via stdin:
echo '<password>' | ssh macbook 'sudo -S <command>'
```

## File transfer

```bash
scp /local/file macbook:/remote/path                                # local → remote
scp macbook:/remote/file /local/path                                # remote → local
rsync -avz /local/ macbook:/remote/                                 # sync directory
```

## Chaining: MacBook → jeff-ubuntu

After SSHing into the MacBook, you can chain to jeff-ubuntu from there. This is useful when you need the MacBook's tooling (e.g. `colima`, `docker`, `cmux`) to act on jeff-ubuntu artifacts:

```bash
ssh macbook 'ssh jeff-ubuntu "systemctl --user restart ezgha"'
```

Note: jeff-ubuntu must be reachable from the MacBook. From the home LAN, it's `192.168.254.128`. From off-LAN, use Tailscale or skip chaining.

## Common tasks

| Task | Command |
|------|---------|
| Check ezgha status | `ssh macbook '~/.cargo/bin/ezgha status \| grep -E "managed\|registered"'` |
| Check fleet-watchdog log | `ssh macbook 'tail -n 20 /tmp/ezgha-watchdog.log'` |
| Restart ezgha | `ssh macbook 'launchctl kickstart -k gui/$(id -u)/org.jleechanorg.ezgha'` |
| Check colima VM | `ssh macbook 'limactl list'` |
| Check disk | `ssh macbook 'df -h /'` |
| Tail launchd stderr | `ssh macbook 'tail -n 30 ~/Library/Logs/ezgha-launchd-stderr.log'` |
| Install / upgrade `~/.claude/skills` from jeff-ubuntu | `scp /path/to/skill macbook:~/.claude/skills/skill-name/` |

## Reverse direction: jeff-ubuntu → MacBook (this skill's primary use case)

To install a skill (e.g. `/ezgha-watchdog`) on the MacBook from jeff-ubuntu:

```bash
# Option A: copy from jeff-ubuntu's local clone
ssh macbook 'mkdir -p ~/.claude/skills/ezgha-watchdog'
scp ~/.claude/skills/ezgha-watchdog/SKILL.md macbook:~/.claude/skills/ezgha-watchdog/
scp ~/.claude/skills/ezgha-watchdog/scripts/ezgha-fleet-watchdog.sh macbook:~/.claude/skills/ezgha-watchdog/scripts/

# Option B: pull from GitHub
ssh macbook 'git clone https://github.com/$GITHUB_REPOSITORY.git /tmp/your-project.com && \
  mkdir -p ~/.claude/skills/ezgha-watchdog && \
  cp -r /tmp/your-project.com/.claude/skills/ezgha-watchdog/* ~/.claude/skills/ezgha-watchdog/'
```

## Caveats

- **LAN-only by default**: `192.168.254.199` only reachable when both machines on the same home LAN. Use the Tailscale fallback above for off-LAN access — `ssh macbook-ts` already includes its `IdentityFile`, no `-i` needed; `-i` is only required if you connect to the raw Tailscale IP directly instead of through that alias.
- **macOS SSH keychain**: First SSH attempt may prompt for keychain access; use `ssh-add --apple-use-keychain ~/.ssh/id_macbook` to cache.
- **No headless Docker**: MacBook uses colima for Docker; running Docker on the MacBook requires colima VM to be Running (the `ezgha-fleet-watchdog` script auto-starts it).
- **macOS sandboxing**: Some `~/Library/...` paths may need Full Disk Access for the terminal app to read them.
- **sudo prompts on macOS**: Touch ID prompt instead of password on physical Mac; over SSH use `expect` with password.
- **Always prefer SSH over VNC/Screen Sharing**: SSH is scriptable + auditable + doesn't steal focus.