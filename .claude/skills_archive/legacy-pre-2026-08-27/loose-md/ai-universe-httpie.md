---
description: Use HTTPie to call AI Universe MCP server for multi-model analysis
type: usage
scope: project
---

# AI Universe HTTPie Usage Guide

This skill demonstrates how to use HTTPie to call the AI Universe MCP server directly for multi-model AI feedback.

## Prerequisites

1. **Install HTTPie:**
   ```bash
   # macOS
   brew install httpie

   # Ubuntu/Debian
   apt-get install httpie

   # Python (universal)
   pip install httpie
   ```

2. **Authenticate:**
   ```bash
   node scripts/auth-cli.mjs login
   ```

## Basic HTTPie Usage with MCP

### Get Authentication Token

> **Prerequisite:** Run `node scripts/auth-cli.mjs login` at least once so a valid token exists locally.

```bash
# Export token for reuse
export TOKEN=$(node scripts/auth-cli.mjs token)
```

### MCP Server Configuration

```bash
MCP_URL="https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp"
```

## Example: Second Opinion Request

### 1. Simple Question

```bash
echo '{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "agent.second_opinion",
    "arguments": {
      "question": "Should I use Redis or in-memory caching for rate limiting?"
    }
  },
  "id": 1
}' | http POST "$MCP_URL" \
  Accept:'application/json, text/event-stream' \
  Authorization:"Bearer $TOKEN" \
  --timeout=180
```

### 2. Design Review Request

```bash
# Create request JSON
REQUEST_JSON=$(cat <<'EOF'
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "agent.second_opinion",
    "arguments": {
      "question": "Design Review: Authentication system using Firebase\n\nAnalyze the architectural decisions:\n- Is OAuth flow appropriate?\n- Are there better alternatives?\n- What are potential security issues?\n- Industry best practices comparison?"
    }
  },
  "id": 1
}
EOF
)

# Send request with HTTPie
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Accept:'application/json, text/event-stream' \
  Authorization:"Bearer $TOKEN" \
  --timeout=180 \
  --print=b
```

### 3. Code Review Request

```bash
QUESTION="Code Review: Review this authentication flow for:
- Security vulnerabilities
- Token handling best practices
- Error handling gaps
- Rate limiting implementation
- Session management"

echo "{
  \"jsonrpc\": \"2.0\",
  \"method\": \"tools/call\",
  \"params\": {
    \"name\": \"agent.second_opinion\",
    \"arguments\": {
      \"question\": $(echo "$QUESTION" | jq -Rs .)
    }
  },
  \"id\": 1
}" | http POST "$MCP_URL" \
  Accept:'application/json, text/event-stream' \
  Authorization:"Bearer $TOKEN" \
  --timeout=180
```

### 4. Bug Investigation Request

```bash
http POST "$MCP_URL" \
  Accept:'application/json, text/event-stream' \
  Authorization:"Bearer $TOKEN" \
  jsonrpc=2.0 \
  method=tools/call \
  params:='{
    "name": "agent.second_opinion",
    "arguments": {
      "question": "Bug Investigation: Investigate potential issues:\n- Race conditions in async operations\n- Memory leaks in long-running processes\n- Edge cases in error handling\n- Type safety concerns"
    }
  }' \
  id:=1
```

## HTTPie Features for MCP Calls

### 1. Pretty Print Response

```bash
# Default behavior - pretty JSON output
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN"
```

### 2. Download Response to File

```bash
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN" \
  --download \
  --output=response.json
```

### 3. Show Request Headers

```bash
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN" \
  --print=HhBb  # H=request headers, h=response headers, B=request body, b=response body
```

### 4. Follow Redirects

```bash
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN" \
  --follow
```

### 5. Custom Timeout

```bash
echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN" \
  --timeout=300  # 5 minutes
```

## Parse Response with jq

### Extract Primary Opinion

```bash
RESPONSE=$(echo "$REQUEST_JSON" | http POST "$MCP_URL" \
  Authorization:"Bearer $TOKEN" \
  --print=b)

echo "$RESPONSE" | jq -r '.result.content[0].text' | jq -r '.primary.response'
```

### Extract Synthesis

```bash
echo "$RESPONSE" | jq -r '.result.content[0].text' | jq -r '.synthesis.response'
```

### Extract Cost Information

```bash
echo "$RESPONSE" | jq -r '.result.content[0].text' | jq '{
  models: .summary.totalModels,
  tokens: .summary.totalTokens,
  cost: .summary.totalCost
}'
```

## Rate Limit Status Check

```bash
# Get current rate limit status
USER_ID=$(node scripts/auth-cli.mjs status | awk '/UID:/ {print $2}')
if [ -z "$USER_ID" ]; then
  echo "❌ Unable to determine user ID. Run: node scripts/auth-cli.mjs login"
else
  jq -n --arg user_id "$USER_ID" '{
    jsonrpc: "2.0",
    method: "tools/call",
    params: {
      name: "rate-limit.status",
      arguments: {
        userId: $user_id
      }
    },
    id: 1
  }' | http POST "$MCP_URL" \
    Authorization:"Bearer $TOKEN"
fi
```

## Error Handling

### Check for Errors in Response

```bash
if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  echo "Error:" $(echo "$RESPONSE" | jq -r '.error')

  # Check for rate limit
  if echo "$RESPONSE" | jq -e '.details.resetTime' >/dev/null 2>&1; then
    echo "Rate limited. Reset at:" $(echo "$RESPONSE" | jq -r '.details.resetTime')
  fi
fi
```

## Integration with Scripts

### Complete HTTPie Script Example

```bash
#!/bin/bash

# Get token
TOKEN=$(node scripts/auth-cli.mjs token 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "❌ Not authenticated. Run: node scripts/auth-cli.mjs login"
  exit 1
fi

# Construct question
QUESTION="$1"
if [ -z "$QUESTION" ]; then
  echo "Usage: $0 'your question here'"
  exit 1
fi

# Send request
RESPONSE=$(echo "{
  \"jsonrpc\": \"2.0\",
  \"method\": \"tools/call\",
  \"params\": {
    \"name\": \"agent.second_opinion\",
    \"arguments\": {
      \"question\": $(echo "$QUESTION" | jq -Rs .)
    }
  },
  \"id\": 1
}" | http POST "https://ai-universe-backend-dev-114133832173.us-central1.run.app/mcp" \
  Accept:'application/json, text/event-stream' \
  Authorization:"Bearer $TOKEN" \
  --timeout=180 \
  --print=b)

# Parse and display
echo "$RESPONSE" | jq -r '.result.content[0].text' | jq '.'
```

## HTTPie vs curl

**Why HTTPie is preferred:**
- ✅ More readable syntax
- ✅ Automatic JSON formatting
- ✅ Pretty-printed output by default
- ✅ Better error messages
- ✅ Session support
- ✅ Easier header management

**HTTPie Example:**
```bash
http POST $URL Authorization:"Bearer $TOKEN" < request.json
```

**curl Equivalent:**
```bash
curl -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @request.json
```

## See Also

- [ai-universe-auth.md](ai-universe-auth.md) - Authentication setup
- [second_opinion.md](../commands/second_opinion.md) - Second opinion command docs
- `~/.claude/scripts/secondo-cli.sh` - Implementation reference
