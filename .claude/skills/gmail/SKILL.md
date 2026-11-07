---
name: gmail
description: Read and search Gmail for $GMAIL_ACCOUNT using gog CLI — authoritative method for all Gmail access
type: reference
scope: global
---

# Gmail Access via gog CLI

**Tool**: `gog` — Google CLI with Gmail/Calendar/Drive/Sheets support  
**Binary**: whatever `command -v gog` finds on PATH. If nothing, stop with `gog not installed: install the gog CLI and authenticate it for $GMAIL_ACCOUNT`  
**Auth**: gog's own credential store (on macOS, the login keychain; other platforms use gog's platform store). Run gog's auth flow once per machine  
**Account**: `$GMAIL_ACCOUNT` (required; e.g. `<you>@gmail.com`. If unset, stop with `GMAIL_ACCOUNT not configured: Gmail address for gog. Example: export GMAIL_ACCOUNT=<you>@gmail.com`)

## Core Commands

```bash
# Preflight
command -v gog >/dev/null || { echo "gog not installed: install the gog CLI first" >&2; exit 1; }
[ -n "${GMAIL_ACCOUNT:-}" ] || { echo "GMAIL_ACCOUNT not configured: Gmail address for gog. Example: export GMAIL_ACCOUNT=<you>@gmail.com" >&2; exit 1; }

# Search (Gmail query syntax)
gog gmail search -a "$GMAIL_ACCOUNT" "<query>" --limit 10

# Get full message body by ID
gog gmail get -a "$GMAIL_ACCOUNT" <messageId>

# Recent inbox
gog gmail search -a "$GMAIL_ACCOUNT" "in:inbox newer_than:1d" --limit 20

# JSON output for scripting
gog gmail search -a "$GMAIL_ACCOUNT" "<query>" --json --limit 5
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
<message-id>      2026-05-26 10:51  Example Sender...       [Consulting] New...    INBOX
```

Use the ID with `gog gmail get` to read the full body.

## Anti-patterns (NEVER use these for Gmail)

- ❌ Browser automation / Chrome MCP tabs
- ❌ `mcp-agent-mail` (that's inter-agent messaging via port 8765, not Gmail)
- ❌ `@gongrzhe/server-gmail-autoauth-mcp` (not configured)
- ❌ Navigating to mail.google.com in browser

## Slash Command

`/gmail <query>` — calls `gog gmail search -a "$GMAIL_ACCOUNT" "<query>"`
