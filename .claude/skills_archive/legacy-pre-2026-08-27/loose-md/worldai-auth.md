---
description: Authenticate with the WorldAI Firebase project for Your Project
type: setup
scope: project
---

# WorldAI Authentication Setup

Use this skill when you need an ID token for the **WorldAI** Firebase project (`worldarchitecture-ai`).

## Auth Scripts Location

Auth scripts live in the repo under `.claude/scripts/`:
- `.claude/scripts/auth-worldai.mjs` — WorldAI project auth (requires `FIREBASE_API_KEY` env var)
- `.claude/scripts/auth-aiuniverse.mjs` — AI Universe project auth
- `.claude/scripts/auth-cli.mjs` — Generic multi-project auth CLI

## Commands

```bash
# Login for WorldAI (interactive browser OAuth)
node .claude/scripts/auth-worldai.mjs login

# Get a token (auto-refreshes expired tokens using refresh token)
node .claude/scripts/auth-worldai.mjs token

# Check status
node .claude/scripts/auth-worldai.mjs status
```

## Token Locations

Tokens are stored by `auth-cli.mjs` under `~/.ai-universe/`:
- `~/.ai-universe/auth-token-worldarchitecture-ai.json` — WorldAI tokens
- `~/.ai-universe/auth-token-ai-universe-b3551.json` — AI Universe tokens

Token file schema (camelCase keys):
```json
{
  "idToken": "...",
  "refreshToken": "...",
  "expiresAt": "2026-01-01T00:00:00.000Z"
}
```

## Manual Token Refresh

If the auth-worldai.mjs wrapper fails, refresh the worldarchitecture-ai token directly:
```python
import urllib.request, urllib.parse, json, os, datetime

token_path = os.path.expanduser('~/.ai-universe/auth-token-worldarchitecture-ai.json')
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

## Testing Against Production Server

When using `--server` flag with testing_mcp tests against production (`https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app`), the MCPClient auto-loads the auth token from `~/.ai-universe/auth-token-worldarchitecture-ai.json` and passes it as a `Bearer` token. Ensure the token is refreshed before running.

If you see project mismatch errors, re-run login with the correct project-specific script.
