---
name: mac-remote
description: "Steer work on a remote macOS host ($MAC_REMOTE_HOST) via SSH. Use when asked to run commands, install software, check services, or manage files on the Mac from a Linux host or another machine. Auto-detects whether running locally on the Mac (no SSH) or remotely (SSH into the Mac first)."
---

# Mac Remote — macOS SSH Steering

Mirror of `/linux` (`$LINUX_REMOTE_HOST`), but targeting a Mac. Runs from any machine that can reach the Mac's SSH port.

## Configuration

This skill targets the macOS host named by `MAC_REMOTE_HOST` (an SSH alias from
`~/.ssh/config`). There is no default host; stop if it is unset:

```bash
: "${MAC_REMOTE_HOST:?MAC_REMOTE_HOST not configured: SSH alias of your macOS host. Example: export MAC_REMOTE_HOST=mymac}"
MAC_TS="${MAC_REMOTE_HOST_TS:-$MAC_REMOTE_HOST}"   # optional tailnet alias
```

A companion Linux host, when a step needs one, is `LINUX_REMOTE_HOST` (see
[linux-remote](../linux-remote/SKILL.md)). The repository's
`docs/portability-env-vars.md` defines both names.

## Connection

| Field | Value |
|---|---|
| **Host alias** | `$MAC_REMOTE_HOST` (after the `~/.ssh/config` setup below; examples use `mymac`) |
| **Hostname (LAN)** | `<mac-hostname>.local` or `<mac-lan-ip>` |
| **Hostname (Tailscale)** | `<mac-tailscale-ip>` (works off-LAN via Tailscale) |
| **User** | `<mac-user>` |
| **Key** | `~/.ssh/<mac-key>` |
| **SSH port** | 22 (default) |
| **OS** | macOS; check with `ssh "$MAC_REMOTE_HOST" 'sw_vers; uname -m'` |

## Off-LAN fallback: Tailscale, then Slack

If `ssh "$MAC_REMOTE_HOST"` times out or is refused (off the LAN, or the LAN link is down), use the tailnet alias instead when one is configured:

```bash
ssh "$MAC_TS" '<command>'
```

`MAC_REMOTE_HOST_TS` names a real `~/.ssh/config` stanza on the SSHing machine (same `IdentityFile` as the LAN alias), so it is a drop-in replacement for `$MAC_REMOTE_HOST` in every command in this skill. `ssh` does **not** fail over automatically; try the LAN alias first, then fall back to the tailnet alias. Re-verify with `tailscale status` if it ever seems dead.

If both aliases fail, see [cross-machine-ssh-tier](../cross-machine-ssh-tier/SKILL.md) for the Tier 3 messaging-gateway fallback and its debugging caveats (OAuth-scope-vs-connection, bot-message filtering) — that skill is the shared source of truth for this whole ladder, used identically by `linux-remote`, `linux-mirror`, and `mac-mirror`.

## Detect local-vs-remote automatically

Before SSHing, check if you're already on the Mac:

```bash
if [[ "$(uname -s)" == "Darwin" && "$(hostname -s)" == "<mac-hostname>" ]]; then
  echo "local Mac — no SSH needed"
else
  ssh "$MAC_REMOTE_HOST" '...'  # remote
fi
```

Or simpler — try `uname -s` to detect. On the Mac locally, `Darwin`; on a Linux host or GitHub Actions ubuntu-latest, `Linux`.

## Invoking Dot on the Mac

When a task needs the Mac's Dot assistant, run `dot.sh` on the Mac and let that
machine resolve its own account: an explicit `--account` wins, then the Mac's
machine-local `DOT_ACCOUNT`, then its `~/.config/dot/config.json` default. Do
not inherit or forward the Linux caller's `DOT_ACCOUNT` accidentally; an
explicit per-invocation `--account <name>` is the only cross-machine override.
Apply the installed [Dot skill](../dot/SKILL.md), including its independent
profile and session rules, for all sends, reads, and recovery actions.

## Setup on a remote machine (one-time, e.g. on your Linux host)

```bash
# 1. Generate an SSH key on the remote machine (if none exists)
ssh-keygen -t ed25519 -f ~/.ssh/<mac-key> -N ""

# 2. Copy the public key to the Mac's authorized_keys
ssh-copy-id -i ~/.ssh/<mac-key>.pub <mac-user>@<mac-lan-ip>
# (prompts for the Mac account password once)

# 3. Add the alias to ~/.ssh/config (the name you export as MAC_REMOTE_HOST)
cat >> ~/.ssh/config <<'EOF'

Host mymac
    HostName <mac-lan-ip>
    User <mac-user>
    IdentityFile ~/.ssh/<mac-key>
    StrictHostKeyChecking no
EOF
```

## How to run commands

Once the alias is set up, use `ssh "$MAC_REMOTE_HOST" '<command>'` for one-liners:

