# Aside REPL API — Verified Surface (gotchas + correct recipes)

Captured 2026-07-05 against `aside` CLI v1.26.703.1528 (Aside Daemon 1.26.703.1528); extended 2026-07-13 against v1.26.713.1911 with REPL and Slack membership observations. The historical `slack.getClient()` recipe is retired because it used browser-backed authentication to bypass API scope limits. Several examples in `SKILL.md` Phase 2 show functions that **don't exist or have different return shapes** than documented. This reference is the canonical fix list.

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
const tabs = await listBrowserTabs();
const n = tabs.length;

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

## Available REPL globals (verified 2026-07-05; updated 2026-07-09, 2026-07-13)

```text
navigator, tabs, listBrowserTabs, attachBrowserTab, attachActiveBrowserTab,
getTabByTargetId, openTab, closeTab, snapshot, annotatedScreenshot,
installPageScript, page,
slack,                       // Cookie-backed; do not use for Slack API calls (see §7)
aside,                       // aside sub-primitives: pdf, settings, sessions, routines
applePasswords, captcha, chrome, cua, gmail, googleAccounts, googleDocs,
googlePeople, googleSearch, googleSheets, imageSearch, youtube, linkedin,
twitter, notion, blockToMarkdown, markdownToBlockSpecs, display
```

`Buffer` is also available (built-in). Everything else (fs, require, process, fetch, setTimeout-as-promise) is **not** in the REPL sandbox — use the stdout pattern to ship data out.

> **MISSING from the REPL — verified 2026-07-13 against v1.26.713.1911:** `browser_click`, `browser_type`, `browser_fill`, `browser_press`, `browser_hover`, `browser_snapshot` (full-named version; the bare `snapshot` IS available). Any SKILL.md example that calls `await browser_click({ ref: 'e73' })` will throw `ReferenceError: browser_click is not defined`. Use `mcp__aside-mcp__*` from a runtime that exposes them, or drive the page via `page.evaluate(() => element.click())`.

### 7. Slack operations require approved scopes

The Aside `slack` global uses browser-backed authentication. Do not call it, `slack.getClient()`, or any equivalent cookie-backed API path. For Slack operations, use the approved Slack connector/API with its existing authorized scopes. A missing scope is an authorization boundary: report it or use an appropriate Slack UI action in an already authorized, verified isolated agent-owned browser context. Never inherit personal-browser cookies or use browser cookies to bypass a missing scope.

For bot membership checks, use `conversations.members` through an approved Slack connector/API whose existing scopes permit the call; `conversations.list` shows visible channels and does not prove membership. If the required read scope is unavailable, report that limitation. See §13 for the distinction.

### 8. **`aside repl` is stateless — `tabs[0]` does NOT survive across `repl` invocations**

Every `aside repl "..."` CLI call is a fresh browser connection. State that you set in one invocation (`openTab`, variables, captured refs) is gone by the time the next `repl` call runs. Concretely:

```bash
# ❌ Will fail: t is undefined in the second call.
aside repl "const t = await openTab('https://example.com');"
aside repl "await t.evaluate(() => location.href)"  # ReferenceError

# ✅ Pattern: bundle the entire script into ONE repl call as a heredoc or
# JS string. Use await sleep() inside the same script for any pauses.
aside repl "$(cat <<'JS'
  const t = await openTab('https://example.com');
  await sleep(5000);
  const dump = await t.evaluate(() => ({ url: location.href, title: document.title }));
  console.log(JSON.stringify(dump));
JS
)"

# ✅ Or: write the script to a file and pipe it via stdin / cat.
cat /tmp/script.mjs | tr '\n' ' ' | tr -s ' ' > /tmp/cmd.txt
aside repl "$(cat /tmp/cmd.txt)"
```

For multi-step stateful flows (login → click → type → submit), keep the **entire** sequence inside a single `repl` invocation.

### 9. **DOMRect doesn't serialize through CDP `evaluate` — flatten to plain numbers**

`element.getBoundingClientRect()` returns a `DOMRect`. When you return it from `await t.evaluate(() => rect)`, the JSON wire format strips the rect's enumerable props — you get `{}` back, and any subsequent click-at-coords logic dies silently.

