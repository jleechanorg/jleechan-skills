---
description: Read, search, or send Gmail for $USER@gmail.com using gog CLI
---
# Gmail — Read, Search, Send via gog CLI

Use `gog` (installed at `/opt/homebrew/bin/gog`) with keychain auth for `$USER@gmail.com`.

## Common commands

```bash
# Search inbox
gog gmail search -a $USER@gmail.com "$ARGUMENTS" --limit 10

# Read a specific message by ID
gog gmail get -a $USER@gmail.com <messageId>

# List recent inbox
gog gmail search -a $USER@gmail.com "in:inbox" --limit 20

# Search with Gmail query syntax
gog gmail search -a $USER@gmail.com "subject:foo from:bar@example.com newer_than:1d"
```

## Usage

When the user says "check my email", "did the email arrive", "read my Gmail" — use this workflow:

1. Run `gog gmail search -a $USER@gmail.com "<query>" --limit <n>`
2. Use Gmail query syntax: `subject:`, `from:`, `to:`, `newer_than:1d`, `in:inbox`, etc.
3. For full body: `gog gmail get -a $USER@gmail.com <messageId>`

## Key rules

- Account: always `-a $USER@gmail.com`
- Auth: stored in macOS keychain — no password needed
- NOT browser automation
- NOT mcp-agent-mail (that's inter-agent messaging, not Gmail)
- NOT @gongrzhe/server-gmail-autoauth-mcp
