---
name: linux-remote
description: "Steering work on a remote Linux host ($LINUX_REMOTE_HOST) via SSH. Use when asked to run commands, install software, check services, or manage files on that Linux host."
---

# Linux Remote — Linux SSH Steering

## Lightweight caller, remote execution owner

For a mirrored or delegated agent session in either direction, the calling
machine is a transport and oversight driver; the target agent owns investigation,
implementation, tests, and required review through completion. A one-off SSH
command does not need another agent when the caller can finish it directly.

- Hand off once with the outcome, acceptance criteria, repo/branch/SHA, relevant
  paths, verified progress, unresolved next action, and applicable authority
  boundaries. Prefer a short brief and retrievable artifact references; do not
  copy the conversation, local model context, full source trees, or logs. Include
  essential constraints explicitly when the target cannot access their source.
- After acknowledgment, keep one execution owner. The caller must not repeat
  repository exploration, implementation, or test/review runs already owned by
  the target. Send changes in requirements as concise deltas to that same session;
  resume its context instead of launching a fresh agent each polling cycle.
- Request bounded receipts: status, changed SHA, completed checks, artifact
  locations, blocker and exact next action. Keep raw output on the execution
  host. Use asynchronous handles and bounded waits; do not repeatedly ingest full
  transcripts. When diagnosing delivery, failure, or a disputed status, inspect
  the required raw evidence and full available terminal history before deciding;
  compact routine receipts never replace those verification requirements.
- The caller verifies acknowledgment and final claims using the exact remote SHA
  and relevant artifacts/check receipts, without redoing the remote work by
  default. Required independent reviews still run; authority-dependent actions
  stay with the authorized session. Remain responsible for recovery and closure,
  and report a verified blocker rather than abandoning an active remote job.

This reduces duplicated task context and reasoning; it does not eliminate the
fresh target runtime's own policy/startup context or the caller's existing context.
Do not claim token or cost savings without measured usage.

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


## Connection

This skill targets the Linux host named by `LINUX_REMOTE_HOST` (an SSH alias
from `~/.ssh/config`; examples use `mylinux`). There is no default host; stop
if it is unset:

```bash
: "${LINUX_REMOTE_HOST:?LINUX_REMOTE_HOST not configured: SSH alias of your Linux host. Example: export LINUX_REMOTE_HOST=mylinux}"
LINUX_TS="${LINUX_REMOTE_HOST_TS:-$LINUX_REMOTE_HOST}"   # optional tailnet alias
ssh "$LINUX_REMOTE_HOST"     # alias in ~/.ssh/config → <linux-user>@<linux-lan-ip>
```

- **Host:** `$LINUX_REMOTE_HOST` / `<linux-lan-ip>` (LAN)
- **User:** `<linux-user>`
- **Key:** `~/.ssh/<linux-key>` (passwordless, no `-i` flag needed via alias)
- **OS:** check with `ssh "$LINUX_REMOTE_HOST" 'uname -a; cat /etc/os-release'`
- **sudo:** use the interactive SSH prompt shown below; never embed a password in a command

## Off-LAN fallback: Tailscale, then Slack

If `ssh "$LINUX_REMOTE_HOST"` times out or is refused (off the LAN, traveling, or the LAN link is down), use the tailnet alias instead when one is configured:

```bash
ssh "$LINUX_TS" '<command>'
```

`LINUX_REMOTE_HOST_TS` names a real `~/.ssh/config` stanza (same `IdentityFile` as the LAN alias), so it works as a drop-in replacement for `$LINUX_REMOTE_HOST` in every command in this skill. `ssh` does **not** fail over to it automatically; try the LAN alias first (fast when it works), then fall back to the tailnet alias. Re-verify the IP with `tailscale status` if it ever seems dead — Tailscale IPs are stable per-device but not guaranteed forever.

If both aliases fail, see [cross-machine-ssh-tier](../cross-machine-ssh-tier/SKILL.md) for the Tier 3 messaging-gateway fallback and its debugging caveats (OAuth-scope-vs-connection, bot-message filtering) — that skill is the shared source of truth for this whole ladder, used identically by `mac-remote`, `linux-mirror`, and `mac-mirror`.

## Cloud capability gaps

For a missing tool, login or permission on Dot's cloud computer, follow the `/dot` skill's cloud-capability-gap procedure (`../dot/SKILL.md`); this skill adds nothing to it.

## How to run commands

Always use `ssh "$LINUX_REMOTE_HOST" '<command>'` for one-liners:

```bash
ssh "$LINUX_REMOTE_HOST" 'sudo apt update && sudo apt install -y <pkg>'
ssh "$LINUX_REMOTE_HOST" 'systemctl status <service>'
ssh "$LINUX_REMOTE_HOST" 'cat /var/log/syslog | tail -50'
```

