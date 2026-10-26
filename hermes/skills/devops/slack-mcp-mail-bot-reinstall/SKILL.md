---
name: slack-mcp-mail-bot-reinstall
description: "Repair MCP Mail Slack bot scope and reinstall flow when post/mark behavior diverges after token or scope updates."
type: skill
---

# Slack MCP Mail Bot Reinstall (Scope Repair)

> **Authority and browser boundary:** This guide supports diagnosis by default. A
> missing scope does not authorize an OAuth reinstall, scope change, credential
> update, or token rotation; those require separate explicit authorization.
> Never use personal Chrome profiles, copied/decrypted browser cookies, or
> injected credentials. Any separately authorized browser operation must use a
> dedicated agent-owned automation profile under the browser-control contract.
> If that context is unavailable, stop and report the blocker.

## Goal
Bring the MCP Mail bot identity (`mcp_agent_mail`, bot `<SLACK_ID>`, app `<SLACK_ID>`) to a state where it can both post messages and clear unread/read state for channels and DMs.

> **Read this first if you're not sure which class of failure you're seeing (2026-07-13):**
> There are **TWO distinct bot-broken states** that often look identical to a sweep:
>
> | Symptom | Root cause | Fix |
> |---|---|---|
> | `chat.postMessage` → 200; `conversations.mark` / `conversations.invite` → `missing_scope: channels:write.*` | **Scope gap** — the app install does not have the scope | Diagnose and report the exact missing scope. A separately authorized scope-change workflow is required before repair. |
> | Bot can `chat.postMessage` in DMs it owns but can't read any channel; `conversations.members` shows `<SLACK_ID>` is NOT in any of the channels the sweep flagged | **Channel-membership gap** — bot is not a member. Reinstall does not auto-rejoin. | Diagnose membership with authorized existing scopes; do not use a cookie-backed client or scope bypass. |
>
> Confirm membership with §6.1 before proposing remediation. This guide does not authorize reinstalling or changing credentials/scopes.

## Prerequisites
- Confirmed admin access to the Slack workspace that owns app `<SLACK_ID>`.
- `SLACK_BOT_TOKEN` exists in `~/.mcp_mail/credentials.json` AND in `~/.bashrc` as `HERMES_SLACK_BOT_TOKEN` (line 951) AND `SLACK_MCP_XOXB_TOKEN` (line 949). After any reinstall that rotates the bot token, all three must be updated. See §9.
- Aside is reachable: `aside --version` works and `aside account list` runs.
- If using terminal for verification, be prepared for Slack gateway narration mirrors.

## 1) Diagnose current identity state

### 1.1 Confirm bot identity
```bash
TOKEN=$(python3 - <<'PY'
import json
print(json.load(open('$HOME/.mcp_mail/credentials.json'))['SLACK_BOT_TOKEN'])
PY)

curl -s -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $TOKEN"
```

### 1.2 Verify which class of failure you're seeing (added 2026-07-13)
Run these TWO checks — order matters:

```bash
# (a) Can the bot post?
CHAN='<SLACK_ID>'  # debug channel
TS=$(date +%s)
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data "{\"channel\":\"$CHAN\",\"text\":\"[diag] mcp-mail scope test $TS\"}"

# (b) Is the bot actually a MEMBER of that channel?
curl -s -X POST https://slack.com/api/conversations.members \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "channel=$CHAN" \
  --data-urlencode "limit=200" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('BOT IN CHANNEL:', '<SLACK_ID>' in d.get('members', []))
"
```

If (a) succeeds and (b) returns `False` → **channel-membership gap, NOT scope gap**. Skip to §6. If (a) returns `missing_scope: chat:write` AND (b) is irrelevant because the bot can't post anywhere → continue to §1.3.

### 1.3 Verify read-state scope (scope-gap triage)
```bash
CUR_TS=$(date +%s)
curl -s -X POST 'https://slack.com/api/conversations.mark' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "channel=$CHAN" \
  --data-urlencode "ts=$CUR_TS"
```

Expected:
- posting returns `ok:true`
- mark returns `missing_scope` with `needed: channels:write,groups:write,mpim:write,im:write` -> scope repair required

## 2) Scope-change procedure (separate explicit authorization required)

Only after a separate explicit authorization for this scope change, use the approved Slack app administration flow to add the required bot token scopes:
   - `channels:write`
   - `groups:write`
   - `mpim:write`
   - `im:write`
Then reinstall only within that separately authorized flow. If the failing call is `files.getUploadURLExternal` or `files.completeUploadExternal`, report `missing_scope: files:write` and stop; this guide does not authorize repairing that scope. Never use a personal browser, cookies, credential injection, or unattended OAuth flow. Any credential changes must be explicitly authorized and handled by the designated secure workflow.

