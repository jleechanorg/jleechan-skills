---
name: cross-machine-ssh-tier
description: "Reusable SSH-first-then-Tailscale transport ladder for reaching peer machines (macbook, jeff-ubuntu). Tier 1 is LAN SSH via a `~/.ssh/config` alias; Tier 2 is Tailscale SSH with explicit `-i ~/.ssh/id_<peer>` key, looked up live (never hardcoded); Tier 3 is Slack `#hermes-pc` for when both are down. Used by `mac-remote`, `linux-remote`, `mac-mirror`, `linux-mirror`."
---

# Cross-machine SSH tier ladder

Single source of truth for the "try LAN, then Tailscale, then Slack" transport escalation. Re-used verbatim by:

- [`mac-remote`](../mac-remote/SKILL.md) and [`linux-remote`](../linux-remote/SKILL.md) — ad hoc SSH steering
- [`mac-mirror`](../mac-mirror/SKILL.md) and [`linux-mirror`](../linux-mirror/SKILL.md) — hand off a committed branch + tmux resume

Keep this ladder in sync across all four consumers. If you change the tier definitions or the fallback policy, update the four consumers in the same commit.

## Tier definitions

| Tier | Transport | When it applies | Failure mode |
|---|---|---|---|
| **1** | LAN SSH via `~/.ssh/config` alias (`macbook` / `jeff-ubuntu`) | Both machines on the same home LAN | `Connection refused` when off-LAN or peer's `sshd` is down |
| **2** | Tailscale SSH, explicit `-i ~/.ssh/id_<peer>` key, target IP looked up live via `tailscale status` | Tier 1 refused (off-LAN) and Tailscale mesh is healthy | `tailscaled` not running on either side, peer offline, or the explicit key is missing/has the wrong mode |
| **3** | Slack `#hermes-pc` (channel `C0BDAMWQQJK`) | Tier 1 and Tier 2 both unreachable | Only human-typed posts trigger it; bot/app-attributed messages are silently dropped by design (`SLACK_ALLOW_BOTS=none`). OAuth token must include `channels:history`, `im:history`, `app_mentions:read` (reinstall the Slack App to the workspace after manifest changes — see Tier 3 caveat below). |

## Why a `~/.ssh/config` alias does NOT fail over to Tier 2 automatically

`Host macbook` in `~/.ssh/config` resolves a single `HostName` (e.g. `192.168.254.199`). SSH has no concept of "try LAN first, fall back to Tailscale"; when the LAN IP is unreachable, you get `Connection refused` and the connection ends. You cannot set two `HostName` entries and have SSH retry them — you must do the tier selection in your own script (see ladder below) and **then** call `ssh` with the resolved target + key.

## The ladder

Parameterize by peer. Two valid values for this repo's fleet:

- `macbook` → LAN alias `macbook`, Tailscale peer name pattern `macbook`, key `~/.ssh/id_macbook`
- `jeff-ubuntu` → LAN alias `jeff-ubuntu`, Tailscale peer name pattern `ubuntu`, key `~/.ssh/id_jeff_ubuntu`