```bash
ssh "$MAC_REMOTE_HOST" 'launchctl list | grep <label>'                 # check launchd
ssh "$MAC_REMOTE_HOST" 'brew list | grep <formula>'                    # check Homebrew installs
ssh "$MAC_REMOTE_HOST" 'tail -20 ~/Library/Logs/<service>-stderr.log'  # tail launchd logs
ssh "$MAC_REMOTE_HOST" 'command -v <tool>'                             # locate an installed tool
```

For multi-line scripts, use heredoc:

```bash
ssh "$MAC_REMOTE_HOST" 'bash -s' << 'EOF'
brew update
brew install <formula>
command -v <tool>
EOF
```

## Agent submission and response proof — mandatory

Read and follow the shared [submission and response contract](../linux-remote/SKILL.md#agent-submission-and-response-proof--mandatory) for every Mac agent launch and follow-up, locally or over SSH. For cmux, verify the exact surface and its CLI controls; sending text alone is not submission. Echo a fresh, attributable agent response into the calling terminal before claiming delivery.

## sudo over SSH

```bash
ssh -t "$MAC_REMOTE_HOST" 'sudo -- id -u'
```

Let `sudo` prompt in the interactive SSH session. Replace `id -u` with the
required command. Never embed a password in a command, script, or stdin stream.

## File transfer

```bash
scp /local/file "$MAC_REMOTE_HOST":/remote/path                     # local → remote
scp "$MAC_REMOTE_HOST":/remote/file /local/path                     # remote → local
rsync -avz /local/ "$MAC_REMOTE_HOST":/remote/                      # sync directory
```

## Chaining: Mac → Linux host

After SSHing into the Mac, you can chain to the Linux host from there. This is useful when you need the Mac's tooling (e.g. `colima`, `docker`, `cmux`) to act on Linux-host artifacts:

```bash
: "${LINUX_REMOTE_HOST:?LINUX_REMOTE_HOST not configured: SSH alias of your Linux host. Example: export LINUX_REMOTE_HOST=mylinux}"
ssh "$MAC_REMOTE_HOST" "ssh $LINUX_REMOTE_HOST 'systemctl --user restart <service>'"
```

Note: the Linux alias must also exist in the Mac's `~/.ssh/config` and be reachable from the Mac (LAN or Tailscale); otherwise skip chaining.

## Common tasks

| Task | Command |
|------|---------|
| Check a launchd job | `ssh "$MAC_REMOTE_HOST" 'launchctl list \| grep <label>'` |
| Tail a job log | `ssh "$MAC_REMOTE_HOST" 'tail -n 20 <log-path>'` |
| Restart a service | Resolve the installed service label from its owner documentation, then use the `launchctl` procedure there |
| Check colima VM | `ssh "$MAC_REMOTE_HOST" 'limactl list'` |
| Check disk | `ssh "$MAC_REMOTE_HOST" 'df -h /'` |
| Tail launchd stderr | `ssh "$MAC_REMOTE_HOST" 'tail -n 30 ~/Library/Logs/<service>-stderr.log'` |
| Install / upgrade a skill in `~/.claude/skills` | `scp -r /path/to/skill "$MAC_REMOTE_HOST":~/.claude/skills/<skill>/` |

## Reverse direction: Linux host → Mac (this skill's primary use case)

To install a skill (`<skill>`, including its `scripts/`) on the Mac from another machine:

```bash
# Option A: copy from the local install
ssh "$MAC_REMOTE_HOST" 'mkdir -p ~/.claude/skills/<skill>'
scp -r ~/.claude/skills/<skill>/. "$MAC_REMOTE_HOST":~/.claude/skills/<skill>/

# Option B: pull from GitHub into a temporary clone on the Mac
ssh "$MAC_REMOTE_HOST" 'tmp=$(mktemp -d) && git clone <skills-repo-url> "$tmp/skills" && \
  mkdir -p ~/.claude/skills/<skill> && \
  cp -r "$tmp/skills/.claude/skills/<skill>/." ~/.claude/skills/<skill>/'
```

## Caveats

- **LAN-only by default**: `<mac-lan-ip>` only reachable when both machines are on the same LAN. Use the Tailscale fallback above for off-LAN access — the `MAC_REMOTE_HOST_TS` alias already includes its `IdentityFile`, no `-i` needed; `-i` is only required if you connect to the raw Tailscale IP directly instead of through that alias.
- **macOS SSH keychain**: First SSH attempt may prompt for keychain access; use `ssh-add --apple-use-keychain ~/.ssh/<mac-key>` to cache.
- **No headless Docker**: Macs commonly use colima for Docker; running Docker there requires the colima VM to be Running.
- **macOS sandboxing**: Some `~/Library/...` paths may need Full Disk Access for the terminal app to read them.
- **sudo prompts on macOS**: Touch ID may be available on the physical Mac; over SSH use the interactive `ssh -t` prompt above.
- **Always prefer SSH over VNC/Screen Sharing**: SSH is scriptable + auditable + doesn't steal focus.
