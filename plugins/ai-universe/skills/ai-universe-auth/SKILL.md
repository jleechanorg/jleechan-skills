---
name: ai-universe-auth
description: Authenticate with AI Universe MCP server for multi-model commands
type: setup
scope: project
---

# AI Universe Authentication Setup

This skill provides authentication setup for the AI Universe MCP server, which powers the `/secondo` command for multi-model AI feedback.

Use existing credentials and their supported refresh path first. Follow the
shared credential and isolated-browser owners before starting an interactive
login; this recipe does not authorize new access, personal-browser use or
credential rotation. Capture token output in a variable, never in logs or chat.

## Select the authentication runtime

Before any authentication command, use the host's already loaded nvm setup to
resolve its installed Node 22. If nvm or Node 22 is unavailable, report that
prerequisite; do not use a different major version or change persistent defaults.

```bash
AUTH_NODE="$(nvm which 22)" || exit 1
[ -x "$AUTH_NODE" ] || exit 1
case "$("$AUTH_NODE" --version)" in v22.*) ;; *) exit 1 ;; esac
```

Use this same verified `AUTH_NODE` executable for every command below.


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
cd ~/projects/ai_universe && "$AUTH_NODE" scripts/auth-cli.mjs status

# Or from ~/.claude if deps installed
"$AUTH_NODE" ~/.claude/scripts/auth-cli.mjs status
```

## Multi-Project Support

The script supports **two Firebase projects**. Use the correct one for your use case:

| Project | Firebase ID | Use Case | Command |
|---------|-------------|----------|---------|
| **AI Universe** | `ai-universe-b3551` | `/secondo`, multi-model synthesis | `"$AUTH_NODE" scripts/auth-cli.mjs token` (default) |
| **WorldAI** | `worldarchitecture-ai` | Your Project app auth | `"$AUTH_NODE" scripts/auth-cli.mjs token --project worldarchitecture-ai` |

### When to Use Each Project

#### AI Universe (`ai-universe-b3551`) - DEFAULT
- `/secondo` command for multi-model second opinions
- AI Universe MCP server calls
- Multi-model synthesis API

```bash
# Use an existing verified token or supported silent refresh immediately.
# Interactive login is only an authorized recovery step when needed.
TOKEN=$("$AUTH_NODE" scripts/auth-cli.mjs token)
```

#### WorldAI (`worldarchitecture-ai`)
- Your Project application authentication
- Firebase auth for the RPG game platform
- Direct WorldAI API calls

```bash
# Use an existing verified token or supported silent refresh immediately.
TOKEN=$("$AUTH_NODE" scripts/auth-cli.mjs token --project worldarchitecture-ai)
```

## Prerequisites

- Node.js 22 installed and selected through the verified `AUTH_NODE` above
- Express dependency installed (`npm install express`)
- Browser for OAuth flow

## Authentication Flow

### 1. Interactive Login (authorized recovery only)

Use existing credentials and their supported refresh path first. Before an
interactive login, complete both required credential probes and follow the
browser owner for explicit authority and a verified task-owned isolated
browser. If those conditions are not met, report the exact dependency without
starting login.

```bash
# AI Universe (default) - for /secondo
"$AUTH_NODE" scripts/auth-cli.mjs login

# WorldAI - for Your Project
"$AUTH_NODE" scripts/auth-cli.mjs login --project worldarchitecture-ai
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
"$AUTH_NODE" scripts/auth-cli.mjs status
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
TOKEN=$("$AUTH_NODE" scripts/auth-cli.mjs token)
test -n "$TOKEN" && printf 'Token available\n'

# For WorldAI project
TOKEN=$("$AUTH_NODE" scripts/auth-cli.mjs token --project worldarchitecture-ai)
```

**Token Behavior:**
- **Token Valid**: Returns it immediately
- **Token Expired**: Auto-refreshes using refresh token (silent, no browser popup)
- **Refresh Token Expired**: This token command may prompt for interactive browser OAuth. Do not block retrieval of an existing verified usable token or a supported non-interactive refresh on the two login-failure probes. If the command would start interactive login, first exhaust existing credential routes; start login only after both required probes fail and the browser owner confirms explicit authority and a verified task-owned isolated browser. Otherwise stop before interactive login and report that boundary.

This enables seamless 30+ day sessions.

### 4. Manual Token Refresh

```bash
"$AUTH_NODE" scripts/auth-cli.mjs refresh
```

### 5. Test MCP Connection

```bash
"$AUTH_NODE" scripts/auth-cli.mjs test
```

### 6. Logout

```bash
"$AUTH_NODE" scripts/auth-cli.mjs logout
```

## Troubleshooting

### Script Not Found or Missing Dependencies

```bash
# Option 1: Run from ai_universe project
cd ~/projects/ai_universe && "$AUTH_NODE" scripts/auth-cli.mjs status

# Option 2: Install deps in ~/.claude
cd ~/.claude && npm install express

# Option 3: Copy working script
cp ~/projects/ai_universe/scripts/auth-cli.mjs ~/.claude/scripts/
```

### PROJECT_NUMBER_MISMATCH Error

This means the token was created for a different Firebase project than you're trying to use.

```bash
# Check which project your token is for
"$AUTH_NODE" scripts/auth-cli.mjs status
# Look for "Firebase Project:" line

# Before recovery login: verify Keychain presence and run a cheap non-UI
# credential probe for the intended project; try supported existing credentials.
# Login is only a remaining recovery step after both probes fail.
# Follow the browser owner: an interactive login needs explicit authority
# and a verified task-owned isolated browser, never personal Chrome.
# Then, if authorized, log in for the correct project:
"$AUTH_NODE" scripts/auth-cli.mjs login                              # AI Universe
"$AUTH_NODE" scripts/auth-cli.mjs login --project worldarchitecture-ai  # WorldAI
```

### Port 9005 Already in Use

Inspect the listener with `lsof -nP -iTCP:9005 -sTCP:LISTEN`, then inspect its
PID and parent command. A port match does not establish ownership. Stop only
the verified callback process owned by this task through its supported shutdown
path; leave unrelated listeners running and report the exact port conflict.

### Token Expired

```bash
# Auto-refresh (silent)
TOKEN=$("$AUTH_NODE" scripts/auth-cli.mjs token)

# Or manual refresh
"$AUTH_NODE" scripts/auth-cli.mjs refresh

# If refresh fails, first verify Keychain presence and a cheap non-UI
# credential probe; exhaust supported existing credential routes.
# Only after both probes fail, use the browser owner recovery procedure.
# Interactive login requires explicit authority and a verified task-owned
# isolated browser. If that boundary is unmet, report the exact dependency.
# When those conditions are met:
"$AUTH_NODE" scripts/auth-cli.mjs login
```

## Token Storage

- **Location**: `~/.ai-universe/auth-token-<project-id>.json` (separate file per project)
- **ID Token**: 1-hour expiration (Firebase policy)
- **Refresh Token**: ~30 days, enables silent renewal
- **Security**: Never commit tokens, localhost OAuth only

## Integration with Commands

| Command | Project | Authentication |
|---------|---------|----------------|
| `/secondo` | AI Universe | `"$AUTH_NODE" scripts/auth-cli.mjs token` (default) |
| WorldAI API | WorldAI | `"$AUTH_NODE" scripts/auth-cli.mjs token --project worldarchitecture-ai` |

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

- [AI Universe HTTPie](../ai-universe-httpie/SKILL.md) - HTTPie usage examples
- [Secondo dependencies](../secondo-dependencies/SKILL.md) - /secondo command dependencies