## 3) Verify with CLI (post-reinstall)

Re-run section 1.2 and 1.3 in the same channel.

- `chat.postMessage` must still return `ok:true`.
- `conversations.mark` must return `ok:true` with the same token/channel/ts pattern.

## 4) Dedicated automation context

Use an already configured, dedicated agent-owned automation profile only when a separate authorized workflow requires a browser action. Follow the browser-control contract. If Aside has no such automation context or reports no focused window, stop and report that blocker; never open a normal/personal browser as a fallback. This guide does not authorize OAuth changes.

## 5) Post-change hardening

1. If this bot is used by the dropped-thread cron, follow-up with explicit `conversations.mark` in the same handler that calls `chat.postMessage`.
2. Keep `channels:write` etc scoped only when required.
3. Log the successful verification output in `~/memory/` or `~/roadmap/...` per your normal ops evidence pattern.

## 6) Channel-membership-repair recipe (added 2026-07-13)

Use this when §1.2 step (b) returns `False` — the bot has scopes but is not a member of channels it should be in.

### 6.1 Verify membership gap (not scope gap)

```bash
CHAN='<SLACK_ID>'  # the supposedly-locked-out channel
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://slack.com/api/conversations.members?channel=$CHAN&limit=200" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
m = d.get('members', [])
print('ok:', d.get('ok'), 'total:', len(m))
print('bot <SLACK_ID> in channel?', '<SLACK_ID>' in m)
"
```

### 6.2 Try `conversations.invite` from the bot token first

Some bot installs include `channels:write.invites`. If the result is `not_in_channel` (NOT `missing_scope`), the bot can re-add itself. If it's `missing_scope`, move to §6.3.

```bash
curl -s -X POST https://slack.com/api/conversations.invite \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data "{\"channel\":\"$CHAN\",\"users\":\"<SLACK_ID>\"}"
# {"ok":true, "channel":...}        ← fix landed
# {"ok":false,"error":"missing_scope"}  ← report the exact blocker and stop
```

### 6.3 Retired cookie-backed client bypass

The former `slack.getClient()` recipe used a signed-in workspace client with broader scopes. It is retired. Never use Aside's cookie-backed Slack client, personal browser state, or copied cookies to bypass a missing scope. Report the exact authorization or membership blocker and use only an already-authorized connector with its configured scopes.

### 6.4 Verify from the bot side

After an authorized membership action:

```bash
for CHAN in <SLACK_ID> <SLACK_ID> <SLACK_ID>; do
  curl -s -H "Authorization: Bearer $TOKEN" \
    "https://slack.com/api/conversations.info?channel=$CHAN" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['channel']['name']:25} is_member={d['channel']['is_member']}\")"
done
```