```js
// ❌ Returns {} — JSON lost x/y/width/height
const r = await t.evaluate(() => {
  const el = document.querySelector('#btn');
  return el.getBoundingClientRect();
});

// ✅ Extract primitives explicitly so they survive serialization
const bbox = await t.evaluate(() => {
  const r = document.querySelector('#btn').getBoundingClientRect();
  return {
    x: Math.round(r.x), y: Math.round(r.y),
    w: Math.round(r.width), h: Math.round(r.height),
  };
});
// → { x: 220, y: 124, w: 32, h: 32 }
```

The same trap applies to **any DOM object** that has only getters or non-enumerable properties (DOMMatrix, CSSStyleDeclaration entries, etc.). When in doubt, destructure to plain `{ number, number }` before returning.

### 10. **Console output from `repl` is suppressed unless you use `console.log`**

A common 60-second trap:

```bash
# ❌ Looks like the call hung — no output ever appears
aside repl "Object.keys(globalThis).slice(0, 30).join(',')"
# (returns silently with [ok | 6ms] only)

# ✅ console.log echoes to stdout and is what the caller sees
aside repl "console.log('GLOBAL:', Object.keys(globalThis).slice(0, 30).join(','))"
```

**Reason:** `aside repl` runs the JS via a Node REPL whose final expression value is normally echoed (`[ok | Nms]` only confirms the call returned; the actual value is dropped unless you `console.log` it). For multi-step scripts, always `console.log` what you want captured.

### 11. **Slack `conversations.list` ≠ `conversations.members` — verify membership, not visibility**

Verified 2026-07-13. The Slack Web API returns channel *names* from `conversations.list`, but those channels are not necessarily members of the requesting user/bot. This makes "membership gaps" invisible to anyone checking the wrong endpoint:

```bash
# ❌ Misleading: returns 35 channels but says nothing about membership
curl -sH "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200"
# → returns 35 channels like 'worldai-bugs', 'all-$USER-ai', 'life', etc.
# All look "normal" but the bot may not be a member of any of them.

# ✅ Authoritative: list of member USER-IDs (which includes you if you're a member)
curl -sH "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.members?channel=<SLACK_ID>&limit=200"
# → { ok: true, members: ["<SLACK_ID>","<SLACK_ID>","<SLACK_ID>"] }
# If "<SLACK_ID>" (the bot) is NOT in the array, it's NOT in the channel.
```

**Why this matters:** the morning EA sweep on 2026-07-13 reported "bot is member of 0 channels" — but the channels *list* call had been used to verify, not `members`. The bot was actually a member of all 35 channels; only #worldai-bugs needed re-adding (the bot had been removed there after a stale-token rotation). Verified by direct `conversations.info` and `conversations.history` calls.

### 12. **`aside repl` inline-string shell escaping trap** (verified 2026-07-13)

Inline `aside repl "... JS ..."` with parens, template literals, or object-literal curly braces will often break — but **bash will report the syntax error, not Aside**. The pattern looks like a working invocation that returned an error:

