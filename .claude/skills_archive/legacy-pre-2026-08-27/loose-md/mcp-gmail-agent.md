---
description: MCP Gmail Agent - Email Automation and Processing with Model Context Protocol
type: setup
scope: project
---

# MCP Gmail Agent - Email Automation and Processing

This skill provides comprehensive setup and usage documentation for integrating Gmail with Claude Code via MCP (Model Context Protocol) servers, enabling intelligent email processing and automation.

## 📋 Overview

**Purpose**: Enable Claude to interact with Gmail for automated email processing, including reading, analyzing, drafting responses, organizing, and taking actions based on email content.

**Core Capabilities:**
- Read and search emails
- Send and draft emails
- Manage labels and categories
- Handle attachments
- Create and manage filters
- Archive and organize messages
- Extract action items and create tasks

## 🚀 Prerequisites

- Node.js (>=18.0.0) installed
- Gmail account with appropriate permissions
- Google Cloud Project with Gmail API enabled (for some implementations)
- Claude Code with MCP support

## 🛠️ Available MCP Gmail Servers

### Option 1: @gongrzhe/server-gmail-autoauth-mcp (Recommended)

**Features:**
- Auto-authentication support
- Full Gmail API integration
- Read, send, search, label management
- Attachment handling

**Installation:**

```bash
# Install via npm (optional, npx can run without install)
npm install -g @gongrzhe/server-gmail-autoauth-mcp
```

**Configuration in `.claude/settings.json`:**

```json
{
  "mcpServers": {
    "gmail-autoauth": {
      "command": "npx",
      "args": [
        "-y",
        "@gongrzhe/server-gmail-autoauth-mcp"
      ]
    }
  }
}
```

> **Security note:** The `-y` flag auto-accepts package installation each time the MCP server launches. For production or security-sensitive environments, pin a vetted version by installing the package explicitly (`npm install`) and reference the local binary instead of relying on `npx -y`.

**Authentication Setup:**

```bash
# 1. Set up Google Cloud Project and get OAuth credentials
# Download gcp-oauth.keys.json from Google Cloud Console

# 2. Place credentials in home directory
mkdir -p ~/.gmail-mcp
cp path/to/gcp-oauth.keys.json ~/.gmail-mcp/

# 3. Run authentication flow
npx @gongrzhe/server-gmail-autoauth-mcp auth

# 4. Follow browser OAuth flow to grant permissions
```

### Option 2: tjzaks/gmail-mcp-server

**Features:**
- Open-source implementation
- Customizable for specific workflows
- Full Gmail API access

**Installation:**

```bash
# Clone repository
git clone https://github.com/tjzaks/gmail-mcp-server.git
cd gmail-mcp-server

# Install dependencies
npm install

# Build project
npm run build
```

**Configuration in `.claude/settings.json`:**

```json
{
  "mcpServers": {
    "gmail": {
      "command": "node",
      "args": [
        "/path/to/gmail-mcp-server/build/index.js"
      ],
      "env": {
        "GMAIL_CREDENTIALS_PATH": "${HOME}/.gmail-mcp/credentials.json",
        "GMAIL_TOKEN_PATH": "${HOME}/.gmail-mcp/token.json"
      }
    }
  }
}
```

### Option 3: cafferychen777/gmail-mcp (Chrome Extension)

**Features:**
- No Google Cloud Project required
- No OAuth consent screen setup
- No API keys needed
- Uses existing Chrome session
- Zero configuration authentication

**Installation:**

```bash
# Install Chrome extension
# Visit: https://github.com/cafferychen777/gmail-mcp

# Extension handles authentication automatically using active Gmail session
```

**Configuration in `.claude/settings.json`:**

```json
{
  "mcpServers": {
    "gmail-chrome": {
      "command": "npx",
      "args": [
        "-y",
        "@cafferychen777/gmail-mcp"
      ]
    }
  }
}
```

