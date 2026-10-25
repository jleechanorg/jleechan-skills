---
name: browserclaw
description: Scrape browser traffic with Playwright → infer API endpoints → generate Python client + MCP tools artifacts.
agent_scope: Any AI agent (Codex, Claude Code, OpenClaw, Hermes, AO)
---

# browserclaw

First apply [browser-control's personal browser isolation contract](../browser-control/SKILL.md#personal-browser-isolation--required-for-every-route). The personal Chrome profile, cookies, and login state are off-limits. Cookie/session reuse below applies only to an explicitly authorized agent-owned source profile; existing personal sign-in is not authorization. Do not run legacy personal-profile examples as a fallback.

Inspect browser-driven API traffic and convert captured patterns into reusable artifacts — a Python client for programmatic control and MCP tool definitions for tool-calling agents.

## Scope

**Any public website** — not limited to "the app" or "the auth handshake." browserclaw captures traffic from any URL reachable in an agent-owned Chrome/Chromium session. The "no login bypass" rule is about authentication (don't bypass logins/CAPTCHAs), NOT about which sites you can browse. For an explicitly authorized agent-owned source, use `--storage-state` or the guarded `browserclaw cookies decrypt --db '<agent-owned-source-db>'` + `browserclaw cookies inject --cookies '<private-cookie-json>'` lifecycle. Personal desktop profiles, cookies, and login state are off-limits.

## What it does

1. **Capture** — Playwright + Chromium records HTTP traffic to a HAR file
2. **Infer** — Extract API endpoints (method, URL template, query keys, body keys) from HAR
3. **Enrich** — Optionally call an LLM to add natural-language descriptions
4. **Generate** — Emit `catalog.json`, `generated_client.py`, and `mcp_tools.json`

## Prerequisites

```bash
# Python 3.11+, pip
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python -m playwright install chromium
```

Environment variables (optional, for LLM enrichment):
- `ANTHROPIC_API_KEY` (provider: `anthropic`)
- `OPENAI_API_KEY` (provider: `openai`)
- `GEMINI_API_KEY` (provider: `gemini`)

## Capture flow

### Option A — Manual (interactive, recommended for auth-gated sites)

```bash
browserclaw capture \
  --url https://app.example.com/dashboard \
  --output generated/example/capture.har \
  --manual
```

The tool opens a Chromium window. You log in and browse as usual. Press Enter when done. The HAR (with embedded request/response bodies) is saved.

### Option B — Headless (non-interactive, no stdin needed)

```bash
browserclaw capture \
  --url https://app.example.com \
  --output generated/example/capture.har \
  --headless \
  --wait-after-load 5
```

`--headless` always runs non-interactively. Combine with `--steps` for scripted navigation.

### Option C — Scripted steps (JSON)

```json
[
  {"action": "goto", "url": "https://app.example.com/login"},
  {"action": "fill", "selector": "input[name=email]", "value": "user@example.com"},
  {"action": "fill", "selector": "input[name=password]", "value": "secret"},
  {"action": "click", "selector": "button[type=submit]"},
  {"action": "wait_for_url", "value": "**/dashboard"},
  {"action": "eval", "value": "window.testAuthBypass = {enabled: true}"},
  {"action": "wait_for_timeout", "milliseconds": 2000}
]
```

Supported actions: `goto`, `click`, `fill`, `press`, `wait_for_timeout`, `wait_for_url`, `eval`.

```bash
browserclaw capture \
  --url https://app.example.com \
  --output generated/example/capture.har \
  --steps steps.json
```

### Option D — Authenticated capture (injected headers)

For Firebase-backed SPAs or sites requiring a Bearer token:

```bash
browserclaw capture \
  --url https://app.example.com \
  --output capture.har \
  --headless \
  --extra-headers Authorization="Bearer $FIREBASE_TOKEN"
```

Mint a Firebase test token with the Admin SDK:
```python
import firebase_admin
from firebase_admin import credentials, auth
cred = credentials.Certificate('service-account.json')
firebase_admin.initialize_app(cred)
token = auth.create_custom_token('user-uid').decode()
print(f"Bearer {token}")
```

Use `--eval '{"action":"eval","value":"window.testAuthBypass={enabled:true}"}'` to activate JS test-mode flags in the browser.

### Option E — LLM-planned steps

```bash
browserclaw capture \
  --url https://app.example.com \
  --output generated/example/capture.har \
  --goal "Log in, navigate to invoices, open the first one" \
  --provider anthropic \
  --model claude-sonnet-4-20250514
```

LLM produces a deterministic step plan. No login or CAPTCHA bypass — you still authenticate manually.

### Option F — One-shot (capture + infer + generate)

```bash
browserclaw reverse \
  --url https://app.example.com \
  --output-dir generated/example \
  --manual
```

Runs capture, infer, and generate in sequence. Emits:
- `generated/example/capture.har`
- `generated/example/catalog.json`
- `generated/example/generated_client.py`
- `generated/example/mcp_tools.json`

## Infer flow

```bash
browserclaw infer \
  --har generated/example/capture.har \
  --output generated/example/catalog.json
```

Optionally enrich with an LLM for natural-language descriptions:

```bash
browserclaw infer \
  --har generated/example/capture.har \
  --output generated/example/catalog.json \
  --site example.com \
  --goal "Document the invoice list and detail endpoints" \
  --provider anthropic \
  --model claude-sonnet-4-20250514
```

## Generate flow

```bash
browserclaw generate \
  --catalog generated/example/catalog.json \
  --output-dir generated/example
```

## Artifact reference

### `capture.har`
Raw Playwright HAR — full request/response bodies embedded. Contains all HTTP methods: GET, POST, PUT, PATCH, DELETE, and any others observed.

### `catalog.json`
Structured endpoint catalog. Each entry:
```json
{
  "name": "get_feed_updates",
  "method": "GET",
  "url_template": "https://api.example.com/v1/feed/{id}",
  "host": "api.example.com",
  "query_keys": ["limit", "offset", "filter"],
  "request_body_keys": [],
  "response_header_keys": ["content-type", "x-request-id"],
  "sample_status_codes": [200, 401],
  "sample_content_types": ["application/json"],
  "description": "Inferred from 3 captured requests."
}
```

### `generated_client.py`
A `requests.Session`-based Python client. Example:

```python
"""Generated by browserclaw from capture.har."""

import requests


class BrowserClawClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def get_feed_updates(self, limit=None, offset=None, filter=None):
        """Inferred from 3 captured requests."""
        url = "https://api.example.com/v1/feed".format()
        params = {"limit": limit, "offset": offset, "filter": filter}
        params = {key: value for key, value in params.items() if value is not None}
        payload = {}
        payload = {key: value for key, value in payload.items() if value is not None}
        response = self.session.request(
            "GET",
            url,
            params=params or None,
            json=payload or None,
        )
        response.raise_for_status()
        return response.json() if response.content else None

    def create_feed_item(self, id_0=None, title=None, body=None):
        """POST /v1/feed/{id}/items."""
        url = "https://api.example.com/v1/feed/{id}/items".format(id_0)
        params = {}
        params = {key: value for key, value in params.items() if value is not None}
        payload = {"title": title, "body": body}
        payload = {key: value for key, value in payload.items() if value is not None}
        response = self.session.request(
            "POST",
            url,
            params=params or None,
            json=payload or None,
        )
        response.raise_for_status()
        return response.json() if response.content else None
```

### `mcp_tools.json`
MCP tool definitions for tool-calling agents:
```json
{
  "schema_version": "2025-03-26",
  "site": "example.com",
  "tools": [
    {
      "name": "get_feed_updates",
      "description": "Inferred from 3 captured requests.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "limit": {"type": "string", "description": "Inferred parameter for limit"},
          "offset": {"type": "string", "description": "Inferred parameter for offset"}
        },
        "required": ["limit", "offset"],
        "additionalProperties": false
      },
      "annotations": {
        "method": "GET",
        "urlTemplate": "https://api.example.com/v1/feed"
      }
    }
  ]
}
```

## Using the generated Python client

```python
from generated_client import BrowserClawClient

client = BrowserClawClient()

# Set auth (cookies or token from manual login)
client.session.cookies.set("session", "your-session-cookie")
# or
client.session.headers["Authorization"] = "Bearer your-token"

# List resources
updates = client.get_feed_updates(limit=10, offset=0)
print(updates)

# Create a resource
result = client.create_feed_item(title="Hello", body="World content")
print(result)
```

## Using MCP tools in an agent

Register the `mcp_tools.json` with your agent's MCP server, or parse it and wire each tool to a handler that calls `generated_client.py`.

## When the browser path fails — authorization ceiling

The historical direct-API and cookie-inspection recipes that formerly appeared
here are background only. They do not authorize a new route and MUST NOT be
executed as a fallback. In particular, never run profile sweeps, read a
personal cookie store, copy or decrypt stolen-cookie material, or use an
alternate-browser recipe. The current
[`browser-control` lifecycle](../browser-control/SKILL.md#authorized-credential-reuse-the-safe-cookie-copy-contract)
overrides this skill: use Aside first, and use `browserclaw cookies decrypt` +
inject only for one explicitly authorized agent-owned source, with its
fail-closed cleanup and MFA/consent boundaries. If that authorized route lands
on a login or MFA screen, stop and report the authentication blocker or use a
provider-owned API/OAuth flow; do not probe an internal API with copied cookie
material.

## Guardrails

- **No auth bypass** — You authenticate manually during capture. The tool does not attempt to bypass login, MFA, or CAPTCHA.
- **No stealth** — Captured traffic includes real user-agent, cookies, and headers. The site sees a real browser session.
- **Authorized use only** — Inspect only sites you have permission to reverse-engineer.
- **No browser extension** — All capture runs through Playwright + Chromium directly.
- **Review generated code** — Client stubs and MCP tools are inferred from traffic, not audited APIs. Validate before production use.
