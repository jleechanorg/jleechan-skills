---
name: openclaw-models
description: OpenClaw agent model configs — which work, which are broken/quota-limited, and how to switch
type: reference
---

# OpenClaw Model Reference

**Canonical full configs on this machine**:
- staging source of truth for manual edits: `~/.openclaw/openclaw.json`
- production source of truth: `~/.openclaw_prod/openclaw.json`

**Important runtime detail**: the staging launchd job currently points `OPENCLAW_CONFIG_PATH` at `~/.openclaw/openclaw.staging.json`, which is only a small overlay file. Do not treat that overlay as the canonical full config when checking model/provider settings.
**Auth profiles**: `~/.openclaw/agents/main/agent/auth-profiles.json`

## Current config on this machine (as of 2026-04-09)

```json
"model": {
  "primary": "minimax/MiniMax-M2.7",
  "fallbacks": []
}
```

**Provider block in live configs**: `models.providers.minimax`

**Do not use `minimax-portal/MiniMax-M2.7` on this machine unless you have separately configured `minimax-portal` auth.**
- The installed runtime looks up auth by provider id.
- `auth-profiles.json` currently contains `minimax:default`, not `minimax-portal:*`.
- Earlier `minimax-portal` guidance was stale for this environment and produced `No API key found for provider "minimax-portal"` in gateway logs.

**timeoutSeconds**: live values are lower than the old 900 guidance in some configs; do not assume 900 unless you verify the specific file being used by the service.

## Provider status table

| Model | Status | Auth type | Notes |
|---|---|---|---|
| `minimax/MiniMax-M2.7` | ✅ **CURRENT LIVE CONFIG** | `api_key` → `minimax:default` | Matches both `~/.openclaw/openclaw.json` and `~/.openclaw_prod/openclaw.json` on this machine |
| `minimax-portal/MiniMax-M2.7` | ❌ **STALE FOR THIS MACHINE** | requires `minimax-portal` auth | Do not set as primary here unless you also configure `minimax-portal` credentials |
| `minimax/MiniMax-M2.7-highspeed` | ❌ **PLAN NOT SUPPORTED** | `api_key` → `minimax:default` | HTTP 500 error 2061 — current API key plan does not include this model |
| `openai-codex/gpt-5.3-codex` | ❌ **QUOTA-LIMITED** | OAuth → `openai-codex:default` | Weekly usage cap exhausts; DO NOT use as primary/fallback |
| `openai-codex/gpt-5.3-codex-spark` | ⚠️ Same quota | OAuth → `openai-codex:default` | Same weekly pool as gpt-5.3-codex; used by consensus agent |
| `xai/grok-4-fast` | ❓ UNVERIFIED | `api_key` → `XAI_API_KEY` env | Key was flagged 403/revoked 2026-03-28; verify before using |
| `xai/grok-3-mini` | ❓ UNVERIFIED | `api_key` → `XAI_API_KEY` env | Same key as above |
| `openrouter/auto` | ❓ NOT CONFIGURED | `api_key` → `OPENROUTER_API_KEY` | Key not in openclaw.json env; add before using |
| `anthropic-vertex/claude-sonnet-4-6` | ❓ NOT CONFIGURED | GCP credentials | Needs `gcp-vertex-credentials` profile; not set up |

## Auth profile format (api_key providers)

```json
"minimax:default": {
  "type": "api_key",
  "provider": "minimax",
  "key": "[REDACTED_OPENAI_KEY]"
}
```

**Critical**: must be `"type": "api_key"` (underscore) and `"key"` (not `"apiKey"`).

## How to switch primary model

### Step 0 — PROBE FIRST (mandatory)

**Before writing to openclaw.json, verify the model is available on the current plan:**

```bash
# Get the current MiniMax API key from auth-profiles
KEY=$(python3 -c "import json; d=json.load(open('$HOME/.openclaw/agents/main/agent/auth-profiles.json')); print(d['profiles']['minimax:default']['key'])")

# Probe the candidate model — expect HTTP 200, not 500
curl -s -o /dev/null -w "%{http_code}" \
  https://api.minimax.io/anthropic/v1/messages \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7-highspeed","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}'
```

- **200** → model is available; proceed to switch
- **500 with error 2061** → plan does not support this model; mark ❌ in the status table above; do NOT add to config
- **403/401** → auth issue; check API key

**Never add a model to openclaw.json without a 200 probe response.**

### Step 1 — Update config (surgical — never rewrite the whole file)

```python
import json
path = "$HOME/.openclaw/openclaw.json"
with open(path) as f: d = json.load(f)
d['agents']['defaults']['model']['primary'] = "minimax/MiniMax-M2.7"
d['agents']['defaults']['model']['fallbacks'] = []
with open(path, 'w') as f: json.dump(d, f, indent=2)
```

### Step 2 — Restart gateway

```bash
kill -9 $(lsof -ti :18789); sleep 12; lsof -i :18789 | grep LISTEN
```

### Step 3 — Verify in logs

```bash
grep "agent model" /tmp/openclaw/openclaw-$(date +%F).log | tail -2
```

## Config path warning

If you are debugging staging via launchd, verify the plist first:

```bash
plutil -p ~/Library/LaunchAgents/ai.openclaw.staging.plist | rg OPENCLAW_CONFIG_PATH
```

On this machine the staging daemon points to `~/.openclaw/openclaw.staging.json`, not `~/.openclaw/openclaw.json`.
If you edit the wrong file, the service will not pick up your model change.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| :eyes: reaction but no reply | MiniMax M2.7 timeout exceeded | Increase `timeoutSeconds` (currently 900); check logs for `FailoverError` |
| `HTTP 500 error 2061` in logs | Model not on current API key plan | Mark ❌ in status table; do NOT add to config; probe before switching |
| `LiveSessionModelSwitchError` | Model changed while session was live | Expected after restart; clears on next run |
| `FailoverError: LLM request timed out` | Primary timed out, no working fallback | Highspeed ❌ on this plan; investigate xAI grok or OpenRouter |
| `Profile minimax:default timed out. Trying next account...` | MiniMax slow; fallback also failed | Check fallback list — remove unsupported models |
| Codex `weekly usage` exhausted | ChatGPT Pro plan weekly cap | Switch to minimax immediately |
