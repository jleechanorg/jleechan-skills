---
description: Authenticate with AI Universe MCP server for multi-model commands
type: setup
scope: project
---

# AI Universe Authentication Setup

This skill provides authentication setup for the AI Universe MCP server, which powers the `/secondo` command for multi-model AI feedback.

## Script Location

**IMPORTANT:** Always look for `auth-cli.mjs` in these locations (in order of preference):

| Location | Description | Has node_modules |
|----------|-------------|------------------|
| `scripts/auth-cli.mjs` | Project-local (recommended) | Needs parent project |
| `~/.claude/scripts/auth-cli.mjs` | User-global fallback | Yes (if installed) |
| `~/projects/ai_universe/scripts/auth-cli.mjs` | Source of truth | Yes |

**To run the script**, use a directory that has `node_modules` with `express` installed:

```bash
# From ai_universe project (always works)
cd ~/projects/ai_universe && node scripts/auth-cli.mjs status

# Or from ~/.claude if deps installed
node ~/.claude/scripts/auth-cli.mjs status
```

## Multi-Project Support

The script supports **two Firebase projects**. Use the correct one for your use case:

| Project | Firebase ID | Use Case | Command |
|---------|-------------|----------|---------|
| **AI Universe** | `ai-universe-b3551` | `/secondo`, multi-model synthesis | `node scripts/auth-cli.mjs token` (default) |
| **WorldAI** | `worldarchitecture-ai` | Your Project app auth | `node scripts/auth-cli.mjs token --project worldarchitecture-ai` |

### When to Use Each Project

#### AI Universe (`ai-universe-b3551`) - DEFAULT
- `/secondo` command for multi-model second opinions
- AI Universe MCP server calls
- Multi-model synthesis API

```bash
# Default - no flag needed
node scripts/auth-cli.mjs login
node scripts/auth-cli.mjs token
```

#### WorldAI (`worldarchitecture-ai`)
- Your Project application authentication
- Firebase auth for the RPG game platform
- Direct WorldAI API calls

```bash
# Explicit project flag required
node scripts/auth-cli.mjs login --project worldarchitecture-ai
node scripts/auth-cli.mjs token --project worldarchitecture-ai
```

## Prerequisites

- Node.js (>=20.0.0) installed
- Express dependency installed (`npm install express`)
- Browser for OAuth flow

## Authentication Flow

### 1. Initial Login

```bash
# AI Universe (default) - for /secondo
node scripts/auth-cli.mjs login

# WorldAI - for Your Project
node scripts/auth-cli.mjs login --project worldarchitecture-ai
```

**What happens:**
- Starts local callback server on port 9005
- Opens browser to Firebase Google sign-in
- User signs in with Google account
- ID token and refresh token saved to `~/.ai-universe/auth-token-<project-id>.json`
- ID token expires after 1 hour (Firebase security policy)
- Refresh token enables automatic token renewal

### 2. Check Authentication Status

```bash
node scripts/auth-cli.mjs status
```

**Output includes:**
- User information (name, email, UID)
- Firebase Project being used
- Token creation time
- Token expiration time
- Current validity status

### 3. Get Token for Scripts

```bash
# Get token (auto-refreshes if expired, does nothing if valid)
TOKEN=$(node scripts/auth-cli.mjs token)
echo $TOKEN

# For WorldAI project
TOKEN=$(node scripts/auth-cli.mjs token --project worldarchitecture-ai)
```

**Token Behavior:**
- **Token Valid**: Returns it immediately
- **Token Expired**: Auto-refreshes using refresh token (silent, no browser popup)
- **Refresh Token Expired**: Prompts for login (browser OAuth)

This enables seamless 30+ day sessions.

### 4. Manual Token Refresh

```bash
node scripts/auth-cli.mjs refresh
```

### 5. Test MCP Connection

```bash
node scripts/auth-cli.mjs test
```

### 6. Logout

```bash
node scripts/auth-cli.mjs logout
```

## Troubleshooting

### Script Not Found or Missing Dependencies

```bash
# Option 1: Run from ai_universe project
cd ~/projects/ai_universe && node scripts/auth-cli.mjs status

# Option 2: Install deps in ~/.claude
cd ~/.claude && npm install express

# Option 3: Copy working script
cp ~/projects/ai_universe/scripts/auth-cli.mjs ~/.claude/scripts/
```

### PROJECT_NUMBER_MISMATCH Error

This means the token was created for a different Firebase project than you're trying to use.

```bash
# Check which project your token is for
node scripts/auth-cli.mjs status
# Look for "Firebase Project:" line

# Re-login for the correct project
node scripts/auth-cli.mjs login                              # AI Universe
node scripts/auth-cli.mjs login --project worldarchitecture-ai  # WorldAI
```

### Port 9005 Already in Use

```bash
lsof -ti:9005 | xargs kill -9
```

### Token Expired

```bash
# Auto-refresh (silent)
TOKEN=$(node scripts/auth-cli.mjs token)

# Or manual refresh
node scripts/auth-cli.mjs refresh

# If refresh token expired, re-login
node scripts/auth-cli.mjs login
```

## Token Storage

- **Location**: `~/.ai-universe/auth-token-<project-id>.json` (separate file per project)
- **ID Token**: 1-hour expiration (Firebase policy)
- **Refresh Token**: ~30 days, enables silent renewal
- **Security**: Never commit tokens, localhost OAuth only

## Integration with Commands

| Command | Project | Authentication |
|---------|---------|----------------|
| `/secondo` | AI Universe | `node scripts/auth-cli.mjs token` (default) |
| WorldAI API | WorldAI | `node scripts/auth-cli.mjs token --project worldarchitecture-ai` |

## Keeping Scripts in Sync

The source of truth for `auth-cli.mjs` is `~/projects/ai_universe/scripts/auth-cli.mjs`.

To sync to other locations:
```bash
# Sync to project .claude/scripts/
cp ~/projects/ai_universe/scripts/auth-cli.mjs .claude/scripts/

# Sync to user ~/.claude/scripts/
cp ~/projects/ai_universe/scripts/auth-cli.mjs ~/.claude/scripts/
```

## Related Skills

- [ai-universe-httpie.md](ai-universe-httpie.md) - HTTPie usage examples
- [secondo-dependencies.md](secondo-dependencies.md) - /secondo command dependencies
