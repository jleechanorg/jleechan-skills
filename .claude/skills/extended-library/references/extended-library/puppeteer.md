---
description: /puppeteer Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Manual test execution

**Action Steps:**
With Puppeteer mode active:
1. Server runs on http://localhost:6006?test_mode=true&test_user_id=test-user-123
2. Use MCP functions for navigation, clicking, filling forms
3. Capture screenshots for validation
4. Execute JavaScript for complex interactions

## 📋 REFERENCE DOCUMENTATION

# /puppeteer Command

**Purpose**: Set Puppeteer MCP as the preferred browser automation tool for Claude Code CLI sessions

**Usage**: `/puppeteer`

**Action**: Configure session to use Puppeteer MCP instead of Playwright for browser testing

## What it does

1. **Sets session preference** to use Puppeteer MCP for all browser automation
2. **Adds --puppeteer flag** to test runner commands automatically
3. **Updates test execution** to use MCP tools instead of Playwright
4. **Enables screenshot capture** through Puppeteer MCP functions

## Benefits

- ✅ **No dependency issues** - Uses Claude Code's built-in MCP
- ✅ **Real browser automation** - Not HTTP simulation
- ✅ **Direct integration** - Native to Claude Code environment
- ✅ **Visual validation** - Built-in screenshot capabilities
- ✅ **JavaScript execution** - Full browser scripting support

## Integration with test runners

When `/puppeteer` is active, test commands will automatically:
- Use `./run_ui_tests.sh mock --puppeteer` instead of Playwright
- Execute browser tests via MCP functions
- Capture visual evidence through screenshots
- Provide test server with proper auth bypass

## Usage in session

```bash

# Set Puppeteer preference

/puppeteer

# Now all browser tests use Puppeteer MCP

/testui  # Uses --puppeteer flag automatically
```

## Example workflow

```python

# Navigate to test application

mcp__puppeteer-server__puppeteer_navigate(url="http://localhost:6006?test_mode=true")

# Take screenshot

mcp__puppeteer-server__puppeteer_screenshot(name="initial_state")

# Fill form field

mcp__puppeteer-server__puppeteer_fill(selector="#campaign-title", value="Test Campaign")

# Click button

mcp__puppeteer-server__puppeteer_evaluate(script="document.querySelector('#next-btn').click()")

# Validate result

mcp__puppeteer-server__puppeteer_screenshot(name="after_action")
```

## Compatibility

- Works with all existing test scenarios
- Replaces Playwright for browser automation
- Maintains same test URLs and auth bypass
- Compatible with structured fields testing