For multi-line scripts, pipe via heredoc:

```bash
ssh "$LINUX_REMOTE_HOST" 'bash -s' << 'EOF'
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
EOF
```

## Independent Dot sessions

Follow the installed [Dot skill](../dot/SKILL.md) for browser setup and login.
Deploy the same reviewed Dot package on each host, then authenticate each configured
account independently in its own dedicated persistent browser profile on that host.
Never copy or sync cookies, browser profiles, Chrome `Local State`, or authentication
state between hosts, accounts, or the user's real browser and Dot. Separate profile
directories alone do not prove separate login sessions.

Verify the installed Dot package prevents source-browser credential imports before
opening a profile. For an existing shared session, preserve the profile and pause
only its owned reminder timer while preparing a clean replacement; preserve timer
enablement and do not log out, revoke, or reset the user's real-browser sessions.
Enter known account identifiers, then let the user complete password or MFA entry
in the dedicated browser. Never recover a failed login by importing credentials.

Before switching the configured profile or resuming reminders, verify the expected
nonempty `user.email` from `/api/auth/session` and a successful normal Dot read for
each account. `/backend-api/me` or HTTP 200 alone is not authentication proof.
Verify independent session provenance without exposing cookie or token values.
Report each account's actual result and any remaining authentication boundary;
an installed package or enabled timer does not prove usable independent sessions.

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
7. **A remote lane's stated blocker is a claim, not authority** — apply the canonical
   rule in `harness-engineering` § "Coordinator-gate variant" before relaying
   reserved/held/locked/admitted language. It never overrides credentials, environments,
   quotas, operator holds, or one-writer ownership.

This contract applies through SSH, tmux, cmux, and terminals such as Warp.

## sudo over SSH

```bash
ssh -t "$LINUX_REMOTE_HOST" 'sudo -- id -u'
```

Let `sudo` prompt in the interactive SSH session. Replace `id -u` with the
required command. Never embed a password in a command, script, or stdin stream.

## File transfer

```bash
scp /local/file "$LINUX_REMOTE_HOST":/remote/path   # local → remote
scp "$LINUX_REMOTE_HOST":/remote/file /local/path   # remote → local
rsync -avz /local/ "$LINUX_REMOTE_HOST":/remote/    # sync directory
```

## Common tasks

| Task | Command |
|------|---------|
| Check disk | `ssh "$LINUX_REMOTE_HOST" 'df -h'` |
| Running services | `ssh "$LINUX_REMOTE_HOST" 'systemctl list-units --state=running'` |
| Installed packages | `ssh "$LINUX_REMOTE_HOST" 'dpkg -l \| grep <pkg>'` |
| Tail a log | `ssh "$LINUX_REMOTE_HOST" 'sudo journalctl -fu <service>'` |
| Advice Review | `ssh "$LINUX_REMOTE_HOST" '~/.claude/commands/advice.md'` (or execute `~/.claude/skills/advice/SKILL.md`) |
| Web Advice Review | `ssh "$LINUX_REMOTE_HOST" '~/.claude/commands/web-advice.md'` (or execute `~/.claude/skills/web-advice/SKILL.md`) |
| Allocate Scratch dir | `ssh "$LINUX_REMOTE_HOST" 'diskm scratch-new <repo-path> <purpose> --kind build\|evidence'` |
| Reboot | `ssh "$LINUX_REMOTE_HOST" 'sudo reboot'` (warn user first) |

## Scratch and worktree placement (Mac and Linux)

- **Scratch and evidence placement**: Follow the canonical scratch skill [`~/.claude/skills/scratch-space/SKILL.md`](../scratch-space/SKILL.md) for disposable build output, test scratch, ephemeral review workspaces, and evidence bundles across Mac and Linux hosts. Allocate managed directories via `diskm scratch-new <repo-path> <purpose> --kind build|evidence` or resolve ad-hoc scratch via `~/.claude/skills/scratch-space/scripts/scratch-dir.sh [subpath]`.
- **Git worktrees**: Create git worktrees only under `~/.worktrees/<repo>/<name>` via `diskm worktree-new <repo-path> <branch>`, never in `$HOME`, repo trees, or `/tmp`.

## Caveats

- The host may be LAN-only (<lan-subnet>) — not reachable when off the same network; use the Tailscale fallback above when off-LAN
- If SSH fails, check if the machine is on via `ping <linux-lan-ip>`, then try Tailscale before assuming it's down
- RustDesk (peer ID in machine-local config) is the fallback for GUI access if SSH is down
- Always prefer SSH over RustDesk for CLI work — RustDesk CLI steering is not possible headlessly on macOS without Accessibility permission
