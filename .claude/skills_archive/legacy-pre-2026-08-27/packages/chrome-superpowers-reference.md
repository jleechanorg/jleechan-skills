# Chrome Superpowers MCP - Reference Guide

## Location
Chrome Superpowers is an **MCP (Model Context Protocol) tool**, not a local skill file.

**MCP Tool Name**: `mcp__chrome-superpower__use_browser`

## Where to Find Documentation

### 1. Built-in MCP Tool
The Chrome Superpowers MCP is integrated into Claude Code as a native tool. You can access it through the `mcp__chrome-superpower__use_browser` function.

### 2. Project-Specific Usage Notes
For AI Universe Frontend testing patterns, see:
- **File**: `~/.claude/skills/chrome-localhost3000-usage.md`
- **Contains**: React-specific event handling, selectors, and debugging techniques

### 3. Tool Description
Check the tool definition in your current session for parameter details:
```
mcp__chrome-superpower__use_browser
- action: navigate, click, type, extract, screenshot, eval, select, attr, await_element, await_text
- selector: CSS or XPath (XPath must start with / or //)
- payload: Action-specific data
```

## Quick Reference

**Common Actions:**
- `navigate` - Go to URL
- `click` - Click element by selector
- `eval` - Execute JavaScript
- `screenshot` - Capture screenshot
- `await_element` - Wait for element to appear

**Key Limitations:**
- The `type` action doesn't trigger React onChange handlers
- For React apps, use `eval` with native value setters and event dispatching

## Related Files
- Project-specific usage: `~/.claude/skills/chrome-localhost3000-usage.md`
- Bug investigation findings: `/tmp/disappearing-messages-findings.md`
- Reference bead: `convov-b2e`

## Notes
This is a **system-provided MCP tool**, not a user-created skill. The MCP server is managed by Claude Code's infrastructure, not stored in local files.
