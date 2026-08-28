# Your Project MCP Server Usage

## Overview

The Your Project MCP server uses **JSON-RPC 2.0** protocol over HTTP POST.

## Endpoints

### Local Development Server
```
POST http://localhost:8081/mcp
Content-Type: application/json
```

### GCP Preview/Production Server
```
POST https://<deployment-url>.run.app/mcp
Content-Type: application/json
```

**Note:** GCP preview URLs are provided in PR comments. The MCP endpoint is always `/mcp` appended to the base URL.

**Example GCP Preview:**
- Base URL: `https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app`
- MCP Endpoint: `https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/mcp`
- Health Check: `https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/health`

**Finding GCP Preview URL:**
```bash
gh pr view <PR_NUMBER> --comments | grep "MCP Endpoint" | grep -E 'https://.*\.run\.app'
```

## Authentication Bypass (Local Dev)

Use the `X-Test-User-ID` header for local testing without Firebase auth:
```bash
-H "X-Test-User-ID: <firebase_uid>"
```

**Finding the user ID:** Check server logs for `user=<uid>` entries:
```bash
grep "user=" /tmp/your-project.com/*/flask-server.log | tail -10
```

## Available Tools

```bash
# List all tools
curl -s -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}' | jq '.result.tools[].name'
```

Tools:
- `create_campaign` - Create a new campaign
- `get_campaign_state` - Get current campaign state
- `process_action` - Send player action and get response
- `update_campaign` - Update campaign settings
- `export_campaign` - Export campaign data
- `get_campaigns_list` - List user's campaigns
- `get_user_settings` - Get user preferences
- `update_user_settings` - Update user preferences

## JSON-RPC Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {
      "<arg1>": "<value1>",
      "user_id": "<firebase_uid>"
    }
  },
  "id": 1
}
```

## Common Operations

### Get Campaign State

```bash
cat > /tmp/req.json << 'EOF'
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_campaign_state", "arguments": {"campaign_id": "<campaign_id>", "user_id": "<uid>"}}, "id": 1}
EOF
curl -s -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -H "X-Test-User-ID: <uid>" \
  -d @/tmp/req.json | jq '.result'
```

### Process Player Action

```bash
cat > /tmp/req.json << 'EOF'
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "process_action", "arguments": {"campaign_id": "<campaign_id>", "user_id": "<uid>", "user_input": "I attack the goblin", "mode": "character"}}, "id": 1}
EOF
curl -s -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -H "X-Test-User-ID: <uid>" \
  -d @/tmp/req.json | jq '.result | {dice_rolls, narrative: .narrative[0:200]}'
```

### List Campaigns

```bash
cat > /tmp/req.json << 'EOF'
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_campaigns_list", "arguments": {"user_id": "<uid>"}}, "id": 1}
EOF
curl -s -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -H "X-Test-User-ID: <uid>" \
  -d @/tmp/req.json | jq '.result.campaigns'
```

## Debugging Tips

### Check Server Logs

```bash
# Real-time log monitoring
tail -f /tmp/your-project.com/*/flask-server.log

# Check for dice roll processing
grep -E "NATIVE|Phase|tool_call|dice" /tmp/your-project.com/*/flask-server.log | tail -20

# Find user IDs for campaigns
grep "user=" /tmp/your-project.com/*/flask-server.log | tail -10
```

### GCP Preview Server Endpoints

### Finding GCP Preview URL from PR Comments
```bash
# Get latest GCP preview URL for a PR
gh pr view <PR_NUMBER> --comments | grep "MCP Endpoint" | grep -E 'https://.*\.run\.app' | head -1 | sed -E 's/.*(https:\/\/[^)]+).*/\1/'
```

### GCP Endpoint Structure
- **Base URL**: `https://<deployment-id>.run.app`
- **MCP Endpoint**: `https://<deployment-id>.run.app/mcp` (always `/mcp` appended)
- **Health Check**: `https://<deployment-id>.run.app/health`

### Example: PR #3491 GCP Preview
```bash
# Base URL
https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app

# MCP Endpoint
https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/mcp

# Health Check
https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/health
```

### Testing GCP Preview Endpoint
```bash
# Test MCP endpoint is working
curl -s -X POST https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools[].name'

# Test create_campaign tool
curl -s -X POST https://mvp-site-app-s1-i6xf2p72ka-uc.a.run.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"create_campaign","arguments":{"user_id":"test_user","title":"Test"}}}'
```

**Note:** GCP preview servers may have transient issues. If you get HTTP 404, verify the endpoint URL is correct and try again.

### Test Execution Notes

- **`test_agent_selection_classifier.py`**: Comprehensive integration test that exercises all 7 agents with real LLMs. This test can take 15-20 minutes to complete due to multiple LLM calls per test case. Use a longer timeout (1200 seconds / 20 minutes) when running this test.
- Other tests (`test_classifier_model_loading_failure.py`, `test_json_parsing_failure.py`) complete faster (~1-2 minutes each).

## Common Issues

1. **Campaign not found**: Use correct Firebase UID (not email)
2. **Method not allowed (405)**: Use POST to `/mcp` endpoint
3. **Empty dice_rolls**: LLM may skip tool calls - check Phase 1/2 logs
4. **HTTP 404 on GCP**: Verify endpoint URL is correct (should end with `/mcp`). May be transient - retry.
5. **Port confusion**: GCP preview servers don't use ports - use full URL with `/mcp` path
