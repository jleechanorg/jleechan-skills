---
description: How to start a local development server for Your Project
---

# Running the Local Development Server

## Quick Start

```bash
# Default: random port, background mode, logs in current terminal
./run_local_server.sh

# Non-default port, no log streaming (best for agents/CI)
./run_local_server.sh --no-log-stream

# Force default ports (8081 Flask, 3002 React)
./run_local_server.sh --force-default-port

# Interactive cleanup of existing servers
./run_local_server.sh --cleanup
```

## What It Does

1. Activates/creates Python venv and installs requirements
2. Loads API keys from Google Secret Manager (Gemini, Cerebras, OpenRouter)
3. Picks available ports (branch-hash or random in 8100–8199 range)
4. Cache-busts frontend assets to a temp dir (`/var/folders/.../frontend_v1_cache_bust.*`)
5. Starts Flask backend + MCP server in background
6. Validates both servers are healthy

## Server URLs

After startup, the script prints the URLs:

| Service | Default Port | Random Port Range |
|---------|-------------|-------------------|
| Flask Backend (serves V1 frontend) | 8081 | 8100–8199 |
| MCP Server | 8001 | 8100–8199 |
| React Frontend (V2) | DISABLED | — |

## Auth Bypass for Development

Append URL params to bypass Firebase auth:
```
http://localhost:<PORT>/?test_mode=true&test_user_id=test-user-123
```

With fantasy theme:
```
http://localhost:<PORT>/?test_mode=true&test_user_id=test-user-123&test_theme=fantasy
```

## Log Files

```bash
# Flask logs
cat /tmp/<repo-name>/<branch-name>/flask_backend.log

# Tail live
tail -f /tmp/<repo-name>/<branch-name>/flask_backend.log

# Find errors
grep -i "error\|500\|traceback" /tmp/<repo-name>/<branch-name>/flask_backend.log | tail -20
```

## Hot-swapping CSS for Testing

The server serves from a cache-bust temp dir. To test CSS changes without restarting:

```bash
# Find the active temp dir
find $TMPDIR -maxdepth 1 -name 'frontend_v1_cache_bust.*' -type d

# Copy new CSS into it (server picks up changes immediately — no cache)
cp $PROJECT_ROOT/frontend_v1/themes/fantasy.css /var/folders/.../frontend_v1_cache_bust.XXXXXX/themes/fantasy.css
```

## Stopping Servers

```bash
# Option 1: Kill by PID files
kill $(cat /tmp/<repo-name>/<branch-name>/flask_backend.pid) $(cat /tmp/<repo-name>/<branch-name>/mcp_server.pid)

# Option 2: Interactive cleanup
./run_local_server.sh --cleanup

# Option 3: Find and kill by port
lsof -ti :8054 | xargs kill
```

## Capturing Screenshots from Live Server

Use Playwright to capture themed screenshots:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto("http://localhost:8054/?test_theme=fantasy&test_mode=true&test_user_id=screenshot-user")
    page.wait_for_timeout(2000)
    page.screenshot(path="/tmp/screenshot.png")
    browser.close()
```

Or use the smoke test runner:
```bash
# Against the live server (may hang if theme detection differs)
TEST_BASE_URL=http://localhost:8054 python3 testing_ui/test_smoke_fantasy.py

# Start its own server (most reliable)
python3 testing_ui/test_smoke_fantasy.py
```

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Port in use | `./run_local_server.sh --cleanup` or `lsof -ti :<PORT> \| xargs kill` |
| Missing API keys | Ensure `gcloud` is configured with `worldarchitecture-ai` project |
| Venv creation fails | Delete `venv/` and re-run |
| CSS changes not showing | Server serves from cache-bust temp dir; either hot-swap or restart |
| Smoke test hangs on live server | Use direct Playwright script instead (theme detection race condition) |
