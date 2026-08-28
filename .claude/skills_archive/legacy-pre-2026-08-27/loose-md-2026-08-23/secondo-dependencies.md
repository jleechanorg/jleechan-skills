---
description: Dependencies required for /secondo command
type: setup
scope: project
---

# /secondo Command Dependencies

This document lists the dependencies required for the `/secondo` command to function properly.

## Node.js Dependencies

The authentication system (`scripts/auth-cli.mjs`) requires Node.js packages.

**✅ Included in PR**: A root `package.json` with express dependency is now included.

```bash
# Install all dependencies (from project root)
npm install
```

**Required packages:**
- `express` (^4.19.2) - Web framework for OAuth callback server
- Node.js built-ins (http, fs, os, path, child_process)

**Note**: The `package.json` includes `"type": "module"` to support ES modules used by `auth-cli.mjs`.

## System Dependencies

### HTTPie (Preferred)

```bash
# macOS
brew install httpie

# Ubuntu/Debian
apt-get install httpie

# Python (universal)
pip install httpie
```

### curl (Fallback)

Usually pre-installed on most systems. If not:

```bash
# macOS
brew install curl

# Ubuntu/Debian
apt-get install curl
```

### jq (JSON Processing)

Required for JSON parsing in the CLI script:

```bash
# macOS
brew install jq

# Ubuntu/Debian
apt-get install jq
```

## Firebase Configuration

Set environment variables for Firebase authentication:

```bash
export FIREBASE_API_KEY="your-api-key"
export FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
export FIREBASE_PROJECT_ID="your-project-id"
```

## Verification

### Check Node.js Dependencies

```bash
# Verify express module can be required
node -e "require('express')" && echo "✅ express installed" || echo "❌ express missing"

# Test auth-cli.mjs loads without errors
node scripts/auth-cli.mjs
# Should show help message, not module resolution errors
```

### Check System Tools

```bash
command -v http >/dev/null && echo "✅ HTTPie installed" || echo "❌ HTTPie missing"
command -v curl >/dev/null && echo "✅ curl installed" || echo "❌ curl missing"
command -v jq >/dev/null && echo "✅ jq installed" || echo "❌ jq missing"
```

### Test Authentication (After Dependencies)

```bash
# Should show help/error, not crash
node scripts/auth-cli.mjs status
```

## Complete Setup

```bash
# 1. Install Node.js dependencies (from the repository root)
npm install

# 2. Install system tools (if needed)
brew install httpie jq  # macOS
# or
apt-get install httpie jq  # Ubuntu/Debian

# 3. Set Firebase environment variables
export FIREBASE_API_KEY="your-key"
export FIREBASE_AUTH_DOMAIN="your-domain"
export FIREBASE_PROJECT_ID="your-project"

# 4. Test authentication
node scripts/auth-cli.mjs login

# 5. Test secondo command
~/.claude/scripts/secondo-cli.sh "test question"
```

## Troubleshooting

### "Cannot find package 'express'"

Install Node.js dependencies from the project root:
```bash
npm install
```

### "http: command not found"

The script will automatically fall back to curl. But for best experience:
```bash
brew install httpie  # or apt-get install httpie
```

### "jq: command not found"

Install jq for JSON processing:
```bash
brew install jq  # or apt-get install jq
```

### Firebase configuration errors

Ensure environment variables are set:
```bash
echo $FIREBASE_API_KEY  # Should output your API key
echo $FIREBASE_AUTH_DOMAIN  # Should output your domain
echo $FIREBASE_PROJECT_ID  # Should output your project ID
```

## See Also

- [ai-universe-auth.md](ai-universe-auth.md) - Authentication setup guide
- [ai-universe-httpie.md](ai-universe-httpie.md) - HTTPie usage examples
- [second_opinion.md](../commands/second_opinion.md) - Command documentation
