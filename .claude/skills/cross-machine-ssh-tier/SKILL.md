---
name: cross-machine-ssh-tier
description: "Reusable SSH-first-then-Tailscale transport ladder for reaching peer machines. Tier 1 is LAN SSH via a `~/.ssh/config` alias; Tier 2 is Tailscale SSH with explicit `-i ~/.ssh/id_<peer>` key, looked up live (never hardcoded); Tier 3 is a Slack channel watched by a reactive messaging-gateway agent, for when both are down. Used by `mac-remote`, `linux-remote`, `mac-mirror`, `linux-mirror`."
---

# Cross-machine SSH tier ladder

Single source of truth for the "try LAN, then Tailscale, then Slack" transport escalation. Re-used verbatim by:

- [`mac-remote`](../mac-remote/SKILL.md) and [`linux-remote`](../linux-remote/SKILL.md) — ad hoc SSH steering
- [`mac-mirror`](../mac-mirror/SKILL.md) and [`linux-mirror`](../linux-mirror/SKILL.md) — hand off a committed branch + tmux resume

Keep this ladder in sync across all four consumers. If you change the tier definitions or the fallback policy, update the four consumers in the same commit.

Substitute your own host alias / IP / key path / username / channel everywhere a placeholder (`mylinux`, `mymac`, `myusername`, `#my-fallback-channel`) appears below.

## Tier definitions

| Tier | Transport | When it applies | Failure mode |
|---|---|---|---|
| **1** | LAN SSH via `~/.ssh/config` alias (e.g. `mymac` / `mylinux`) | Both machines on the same home LAN | `Connection refused` when off-LAN or peer's `sshd` is down |
| **2** | Tailscale SSH, explicit `-i ~/.ssh/id_<peer>` key, target IP looked up live via `tailscale status` | Tier 1 refused (off-LAN) and Tailscale mesh is healthy | `tailscaled` not running on either side, peer offline, or the explicit key is missing/has the wrong mode |
| **3** | A Slack channel (or similar) watched by a reactive messaging-gateway agent on the peer | Tier 1 and Tier 2 both unreachable | Only human-typed posts trigger it; bot/app-attributed messages are silently dropped by design on most gateways. OAuth token must include the relevant history/mention read scopes (reinstall the app to the workspace after manifest changes — see Tier 3 caveat below). |

## Why a `~/.ssh/config` alias does NOT fail over to Tier 2 automatically

`Host mymac` in `~/.ssh/config` resolves a single `HostName` (e.g. a LAN IP). SSH has no concept of "try LAN first, fall back to Tailscale"; when the LAN IP is unreachable, you get `Connection refused` and the connection ends. You cannot set two `HostName` entries and have SSH retry them — you must do the tier selection in your own script (see ladder below) and **then** call `ssh` with the resolved target + key.

## The ladder

Parameterize by peer:

- `mymac` → LAN alias `mymac`, Tailscale peer name pattern `mymac`, key `~/.ssh/id_mymac`
- `mylinux` → LAN alias `mylinux`, Tailscale peer name pattern matching your Linux box's hostname, key `~/.ssh/id_mylinux`

