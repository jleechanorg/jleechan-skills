---
name: worldai-auth
description: Authenticate with the WorldAI Firebase project for Your Project
type: setup
scope: project
---

# WorldAI Authentication Setup

Use this skill when you need an ID token for the **WorldAI** Firebase project
(`$FIREBASE_PROJECT_ID`).

## Prerequisites

| Variable | Meaning |
|---|---|
| `FIREBASE_PROJECT_ID` | WorldAI Firebase project id (required; never derived) |
| `FIREBASE_API_KEY` | Web API key of that project (`WORLDAI_FIREBASE_API_KEY` also accepted) |
| `AUTH_CLI_PATH` | Optional path to the generic `auth-cli.mjs`; default is `${CLAUDE_HOME:-$HOME/.claude}/scripts/auth-cli.mjs` |

If a required variable is unset, the wrapper prints `<VAR> not configured` and exits.

## Auth Scripts Location

- `scripts/auth-worldai.mjs` in this skill's directory — WorldAI project auth wrapper.
- `auth-cli.mjs` — the generic multi-project auth CLI that the wrapper calls. The main
  skills export installs it to `${CLAUDE_HOME:-$HOME/.claude}/scripts/`.

## Commands

Run these with `<skill-dir>` set to this skill's base directory (Claude Code shows it
when the skill loads):

```bash
# Login for WorldAI (interactive browser OAuth)
node <skill-dir>/scripts/auth-worldai.mjs login

# Get a token (auto-refreshes expired tokens using refresh token)
node <skill-dir>/scripts/auth-worldai.mjs token

# Check status
node <skill-dir>/scripts/auth-worldai.mjs status
```

## Token Locations

Tokens are stored by `auth-cli.mjs` under `~/.ai-universe/`:
- `~/.ai-universe/auth-token-${FIREBASE_PROJECT_ID}.json` — WorldAI tokens
- `~/.ai-universe/auth-token-<project-id>.json` — tokens for any other project

Token file schema (camelCase keys):
```json
{
  "idToken": "...",
  "refreshToken": "...",
  "expiresAt": "2026-01-01T00:00:00.000Z"
}
```

## Manual Token Refresh

If the auth-worldai.mjs wrapper fails, refresh the WorldAI token directly:
```python
import urllib.request, urllib.parse, json, os, datetime

project_id = os.environ['FIREBASE_PROJECT_ID']
token_path = os.path.expanduser(f'~/.ai-universe/auth-token-{project_id}.json')
with open(token_path) as f:
    token_data = json.load(f)

url = 'https://securetoken.googleapis.com/v1/token?key=<FIREBASE_API_KEY>'
data = urllib.parse.urlencode({
    'grant_type': 'refresh_token',
    'refresh_token': token_data['refreshToken']
}).encode()
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
with urllib.request.urlopen(req, timeout=15) as resp:
    result = json.loads(resp.read())

# Update token file preserving camelCase schema
token_data['idToken'] = result['id_token']
token_data['refreshToken'] = result['refresh_token']
token_data['expiresAt'] = (datetime.datetime.now(datetime.timezone.utc)
    + datetime.timedelta(seconds=int(result['expires_in']))).isoformat()
with open(token_path, 'w') as f:
    json.dump(token_data, f, indent=2)
```

## Testing Against a Deployed Server

When using the `--server` flag with testing_mcp tests against a deployed server
(`--server "$MCP_SERVER_URL"`, for example `https://<dev-service-url>`), the MCPClient
auto-loads the auth token from `~/.ai-universe/auth-token-${FIREBASE_PROJECT_ID}.json`
and passes it as a `Bearer` token. Ensure the token is refreshed before running.

If you see project mismatch errors, re-run login with the correct project-specific script.