After this block runs, `$SSH_TARGET` holds either `macbook` / `jeff-ubuntu` (Tier 1) or `jleechan@<tailscale-ip>` (Tier 2), or is empty (Tier 3 — fall through to your surrounding code's `if [ -n "$SSH_TARGET" ]` guard).

```bash
# Inputs:
#   PEER_LAN_ALIAS   — e.g. "macbook" or "jeff-ubuntu"
#   PEER_TS_PATTERN  — awk pattern for `tailscale status`, e.g. "macbook" or "ubuntu"
#   PEER_KEY         — absolute key path, e.g. "$HOME/.ssh/id_macbook"
# Outputs:
#   SSH_ARGS   — extra args for `ssh` (Tier 2 sets `-i <key>`; Tier 1 leaves empty)
#   SSH_TARGET — destination string, or empty if both Tier 1 and Tier 2 failed
SSH_ARGS=()
SSH_TARGET="$PEER_LAN_ALIAS"   # Tier 1 default: the LAN alias

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
  echo "SSH_OK via Tier 1 (LAN alias)"
else
  # Tier 2 — Tailscale SSH (off-LAN fallback). Re-verify the IP every call;
  # never hardcode it. last-known example: macbook=100.67.70.24,
  # jeff-ubuntu=100.115.209.119, but those change with tailscale key rotations.
  TS_IP=$(tailscale status | awk "/${PEER_TS_PATTERN}/{print \$1}")
  SSH_ARGS=(-i "$PEER_KEY")
  SSH_TARGET="jleechan@${TS_IP}"
  if ssh "${SSH_ARGS[@]}" -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
    echo "SSH_OK via Tier 2 (Tailscale)"
  else
    SSH_TARGET=""   # both Tier 1 and Tier 2 failed — caller must handle Tier 3
  fi
fi
```

Concrete invocations:

```bash
# Reaches macbook — note the key is `id_macbook`, NOT `id_jeff_ubuntu`
PEER_LAN_ALIAS="macbook"
PEER_TS_PATTERN="macbook"   # matches "jeffreys-macbook-pro" in `tailscale status`
PEER_KEY="$HOME/.ssh/id_macbook"

# Reaches jeff-ubuntu — key is `id_jeff_ubuntu`
PEER_LAN_ALIAS="jeff-ubuntu"
PEER_TS_PATTERN="ubuntu"    # matches "jeff-ubuntu" or any peer with "ubuntu" in the name
PEER_KEY="$HOME/.ssh/id_jeff_ubuntu"
```

## Tier 3 — Slack `#hermes-pc` fallback

When `$SSH_TARGET` is empty after the Tier 1/2 ladder, both LAN and Tailscale SSH are unreachable. Post the full hand-off context (repo path, branch, commit SHA, exact next-command) to channel `C0BDAMWQQJK` (`#hermes-pc`). The peer machine's Hermes gateway will pick it up via Socket Mode and continue the work there. Channel/JID details:

- Channel: `#hermes-pc` (channel ID `C0BDAMWQQJK`, "Hermes-PC takeover / runner health")
- The MacBook's default Hermes gateway (app_id `A0AESRKA7L3`, bot `hermes`) is also reactive in this channel — confirmed repeatedly (5+ times) during the linux-mirror Tier-3 debugging session (2026-09-16); every human-typed message posted there got an immediate reply from this Mac's own gateway, even while jeff-ubuntu's separate `hermespc` bot was broken.

### Tier 3 caveats

- **Only human-typed messages trigger a response.** Messages posted via a bot-associated token (including Slack API calls using an OAuth-app-issued user token) get silently dropped by design (`SLACK_ALLOW_BOTS=none`). If this tier ever goes quiet, check OAuth scopes-vs-reinstall status before assuming a connection/socket problem — that's exactly what cost hours the first time.
- **OAuth scope mismatches after a manifest edit.** First-time debugging on 2026-09-15 found jeff-ubuntu's Hermes gateway did NOT react to messages in `#hermes-pc` — a test message sat unanswered for 5+ minutes. Root cause: the bot's OAuth token was missing `channels:history`, `im:history`, `app_mentions:read` because the Slack App was never reinstalled to the workspace after those scopes were added to its manifest. Socket Mode itself was healthy (which is why the connection looked fine while messages were silently dropped). **Fix:** reinstall the app via Slack API dashboard → OAuth & Permissions → "Reinstall to \<workspace\>". This reissues the bot token with the currently-declared scopes actually granted. Verify with a genuine end-to-end round-trip and check `journalctl --user -u hermes-gateway.service` on jeff-ubuntu (the systemd journal is more reliable than `~/.hermes/logs/agent.log` for this level of detail).
- **No shared context with your current session.** The receiving gateway has no idea what you've already tried or what state you're in. Post a complete, self-contained message — repo + branch + commit + exact next-command — addressed generally (no special mention syntax is needed, plain human-typed messages work). Do not assume it knows the prior turns of your Claude/Cursor session.
- **Address to the channel, not a bot.** No `@hermes` mention syntax is required (and is in fact filtered out by the same bot-detection rule if it originates from an API token).

## Key selection (`id_jeff_ubuntu` vs `id_jeff_macbook`)

Same physical machine (e.g. the MacBook) and same `jleechan` user, but the per-direction SSH key is named after the *peer direction*:

- Connecting MacBook ← jeff-ubuntu: key on jeff-ubuntu is `~/.ssh/id_macbook` (named for the peer it talks to), authorized in MacBook's `~/.ssh/authorized_keys`.
- Connecting jeff-ubuntu ← MacBook: key on MacBook is `~/.ssh/id_jeff_ubuntu` (named for the peer it talks to), authorized in jeff-ubuntu's `~/.ssh/authorized_keys`.

This naming lets each peer list its authorized_keys by file name to see which direction the key belongs to. The ladder above encodes the right key by peer — do not swap them.

## IP re-verification pattern

Never hardcode a Tailscale IP in committed code. Even "last known" values go stale on tailscale key rotations or mesh reconfiguration. Use:

```bash
# All live Tailscale peers (one IP per line, in priority order)
tailscale status | awk '/peer/{print $1}'

# A specific peer (case-sensitive substring match against the peer hostname)
tailscale status | awk "/${PEER_TS_PATTERN}/{print \$1}"
```

A single peer usually has exactly one IP; if a peer rotates keys, both the old and new IPs may show briefly — `awk` returns the first match, which is the active one. If the pattern matches zero peers, `TS_IP` is empty and the Tier 2 ssh call fails fast with a hostname-resolution error, which is the correct outcome (caller falls through to Tier 3).