```bash
# ❌ Bash tokenizes the JS, errors on the `(` inside `.filter(l => ...)`, never reaches Aside
aside repl "const lines = String(s.tree).split('\n').filter(l => /ref=e\d+/.test(l)).slice(0, 60); console.log(lines.length)"
# bash: eval: line 16: syntax error near unexpected token `('
# [error | <Nms>]

# ✅ Pattern A — write JS to a file, cat-into-arg  (the bullet-proof path)
cat > /tmp/script.js <<'JS'
const lines = String(s.tree).split('\n').filter(l => /ref=e\d+\]/.test(l));
console.log('hits:', lines.length);
JS
aside repl "$(cat /tmp/script.js)"

# ✅ Pattern B — heredoc the file CONTENTS as the inline code
aside repl "$(cat <<'JS'
  const lines = ...;
  console.log(lines);
JS
)"
```

**Use a quoted heredoc `<<'JS'`** (not `<<JS`) to prevent bash from expanding `${var}` and `$(cmd)` inside the JS — unquoted heredoc expansion + Aside REPL together produce very confusing errors.

**Heuristic:** if your `aside repl "<...>"` invocation has more than ~3 `(`/`)`, more than one `=>`, OR template-literal backticks — write it to a file first.

### 13. Slack bot membership after reinstall or token rotation

Slack does not automatically rejoin a bot to channels after app reinstall or token rotation. Verify actual membership through an approved Slack connector/API with the existing required scopes; `conversations.list` alone only shows channels visible to the caller. To rejoin, use an approved API call with its existing authorized scopes, or an authorized UI action in an already verified isolated agent-owned browser context. If the required scope or human authorization is missing, report the boundary. Do not use Aside's cookie-backed Slack client or any browser-cookie API bypass.

### 14. **Aside CLI exits "fetch failed" when its background service is unavailable**

Symptom: every `aside account list`, `aside repl`, and `aside mcp` returns `fetch failed` immediately. Diagnostic reports (`~/Library/Logs/DiagnosticReports/AsideUpdater-*.ips`) accumulate because the bundled updater can't reach the GUI.

Do not activate, restart, or repair the desktop app as part of browser
automation. Start or reconnect only an agent-owned profile in background mode
(aside-browser-default § Background mode). If that fails or the CLI is
unavailable, use isolated headless Chromium and report the layer that failed.
Do not use this diagnosis as authority to inspect or change the user's desktop.

```bash
pgrep -lf "Aside.app/Contents/MacOS/Aside"
aside account list
```

If `aside mcp` is in a crash-restart loop, do not start the GUI app or kill/restart processes. Use isolated headless Chromium for the task and report that Aside is unavailable. Historical recovery observations do not authorize changing desktop state.

### 15. **`aside --effort ultrabrowse` times out (>180s) on multi-step structured flows** (verified 2026-07-14)

The NL-agent mode is fine for genuinely exploratory tasks ("find a contact who knows X", "summarize this article") but **too slow for deterministic multi-step flows** (open URL → click N tabs → scrape text → categorize). Verified 2026-07-14 driving the Slack Later page: a single ultrabrowse prompt "go through all my slack reminders and categorize stale vs needs attention" timed out at 180s with no useful output. Direct REPL with the bundled script pattern completed in ~15-25s per tab.

**Rule of thumb:** if your task has more than ~2 sequential browser steps AND has deterministic structure, use `aside repl` with the script-from-file pattern (§12). Reserve ultrabrowse for exploratory one-shot lookups.

See `references/slack-web-ui-scraping.md` for a full worked example (Slack Later page).

### 16. **Heavy SPA landing pages disconnect CDP; lightweight JSON endpoints survive** (verified 2026-07-15, PR #7953 evidence)

When the target site is a heavy SPA (React/Vue bundle > 1 MB, hundreds of `fetch` calls per second during hydration, dozens of `requestAnimationFrame` ticks), `await openTab(url)` followed by `await annotatedScreenshot(p)` frequently fails with:

```
Error: CDP websocket disconnected
    at WebSocket.<anonymous> (...aside-daemon:1267:490740)
```

Verified twice in the same session against `mvp-site-app-s3-i6xf2p72ka-uc.a.run.app`:
- `/` (heavy React landing page): **5 consecutive CDP disconnects**, screenshot returns empty PNG (0 bytes).
- `/health` (lightweight JSON page, returns ~250 bytes of status info): works first try, returns 51 KB annotated PNG.

**The pattern that works:** **navigate to the lightest possible endpoint first** (`/health`, `/api/ping`, `/status.json`), screenshot that to prove the deploy is alive, then accept that the heavy SPA UI cannot be captured without a real logged-in session. Don't burn 5+ retries on the heavy page hoping it'll work.

```js
// ✅ Works: lightweight endpoint
const p = await openTab('https://app.example.com/health');
await new Promise(r => setTimeout(r, 4000));
const shot = await annotatedScreenshot(p);
console.log('B64=' + shot.base64Image);

