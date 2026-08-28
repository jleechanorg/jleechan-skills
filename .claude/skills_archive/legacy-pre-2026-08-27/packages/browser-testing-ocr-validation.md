# Browser Testing with OCR Validation

**CRITICAL**: Always validate browser screenshots with OCR when testing UI changes, especially for bugs where visual elements may or may not be present.

## Why OCR Validation is Essential

- **Human perception bias**: Looking at screenshots can lead to assumptions about what's visible
- **Memory errors**: Agents may remember what *should* be there rather than what *is* there
- **Proof of fix**: OCR provides concrete text evidence of what's actually rendered
- **No guessing**: OCR output is definitive - either the text is there or it's not

## Primary Method: Chrome Superpowers Auto-Capture (`page.md`)

Chrome Superpowers **automatically captures** `page.md` on every DOM-changing action (navigate, click, type, select, eval). This extracts text directly from the DOM - more accurate than image OCR.

### Auto-Captured Files Location
```
/tmp/chrome-session-{id}/{action-number}-{action}-{timestamp}/
├── page.md          # DOM text extraction (primary OCR)
├── page.html        # Full rendered DOM
├── screenshot.png   # Visual page state
└── console-log.txt  # Browser console output
```

### Using Auto-Captured page.md
```python
# 1. Navigate (triggers auto-capture)
mcp__chrome-superpower__use_browser(action="navigate", payload="https://example.com")

# 2. Read the auto-captured page.md for text validation
Read(file_path="/tmp/chrome-session-xxx/001-navigate-yyy/page.md")
# Contains all text content extracted from the DOM
```

**Advantages:**
- 100% accurate text from actual DOM (not image recognition)
- Automatic - no extra steps needed
- Includes all visible text content
- Works with dynamically loaded content

## Secondary Method: Claude Code Native Vision

Claude Code is a **multimodal LLM** that can directly see and analyze images. When you use the Read tool on a PNG file, Claude sees the image content directly.

### Using Claude Vision for OCR
```python
# Simply read the image file - Claude sees it directly
Read(file_path="/tmp/screenshots/test-screenshot.png")
# Claude will describe: user emails, button text, form content, UI state, etc.
```

**Advantages over external OCR:**
- Higher accuracy for complex layouts
- Understands context and UI elements
- Can describe visual state (colors, positioning, icons)
- No external dependencies needed

## Tertiary Method: Tesseract OCR (Cross-Validation)

Use Tesseract as an additional method for cross-validation when needed.

This system has Tesseract installed at `/opt/homebrew/bin/tesseract` with Python bindings.

### Verify Installation
```bash
which tesseract  # Should return /opt/homebrew/bin/tesseract
tesseract --version
```

### Install Python Dependencies (if needed)
```bash
python3 -m pip install --user pillow pytesseract
```

## Standard OCR Validation Workflow

### 1. Take Screenshot
```bash
# Using Chrome Superpowers MCP
mcp__chrome-superpower__use_browser(action: "screenshot", payload: "/tmp/screenshots/test-name.png")
```

### 2. Run OCR to Extract Text
```python
python3 - <<'PY'
from PIL import Image
import pytesseract

image_path = "/tmp/screenshots/test-name.png"
img = Image.open(image_path)
text = pytesseract.image_to_string(img)
print(text)
PY
```

### 3. Validate Expected Content
```python
python3 - <<'PY'
from PIL import Image
import pytesseract

image_path = "/tmp/screenshots/after-send.png"
img = Image.open(image_path)
text = pytesseract.image_to_string(img)

# Check for specific content
if "expected user message" in text:
    print("✅ SUCCESS: Message IS visible")
else:
    print("❌ FAILURE: Message NOT visible")

print("\n=== Full OCR Output ===")
print(text)
PY
```

## Real-World Example: Disappearing Messages Bug

**Problem**: Messages appeared to disappear after clicking Send, but visual inspection of screenshots was unreliable.

**Solution**: Used OCR to definitively prove the bug:

```python
python3 - <<'PY'
from PIL import Image
import pytesseract

image_path = "/tmp/screenshots/after-send-before-response.png"
img = Image.open(image_path)
text = pytesseract.image_to_string(img)

# Look for the user's message text
if "verify bug fix test" in text or "VERIFY FIX" in text:
    print("✅ Message IS visible (optimistic UI working)")
else:
    print("❌ Message NOT visible (bug confirmed)")

print("\nOCR Output:")
print(text)
PY
```

**Result**: OCR showed the message was NOT in the OCR output, confirming the bug was still present even though the screenshot "looked fine" to human eyes.

## Best Practices

### ✅ DO:
- **Always use OCR for visual regression tests**
- **Verify both positive and negative cases** (element present vs absent)
- **Include OCR output in bug reports** as proof
- **Test immediately after UI actions** (click, type, submit)
- **Use descriptive test messages** that are easy to grep for ("VERIFY FIX - test message")

### ❌ DON'T:
- **Never rely solely on visual inspection** of screenshots
- **Don't assume** what you remember seeing in earlier screenshots
- **Don't skip OCR** because "it looks right"
- **Don't use generic messages** like "test" (hard to validate in OCR)

## When to Use OCR

**MANDATORY for:**
- ✅ Testing disappearing/appearing UI elements
- ✅ Validating message visibility in chat interfaces
- ✅ Confirming modal/dialog content
- ✅ Verifying form input/output
- ✅ Checking loading states and error messages

**OPTIONAL for:**
- Layout/styling changes (colors, spacing)
- Interactive element positioning
- Animation/transition testing

## OCR Limitations

- **Text must be readable**: Small fonts, low contrast may not OCR well
- **Complex layouts**: OCR may not preserve exact formatting
- **Images/icons**: OCR only reads text, not graphical elements
- **Dynamic content**: Take screenshot at the right moment

## Example Test Script

```bash
#!/bin/bash

# Test: Verify user message stays visible after Send

# 1. Navigate and type message
python3 - <<'PY'
# (use Chrome Superpowers to type message)
PY

# 2. Click Send
python3 - <<'PY'
# (use Chrome Superpowers to click Send button)
PY

# 3. Immediate screenshot
python3 - <<'PY'
# (use Chrome Superpowers to capture screenshot)
PY

# 4. OCR validation
python3 - <<'PY'
from PIL import Image
import pytesseract

img = Image.open("/tmp/screenshots/after-send.png")
text = pytesseract.image_to_string(img)

if "expected message text" in text:
    print("✅ TEST PASSED")
    exit(0)
else:
    print("❌ TEST FAILED")
    print(text)
    exit(1)
PY
```

## Integration with Test Suites

Add OCR validation to Cypress/Playwright tests:

```javascript
// Cypress example
cy.task('ocrScreenshot', '/tmp/screenshots/test.png').then((text) => {
  expect(text).to.include('expected message')
})
```

## Summary

**Golden Rule**: If you're testing whether UI elements are visible in a browser, ALWAYS use OCR to validate. Don't trust your eyes or memory - trust the OCR output.
