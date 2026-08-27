---
name: mvp-site-app-dev-i6xf2p72ka-uc-a-run-app-root
description: "API skill for mvp-site-app-dev-i6xf2p72ka-uc.a.run.app. Use when: interacting with this site's APIs, automating workflows, debugging requests. Auth: Unknown — capture may reveal auth mechanism."
tags: [campaign]
---

# mvp-site-app-dev-i6xf2p72ka-uc.a.run.app

## Auth

Unknown — capture may reveal auth mechanism

For Firebase/JWT sites: use superpower chrome's `window.fetchApi()` which attaches the correct token automatically.

## Endpoints

| Method | Path | Description | Content-Type |
|--------|------|-------------|--------------|
| GET | `https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/campaigns` | Captured via superpower chrome fetchApi |  |
| GET | `https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/settings` | Captured via superpower chrome fetchApi |  |
| GET | `https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/time` | Captured via superpower chrome fetchApi |  |

## Response Shapes (captured)

**GET https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/campaigns**
```json
[
  {
    "created_at": "2026-04-15T09:57:22.210005+00:00",
    "id": "9KUApA77D7snKenULuKh",
    "initial_prompt": "Character: A brave AI agent exploring APIs | Setting: A world where browsers make API calls",
    "last_played": "2026-04-15T09:58:35.078406+00:00",
    "title": "Claude Browserclaw Test"
  },
  {
    "created_at": "2026-04-14T03:48:48.615069+00:00",
    "id": "cntvDfj7cGUhUFkxcmV3",
    "initial_prompt": "Character: Aric the Fighter (Level 5) | Setting: A dark dungeon with torchlight | Description: Same-...",
    "last_played": "2026-04-14T03:50:40.282558+00:00",
    "title": "Same Size Test 1776138519"
  },
  {
    "created_at": "2026-04-14T03:26:58.113332+00:00",
    "id": "L5iB5eWq8TyzQW3qFDDv",
    "initial_prompt": "Character: Aric the Fighter (Level 5) | Setting: A dark dungeon with torchlight | Description: Same-...",
    "last_played": "2026-04-14T03:50:12.349758+00:00",
    "title": "Same Size Test 1776137125"
  },
  {
    "created_at": "2026-04-14T03:19:54.362303+00:00",
    "id": "z7eDk3NzY1mB6BTm23yu",
    "initial_prompt": "Character: Aric the Fighter (Level 5) | Setting: A dark dungeon with torchlight | Description: Same-...",
    "last_played": "2026-04-14T03:46:19.030851+00:00",
    "title": "Same Size Test 1776136773"
  },
  {
    "created_at": "2026-04-14T03:32:48.030641+00:00",
    "id": "Z2sEA1hQW3YJbyQHvvt6",
    "initial_prompt": "Character: Aric the Fighter (Level 5) | Setting: A dark dungeon with torchlight | Description: Same-...",
    "last_played": "2026-04-14T03:34:04.293029+00:00",
    "title": "Same Size Test 1776137520"
  },
  {
    "created_at": "2026-04-14T03:28:50.785347+00:00",
    "id": "XHWCpllzfKNgwf6o1Jvc",
    "initial_prompt": "Character: Aric the Fighter (Level 5) | Setting: A dark dungeon with torchlight | Description: Same-...",
    "last_played": "2026-04-14T03:33:37.986261+00:00",
    "title": "Same Size Test 1776137287"
  },
  {
    "created_at": "2026-04-14T03:22:39.855096+00:00",
    "id": "zheWLda5wsD
    ... (truncated)
```

**GET https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/settings**
```json
{
  "cerebras_model": "qwen-3-235b-a22b-instruct-2507",
  "debug_mode": true,
  "faction_minigame_enabled": true,
  "gemini_model": "gemini-2.5-flash",
  "has_custom_cerebras_key": false,
  "has_custom_gemini_key": false,
  "has_custom_openclaw_gateway_token": true,
  "has_custom_openclaw_key": false,
  "has_custom_openrouter_key": false,
  "llm_provider": "gemini",
  "openclaw_gateway_port": 18789,
  "openclaw_gateway_url": "https://example.com",
  "openrouter_model": "meta-llama/llama-3.1-70b-instruct"
}
```

**GET https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/api/time**
```json
{
  "server_time_utc": "2026-04-15T10:04:44.085008+00:00",
  "server_timestamp": 1776247484,
  "server_timestamp_ms": 1776247484085
}
```


## Usage Examples

### Via browserclaw (recommended)
```bash
# Extend the capture
browserclaw capture --url "https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app" --output /tmp/capture.har --manual

# Re-infer endpoints
browserclaw infer --har /tmp/capture.har --output /tmp/catalog.json --site "mvp-site-app-dev-i6xf2p72ka-uc.a.run.app"
```

### Via superpower chrome (for authenticated sites)
```javascript
// In Chrome DevTools console on the target site:
const data = (await window.fetchApi('/api/endpoint')).data;
console.log(JSON.stringify(data, null, 2));
```

### Via generated client
```python
from generated_client import BrowserClawClient
client = BrowserClawClient()
# Auth handled by the site — use superpower chrome for authenticated calls
```

## Extending This Skill

```bash
# Capture more of the site
browserclaw learn --url "https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/more/routes" --output-dir ./extended --save-skill

# WebSocket capture (if site uses WS)
browserclaw capture-ws --url "https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app" --output /tmp/ws.json --manual
browserclaw generate-ws --ws-capture /tmp/ws.json --output-dir ./ws_generated
```

## Notes

- Source HAR: `None`
- Endpoints captured: 3
- LLM provider used for enrichment: none
- This skill is auto-generated by browserclaw — verify accuracy before deploying.