// ❌ Fails: heavy SPA landing page
const p2 = await openTab('https://app.example.com/');
await new Promise(r => setTimeout(r, 8000));  // longer wait doesn't help
const shot2 = await annotatedScreenshot(p2);
// → Error: CDP websocket disconnected
```

**Why this happens (theory, not verified):** Aside's persistent daemon attaches a single CDP session per `openTab` call. Heavy SPAs keep the renderer process busy for 5-15s after navigation, exhausting whatever timeout Aside's MCP-to-CDP bridge sets. Lightweight JSON pages resolve all activity within ~1s.

**Fallbacks when you MUST capture the heavy SPA:**

1. **`page.evaluate(() => document.body.innerHTML)` first** — capture the DOM while it's still alive, before the screenshot call that disconnects. Decode later via curl regex / grep on the captured HTML.
2. **Use the browser-control contract** for any authorized authenticated test. Never use a personal browser session, copied personal cookies, bearer injection, or direct API probing as a rendering workaround. An explicitly authorized transfer from one agent-owned source profile is governed by that contract.
3. **Use an authorized source-level check only when it answers the question.** Do not use curl/regex against deployed bundles as a substitute for authenticated UI behavior or evidence; report that the UI state could not be verified if the authorized browser path is unavailable.
4. **Direct invocation of the underlying function** — if the evidence target is a backend function (like `_build_allowed_response`), import it in Python and call it directly with realistic data. Bypasses the entire SPA render.

**The principle:** when browser automation fails, fall back to **the cheapest evidence tier that still answers the user's question**. Don't fabricate a screenshot, don't pretend CDP worked, and don't loop retries on the failing path.

## Source transcripts

Original investigation: aside repl live probe during social-poster skill build (2026-07-05). Captured by running each candidate API call individually:

```text
aside repl "console.log(typeof listBrowserTabs)"        → "function"
aside repl "const t = listBrowserTabs(); t.length"      → undefined (it's a Promise)
aside repl "const t = await listBrowserTabs(); t.length" → number ✓
aside repl "const t = await listBrowserTabs(); t[0].url" → URL string ✓
aside repl "const t = await listBrowserTabs(); t[0].url()" → TypeError: t.url is not a function
aside repl "console.log(typeof require)"               → "undefined"
aside repl "console.log(typeof process)"               → "undefined"
aside repl "console.log(typeof Buffer)"                → "function"
aside repl "const s = await screenshot(p); s.length"   → "screenshot is not defined"
aside repl "const s = await annotatedScreenshot(p); Object.keys(s)"   → "[ 'base64Image' ]"
aside repl "const s = await annotatedScreenshot(p); s.base64Image.slice(0,30)"
                                                      → "iVBORw0KGgoAAAANSUhEUgAAC0AAAAc"  (PNG base64 ✓)
```

Historical bot-rejoin transcript omitted because it documents the retired cookie-backed Slack API bypass.

Heavy-SPA CDP-disconnect verification (2026-07-15, PR #7953 evidence):

```text
# Heavy SPA landing page — 5 disconnects
aside repl "const p = await openTab('https://mvp-site-app-s3-...run.app/'); await sleep(8000); const s = await annotatedScreenshot(p); console.log('B64=' + s.base64Image)"
→ ✔︎ Opened a new tab and set it active: tabs[0], page → WorldAI (https://mvp-site-app-s3-...)
→ landed at: https://your-project.com/ | title: WorldAI
→ Error: CDP websocket disconnected
    at #y (file:///.../Aside Daemon.app/Contents/MacOS/aside-daemon:1267:490740)

# Lightweight /health endpoint — works first try
aside repl "const p = await openTab('https://mvp-site-app-s3-...run.app/health'); await sleep(4000); const s = await annotatedScreenshot(p); console.log('B64=' + s.base64Image)"
→ ✔︎ Opened a new tab and set it active: tabs[0], page →  (https://mvp-site-app-s3-.../health)
→ health page url: https://your-project.com/ | title: WorldAI
→ SHOT_BASE64_LEN: 68516
→ [ok | 5668ms]
```

The `/health` screenshot was saved to `/tmp/wt-pr7953/_shot.png` (51 KB PNG, 2880×1800) and pushed to a public gist (`4ab1139eae87bde6102bc0961cb0168b` SHA `5547f92`) using the clone-and-replace recipe from `evidence-attach-to-slack`. The `image/png` content-type rendered inline in the Slack thread via gist raw URL embed — proving the deploy was alive at 2026-07-15T18:56:58Z, even though the rate-limit modal UI itself was unreachable through the SPA auth gate.
