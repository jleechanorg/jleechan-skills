---
name: aside-browser-default
description: Aside browser is the PRIMARY browser tool for all Hermes/Claude/Codex work. Use aside CLI (repl/mcp/exec modes) or aside-mcp before Playwright MCP / superpowers-chrome. Use when opening browsers, scraping, UI tests, localhost verification, cookie injection flows, or any browser-driven automation. Playwright MCP and superpowers-chrome are explicit fallbacks for cases Aside can't handle (e.g., headless CI runners, Playwright-specific test fixtures). Reversible — see ~/.hermes/scripts/rollback-aside-default.sh.
when_to_use: Browser automation, scraping, screenshots, localhost UI checks, cookie injection flows, /browser command, public-data lookups
allowed-tools: mcp__aside-mcp, aside, mcp__playwright-mcp (fallback), mcp__plugin-superpowers-chrome__chrome_use_browser (fallback)
context: hermes
---

# Aside Browser Default

## Contract

**Default: Aside first.** For all browser work, agents should reach for the Aside CLI / Aside MCP server before Playwright MCP or superpowers-chrome. Playwright MCP and superpowers-chrome are **named fallbacks** — preserved, not deleted — for cases Aside can't handle (rare; mostly headless CI runners and Playwright-specific test fixtures).

| Tool | Role | When to use |
|------|------|-------------|
| **`aside` CLI / `aside-mcp`** | **Primary** | Default for everything: UI tests, localhost verification, scraping, cookie flows, public-data lookups |
| `mcp__playwright-mcp` | Fallback | Only when Aside CLI is unavailable, or for Playwright-specific fixtures (trace viewer, `--isolated` profile mode, video recording) |
| `mcp__plugin-superpowers-chrome__chrome_use_browser` | Fallback | Only when Chrome-specific behavior is required (e.g., you need Chrome's exact `--user-data-dir` semantics for a particular test) |

**Explicit opt-in phrases only:** Jeffrey says *"show browser"*, *"headed mode"*, *"visible browser"*, or *"I want to see the window"* in the **current thread**. Aside drives a real GUI browser session and is not headless. Without opt-in, use Aside only when its existing session can be driven without surfacing a new window; otherwise use the guarded Playwright Chromium headless fallback.

## Why Aside

Aside is a Y Combinator–backed AI-native Chromium browser launched June 2026. Advantages over the prior default:

- **AI-native design** — Aside's `aside "..."` NL agent and `--effort ultrabrowse` mode can plan + execute multi-step browser workflows without the agent writing Playwright scripts.
- **Same Chrome internals** — Aside is Chromium-based, so `document.querySelector`, CDP, computed styles, etc. all work identically.
- **Persistent browser session** — Aside runs as a long-lived daemon (`~/Library/Application Support/Aside/AsideDaemon/...`); opening 100 tabs across 100 agent calls doesn't spawn 100 browser processes.
- **MCP server first-class** — `aside mcp` exposes the browser over the standard MCP protocol, so any agent runtime that supports MCP (Claude Code, Codex, Cursor, AO) can use it as a drop-in browser tool.

## Phases

### Phase 1 — Before any browser action

1. **Check Aside is alive:** `aside account list` should show `* u0 $USER@gmail.com  signed in  profiles: Profile 0`. If not, see "Aside is not running" below.
2. **For complex multi-step work** (scraping, public-data lookups, forms), prefer `aside "..."` NL agent with `--effort ultrabrowse`.
3. **For deterministic scripted work** (screenshot a URL, click a button, fill a form), prefer `aside repl "..."` with the Playwright-shaped API (`openTab`, `snapshot`, `listBrowserTabs`).
4. **For agent-runtime MCP tool exposure** (Claude Code/Codex tool calls), use `mcp__aside-mcp__*` if the runtime exposes it; otherwise drop to `aside repl` from a terminal tool call.
5. **Only if Aside is unavailable or inappropriate**, fall back to `mcp__playwright-mcp` (headless Chromium).

### Phase 2 — During automation

- **REPL pattern** (works in both `aside repl` and `aside mcp`) — see `references/aside-repl-api-gotchas.md` for the full verified surface; the most common pitfalls are: `screenshot()` doesn't exist (use `annotatedScreenshot()`), `fs`/`require`/`process` are not in the REPL sandbox, `listBrowserTabs()` is a Promise whose entries use plain properties (not methods), and **there is NO `browser_click`/`type`/`fill`/`hover`/`press` primitive in the REPL** — the REPL only supports `openTab` / `snapshot` / `annotatedScreenshot` / `closeAllTabs` / direct `evaluate()`-style access via the `page` global. To click or type, you must drive the page via injected JS (e.g. `await page.evaluate(...)` or dispatch a click event manually), or use the full `mcp__aside-mcp__*` tool surface from an agent runtime that exposes it. Verified missing on `aside` v1.26.713.1911 (2026-07-13):
  ```js
  // ❌ DOES NOT EXIST — these will throw ReferenceError
  await browser_click({ ref: 'e73' });
  await browser_type({ ref: 'e3', text: 'hi' });
  await browser_press({ key: 'Enter' });
  await browser_fill(...);

  // ✅ Workaround for one-off clicks: use the page global + native click
  //    (require the Aside REPL to have the `page` global — see gotchas §10)
  await page.evaluate(() => document.querySelector('[ref-attr], button').click());

  // ✅ Workaround for high-trust flows: use the slack.getClient() bypass
  //    (bypasses the browser entirely for Slack API calls that need
  //     scopes the user's XOXP token lacks — see gotchas §11)
  const c = await slack.getClient('T09FXQ4LCQP');
  const r = await c.apiCall('conversations.invite', {
    channel: 'C0BDEAJH8PK',
    users: 'U0A4G7LDJ4R',
  });
  console.log('invite ok:', r.ok);
  ```

- **Multi-line REPL scripts MUST go through `$(cat file)` or heredoc, NOT inline string args** — verified 2026-07-13. When JS contains parentheses inside template literals or string-concatenation (e.g. `String(s.tree).split('\n').filter(l => /ref=e\d+/.test(l))`), bash will mangle the parens before Aside ever sees them, returning `bash: eval: line 16: syntax error near unexpected token '('` instead of the Aside "ReferenceError" you'd expect. The fix:
  ```bash
  # ❌ Breaks on shell tokenization — bash reads `(` as a syntax error
  aside repl "const x = String(s.tree).split('\n').filter(l => /ref=e\d+/.test(l));"

  # ✅ Pattern A — write JS to a file, cat into the arg
  cat > /tmp/script.js <<'JS'
  const x = String(s.tree).split('\n').filter(l => /ref=e\d+\]/.test(l));
  console.log('hits:', x.length);
  JS
  aside repl "$(cat /tmp/script.js)"

  # ✅ Pattern B — heredoc the file CONTENTS as the inline code
  aside repl "$(cat <<'JS'
    const x = ...;
    console.log(x);
  JS
  )"
  ```
  Use `<<'JS'` (quoted heredoc) to prevent bash from expanding `${var}` / `$(cmd)` inside your JS.
- **NL agent pattern** (best for "find X on this site" tasks):
  ```bash
  aside --effort ultrabrowse "Find the next available AirBnB near 1127 Riverside Drive that sleeps 4 and has AC, return the listing URL + price + availability dates"
  ```
- **Live tab list pattern** (when an Aside tab is already open):
  ```js
  // ⚠️ listBrowserTabs() is a Promise; entries are plain-property objects
  const tabs = await listBrowserTabs();
  tabs.forEach(t => console.log(t.url, '|', t.title));
  ```
- **Screenshot-to-disk pattern** (REPL has no `fs`/`require`/`process` — emit base64 to stdout, decode in caller):
  ```js
  const p = await openTab('https://example.com');
  await new Promise(r => setTimeout(r, 4500));
  const shot = await annotatedScreenshot(p);   // NOT screenshot() — that doesn't exist
  console.log('B64:' + shot.base64Image);
  ```
- OAuth capture-and-drive pattern** (verified 2026-07-06 on Granola MCP): many Node.js OAuth clients (`mcporter`, etc.) call `spawn('open', [url])` to launch the system browser. If you shadow `open` on `$PATH` with a wrapper that logs the URL first, then drive Aside Chrome to that captured URL via `aside repl openTab(url)`, you can complete browser-based OAuth flows WITHOUT user-side terminal access. **Critical**: only `aside repl` works — `aside exec` is gated by Codex usage limits and will return "Codex error: The usage limit has reached" for OAuth flows. See `references/oauth-capture-and-drive.md` for the full 7-step recipe with the `PATH`-override wrapper, callback-server verification, and verification checklist.
- **Slack API bypass via `slack.getClient()`** (verified 2026-07-13, aside v1.26.713.1911): when you need to call a Slack Web API method that the user's XOXP token lacks scope for (e.g. `conversations.invite` returns `missing_scope: channels:write.invites`, or `conversations.create` needs `channels:write`), use the Aside-managed Slack client instead of raw `curl`. The client is signed-in to all workspaces the user has profiles for and inherits the user's workspace scopes — bypassing bot-scope and channel-scope limits of any single token. Full method signature in gotchas-reference §11 (the canonical verified recipe):
  ```js
  // List joined workspaces
  const ws = await slack.listWorkspaces();
  // → [{ teamId: "T09FXQ4LCQP", name: "$USER AI", url: "...", isLastActive: true, userId: "U09GH5BR3QU" }]

  // Get a Web-API client for the user's workspace
  const c = await slack.getClient('T09FXQ4LCQP');

  // Call any Slack method — accepts exact same args as web API docs
  const inv = await c.apiCall('conversations.invite', {
    channel: 'C0BDEAJH8PK',   // channel id, NOT name
    users:   'U0A4G7LDJ4R',   // user id, NOT @handle
  });
  // → { ok: true, channel: { id, is_member: true, latest: { subtype: "channel_join", ... } } }
  ```
  **Use case (the bot-rejoin bug):** when a slack bot (`U…`) was removed from channels but is still a valid app, and the user's XOXP token returns `missing_scope: channels:write.invites` on `conversations.invite`, this is the ONLY path to re-add the bot without bothering the user to click in the Slack UI. Verified 2026-07-13 against MCP Mail bot `U0A4G7LDJ4R` across `#worldai-bugs`, `#life`, `#worldai`, `#all-$USER-ai`, etc.

- **Session continuity** (continue a prior NL session):
  ```bash
  aside --session <id> "Continue from where we left off"
  ```
- **Account switching** (rare; for multi-account flows):
  ```bash
  aside --account u1 "open https://example.com"
  ```

### Phase 3 — After session

- Close any tabs the agent opened if they're not useful for the user: `aside repl "closeAllTabs()"`.
- If you called any headed action (no opt-in required for Aside, but worth checking), end the turn by confirming the next agent session starts headless again.

## Aside is not running

If `aside account list` fails or shows no signed-in account:

```bash
# 1. Is the Aside GUI app open?
pgrep -lf "Aside.app" | head -3

# 2. If not, launch it (the daemon will auto-start)
open -a "/Applications/Aside.app"

# 3. Wait ~3 seconds, then verify
sleep 3 && aside account list
```

If `aside` CLI itself is missing:

```bash
curl -fsSL https://releases.aside.com/install.sh | bash
```

## Anti-patterns (BANNED)

- ❌ Calling `mcp__playwright-mcp__*` as a first resort without checking Aside first
- ❌ Calling `show_browser` / headed mode without explicit opt-in (Aside is a real GUI browser — not headless — and the headless-only default applies only when falling back to Playwright or `browserclaw`)
- ❌ Spawning a fresh Playwright Chromium per agent call (Aside's persistent daemon is faster + more stateful)
- ❌ Using `mcp__claude-in-chrome__*` for any browser work (requires extension, fails headless/CI)
- ❌ Assuming Chrome Default cookies reflect the user's actual session — **Aside and Chrome have INDEPENDENT cookie DBs** (different Safe Storage keychains, different file paths). A user logged into `app.monarch.com` via Aside may have ZERO cookies for it in Chrome's `Default/Cookies`, yet the full session lives in `~/Library/Application Support/Aside/Default/Cookies`. Before declaring "no auth," sweep `browserclaw cookies decrypt --db <aside-db> --keychain-service 'Aside Safe Storage' --keychain-account 'Aside'` (verified 2026-07-22: 10 valid `.api.monarch.com` cookies including `session_id` + `csrftoken` lived in Aside's DB; Chrome's profile had zero). See `references/aside-cookie-portability.md` for the full multi-DB sweep pattern.
- ❌ Copying cookies between browsers without re-encrypting under the target's Safe Storage key
- ❌ Assuming Aside CLI can read Chrome/Comet/Arc history (separate cookie stores)
- ❌ Calling `screenshot()` in the REPL — it doesn't exist; use `annotatedScreenshot()` which returns `{base64Image: "..."}`. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `listBrowserTabs()` synchronously — it's a Promise; entries are `{url, title}` plain-property objects, not callables. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `require('fs')` or `process.stdout` inside the REPL — only `Buffer` and the Aside functions are in scope. Save files by emitting base64 to stdout and decoding in the caller.
- ❌ Calling `browser_click` / `browser_type` / `browser_fill` / `browser_press` from `aside repl` — **these primitives don't exist in the REPL** (verified v1.26.713.1911, 2026-07-13). Use `mcp__aside-mcp__*` from a runtime that exposes them, or drive the page via `page.evaluate(...)`. See Pattern `slack.getClient()` bypass below for Slack-specific shortcuts.
- ❌ Passing multi-line JS with parens / curly braces / template literals directly as an `aside repl "..."` inline arg — bash tokenizes before Aside sees the code. Use `$(cat /tmp/script.js)` or a quoted heredoc instead. Wasted two REPL invocations on 2026-07-13 on `aside repl "lines.filter(l => /button \"/button '.+'/i.test(l)).slice(0, 60)..."`.
- ❌ Using Aside inference (`aside "..."` NL agent, `aside --effort ultrabrowse`, `aside exec`, `aside exec -m`) for `/web-advice` — `/web-advice` navigates directly to the real web chat pages to leverage the user's subscriptions. Prefer `aside-mcp` / `aside repl`; use the canonical skill's approved Playwright/Chrome browser fallbacks only when Aside is unavailable or unsupported. Aside inference consumes Aside's token quota and does not use the web chat subscriptions.

## Path / tool availability matrix (as of 2026-06-27)

| Component | Path / URL | Verified? |
|---|---|---|
| Aside GUI app | `/Applications/Aside.app` | ✅ |
| Aside CLI binary | `$HOME/.local/bin/aside` → `~/.aside/cli/Aside CLI.app/Contents/MacOS/aside` | ✅ |
| Aside CLI version | `1.26.626.1517` | ✅ |
| Aside daemon | `~/Library/Application Support/Aside/AsideDaemon/mac-arm64/1.26.627.1553/Aside Daemon.app` | ✅ |
| Aside account | `* u0 $USER@gmail.com` Google provider, `Profile 0` | ✅ |
| Aside MCP (HTTP) | `http://127.0.0.1:8013/mcp` | ✅ (in `~/.claude/mcp-strict.json` + `~/.claude.json`) |
| Aside MCP (stdio) | `aside mcp` | ✅ |
| Aside Safe Storage keychain | `Aside Safe Storage` / `Aside` | ✅ |
| Aside cookie DB | `~/Library/Application Support/Aside/Default/Cookies` | ✅ |

## Cross-browser cookie portability

Aside uses its own macOS Keychain entry (`Aside Safe Storage`), separate from Chrome's (`Chrome Safe Storage`). Cookies cannot be cross-imported without re-encryption. The `browserclaw` skill now supports `--keychain-service 'Aside Safe Storage'` and `--keychain-account 'Aside'` for Aside → Playwright inject. The reverse direction (Chrome → Aside) is not supported in `browserclaw` yet — log a request via `/learn` if needed.

## Verification

```bash
# 1. CLI alive
aside --version       # 1.26.626.1517
aside account list    # * u0  $USER@gmail.com  signed in

# 2. REPL alive
aside repl "console.log('ok')"        # [ok | <Nms>]
aside repl "listBrowserTabs().length" # a number (0 if no tabs open)

# 3. NL agent alive
aside "Open https://example.com and report the title"  # returns "Example Domain"

# 4. MCP server reachable
curl -fsS http://127.0.0.1:8013/mcp -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | head -5
```

## Output format

When reporting browser work, include `browser_mode: aside-cli` (or `aside-mcp` / `playwright-fallback` / `superpowers-chrome-fallback`) in the status line.

## Reversal

To switch back to Playwright MCP as the default:

```bash
bash ~/.hermes/scripts/rollback-aside-default.sh
```

This script:
1. Saves a snapshot of the current `~/.claude.json` mcpServers block to `~/.hermes/snapshots/pre-aside-default-YYYY-MM-DD.json`.
2. Removes the `aside-browser-default` skill folder.
3. Removes `aside-mcp` from `~/.claude.json`.
4. Reverts SOUL.md / AGENTS.md / CLAUDE.md browser COMMIT blocks to their pre-aside-default state (the blocks are read from the snapshot).
5. Resets macOS default browser to Chrome via `defaultbrowser chrome`.

The script is idempotent — running it twice is safe.

## References
- **Cross-references:**
  - `references/aside-repl-api-gotchas.md` — verified REPL API surface (2026-07-05; updated 2026-07-09, 2026-07-13, 2026-07-14, 2026-07-15): `screenshot()` doesn't exist, `fs`/`require`/`process` not available, `listBrowserTabs()` is a Promise, `openTab()` returns CDP target object, `slack.getClient()` is the only zero-scope-setup Slack channel-create path, `aside repl` is stateless across invocations, `DOMRect` from `evaluate()` must be flattened before serialization, console.log required for output capture, "fetch failed" = Aside GUI not running, `aside --effort ultrabrowse` times out on multi-step structured flows, **heavy SPA landing pages disconnect CDP — capture lightweight JSON endpoints first** (2026-07-15). Must-read before writing any `aside repl` automation.
  - `references/slack-web-ui-scraping.md` — verified recipe for scraping Slack web views (Later page, Activity, Saved items, DMs) via Aside: tab click selectors (`button.c-tabs__tab`), virtualized-list scroll pattern, `Incomplete • X ago` / `Due in X` regex parser, XOX-P fallback for posting results back. Verified 2026-07-14 against the Later page.
- `references/oauth-capture-and-drive.md` — 7-step recipe for driving browser-based OAuth flows (Granola MCP verified 2026-07-06) by shadowing `open` on PATH, capturing the URL mcporter tries to launch, then `aside repl openTab(url)` — works when the user is already signed in to the upstream IdP in Aside Chrome. **Correction**: the earlier claim that "Aside cannot do OAuth" was wrong for `aside repl`; only `aside exec` is Codex-gated.
- `references/aside-cookie-portability.md` — full Chrome-vs-Aside cookie-DB sweep recipe + verified 2026-07-22 case where the user was authenticated to `api.monarch.com` in Aside but Chrome Default had 0 cookies. Always run the multi-DB sweep before declaring "the user isn't logged in." Covers `--keychain-service 'Aside Safe Storage'`, the no-entry-due-to-no-cookies-written-yet fail mode, and Slack's newer cookie-format caveat (Aside decrypts `d` to hex; Chrome keeps it as `xoxd-`; Slack rejects the Aside format).
- `/learn` capture for this switch: `~/.claude/projects/-Users-$USER--hermes/memory/feedback_2026-06-27_aside-browser-default-switch.md`
- Wiki source page: `~/llm_wiki/wiki/sources/aside-browser-default-switch-2026-06-27.md`
- Wiki entity: `~/llm_wiki/wiki/entities/AsideBrowser.md`
- Wiki concept: `~/llm_wiki/wiki/concepts/ReversibleFacadePattern.md`
- Roadmap learnings: `~/roadmap/learnings-2026-06.md` (2026-06-27 entry)
- Rollback script: `~/.hermes/scripts/rollback-aside-default.sh`
- Aside docs: <https://docs.aside.com/help/developers>
- Install: `curl -fsSL https://releases.aside.com/install.sh | bash`
