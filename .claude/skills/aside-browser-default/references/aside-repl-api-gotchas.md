# Aside REPL API — Verified Surface (gotchas + correct recipes)

Captured 2026-07-05 against `aside` CLI v1.26.703.1528 (Aside Daemon 1.26.703.1528). Several examples in `SKILL.md` Phase 2 show functions that **don't exist or have different return shapes** than documented. This reference is the canonical fix list.

## Top-line gotchas

### 1. `screenshot(p)` does NOT exist — use `annotatedScreenshot(p)`

```js
// ❌ Reference in SKILL.md — DOES NOT WORK
const png = await screenshot(p);

// ✅ Correct — returns { base64Image: "..." } (PNG base64)
const shot = await annotatedScreenshot(p);
console.log(shot.base64Image);
```

The annotation layer adds red numbered boxes (good for UI debugging, useless for marketing screenshots — see "disable annotations" below).

### 2. `fs` / `require` / `process` are NOT available in the REPL

```js
// ❌ Will throw "External modules are not available in the REPL"
const fs = require('fs');
fs.writeFileSync('/tmp/foo.png', Buffer.from(b64, 'base64'));

// ❌ Will throw — process is undefined
process.stdout.write(b64);
```

The REPL sandbox has only `Buffer` and the Aside functions. To save a screenshot to disk:

**Pattern: emit base64 to stdout, decode in Python/Node from outside.**

```js
// Inside aside repl
const shot = await annotatedScreenshot(p);
console.log('B64:' + shot.base64Image);   // stdout to caller
```

```python
# From Python / shell, capture + decode
import subprocess, base64, re
r = subprocess.run(["aside", "repl", code], capture_output=True, text=True)
m = re.search(r"B64:([A-Za-z0-9+/=]+)", r.stdout)
png = base64.b64decode(m.group(1))
Path("/tmp/foo.png").write_bytes(png)
```

### 3. `listBrowserTabs()` returns a **Promise**, not an array

```js
// ❌ Will throw "listBrowserTabs(...).map is not a function"
listBrowserTabs().map(t => t.url());

// ❌ Will return undefined
const n = listBrowserTabs().length;

// ✅ Must await
const tabs = await listBrowserTabs();
console.log(tabs.length);
```

### 4. Tab entries use **plain properties**, not functions

```js
// ❌ "t.url is not a function"
tabs.forEach(t => console.log(t.url()));

// ✅ Properties
tabs.forEach(t => console.log(t.url, '|', t.title));

// ✅ Index lookup works too
tabs[0].url
```

### 5. `openTab(url)` returns a CDP **target object**, not a tab id

```js
// ❌ The object is not an integer tab id — confusing for downstream APIs
const p = await openTab('https://example.com');
typeof p;  // "object" (CDP target), NOT a number
```

For most operations (`snapshot`, `annotatedScreenshot`, `closeTab`), pass this object directly — Aside resolves it internally. Don't try to use it as a tab index.

### 6. `closeTab(target)` requires the **target object**, not a URL

```js
// ❌ Will fail
await closeTab('https://example.com');

// ✅ Pass the same object openTab returned
const p = await openTab('https://example.com');
await closeTab(p);
```

To close the most-recently-opened tab, store the return value from `openTab` in a closure variable.

## Canonical "open + screenshot to disk" recipe

```python
import subprocess, re, base64, json
from pathlib import Path

def aside_screenshot(url: str, out_path: Path, wait_ms: int = 4500) -> dict:
    code = (
        f"const p = await openTab({json.dumps(url)}); "
        f"await new Promise(r => setTimeout(r, {wait_ms})); "
        "const shot = await annotatedScreenshot(p); "
        "console.log('B64:' + shot.base64Image);"
    )
    r = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=60)
    out = r.stdout + r.stderr
    m = re.search(r"B64:([A-Za-z0-9+/=]+)", out)
    if not m:
        return {"ok": False, "error": next((l.strip() for l in out.split('\n') if l.strip() and '✔' not in l), '(no output)')[:200]}
    png = base64.b64decode(m.group(1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png)
    return {"ok": True, "bytes": len(png), "path": str(out_path)}
```

## Disable annotation overlay (for clean screenshots)

`annotatedScreenshot` always overlays red numbered boxes. For clean marketing/screenshot-to-send-in-Slack images, this is undesirable. As of 2026-07-05 there's **no documented flag to disable annotations**. Workarounds:

1. **Crop the image** in Python with `PIL` after capture.
2. **Use `aside --effort ultrabrowse` NL mode** for screenshots — different code path, may skip annotations.
3. **Fall back to Playwright MCP** (`mcp__playwright-mcp__browser_take_screenshot`) for one-off clean screenshots; do NOT make it the default.

Open question: does Aside have a non-annotated `screenshot()` function? It did not exist in the REPL globals dump as of 2026-07-05. If you find one, update this file.

## Aside CLI version-pinning caveat

The `aside` CLI auto-updates the daemon on each invocation sometimes (saw daemon go from `1.26.627.1553` to `1.26.703.1528` mid-session on 2026-07-05). Behavior across versions should be stable but check `aside --version` and the `~/Library/Application Support/Aside/AsideDaemon/` path if a script starts failing — it may have moved.

## Available REPL globals (verified 2026-07-05)

```text
navigator, tabs, listBrowserTabs, attachBrowserTab, attachActiveBrowserTab,
getTabByTargetId, openTab, closeTab, snapshot, annotatedScreenshot,
installPageScript, page
```

`Buffer` is also available (built-in). Everything else (fs, require, process, fetch, setTimeout-as-promise) is **not** in the REPL sandbox — use the stdout pattern to ship data out.

## Source transcripts

Original investigation: aside repl live probe during social-poster skill build (2026-07-05). Captured by running each candidate API call individually:

```text
aside repl --account <agent-account> "console.log(typeof listBrowserTabs)"        → "function"
aside repl --account <agent-account> "const t = listBrowserTabs(); t.length"      → undefined (it's a Promise)
aside repl --account <agent-account> "const t = await listBrowserTabs(); t.length" → number ✓
aside repl --account <agent-account> "const t = await listBrowserTabs(); t[0].url" → URL string ✓
aside repl --account <agent-account> "const t = await listBrowserTabs(); t[0].url()" → TypeError: t.url is not a function
aside repl --account <agent-account> "console.log(typeof require)"               → "undefined"
aside repl --account <agent-account> "console.log(typeof process)"               → "undefined"
aside repl --account <agent-account> "console.log(typeof Buffer)"                → "function"
aside repl --account <agent-account> "const s = await screenshot(p); s.length"   → "screenshot is not defined"
aside repl --account <agent-account> "const s = await annotatedScreenshot(p); Object.keys(s)" → "[ 'base64Image' ]"
aside repl --account <agent-account> "const s = await annotatedScreenshot(p); s.base64Image.slice(0,30)"
                                                      → "iVBORw0KGgoAAAANSUhEUgAAC0AAAAc"  (PNG base64 ✓)
```