> **Environment compatibility:** This approach assumes access to a Chrome browser session. It is typically unsuitable for headless or CLI-only Claude Code environments where browser extensions cannot run.

## 🔑 Google Cloud Setup (for OAuth-based servers)

### Step 1: Create Google Cloud Project

```bash
# 1. Visit Google Cloud Console: https://console.cloud.google.com
# 2. Create new project or select existing
# 3. Enable Gmail API:
#    - Navigate to "APIs & Services" > "Library"
#    - Search for "Gmail API"
#    - Click "Enable"
```

### Step 2: Configure OAuth Consent Screen

```bash
# 1. Navigate to "APIs & Services" > "OAuth consent screen"
# 2. Select "External" user type (or "Internal" for Workspace)
# 3. Fill in application details:
#    - App name: "Claude MCP Gmail"
#    - User support email: your email
#    - Developer contact: your email
# 4. Add scopes:
#    - .../auth/gmail.readonly (read emails)
#    - .../auth/gmail.modify (modify labels, archive)
#    - .../auth/gmail.compose (draft and send)
#    - .../auth/gmail.labels (manage labels)
```

### Step 3: Create OAuth Credentials

```bash
# 1. Navigate to "APIs & Services" > "Credentials"
# 2. Click "Create Credentials" > "OAuth client ID"
# 3. Application type: "Desktop app"
# 4. Name: "Claude Gmail MCP"
# 5. Download JSON file as "gcp-oauth.keys.json"
```

### Step 4: Place Credentials

```bash
# Create directory
mkdir -p ~/.gmail-mcp

# Copy credentials
cp ~/Downloads/gcp-oauth.keys.json ~/.gmail-mcp/

# Secure permissions
chmod 600 ~/.gmail-mcp/gcp-oauth.keys.json
```

## 🔐 Authentication Flow

### Initial Authentication

```bash
# Run authentication command
npx @gongrzhe/server-gmail-autoauth-mcp auth

# Or for other implementations:
node /path/to/gmail-mcp-server/build/auth.js
```

**What happens:**
1. Local callback server starts (default port 9005 unless overridden by the MCP server configuration)
2. Browser opens to Google OAuth consent screen
3. User signs in and grants permissions
4. OAuth tokens saved to `~/.gmail-mcp/token.json`
5. Access token expires after 1 hour
6. Refresh token enables automatic renewal

### Check Authentication Status

```bash
# For auto-auth implementation
npx @gongrzhe/server-gmail-autoauth-mcp status

# Manually check token file
cat ~/.gmail-mcp/token.json | jq .
```

### Token Refresh

**Automatic**: MCP server automatically refreshes expired access tokens using refresh token

**Manual**:
```bash
npx @gongrzhe/server-gmail-autoauth-mcp refresh
```

**Proactive rotation:** Schedule periodic re-authentication (e.g., quarterly) for long-running deployments to ensure credentials remain valid even if refresh tokens lapse due to inactivity.

### Re-authentication

If refresh token expires (rare, typically 6 months of inactivity):

```bash
# Delete old token
rm ~/.gmail-mcp/token.json

# Re-authenticate
npx @gongrzhe/server-gmail-autoauth-mcp auth
```

## 📧 MCP Gmail Tools & Capabilities

### Available MCP Tools (typical implementations)

**Email Reading:**
- `mcp__gmail__get_messages` - Retrieve messages by query
- `mcp__gmail__get_message` - Get specific message by ID
- `mcp__gmail__search` - Search emails with Gmail query syntax
- `mcp__gmail__list_unread` - Get unread messages

**Email Sending:**
- `mcp__gmail__send_message` - Send new email
- `mcp__gmail__create_draft` - Create draft email
- `mcp__gmail__reply` - Reply to message
- `mcp__gmail__forward` - Forward message

**Organization:**
- `mcp__gmail__apply_label` - Add label to message
- `mcp__gmail__remove_label` - Remove label from message
- `mcp__gmail__create_label` - Create new label
- `mcp__gmail__archive` - Archive message
- `mcp__gmail__trash` - Move to trash
- `mcp__gmail__star` - Star/unstar message

