---
name: linux-remote
description: "Steering work on $USER's Ubuntu machine (jeff-ubuntu) via SSH. Use when asked to run commands, install software, check services, or manage files on the Ubuntu box."
---

# Linux Remote — jeff-ubuntu SSH Steering

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


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

## Agent submission and response proof — mandatory

For every instruction sent to an interactive agent, including initial launches,
resumed sessions, follow-ups, and existing composer drafts:

1. Resolve the exact tmux pane or cmux surface and verify its foreground application
   and screen before typing. Capture a baseline and retain the intended instruction.
   Never send agent prose to a shell, trust dialog, or unknown foreground process.
   Preserve unrelated composer text and queued work.
2. Submit explicitly using the application's current controls. In Codex, a busy
   composer displaying “tab to queue message” requires Tab to queue; an idle
   composer uses Enter to submit. Send text and the submit key in separate calls
   after verifying the text arrived. Inspect other CLIs' actual controls rather
   than assuming Enter submits. Initial prompt argv still requires response proof.
3. Re-read after submission. Text remaining in the editable composer is NOT
   submitted. A queue entry proves only QUEUED, not received or acted upon.
   Do not resend queued instructions or interrupt active work merely to obtain
   acknowledgment. Inspect the queue and transcript before retrying uncertain
   submissions to avoid duplicate execution.
4. Wait for a fresh agent-authored response attributable to that instruction.
   Request a brief acknowledgment naming the task or a unique dispatch marker
   when composing new instructions. Verify chronology against the baseline and
   inspect the actual transcript when screen output is ambiguous. Echoed input,
   prompts, spinners, process liveness, transport exit status, READY/RESUMED, and
   queue entries are never substitutes for an agent response.
5. Echo the actual response excerpt into the calling/main terminal and the
   user-facing update, labeled with host, session/pane or surface, observation time,
   and instruction or dispatch marker. Redact secrets. Report ACKNOWLEDGED only
   when that response exists; acknowledgment proves delivery, not task completion.
   Validate completion claims against the requested artifacts or checks.
6. Continue monitoring with bounded asynchronous waits and regular progress
   updates. Set a response deadline appropriate to the active job. If it expires
   or the agent fails, report QUEUED/UNCONFIRMED/BLOCKED with the observed reason,
   preserve the instruction, and perform scoped recovery. Never claim success
   from submitted text alone.

This contract applies through SSH, tmux, cmux, and terminals such as Warp.

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
