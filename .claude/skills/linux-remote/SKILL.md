---
name: linux-remote
description: "Steering work on $USER's Ubuntu machine (jeff-ubuntu) via SSH. Use when asked to run commands, install software, check services, or manage files on the Ubuntu box."
---

# Linux Remote — jeff-ubuntu SSH Steering

## Connection

```bash
ssh jeff-ubuntu          # alias in ~/.ssh/config → $USER@192.168.254.128
```

- **Host:** `jeff-ubuntu` / `192.168.254.128` (LAN only)
- **User:** `$USER`
- **Key:** `~/.ssh/id_jeff_ubuntu` (passwordless, no `-i` flag needed via alias)
- **OS:** Ubuntu 24.04, kernel 6.17, x86_64
- **sudo password:** stored in user's head — prompt user if needed, or use `expect` if already known in context

## Off-LAN fallback: Tailscale, then Slack

If `ssh jeff-ubuntu` times out or is refused (off home LAN, traveling, or the LAN link is just down — happens occasionally even at home), use the dedicated Tailscale alias instead — proven working 2026-09-16/17, including with the LAN link fully down:

```bash
ssh jeff-ubuntu-ts '<command>'
```

`jeff-ubuntu-ts` is a real `~/.ssh/config` stanza (same `IdentityFile` as the LAN alias) — no manual `-i`/IP lookup needed, it just works as a drop-in replacement for `jeff-ubuntu` in every command in this skill. `ssh jeff-ubuntu` does **not** fail over to it automatically; try the LAN alias first (fast when it works), fall to `-ts` on failure. Re-verify the IP with `tailscale status | grep ubuntu` if it ever seems dead — Tailscale IPs are stable per-device but not guaranteed forever.

If both the LAN alias and `jeff-ubuntu-ts` fail, see [cross-machine-ssh-tier](../cross-machine-ssh-tier/SKILL.md) for the Tier 3 messaging-gateway fallback and its debugging caveats (OAuth-scope-vs-connection, bot-message filtering) — that skill is the shared source of truth for this whole ladder, used identically by `mac-remote`, `linux-mirror`, and `mac-mirror`.

## How to run commands

Always use `ssh jeff-ubuntu '<command>'` for one-liners:

```bash
ssh jeff-ubuntu 'sudo apt update && sudo apt install -y <pkg>'
ssh jeff-ubuntu 'systemctl status <service>'
ssh jeff-ubuntu 'cat /var/log/syslog | tail -50'
```

For multi-line scripts, pipe via heredoc:

```bash
ssh jeff-ubuntu 'bash -s' << 'EOF'
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
EOF
```

## sudo with known password

If the user's password is in context (currently: ask user), use `expect`:

```bash
expect -c "
spawn ssh jeff-ubuntu sudo <command>
expect {
  \"password\" { send \"<password>\r\"; exp_continue }
  eof
}
"
```

Or pass via stdin:
```bash
echo '<password>' | ssh jeff-ubuntu 'sudo -S <command>'
```

## File transfer

```bash
scp /local/file jeff-ubuntu:/remote/path      # local → remote
scp jeff-ubuntu:/remote/file /local/path      # remote → local
rsync -avz /local/ jeff-ubuntu:/remote/       # sync directory
```

## Common tasks

| Task | Command |
|------|---------|
| Check disk | `ssh jeff-ubuntu 'df -h'` |
| Running services | `ssh jeff-ubuntu 'systemctl list-units --state=running'` |
| Installed packages | `ssh jeff-ubuntu 'dpkg -l \| grep <pkg>'` |
| Tail a log | `ssh jeff-ubuntu 'sudo journalctl -fu <service>'` |
| Advice Review | `ssh jeff-ubuntu '~/.claude/commands/advice.md'` (or execute `~/.claude/skills/advice/SKILL.md`) |
| Web Advice Review | `ssh jeff-ubuntu '~/.claude/commands/web-advice.md'` (or execute `~/.claude/skills/web-advice/SKILL.md`) |
| Reboot | `ssh jeff-ubuntu 'sudo reboot'` (warn user first) |

## Caveats

- Machine is LAN-only (192.168.254.x) — not reachable when off same network; use the Tailscale fallback above when off-LAN
- If SSH fails, check if machine is on via `ping 192.168.254.128`, then try Tailscale before assuming it's down
- RustDesk (peer ID `406402544`) is the fallback for GUI access if SSH is down
- Always prefer SSH over RustDesk for CLI work — RustDesk CLI steering is not possible headlessly on macOS without Accessibility permission
