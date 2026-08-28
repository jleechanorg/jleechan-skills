---
name: gmail
description: Read and search Gmail for $USER@gmail.com using gog CLI — authoritative method for all Gmail access
type: reference
scope: global
---

# Gmail Access via gog CLI

**Tool**: `gog` — Google CLI with Gmail/Calendar/Drive/Sheets support  
**Binary**: `/opt/homebrew/bin/gog`  
**Auth**: macOS keychain (persistent, no re-auth needed)  
**Account**: `$USER@gmail.com`

## Core Commands

```bash
# Search (Gmail query syntax)
gog gmail search -a $USER@gmail.com "<query>" --limit 10

# Get full message body by ID
gog gmail get -a $USER@gmail.com <messageId>

# Recent inbox
gog gmail search -a $USER@gmail.com "in:inbox newer_than:1d" --limit 20

# JSON output for scripting
gog gmail search -a $USER@gmail.com "<query>" --json --limit 5
```

## Gmail Query Syntax Examples

```
subject:[Consulting]               # subject contains [Consulting]
from:noreply@github.com            # from a sender
newer_than:1d                      # last 24 hours
newer_than:1h                      # last 1 hour
in:inbox is:unread                 # unread inbox
has:attachment                     # messages with attachments
```

## Output Format

```
ID                DATE              FROM                    SUBJECT                LABELS
19e656a13d3ad37d  2026-05-26 10:51  AI Universe Contact...  [Consulting] New...    INBOX
```

Use the ID with `gog gmail get` to read the full body.

## Anti-patterns (NEVER use these for Gmail)

- ❌ Browser automation / Chrome MCP tabs
- ❌ `mcp-agent-mail` (that's inter-agent messaging via port 8765, not Gmail)
- ❌ `@gongrzhe/server-gmail-autoauth-mcp` (not configured)
- ❌ Navigating to mail.google.com in browser

## Slash Command

`/gmail <query>` — calls `gog gmail search -a $USER@gmail.com "<query>"`
