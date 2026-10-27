---
name: aside-browser-default
description: Run Aside in background (no-focus-steal) mode on an agent-owned profile by default for live and authenticated sites; use isolated headless Chromium for CI, Linux, deterministic tests, or when background mode cannot be verified. See browser-control for the personal-browser isolation contract.
when_to_use: Browser automation, scraping, screenshots, localhost UI checks, cookie injection flows, /browser command, public-data lookups
allowed-tools: mcp__aside-mcp, aside, mcp__playwright-mcp (fallback), mcp__plugin-superpowers-chrome__chrome_use_browser (fallback)
context: hermes
---

# Aside Browser Default

## Contract

Aside is a real GUI browser, not headless (it has no headless flag). Run it in background mode by default (§ Background mode): agent-owned profile, started and driven without taking focus, frontmost app verified unchanged. If background mode cannot be verified, use isolated headless Chromium.

Apply `~/.claude/skills/browser-control/SKILL.md` § Personal browser isolation first. Aside runs in background mode on an agent-owned profile; otherwise use isolated headless Playwright Chromium. Never attach to, focus, or import cookies from the personal Chrome browser.

**Default: Aside in background mode** for live websites and authenticated sessions on an agent-owned profile. Isolated headless Chromium is the default for CI, Linux, deterministic local-app tests, and whenever background mode is unavailable or unverified. No user request to show or use a browser authorizes use of a personal window/profile.

