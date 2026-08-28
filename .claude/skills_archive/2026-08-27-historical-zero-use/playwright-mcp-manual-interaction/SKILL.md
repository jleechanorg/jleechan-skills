# Playwright MCP - Manual Interaction Guide

## Status
Playwright MCP is **DISABLED BY DEFAULT** in Claude Code CLI and Codex CLI for context optimization.

**Location**: Can be run locally but not installed to CLI by default

## Why Disabled by Default
- **Context Optimization**: Reduces token usage during normal operations
- **Manual Control**: Available when explicitly needed for browser automation tasks
- **Local Availability**: Server can still be started manually for testing

## Enabling Playwright MCP

### Option 1: Enable in mcp_common.sh (Global)
```bash
# Set environment variable before running MCP setup
export PLAYWRIGHT_ENABLED=true
bash scripts/mcp_common.sh
```

### Option 2: Manual Server Installation
```bash
# Install Playwright MCP server globally
npm install -g @playwright/mcp

# Verify installation
npx -y @playwright/mcp --help
```

## Manual Interaction via Bash Commands

### Starting the Playwright MCP Server Manually

**Direct Node Execution**:
```bash
# Start the server (stdio mode - for manual testing)
node "$(npm root -g)/@playwright/mcp/dist/index.js"
```

**Using npx**:
```bash
# Run directly with npx
npx -y @playwright/mcp
```

### Server Communication Protocol

The Playwright MCP server uses **JSON-RPC over stdio**. Here's how to interact manually:

**⚠️ Note on Protocol Version**: The examples use protocol version "2024-11-05" which is current as of this writing. To verify the latest supported protocol version, consult the [MCP specification](https://modelcontextprotocol.io/docs) or check the server's initialization response.

**⚠️ Note on One-Shot Commands**: The examples below use piped echo commands for demonstration. Each `npx -y @playwright/mcp` invocation starts a **new server instance** that exits after processing one message. For **persistent sessions** with multiple commands, use the Interactive Testing Script or Node.js REPL approaches shown later in this document.

**1. Initialize the Server** (one-shot example):
```bash
# Send initialization request (starts new server instance)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"1.0.0"}}}' | npx -y @playwright/mcp
```

**2. List Available Tools** (one-shot example):
```bash
# Request tools list (starts new server instance)
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | npx -y @playwright/mcp
```

**3. Execute Browser Actions** (one-shot examples):
```bash
# Navigate to URL
echo '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "browser_navigate",
    "arguments": {
      "url": "https://example.com"
    }
  }
}' | npx -y @playwright/mcp

# Click element
echo '{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "browser_click",
    "arguments": {
      "selector": "button#submit"
    }
  }
}' | npx -y @playwright/mcp

# Take screenshot
echo '{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "browser_screenshot",
    "arguments": {
      "path": "docs/screenshot.png"
    }
  }
}' | npx -y @playwright/mcp
```

## Integration with Claude Code (When Enabled)

If you enable Playwright MCP in your CLI configuration, it will be available as:

**MCP Tool Pattern**: `mcp__playwright__*`

### Common Tools Available:
- `browser_navigate` - Navigate to URL
- `browser_click` - Click element by selector
- `browser_screenshot` - Capture screenshot
- `browser_evaluate` - Execute JavaScript in browser context
- `browser_fill` - Fill form fields
- `browser_press` - Press keyboard keys

## Testing Locally Without CLI Installation

### Interactive Testing Script
```bash
#!/bin/bash
# Save as: scripts/test_playwright_mcp.sh

# Create named pipe for bidirectional communication
PIPE_PATH=$(mktemp -u)
mkfifo "$PIPE_PATH"

# Start server reading from pipe, output to log
npx -y @playwright/mcp < "$PIPE_PATH" > /tmp/mcp-output.log 2>&1 &
SERVER_PID=$!

# Open pipe for writing
exec 3> "$PIPE_PATH"

# Wait for server to start
sleep 2

# Send test commands
echo "Initializing..."
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' >&3

echo "Listing tools..."
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' >&3

# Wait for responses
sleep 2

# Cleanup
exec 3>&-
kill $SERVER_PID 2>/dev/null
rm -f "$PIPE_PATH"

# Show results
echo "Server output:"
cat /tmp/mcp-output.log
```

### Using Node.js REPL
```javascript
// Start Node.js REPL
const { spawn } = require('child_process');

// Spawn Playwright MCP server
const mcp = spawn('npx', ['-y', '@playwright/mcp']);

// Send JSON-RPC request
function sendRequest(method, params = {}, id = 1) {
  const request = JSON.stringify({
    jsonrpc: '2.0',
    id: id,
    method: method,
    params: params
  });
  mcp.stdin.write(request + '\n');
}

// Listen for responses
mcp.stdout.on('data', (data) => {
  console.log('Response:', data.toString());
});

// Initialize
sendRequest('initialize', {
  protocolVersion: '2024-11-05',
  capabilities: {},
  clientInfo: { name: 'node-test', version: '1.0.0' }
});

// List tools
sendRequest('tools/list', {}, 2);
```

## Configuration Files

### Where Playwright MCP Would Be Registered (If Enabled)
```json
// ~/.claude/config.json (Claude Code CLI)
{
  "mcpServers": {
    "playwright-mcp": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"]
    }
  }
}
```

```json
// ~/.codex/config.json (Codex CLI)
{
  "mcpServers": {
    "playwright-mcp": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"]
    }
  }
}
```

## Use Cases for Manual Interaction

1. **Testing Browser Automation**: Test Playwright scripts without full CLI integration
2. **Debugging**: Manually send commands to debug browser automation issues
3. **CI/CD Integration**: Run Playwright MCP in headless mode for automated testing
4. **Development**: Develop and test new browser automation workflows

## Re-enabling for Specific Projects

If you need Playwright MCP for a specific project:

```bash
# Project-specific enable
cd /path/to/project
export PLAYWRIGHT_ENABLED=true
bash scripts/mcp_common.sh

# This will add Playwright MCP to your CLI configs
```

## Troubleshooting

### Server Not Starting
```bash
# Verify installation
npm list -g @playwright/mcp

# Reinstall if needed
npm install -g @playwright/mcp

# Check Node.js version (requires Node 18+)
node --version
```

### Communication Issues
```bash
# Test stdio communication
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | npx -y @playwright/mcp

# Should see JSON-RPC response
```

### Browser Launch Failures
```bash
# Install Playwright browsers
npx playwright install

# Install system dependencies (Ubuntu/Debian)
npx playwright install-deps
```

## Alternative: Use Chrome Superpowers MCP

For simple browser automation needs, consider using Chrome Superpowers MCP which is enabled by default:

**Tool**: `mcp__chrome-superpower__use_browser`

See: `.claude/skills/chrome-superpowers-reference.md`

## Related Files
- **Installation Script**: `scripts/mcp_common.sh` (PLAYWRIGHT_ENABLED flag)
- **Chrome Alternative**: `.claude/skills/chrome-superpowers-reference.md`
- **Browser Testing**: `.claude/skills/browser-testing-ocr-validation.md`

## Notes
- Playwright MCP is a **system-level MCP server**, not a user-created skill
- Disabled by default to optimize context usage in normal operations
- Can be manually started and controlled via bash commands and JSON-RPC
- Full CLI integration available by setting `PLAYWRIGHT_ENABLED=true`