After this block runs, `$SSH_TARGET` holds either the LAN alias (Tier 1) or `myusername@<tailscale-ip>` (Tier 2), or is empty (Tier 3 — fall through to your surrounding code's `if [ -n "$SSH_TARGET" ]` guard).

If your caller runs under `set -u` (nounset), expanding `"${SSH_ARGS[@]}"` while `SSH_ARGS=()` is still empty (the Tier 1 success path) throws `unbound variable` on macOS's stock bash 3.2 — bash's own array-expansion-under-nounset bug, fixed in 4.4+. Use `"${SSH_ARGS[@]+"${SSH_ARGS[@]}"}"` in a `set -u` context, or just don't set `-u` around this block.

```bash
# Inputs:
#   PEER_LAN_ALIAS   — e.g. "mymac" or "mylinux"
#   PEER_TS_PATTERN  — awk pattern for `tailscale status`, e.g. "mymac" or "mylinux"
#   PEER_KEY         — absolute key path, e.g. "$HOME/.ssh/id_mymac"
#   PEER_USER        — remote login user, e.g. "myusername"
# Outputs:
#   SSH_ARGS   — extra args for `ssh` (Tier 2 sets `-i <key>`; Tier 1 leaves empty)
#   SSH_TARGET — destination string, or empty if both Tier 1 and Tier 2 failed
SSH_ARGS=()
SSH_TARGET="$PEER_LAN_ALIAS"   # Tier 1 default: the LAN alias

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
  echo "SSH_OK via Tier 1 (LAN alias)"
else
  # Tier 2 — Tailscale SSH (off-LAN fallback). Re-verify the IP every call;
  # never hardcode it — Tailscale IPs are stable per-device but can change
  # on key rotations or mesh reconfiguration.
  TS_IP=$(tailscale status | awk "/${PEER_TS_PATTERN}/{print \$1}")
  SSH_ARGS=(-i "$PEER_KEY")
  SSH_TARGET="${PEER_USER}@${TS_IP}"
  if ssh "${SSH_ARGS[@]}" -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
    echo "SSH_OK via Tier 2 (Tailscale)"
  else
    SSH_TARGET=""   # both Tier 1 and Tier 2 failed — caller must handle Tier 3
  fi
fi
```

Concrete invocations:

```bash
# Reaches mymac — note the key is `id_mymac`, NOT the Linux peer's key
PEER_LAN_ALIAS="mymac"
PEER_TS_PATTERN="mymac"     # matches your Mac's Tailscale hostname
PEER_KEY="$HOME/.ssh/id_mymac"
PEER_USER="myusername"

# Reaches mylinux — key is `id_mylinux`
PEER_LAN_ALIAS="mylinux"
PEER_TS_PATTERN="mylinux"   # matches your Linux box's Tailscale hostname
PEER_KEY="$HOME/.ssh/id_mylinux"
PEER_USER="myusername"
```

## Tier 3 — messaging-gateway fallback

When `$SSH_TARGET` is empty after the Tier 1/2 ladder, both LAN and Tailscale SSH are unreachable. Post the full hand-off context (repo path, branch, commit SHA, exact next-command) to a channel a reactive gateway agent on the peer machine is watching (e.g. a Hermes-style gateway, or anything that runs commands on your behalf). It has no shared context with your current session — give complete, explicit instructions, don't assume it can infer intent from prior conversation turns.

### Tier 3 caveats

- **Only human-typed messages trigger a response, on most gateways.** Messages posted via a bot-associated token (including API calls using an OAuth-app-issued user token) commonly get silently dropped by design. If this tier ever goes quiet, check OAuth scopes-vs-reinstall status before assuming a connection/socket problem — see the discriminating check below, it's usually the faster diagnosis.
- **OAuth scope mismatches after a manifest edit are a common, easy-to-miss root cause.** A connection can report fully healthy — process alive, socket/session established, ping/pong succeeding — while a specific required permission was declared in the integration's manifest but never actually granted to the live credential (e.g. added to a Slack app's manifest after the app was already installed — the scope isn't live until the app is reinstalled/reauthorized). **Discriminating check:** call the platform's own auth-introspection endpoint with the gateway's actual live credential (for Slack: `auth.test`, or attempt the specific scoped call you need and read the error — `missing_scope` names the gap directly) rather than trusting the integration's own settings UI, which can show a scope as "configured" when it was never granted. **Remedy:** reinstall/reauthorize the app so the currently-declared scopes actually take effect — a bare process/service restart does not do this.
- **A message-filtering rule you're tripping as a test artifact, not a real failure.** Many gateways correctly drop messages attributed to a bot/app identity by default (including messages posted via some *other* app's OAuth-issued token, which platforms often tag with that app's identity even when the underlying account is a real human). Verify with a message you know is genuinely human-originated — typed directly in the client, not posted via any API token — before concluding the gateway itself is broken.
- **No shared context with your current session.** The receiving gateway has no idea what you've already tried or what state you're in. Post a complete, self-contained message — repo + branch + commit + exact next-command — addressed generally (most gateways need no special mention syntax; a plain human-typed message in the channel is sufficient, and mention syntax can even be filtered out by the same bot-detection rule if it originates from an API token).
- Only after ruling both scope-mismatch and message-filtering out is it worth suspecting the connection layer itself — enable debug-level logging on the gateway process and check its actual log destination, which for a systemd-managed service is the journal (e.g. `journalctl --user -u <service>`), or the equivalent launchd log for a macOS service — not necessarily its own app log file, which may not show this level of detail.

## Key selection — name keys after the peer they connect to, not the local machine

The SSH key used on machine A to reach machine B should be named for B (the peer), not for A. This lets each machine's `authorized_keys` be read by file name to see which direction/peer each key belongs to:

- Connecting mymac ← mylinux: key on mylinux is `~/.ssh/id_mymac` (named for the peer it talks to), authorized in mymac's `~/.ssh/authorized_keys`.
- Connecting mylinux ← mymac: key on mymac is `~/.ssh/id_mylinux` (named for the peer it talks to), authorized in mylinux's `~/.ssh/authorized_keys`.

The ladder above encodes the right key by peer — do not swap them.

## IP re-verification pattern

Never hardcode a Tailscale IP in committed code. Even "last known" values go stale on tailscale key rotations or mesh reconfiguration. Use:

```bash
# All live Tailscale peers (one IP per line) — plain `tailscale status`
# output has no literal "peer" token per line, so match everything:
tailscale status | awk '{print $1}'

# A specific peer (case-sensitive substring match against the peer hostname)
tailscale status | awk "/${PEER_TS_PATTERN}/{print \$1}"
```

A single peer usually has exactly one IP; if a peer rotates keys, both the old and new IPs may show briefly — `awk` returns the first match, which is the active one. If the pattern matches zero peers, `TS_IP` is empty and the Tier 2 ssh call fails fast with a hostname-resolution error, which is the correct outcome (caller falls through to Tier 3).
