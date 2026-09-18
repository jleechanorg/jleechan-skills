---
name: linux-remote
description: "Steering work on $USER's Ubuntu machine (jeff-ubuntu) via SSH. Use when asked to run commands, install software, check services, or manage files on the Ubuntu box. Resolves the connection via the shared SSH-first-then-Tailscale tier ladder (see cross-machine-ssh-tier)."
---

# Linux Remote — jeff-ubuntu SSH Steering

## Connection

```bash
ssh jeff-ubuntu          # alias in ~/.ssh/config → $USER@192.168.254.128
```

- **Host:** `jeff-ubuntu` / `192.168.254.128` (LAN only — Tier 1 default)
- **Tailscale IP:** look up live via `tailscale status | awk '/ubuntu/{print $1}'` (last known `100.115.209.119`) — **never hardcode**; Tier 2 fallback when off-LAN
- **User:** `$USER`
- **Key (Tier 1):** `~/.ssh/id_jeff_ubuntu` (passwordless via alias)
- **Key (Tier 2 explicit):** `-i ~/.ssh/id_jeff_ubuntu` (the ladder sets this automatically when the alias is refused)
- **OS:** Ubuntu 24.04, kernel 6.17, x86_64
- **sudo password:** stored in user's head — prompt user if needed, or use `expect` if already known in context

For the rationale behind Tier 1 (LAN alias) → Tier 2 (Tailscale + explicit `-i`) → Tier 3 (Slack `#hermes-pc`), key naming (`id_jeff_ubuntu` vs `id_macbook`), Tailscale-IP re-verification, and the OAuth-scopes-reinstall gotcha, see [`cross-machine-ssh-tier`](../cross-machine-ssh-tier/SKILL.md).

## Resolve the connection (shared tier ladder)

Replace `ssh jeff-ubuntu '<command>'` with the shared ladder so Tier 2 (Tailscale) is tried automatically when Tier 1 (LAN) is refused. After the block below runs, `$SSH_TARGET` is `jeff-ubuntu` (Tier 1) or `jleechan@<tailscale-ip>` (Tier 2); `$SSH_ARGS` carries the explicit `-i` key when Tier 2 was used. If both tiers fail, `$SSH_TARGET` is empty and you fall through to the Slack `#hermes-pc` hand-off in the shared skill.

```bash
# Peer = jeff-ubuntu (LAN alias `jeff-ubuntu`, Tailscale peer name pattern
# `ubuntu`, per-direction key `id_jeff_ubuntu`). The ladder itself lives in
# cross-machine-ssh-tier/SKILL.md — paste/inline as needed.
PEER_LAN_ALIAS="jeff-ubuntu"
PEER_TS_PATTERN="ubuntu"
PEER_KEY="$HOME/.ssh/id_jeff_ubuntu"
# (the ladder itself is defined in cross-machine-ssh-tier/SKILL.md — paste/inline as needed;
#  see "The ladder" section there)
```

Then run the actual command:

```bash
ssh "${SSH_ARGS[@]}" "$SSH_TARGET" '<command>'
```

The ladder's Tier 1 default is the `jeff-ubuntu` alias — so simple existing one-liners like `ssh jeff-ubuntu 'df -h'` keep working unchanged when on the same LAN.

## How to run commands

Always use `ssh jeff-ubuntu '<command>'` for one-liners (Tier 1 default):

```bash
ssh jeff-ubuntu 'sudo apt update && sudo apt install -y <pkg>'
ssh jeff-ubuntu 'systemctl status <service>'
ssh jeff-ubuntu 'cat /var/log/syslog | tail -50'
```

For multi-line scripts, pipe via heredoc:

```bash
ssh jeff-ubuntu 'bash -s' << 'INNER_EOF'
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
INNER_EOF
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

`scp` also follows the `~/.ssh/config` alias, so the one-liners above work whenever `ssh jeff-ubuntu` does. Off-LAN, `scp` will error — fall back to Tier 2 / Tier 3 per the shared ladder, or pre-resolve a Tailscale target like the mac-remote skill does (`scp /local/file "jleechan@$(tailscale status | awk '/ubuntu/{print $1}'):/remote/path"` with the explicit `-i ~/.ssh/id_jeff_ubuntu`).

## Common tasks

| Task | Command |
|------|---------|
| Check disk | `ssh jeff-ubuntu 'df -h'` |
| Running services | `ssh jeff-ubuntu 'systemctl list-units --state=running'` |
| Installed packages | `ssh jeff-ubuntu 'dpkg -l | grep <pkg>'` |
| Tail a log | `ssh jeff-ubuntu 'sudo journalctl -fu <service>'` |
| Advice Review | `ssh jeff-ubuntu '~/.claude/commands/advice.md'` (or execute `~/.claude/skills/advice/SKILL.md`) |
| Web Advice Review | `ssh jeff-ubuntu '~/.claude/commands/web-advice.md'` (or execute `~/.claude/skills/web-advice/SKILL.md`) |
| Reboot | `ssh jeff-ubuntu 'sudo reboot'` (warn user first) |

## Caveats

- Machine is LAN-only (192.168.254.x) by default — Tier 1 covers that. Off-LAN, the shared ladder auto-escalates to Tailscale (Tier 2) or Slack `#hermes-pc` (Tier 3) — see [`cross-machine-ssh-tier`](../cross-machine-ssh-tier/SKILL.md).
- If the entire ladder fails (Tier 1 and Tier 2 both refuse), check if the machine is on via `ping 192.168.254.128` to disambiguate LAN silence from `sshd` being down.
- RustDesk (peer ID `406402544`) is the fallback for GUI access if SSH and Tailscale are both down.
- Always prefer SSH over RustDesk for CLI work — RustDesk CLI steering is not possible headlessly on macOS without Accessibility permission.