And pull `conversations.history` on the most important channel to confirm the bot can actually READ posts:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://slack.com/api/conversations.history?channel=<SLACK_ID>&limit=3" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('ok:', d.get('ok'), 'msgs:', len(d.get('messages',[])))
if d.get('messages'):
    m = d['messages'][0]
    print(f\"latest: user={m.get('user','?')} text={m.get('text','')[:80]}\")"
```

## 7) Disable the Slack listening side (NEW 2026-07-18)

Use this lane when the user says **"I don't want mcp-agent-mail to be passively listening"** / "turn off the Slack side of mcp-mail" / "the bot keeps replying without being asked" / "kill the bidirectional sync." The server keeps running for MCP tool calls (inter-agent mail), but it stops touching Slack.

### 7.1 Why this lane is needed

The "passive listening" is real and bidirectional. `mcp_agent_mail` uses **Socket Mode** when `SLACK_APP_TOKEN=xapp-...` is set: it opens a WebSocket to Slack and Slack pushes events in real-time without a public URL. With `SLACK_BOT_TOKEN=xoxb-...` also set, the bot identity (`mcp_agent_mail`, bot `<SLACK_ID>`, app `<SLACK_ID>`, Slack user `<SLACK_ID>`) auto-posts outbound mirror messages. That outbound mirror is exactly what users complain about as "the bot is acting on its own."

Scope/membership repair (§1-§6) is *the wrong lane* for this complaint — the bot isn't broken, it's working as configured.

### 7.2 Identify the running server first

```bash
pgrep -fl 'mcp_agent_mail.cli serve-http'        # server PID
launchctl print gui/$(id -u)/com.mcp.agent.mail  # launchd label + state
lsof -nP -iTCP -sTCP:LISTEN -p <PID> | grep TCP  # listen socket (default 127.0.0.1:8765)
```

Server always runs from `$HOME/mcp_mail/scripts/run_server_with_token.sh` under launchd `com.mcp.agent.mail` (`~/Library/LaunchAgents/com.mcp.agent.mail.plist`, `KeepAlive=true`, `RunAtLoad=true`). State `running` is normal.

Confirm tokens are in the inherited env (NOT in `~/.mcp_mail/credentials.json` — empty in PyPI installs; tokens come from `~/.bashrc` via `bash -lc`):

```bash
ps -p <PID> -o pid,etime,command
grep -nE '^export SLACK_(APP|BOT|WEBHOOK)_TOKEN=' ~/.bashrc   # approximate line numbers 946-947
```

### 7.3 Two scopes — pick ONE before touching anything

| Scope | What changes | What stays | Cost |
|---|---|---|---|
| **A) Soft disable** | Socket Mode never opens; outbound mirror silent; mcp-agent-mail MCP tools still work for inter-agent routing | Server running | One bashrc edit + launchd bounce |
| **B) Full shutdown** | Everything gone | Nothing — re-enable is manual | launchd disable + plist rename |

> A "soft disable" is almost always correct. The MCP layer (inter-agent message routing) is the actual product; the Slack sync is a side feature the user opted into but didn't ask the bot to act on independently.

### 7.4 Soft disable (Scope A) — exact commands

```bash
# 1. Stop the running server so step 3 inherits the new env
launchctl bootout gui/$(id -u)/com.mcp.agent.mail

# 2. Comment out the Slack tokens at the source (bashrc ~lines 946-947).
#    Keep the values so this is reversible — just remove the export
sed -i.bak -E 's/^export (SLACK_(BOT|APP)_TOKEN=)/#\1/' ~/.bashrc
grep -nE '^#?export SLACK_(APP|BOT)_TOKEN=' ~/.bashrc   # confirm both are now commented

# 3. Restart under launchd — empty token env → Slack sync code paths short-circuit
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mcp.agent.mail.plist

# 4. Verify Socket Mode didn't reopen
sleep 3
pgrep -fl 'mcp_agent_mail.cli serve-http'              # new PID
lsof -nP -iTCP -sTCP:LISTEN -p <NEW_PID> | grep TCP   # 127.0.0.1:8765 only — no Slack WS
grep -E 'slack|bolt|SocketMode' /tmp/mcp_agent_mail_server.log | tail -20  # should be silent
```

Expected: server up on port 8765, **no log lines mentioning Slack/bolt/SocketMode** = passive listening is off. Outbound `chat.postMessage` calls also stop because `SLACK_BOT_TOKEN` is empty.

### 7.5 Full shutdown (Scope B) — exact commands

```bash
launchctl bootout gui/$(id -u)/com.mcp.agent.mail
launchctl disable gui/$(id -u)/com.mcp.agent.mail
mv ~/Library/LaunchAgents/com.mcp.agent.mail.plist{,.disabled-$(date +%Y-%m-%d)}
```

Re-enable later: rename plist back, `launchctl enable gui/$(id -u)/com.mcp.agent.mail`, `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mcp.agent.mail.plist`.

⚠️ Anything registered through `mcp_mail/scripts/integrate_claude_code.sh` or `integrate_codex_cli.sh` will lose the MCP mail layer until you re-enable.

### 7.6 Pitfalls

- **Don't just `kill <PID>`.** `KeepAlive=true` will respawn it within seconds and the new process inherits the same env — if you didn't change bashrc first, you killed nothing.
- **Don't trust `~/.mcp_mail/credentials.json`.** PyPI installs don't write there; tokens come from the shell login env at `bash -lc` time. Always verify with `grep -E '^export SLACK_' ~/.bashrc`.
- **The `SLACK_WEBHOOK_URL` env var is the *mirror* (outgoing Slack incoming-webhook) path, NOT the listener.** If only `SLACK_WEBHOOK_URL` is set and `SLACK_APP_TOKEN` is empty, the server can't receive Socket Mode events — it's one-way outbound only via webhook. Both must be unset (or both `BOT_TOKEN` and `APP_TOKEN`) for full soft-disable.
- **Comment out, don't delete, the exports.** This change is destructive from the user's perspective but reversible in seconds. Deleting loses the token values and forces a Slack-app OAuth dance to recover.
- **Don't hit `launchctl disable` first.** That persists across reboots but `bootout` alone is per-session. Without `disable`, the next login resurrects the service. Order matters: `bootout` → `disable` → `mv plist`.
- **Don't edit the running server's env.** Killing and restarting with new env is the only safe path; in-place edits don't propagate to child processes via Socket Mode.

### 7.7 Verify the disable actually stuck

Within 5 minutes of a soft disable, the bot identity `<SLACK_ID>` should produce **zero new messages** in any channel where it was previously mirroring. Spot-check from the user's XOXP token (not the bot's — bot is suspended now):

```bash
CHAN='<SLACK_ID>'  # the channel the user complained about
curl -s -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  "https://slack.com/api/conversations.history?channel=${CHAN}&limit=5" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
for m in d.get('messages',[])[:5]:
    user = m.get('user') or m.get('bot_id') or '?'
    text = (m.get('text') or '')[:60].replace(chr(10),' ')
    print(f\"{m['ts']}  user={user}  text={text}\")
"
```

Expected: zero rows where `bot_id == '<SLACK_ID>'` (mcp_agent_mail's bot ID). If rows still appear, §7.4 step 2's bashrc edit didn't take — re-run `source ~/.bashrc` and bounce launchd again.

## 8) Related references

- `~/.hermes/skills/devops/slack-mcp-mail-bot-reinstall/references/disable-passive-listening-2026-07-18.md` — full transcript of the 2026-07-18 disable flow with bashrc line numbers and config schema proof.
- `~/.hermes/skills/devops/slack-mcp-mail-bot-reinstall/references/files-write-scope-reinstall-2026-07-19.md` — retired historical transcript; it is not a recovery procedure or authority to change scopes or credentials.
- `~/.hermes/skills/dropped-messages/references/bot-read-tracking-scope-gap-2026-06-23.md`
- `~/.hermes/skills/dropped-messages/references/cross-channel-post-unreachable-workspace-2026-06-25.md`
- `~/.hermes/skills/aside-browser-default/references/aside-repl-api-gotchas.md` §7 + §11 + §12 — background only; the cookie-backed `slack.getClient()` route is retired and must not be used as a bypass.

## 9) Token updates (only after separate explicit authorization)

Only within a separately authorized credential-change workflow, when an approved OAuth reinstall lands, the bot's `xoxb-...` token rotates and **three storage locations** must all be updated, not just one:

| Storage | Variable | Approx. location |
|---|---|---|
| `~/.bashrc` | `HERMES_SLACK_BOT_TOKEN` | line 951 (used by `launchd-env-wrapper.sh`) |
| `~/.bashrc` | `SLACK_MCP_XOXB_TOKEN` | line 949 (used by `slack-mcp-server` Go daemon) |
| `~/.mcp_mail/credentials.json` | `SLACK_BOT_TOKEN` | (used by `mcp_agent_mail` Python daemon) |

Failure mode if you miss one: that daemon's next restart picks up the old (now-revoked) token and the failing call still returns `missing_scope` for the new grant. Always verify with `bash -lc 'source ~/.bashrc; [ "$HERMES_SLACK_BOT_TOKEN" = "$SLACK_MCP_XOXB_TOKEN" ] && [ "$HERMES_SLACK_BOT_TOKEN" = "$(jq -r .SLACK_BOT_TOKEN ~/.mcp_mail/credentials.json)" ]' && echo OK` after the edit.

Backup convention: copy to `~/.bashrc.bak.YYYYMMDD-HHMMSS` and `~/.mcp_mail/credentials.json.bak.YYYYMMDD-HHMMSS` before any token mutation. Restoration is `cp` back.

## 10) `files:write:user` note (reference only)

Slack uses the scope name `files:write`. This is a factual reference only; it does not authorize changing bot or user scopes. For a missing upload scope, follow §11 and stop.

## 11) Missing upload scope (safe boundary)

If an upload returns `missing_scope: files:write`, report the exact error and
stop. Use only an already-authorized connector/uploader with its configured
scope. Do not use a personal browser profile or cookies, inject credentials,
drive an unattended OAuth/reinstall flow, or rotate tokens as a workaround.
The historical browser-driven transcript at
`references/files-write-scope-reinstall-2026-07-19.md` is retired and contains
no operational recovery steps.

## 12) `slack-mcp-server` (Go daemon) token preference (reference only)

The Go-based `slack-mcp-server` on port 8006 is a separate daemon from the Python `mcp_agent_mail` server. It reads `SLACK_MCP_XOXB_TOKEN` (bot) AND `SLACK_MCP_XOXP_TOKEN` (user) from bashrc, but if **both** are set it logs:

```
Both SLACK_MCP_XOXP_TOKEN and SLACK_MCP_XOXP_TOKEN are set. Using User token (xoxp) for full features. Bot token will be ignored.
```

This describes the configured token preference only. Do not change user scopes, clear or replace tokens, or alter credential configuration as an upload workaround; follow §11 for a missing upload scope.