| Tool | Role | When to use |
|------|------|-------------|
| **`aside` CLI / `aside-mcp`** | Default (background mode) | Agent-owned profile in background mode per § Background mode; never foreground it or use personal tabs/profile |
| `mcp__playwright-mcp` | Default (headless) | Headless isolated browser for CI, Linux, deterministic tests, and when Aside background mode is not verified |
| `mcp__plugin-superpowers-chrome__chrome_use_browser` | Fallback | Only when Chrome-specific behavior is required (e.g., you need Chrome's exact `--user-data-dir` semantics for a particular test) |

Keep Chromium headless by default. A current-thread explicit request for visible automation permits a headed window only in a separate, verified task-owned browser process/profile/context. Never use a personal or default profile, or bring a desktop app to the foreground. Verify background operation (frontmost app unchanged) for the current task, or use isolated headless Chromium.

## Background mode

Aside has no headless flag; background mode is the supported no-focus-steal equivalent (macOS only).

1. **Start only the agent profile,** whether the app is stopped or the profile shows `disconnected` in `aside host profiles --account <agent-account>` (or `aside repl` reports it is not connected). Never use `open -a`, `open -g -a`, or `open <url>`: a plain launch takes focus and a cold app start can restore personal profile windows. Run `/Applications/Aside.app/Contents/MacOS/Aside --profile-directory="<agent profile dir>" --no-startup-window &`. Afterwards, `aside host profiles` must show every personal account still `disconnected`; if a personal profile connected, stop using Aside for the task and report it. Find the directory in `~/Library/Application Support/Aside/Local State` (`profile.info_cache`, matching the agent account email). Never start a personal profile.
2. **Drive tabs only through** `aside repl --account <agent-account>` or `aside-mcp` (`openTab`, `snapshot`, `closeTab`).
3. **Verify:** record the frontmost app (`osascript -e 'tell application "System Events" to get name of first process whose frontmost is true'`) before starting Aside and again after the first action. If it changed, stop using Aside for the task and switch to isolated headless Chromium.

## Why Aside

Aside is a Y Combinator–backed AI-native Chromium browser launched June 2026. Advantages over the prior default:

- **AI-native design** — Aside's `aside "..."` NL agent and `--effort ultrabrowse` mode can plan + execute multi-step browser workflows without the agent writing Playwright scripts.
- **Same Chrome internals** — Aside is Chromium-based, so `document.querySelector`, CDP, computed styles, etc. all work identically.
- **Persistent browser session** — Aside runs as a long-lived daemon (`~/Library/Application Support/Aside/AsideDaemon/...`); opening 100 tabs across 100 agent calls doesn't spawn 100 browser processes.
- **MCP server first-class** — `aside mcp` exposes the browser over the standard MCP protocol, so any agent runtime that supports MCP (Claude Code, Codex, Cursor, AO) can use it as a drop-in browser tool.

## Phases

### Phase 1 — Before any browser action

1. **Start or reuse Aside in background mode** (§ Background mode) on an agent-owned profile. Metadata or account-list output alone does not prove a connected profile; check `aside host profiles --account <id>`.
2. **For complex multi-step work** (scraping, public-data lookups, forms), prefer `aside "..."` NL agent with `--effort ultrabrowse`.
3. **For deterministic scripted work** (screenshot a URL, click a button, fill a form), prefer `aside repl "..."` with the Playwright-shaped API (`openTab`, `snapshot`, `listBrowserTabs`).
4. **For agent-runtime MCP tool exposure** (Claude Code/Codex tool calls), use `mcp__aside-mcp__*` if the runtime exposes it; otherwise drop to `aside repl` from a terminal tool call.
5. **Otherwise use** `mcp__playwright-mcp` (headless Chromium) in an isolated context.

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
  aside --account <agent-account> --effort ultrabrowse "Find the next available AirBnB near 1127 Riverside Drive that sleeps 4 and has AC, return the listing URL + price + availability dates"
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
- **OAuth:** use the provider-supported flow in an isolated, agent-owned browser context. Do not intercept system URL openers, log authorization URLs, clear cached grants, or launch/drive a desktop browser. The old capture-and-drive reference is retired and non-executable.
- **Slack operations:** use the approved Slack connector/API with its existing authorized scopes. If a method is unavailable or returns `missing_scope`, do not use `slack.getClient()` or browser cookies to bypass that limit; use an authorized Slack UI action in an already verified, isolated agent-owned browser context when appropriate, or report the missing authorization. See `references/aside-repl-api-gotchas.md` for this boundary and safe membership checks.

- **Session continuity** (continue a prior NL session):
  ```bash
  aside --session <id> "Continue from where we left off"
  ```
- **Account switching** (rare; for multi-account flows):
  ```bash
  aside --account u1 "open https://example.com"
  ```

### Phase 3 — After session

- Close only the exact tabs opened by this task when they are no longer useful. Never call `closeAllTabs()` on a shared browser.
- Keep Chromium headless by default. If the current thread explicitly requests visible automation, use only a separate, verified task-owned browser process/profile/context; never the personal/default browser.

## Aside is not running

Start it in background mode (§ Background mode). If the app is not installed, background start fails, or the frontmost app changes, use isolated headless Chromium. Never use plain `open -a Aside`, `open <url>`, or anything that activates the app.

If the Aside CLI or app is unavailable, use isolated headless Chromium. Installation and app recovery are outside this browser-task route.

## Anti-patterns (BANNED)

- ❌ Falling back to a personal browser when the isolated headless route is unavailable
- ❌ Calling `show_browser` by default or launching headed mode as an ordinary fallback; the headless-only default applies to Playwright/browserclaw fallback routes. An explicit current-thread visible-mode request may use a separate verified task-owned profile.
- ❌ Using `mcp__claude-in-chrome__*` for any browser work (requires extension, fails headless/CI)
- ❌ Assuming one authorized agent-owned source reflects every browser session — **Aside and other browsers have independent cookie DBs**. Before declaring "no auth," inspect only the one source profile/DB explicitly authorized for this task, using its matching Safe Storage service/account and the guarded browser-control lifecycle. Never sweep desktop browser profiles or personal cookie stores. See `references/aside-cookie-portability.md` for portability constraints.
- ❌ Copying cookies between browsers. The only permitted exception is the explicitly authorized, one-agent-owned-source transfer in browser-control; it must use the guarded private-temp lifecycle and must not bypass an access control.
- ❌ Assuming Aside CLI can read Chrome/Comet/Arc history (separate cookie stores)
- ❌ Calling `screenshot()` in the REPL — it doesn't exist; use `annotatedScreenshot()` which returns `{base64Image: "..."}`. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `listBrowserTabs()` synchronously — it's a Promise; entries are `{url, title}` plain-property objects, not callables. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `require('fs')` or `process.stdout` inside the REPL — only `Buffer` and the Aside functions are in scope. Save files by emitting base64 to stdout and decoding in the caller.
- ❌ Calling `browser_click` / `browser_type` / `browser_fill` / `browser_press` from `aside repl` — **these primitives don't exist in the REPL** (verified v1.26.713.1911, 2026-07-13). Use `mcp__aside-mcp__*` from a runtime that exposes them, or drive the page via `page.evaluate(...)`.
- ❌ Passing multi-line JS with parens / curly braces / template literals directly as an `aside repl "..."` inline arg — bash tokenizes before Aside sees the code. Use `$(cat /tmp/script.js)` or a quoted heredoc instead. Wasted two REPL invocations on 2026-07-13 on `aside repl "lines.filter(l => /button \"/button '.+'/i.test(l)).slice(0, 60)..."`.
- ❌ Using Aside inference (`aside "..."` NL agent, `aside --effort ultrabrowse`, `aside exec`, `aside exec -m`) for `/web-advice` — `/web-advice` navigates directly to the real web chat pages to leverage the user's subscriptions. Prefer `aside-mcp` / `aside repl`; use the canonical skill's approved Playwright/Chrome browser fallbacks only when Aside is unavailable or unsupported. Aside inference consumes Aside's token quota and does not use the web chat subscriptions.

## Path / tool availability matrix (as of 2026-06-27)

| Component | Path / URL | Verified? |
|---|---|---|
| Aside GUI app | `/Applications/Aside.app` | ✅ |
| Aside CLI binary | `$HOME/.local/bin/aside` → `~/.aside/cli/Aside CLI.app/Contents/MacOS/aside` | ✅ |
| Aside CLI version | `1.26.626.1517` | ✅ |
| Aside daemon | `~/Library/Application Support/Aside/AsideDaemon/mac-arm64/1.26.627.1553/Aside Daemon.app` | ✅ |
| Aside account | `* u0 '<account-email>'` Google provider, `Profile 0` | ✅ |
| Aside MCP (HTTP) | `http://127.0.0.1:8013/mcp` | ✅ (in `~/.claude/mcp-strict.json` + `~/.claude.json`) |
| Aside MCP (stdio) | `aside mcp` | ✅ |
| Aside Safe Storage keychain | `Aside Safe Storage` / `Aside` | ✅ |
| Aside cookie DB | `~/Library/Application Support/Aside/Default/Cookies` | ✅ |

## Cross-browser cookie portability

Aside and Chrome use separate macOS Keychain entries. This is portability background, not permission to copy cookies. Any transfer is limited to the exact, explicitly authorized agent-owned source and guarded private-temp lifecycle in browser-control; personal Chrome is never a source. Re-encryption does not authorize bypassing an access control.

## Verification

```bash
# 1. CLI alive
aside --version       # 1.26.626.1517
aside account list    # * u0  '<account-email>'  signed in

# 2. REPL alive
aside repl "console.log('ok')"        # [ok | <Nms>]
  aside repl "(async () => console.log((await listBrowserTabs()).length))()" # number of open tabs

# 3. NL agent alive
aside "Open https://example.com and report the title"  # returns "Example Domain"

# 4. MCP server reachable
curl -fsS http://127.0.0.1:8013/mcp -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | head -5
```

## Output format

When reporting browser work, include `browser_mode: aside-cli` (or `aside-mcp` / `playwright-fallback` / `superpowers-chrome-fallback`) in the status line.

## Administrative rollback

`~/.hermes/scripts/rollback-aside-default.sh` changes user-wide agent configuration and resets the macOS default browser. It is not a browser-recovery fallback and must not be run during ordinary browser work. Any configuration migration requires a separate, explicitly scoped task.

## References
- **Cross-references:**
  - `references/aside-repl-api-gotchas.md` — verified REPL API surface (2026-07-05; updated 2026-07-09, 2026-07-13, 2026-07-14, 2026-07-15): `screenshot()` doesn't exist, `fs`/`require`/`process` not available, `listBrowserTabs()` is a Promise, `openTab()` returns CDP target object, `aside repl` is stateless across invocations, `DOMRect` from `evaluate()` must be flattened before serialization, console.log required for output capture, "fetch failed" = Aside GUI not running, `aside --effort ultrabrowse` times out on multi-step structured flows, **heavy SPA landing pages disconnect CDP — capture lightweight JSON endpoints first** (2026-07-15). Must-read before writing any `aside repl` automation.
  - `references/slack-web-ui-scraping.md` — verified recipe for scraping Slack web views (Later page, Activity, Saved items, DMs) via Aside: tab click selectors (`button.c-tabs__tab`), virtualized-list scroll pattern, `Incomplete • X ago` / `Due in X` regex parser, XOX-P fallback for posting results back. Verified 2026-07-14 against the Later page.
- `references/oauth-capture-and-drive.md` — retired OAuth recipe notice. Do not execute the former opener-shadowing, desktop-browser, or direct API-probe flow.
  - `references/aside-cookie-portability.md` — background on Aside's separate cookie store and keychain. For an explicitly authorized authenticated-content task, inspect only the one authorized agent-owned source and use the canonical guarded lifecycle in `~/.claude/skills/browser-control/SKILL.md`; do not run the legacy multi-DB sweep or query personal Chrome stores. Covers `--keychain-service 'Aside Safe Storage'`, the no-entry-due-to-no-cookies-written-yet fail mode, and Slack's newer cookie-format caveat (Aside decrypts `d` to hex; Chrome keeps it as `xoxd-`; Slack rejects the Aside format).
- `/learn` capture for this switch: `~/.claude/projects/-Users-$USER--hermes/memory/feedback_2026-06-27_aside-browser-default-switch.md`
- Wiki source page: `~/llm_wiki/wiki/sources/aside-browser-default-switch-2026-06-27.md`
- Wiki entity: `~/llm_wiki/wiki/entities/AsideBrowser.md`
- Wiki concept: `~/llm_wiki/wiki/concepts/ReversibleFacadePattern.md`
- Roadmap learnings: `~/roadmap/learnings-2026-06.md` (2026-06-27 entry)
- Aside docs: <https://docs.aside.com/help/developers>
