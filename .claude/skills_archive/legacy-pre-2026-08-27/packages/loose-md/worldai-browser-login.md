---
description: Browser-based login to WorldAI via Firebase Google OAuth using Chrome Superpowers MCP
type: reference
scope: project
---

# WorldAI Browser Login via MCP

This skill documents how to authenticate with WorldAI in a real browser using Chrome Superpowers MCP or Playwright MCP for browser-based testing.

## Test Accounts

| Account | Purpose | Campaigns |
|---------|---------|-----------|
| `<your-email@gmail.com>` | Secondary test account | 44 campaigns |
| `$USER@gmail.com` | Primary account (owner) | 146 campaigns |

## Server URLs

| Environment | URL |
|-------------|-----|
| Deployed Dev | `https://mvp-site-app-s2-i6xf2p72ka-uc.a.run.app` |
| Local | `http://localhost:8081` |

## Chrome Superpowers MCP Login Flow

### Step 1: Navigate to WorldAI

```python
# Navigate to deployed server
mcp__chrome-superpower__use_browser(
    action="navigate",
    payload="https://mvp-site-app-s2-i6xf2p72ka-uc.a.run.app"
)
```

### Step 2: Click Sign In with Google

```python
# Click the Google sign-in button
mcp__chrome-superpower__use_browser(
    action="click",
    selector="//button[contains(text(), 'Sign in with Google')]"
)
```

### Step 3: Complete OAuth in Popup

The Firebase OAuth popup will open. The MCP browser cannot track the popup window, but:
- If you've previously signed in with Google in the same browser profile, it may auto-complete
- Manual intervention may be needed to click your Google account
- After successful auth, the main page will show your email in the header

### Step 4: Verify Login Success

```python
# Extract page content to verify login
mcp__chrome-superpower__use_browser(
    action="extract",
    payload="text",
    selector="body"
)
```

**Success indicators:**
- Email address visible in header (e.g., `$USER@gmail.com`)
- "My Campaigns" section visible
- Campaign count shown (e.g., "Showing 146 of 146 campaigns")

### Step 5: Navigate to Campaign

```python
# Navigate directly to a campaign
mcp__chrome-superpower__use_browser(
    action="navigate",
    payload="http://localhost:8081/game/CAMPAIGN_ID"
)
```

## Evidence Collection

### Screenshot Capture

```python
# Capture screenshot as evidence
mcp__chrome-superpower__use_browser(
    action="screenshot",
    payload="evidence-name.png"
)
```

Screenshots are saved to Chrome Superpowers temp directory:
`/var/folders/j0/.../chrome-session-*/XXX-action-timestamp/screenshot.png`

### Copy to Evidence Directory

```bash
# Create evidence directory
mkdir -p /tmp/worldai-browser-evidence/

# Copy screenshot
cp /path/to/chrome-session/*/screenshot.png /tmp/worldai-browser-evidence/
```

### OCR Validation

**Primary Method: Claude Code Native Vision**

Claude Code can directly read and analyze image files as a multimodal LLM:

```python
# Use the Read tool on PNG files - Claude sees the image directly
Read(file_path="/tmp/worldai-browser-evidence/screenshot.png")
# Claude will describe what it sees: user email, campaign list, UI state
```

**Secondary Method: Tesseract OCR (Cross-validation)**

```python
python3 - <<'PY'
from PIL import Image
import pytesseract

image_path = "/tmp/worldai-browser-evidence/screenshot.png"
img = Image.open(image_path)
text = pytesseract.image_to_string(img)

# Verify login success - check for @gmail.com to detect any logged-in user
if "@gmail.com" in text:
    print("SUCCESS: User is logged in")

# Also check for expected page content
if "My Campaigns" in text:
    print("SUCCESS: Campaigns page visible")

print("\n=== Full OCR Output ===")
print(text)
PY
```

## Example: Full Login Test

```python
# 1. Navigate
mcp__chrome-superpower__use_browser(action="navigate", payload="https://mvp-site-app-s2-i6xf2p72ka-uc.a.run.app")

# 2. Click Sign In
mcp__chrome-superpower__use_browser(action="click", selector="//button[contains(text(), 'Sign in with Google')]")

# 3. Wait for OAuth popup (manual intervention if needed)

# 4. Take screenshot
mcp__chrome-superpower__use_browser(action="screenshot", payload="login-test.png")

# 5. Extract and verify
mcp__chrome-superpower__use_browser(action="extract", payload="text", selector="body")
```

## Playwright MCP Alternative

If Chrome Superpowers is unavailable, use Playwright MCP:

```python
# Navigate
mcp__playwright-mcp__browser_navigate(url="https://mvp-site-app-s2-i6xf2p72ka-uc.a.run.app")

# Get snapshot
mcp__playwright-mcp__browser_snapshot()

# Click login button
mcp__playwright-mcp__browser_click(element="Sign in with Google button", ref="button-ref")

# Take screenshot
mcp__playwright-mcp__browser_take_screenshot()
```

## Troubleshooting

### Session Lost After Navigation

Firebase OAuth sessions may not persist across page navigations in MCP browsers.

**Solution**: Navigate to the target page directly after authentication completes, or use the same tab for all operations.

### OAuth Popup Not Completing

The MCP browser cannot interact with popup windows.

**Solution**: Use a browser profile that's already logged into Google, or manually complete the OAuth flow when the popup appears.

### "No token provided" Error

The API endpoint requires Firebase authentication.

**Solution**: Ensure you've completed the OAuth flow and the session is active. Check the header for your email address.

## Related Skills

- [browser-testing-ocr-validation.md](browser-testing-ocr-validation.md) - OCR validation for browser tests
- [chrome-superpowers-reference.md](chrome-superpowers-reference.md) - Chrome Superpowers MCP reference
- [playwright-mcp-manual-interaction.md](playwright-mcp-manual-interaction.md) - Playwright MCP manual interaction