**Advanced:**
- `mcp__gmail__get_attachment` - Download attachment
- `mcp__gmail__batch_modify` - Modify multiple messages
- `mcp__gmail__get_threads` - Retrieve email threads
- `mcp__gmail__modify_thread` - Modify entire thread

> **Tool discovery tip:** The names shown above match the actual tool identifiers exposed by most Gmail MCP servers. Run `list-tools` (or check the server's README) after connecting to confirm the exact names available in your deployment.

### Gmail Query Syntax (for search)

```bash
# Unread messages
is:unread

# From specific sender
from:example@domain.com

# Subject contains
subject:"Project Update"

# Has attachment
has:attachment

# Date range
after:2025/01/01 before:2025/01/31

# Multiple conditions
from:github.com is:unread has:attachment

# Exclude
-from:noreply@spam.com

# Specific label
label:important
```

## 🎯 Usage Examples

### Example 1: Read Unread Emails

```bash
# Claude command (after /processmsgs invoked)
Use mcp__gmail__list_unread to retrieve all unread messages
Filter and display sender, subject, date for each
```

### Example 2: Create Draft Reply

```bash
# Analyze email content
# Generate contextually appropriate response
# Use mcp__gmail__create_draft with:
#   - to: original sender
#   - subject: RE: original subject
#   - body: generated response
#   - threadId: original thread (for threading)
```

### Example 3: Label and Archive

```bash
# After processing email:
# 1. Apply label: mcp__gmail__apply_label(messageId, "claude-processed")
# 2. Archive: mcp__gmail__archive(messageId)
# 3. Report action taken
```

### Example 4: Search and Process

```bash
# Search for urgent emails from last 24h
Use mcp__gmail__search with query: "is:unread after:2025/01/20 (urgent OR deadline)"
For each result:
  - Parse content
  - Extract action items
  - Create draft response
  - Apply "urgent" label
```

## 🔄 Integration with /processmsgs Command

The `/processmsgs` command leverages these MCP tools to:

1. **Retrieve** unread emails via `mcp__gmail__list_unread`
2. **Analyze** content for classification
3. **Draft** responses using `mcp__gmail__create_draft`
4. **Label** emails with `mcp__gmail__apply_label`
5. **Archive** processed emails via `mcp__gmail__archive`
6. **Flag** urgent items with `mcp__gmail__star`

## 🐛 Troubleshooting

### MCP Server Not Found

```bash
# Verify MCP server configuration
cat .claude/settings.json | jq .mcpServers

# Test npx execution manually
npx -y @gongrzhe/server-gmail-autoauth-mcp --help

# Check Claude Code logs for MCP startup errors
```

### Authentication Failures

```bash
# Check credentials exist
ls -la ~/.gmail-mcp/

# Verify credentials format
cat ~/.gmail-mcp/gcp-oauth.keys.json | jq .

# Re-run authentication
npx @gongrzhe/server-gmail-autoauth-mcp auth

# Check token validity
cat ~/.gmail-mcp/token.json | jq .expiry_date
```

### Permission Denied Errors

```bash
# Ensure proper OAuth scopes in Google Cloud Console
# Required scopes:
# - https://www.googleapis.com/auth/gmail.readonly
# - https://www.googleapis.com/auth/gmail.modify
# - https://www.googleapis.com/auth/gmail.compose
# - https://www.googleapis.com/auth/gmail.labels

# Delete token and re-authenticate to get new scopes
rm ~/.gmail-mcp/token.json
npx @gongrzhe/server-gmail-autoauth-mcp auth
```

### Rate Limit Issues

```bash
# Gmail API quotas (per Google Cloud Project):
# - 1 billion quota units/day
# - 250 quota units/user/second
#
# Solutions:
# 1. Implement exponential backoff
# 2. Batch requests when possible
# 3. Request quota increase in Google Cloud Console
```

### Port Already in Use (OAuth callback)

```bash
# Find process using port 9005
lsof -ti:9005 | xargs kill -9

# Or modify MCP server config to use different port
# (server-specific, check documentation)
```

## 🔒 Security Best Practices

1. **Credentials Security:**
   ```bash
   # Always secure credential files
   chmod 600 ~/.gmail-mcp/gcp-oauth.keys.json
   chmod 600 ~/.gmail-mcp/token.json

   # Never commit to version control
   echo "~/.gmail-mcp/" >> ~/.gitignore
   ```

2. **Scope Minimization:**
   - Only request OAuth scopes needed for your use case
   - Avoid `gmail.full-access` scope unless absolutely necessary

3. **Token Management:**
   - Tokens stored locally on machine
   - Regularly review authorized apps: https://myaccount.google.com/permissions
   - Revoke access if compromised

4. **MCP Server Trust:**
   - Only install MCP servers from trusted sources
   - Review code for open-source implementations
   - Monitor network activity if concerned

## 📊 Performance Considerations

**Optimization Strategies:**
- Cache email metadata locally for repeated access
- Use batch operations for multiple emails
- Filter emails server-side with Gmail queries (faster than client-side)
- Limit attachment downloads unless necessary
- Use pagination for large result sets

**Rate Limiting:**
```bash
# Implement delays between requests
# Typical safe rate: 1 request/second for sustained operations
# Burst operations: up to 10 requests/second briefly
```

## 🔗 Related Commands

- **`/processmsgs`** - Main command using this MCP integration
- **`/memory`** - Store extracted tasks and action items
- **`/learn`** - Learn from email patterns and improve processing

## 📚 Additional Resources

**Official Documentation:**
- Gmail API: https://developers.google.com/gmail/api
- MCP Specification: https://modelcontextprotocol.io/
- Google OAuth 2.0: https://developers.google.com/identity/protocols/oauth2

**MCP Gmail Implementations:**
- @gongrzhe/server-gmail-autoauth-mcp: https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp
- tjzaks/gmail-mcp-server: https://github.com/tjzaks/gmail-mcp-server
- cafferychen777/gmail-mcp: https://github.com/cafferychen777/gmail-mcp

**Community:**
- Claude MCP Community: https://www.claudemcp.com/
- MCP Servers Hub: https://lobehub.com/mcp/

## ✅ Verification

**Test MCP Gmail Setup:**

```bash
# 1. Restart Claude Code after configuration
# 2. Try simple email read command:
/processmsgs recent

# 3. Check for MCP tool calls in output
# Expected: mcp__gmail__* tools being invoked

# 4. Verify actions taken (drafts, labels, etc.)
# Check Gmail web interface for changes
```

## 🎓 Quick Start Summary

```bash
# 1. Choose MCP implementation (recommend: @gongrzhe/server-gmail-autoauth-mcp)

# 2. Set up Google Cloud Project and get OAuth credentials

# 3. Configure in .claude/settings.json

# 4. Authenticate
npx @gongrzhe/server-gmail-autoauth-mcp auth

# 5. Restart Claude Code

# 6. Test with /processmsgs command
/processmsgs

# 7. Verify emails processed and actions taken
```

## 🚨 Important Notes

- **First Run**: Initial authentication requires browser access
- **Token Expiry**: Access tokens expire after 1 hour but refresh automatically
- **Privacy**: Email content processed locally by Claude, not sent to external APIs (beyond Google Gmail API)
- **User Control**: All send operations create drafts first, user reviews before sending
- **Revocation**: Can revoke access anytime via Google account settings

## 📈 Future Enhancements

**Potential Additions:**
- Sentiment analysis of incoming emails
- Automated calendar integration for meeting requests
- Smart reply suggestions based on user patterns
- Email thread summarization
- Attachment content analysis
- Integration with project management tools
- Multi-account support
- Custom automation rules and workflows
