---
name: aside-browser-default
description: Aside browser is the PRIMARY browser tool for all Hermes/Claude/Codex work. Use aside CLI (repl/mcp/exec modes) or aside-mcp before Playwright MCP / superpowers-chrome. Use when opening browsers, scraping, UI tests, localhost verification, cookie injection flows, or any browser-driven automation. Playwright MCP and superpowers-chrome are explicit fallbacks for cases Aside can't handle (e.g., headless CI runners, Playwright-specific test fixtures). Reversible — see ~/.hermes/scripts/rollback-aside-default.sh.
when_to_use: Browser automation, scraping, screenshots, localhost UI checks, cookie injection flows, /browser command, public-data lookups
allowed-tools: mcp__aside-mcp, aside, mcp__playwright-mcp (fallback), mcp__plugin-superpowers-chrome__chrome_use_browser (fallback)
context: hermes
---

# Aside Browser Default

## Contract

Aside is a real GUI browser, not headless. Its background behavior must be verified for the current operation.

Apply [browser-control's personal browser isolation contract](../browser-control/SKILL.md#personal-browser-isolation--required-for-every-route) first. Aside is primary only when it can operate in the background in an agent-owned tab; otherwise use isolated headless Playwright Chromium. Never attach to, focus, or import cookies from the personal Chrome browser.

**Default: Aside first.** For all browser work, agents should reach for the Aside CLI / Aside MCP server before Playwright MCP or superpowers-chrome. Playwright MCP and superpowers-chrome are **named fallbacks** — preserved, not deleted — for cases Aside can't handle (rare; mostly headless CI runners and Playwright-specific test fixtures).

| Tool | Role | When to use |
|------|------|-------------|
| **`aside` CLI / `aside-mcp`** | **Primary** | Default for everything: UI tests, localhost verification, scraping, cookie flows, public-data lookups |
| `mcp__playwright-mcp` | Fallback | Only when Aside CLI is unavailable, or for Playwright-specific fixtures (trace viewer, `--isolated` profile mode, video recording) |
| `mcp__plugin-superpowers-chrome__chrome_use_browser` | Fallback | Only when Chrome-specific behavior is required (e.g., you need Chrome's exact `--user-data-dir` semantics for a particular test) |

**Explicit opt-in phrases only:** The user says *"show browser"*, *"headed mode"*, *"visible browser"*, or *"I want to see the window"* in the **current thread**. These permit a separate automation window only; the Playwright fallback keeps its headless-only default otherwise. Do not assume Aside navigation is headless; verify background operation or use isolated headless Chromium.

## Why Aside

Aside is a Y Combinator–backed AI-native Chromium browser launched June 2026. Advantages over the prior default:

- **AI-native design** — Aside's `aside "..."` NL agent and `--effort ultrabrowse` mode can plan + execute multi-step browser workflows without the agent writing Playwright scripts.
- **Same Chrome internals** — Aside is Chromium-based, so `document.querySelector`, CDP, computed styles, etc. all work identically.
- **Persistent browser session** — Aside runs as a long-lived daemon (`~/Library/Application Support/Aside/AsideDaemon/...`); opening 100 tabs across 100 agent calls doesn't spawn 100 browser processes.
- **MCP server first-class** — `aside mcp` exposes the browser over the standard MCP protocol, so any agent runtime that supports MCP (Claude Code, Codex, Cursor, AO) can use it as a drop-in browser tool.

## Phases

### Phase 1 — Before any browser action

1. **Check Aside is alive:** `aside account list` should show `* u0 $USER@gmail.com  signed in  profiles: Profile 0`. If not, see "Aside is not running" below.
2. **Probe live browser state before diagnosing failures.** Check whether current signed-in tabs already exist and are usable before concluding Aside is broken.
3. **For complex multi-step work** (scraping, public-data lookups, forms), prefer `aside "..."` NL agent with `--effort ultrabrowse`.
4. **For deterministic scripted work** (screenshot a URL, click a button, fill a form), prefer `aside repl "..."` with the Playwright-shaped API (`openTab`, `snapshot`, `listBrowserTabs`).
5. **For agent-runtime MCP tool exposure** (Claude Code/Codex tool calls), use `mcp__aside-mcp__*` if the runtime exposes it; otherwise drop to `aside repl` from a terminal tool call.
6. **Only if Aside is unavailable or inappropriate**, fall back to `mcp__playwright-mcp` (headless Chromium).

### Phase 1.6 — When the browser path fails: Python+cookies escape hatch

**Do NOT give up** when `openTab` + `attachBrowserTab` both land on a login page even though a cookie DB has the session. The session may be valid for the *API* even when the dashboard is unreachable. Walk this ladder before declaring the site inaccessible:

1. **Use only an explicitly authorized agent-owned cookie DB**, following browser-control's guarded cookie-transfer lifecycle. The personal Chrome profile and cookies are excluded; never sweep them to recover an automation login. Use the source browser's matching Safe Storage service/account and never print cookie values.
2. **Probe the internal GraphQL/REST endpoint directly with `requests`**:
   ```python
   import json, requests
   cookies_blob = json.load(open('cookies.json'))['cookies']
   s = requests.Session()
   for c in cookies_blob:
       s.cookies.set(c['name'], c['value'], domain=c['domain'], path=c.get('path','/'))
   csrf = s.cookies.get('csrftoken', domain='.example.com')
   s.headers.update({
       'X-CSRFToken': csrf or '',
       'Origin': 'https://app.example.com',
       'Referer': 'https://app.example.com/',
       'Content-Type': 'application/json',
   })
   r = s.post('https://api.example.com/graphql', json={"query": "{ me { id email } }"})
   ```
3. **Required headers** (any one missing → 403 CSRF rejection): `X-CSRFToken`, `Origin` (must match the SPA origin, not the API), `Referer` (must match the SPA URL), `Cookie` (auto-set by requests when cookies are loaded).
4. **Worked Monarch example** (verified 2026-07-22): cookies in `/tmp/budget-monarch/aside-all.json`, GraphQL at `https://api.monarch.com/graphql`. First successful probe: `{ me { id email } }` → `id: 170607937752856546, email: $USER@gmail.com`. Schema uses plural field names (`categories`, `accounts`, `transactions`).
5. **Schema-quirk debugging**: opaque "Something went wrong while processing" usually means a hidden required subfield or auth-scoped permission. Mitigate by querying one leaf field at a time (`{ accounts { id } }` first, then `{ accounts { id currentBalance } }`, etc.).

**Anti-pattern:** "Chrome headless cookies didn't work + Aside MCP hits login → conclude the site is inaccessible → ask the user for credentials." That's wrong. Try the API path first.

### Phase 1.5 — Failure classification

Before saying "Aside is broken", classify which layer is actually failing:

1. **Transport healthy, browser workflow healthy**
   - CLI/MCP calls succeed
   - tab listing / openTab / attach work
2. **Transport healthy, fresh-tab workflow unhealthy**
   - CLI/MCP calls succeed
   - existing tabs may still be readable or attachable
   - a specific `openTab()` or profile bridge may fail
3. **Transport healthy, auth/UI blocking**
   - page loads, but the site is at login, consent, or chooser state
   - try one-click continuations before declaring a hard blocker
4. **Transport unhealthy**
   - CLI/MCP init itself fails
5. **Runtime split-brain**
   - standalone `aside` CLI may fail while the agent's built-in Aside browser tool still works
   - or the reverse: the tool session may be stale while a fresh CLI/MCP session is healthy

Always report which layer failed. Do not collapse these into one generic "Aside failed" diagnosis.
Do not assume a failing standalone CLI means the browser tool is dead, or that a stale browser tool session means all Aside entrypoints are dead.

### Phase 2 — During automation

- **REPL pattern** (works in both `aside repl` and `aside mcp`) — see `references/aside-repl-api-gotchas.md` for the full verified surface; the most common pitfall is that `screenshot()` doesn't exist (use `annotatedScreenshot()`), `fs`/`require`/`process` are not in the REPL sandbox, and `listBrowserTabs()` is a Promise whose entries use plain properties (not methods):
  ```js
  const p = await openTab('https://example.com');
  const s = await snapshot(p, { interactive: true });
  console.log(s.tree);     // or s.title, s.url, s.childCount
  await closeTab(p);       // close only this task-owned tab
  ```
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
- **OAuth capture-and-drive pattern** (verified 2026-07-06 on Granola MCP): many Node.js OAuth clients (`mcporter`, etc.) call `spawn('open', [url])` to launch the system browser. If you shadow `open` on `$PATH` with a wrapper that logs the URL first, then drive Aside Chrome to that captured URL via `aside repl openTab(url)`, you can complete browser-based OAuth flows WITHOUT user-side terminal access. **Critical**: only `aside repl` works — `aside exec` is gated by Codex usage limits and will return "Codex error: The usage limit has reached" for OAuth flows. See `references/oauth-capture-and-drive.md` for the full 7-step recipe with the `PATH`-override wrapper, callback-server verification, and verification checklist.
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
- Headed actions require explicit opt-in for a separate automation window. Close only the task-owned window when finished; never hide, restart, or close the user's browser.

## Aside is not running

If `aside account list` fails or shows no signed-in account:

```bash
# 1. Is the Aside GUI app open?
pgrep -lf "Aside.app" | head -3

# If it is unavailable, use isolated headless Chromium.
# Do not activate a GUI app as automatic recovery.
```

If `aside` CLI itself is missing:

```bash
curl -fsSL https://releases.aside.com/install.sh | bash
```

## Additional rules from the 2026-07-11 social-staging run

- A visible compose form is not proof the draft is staged. Read the field back or otherwise verify the text persisted.
- Login walls, chooser screens, and consent prompts are not final blockers. Treat them as recoverable states first.
- Prefer current live browser evidence over stale session logs, old failure notes, or previous daemon incidents.
- If the source content came from a LinkedIn post that links outward, extract and propagate the canonical outbound URL instead of reposting the LinkedIn shortlink.
- If media is central to the post, carry the exact asset path through the workflow so the agent knows what to upload.

## Anti-patterns (BANNED)

- ❌ Calling `mcp__playwright-mcp__*` as a first resort without checking Aside first
- ❌ Declaring a platform "staged" from a screenshot of an empty compose box or login wall
- ❌ Treating a broken `openTab()` path as proof that all existing Aside tabs are unusable
- ❌ Reporting generic "Aside broken" status without separating transport, browser-bridge, and auth-state failures
- ❌ Calling `show_browser` / headed mode without explicit opt-in for a separate automation window; the Playwright fallback retains its headless-only default.
- ❌ Spawning a fresh Playwright Chromium per agent call (Aside's persistent daemon is faster + more stateful)
- ❌ Using `mcp__claude-in-chrome__*` for any browser work (requires extension, fails headless/CI)
- ❌ Copying cookies between browsers without re-encrypting under the target's Safe Storage key
- ❌ Assuming Aside CLI can read Chrome/Comet/Arc history (separate cookie stores)
- ❌ Calling `screenshot()` in the REPL — it doesn't exist; use `annotatedScreenshot()` which returns `{base64Image: "..."}`. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `listBrowserTabs()` synchronously — it's a Promise; entries are `{url, title}` plain-property objects, not callables. See `references/aside-repl-api-gotchas.md`.
- ❌ Using `require('fs')` or `process.stdout` inside the REPL — only `Buffer` and the Aside functions are in scope. Save files by emitting base64 to stdout and decoding in the caller.

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

- `references/aside-repl-api-gotchas.md` — verified REPL API surface (2026-07-05): `screenshot()` doesn't exist, `fs`/`require`/`process` not available, `listBrowserTabs()` is a Promise, `openTab()` returns CDP target object. Must-read before writing any `aside repl` automation.
- `references/oauth-capture-and-drive.md` — 7-step recipe for driving browser-based OAuth flows (Granola MCP verified 2026-07-06) by shadowing `open` on PATH, capturing the URL mcporter tries to launch, then `aside repl openTab(url)` — works when the user is already signed in to the upstream IdP in Aside Chrome. **Correction**: the earlier claim that "Aside cannot do OAuth" was wrong for `aside repl`; only `aside exec` is Codex-gated.
- `/learn` capture for this switch: `~/.claude/projects/-Users-$USER--hermes/memory/feedback_2026-06-27_aside-browser-default-switch.md`
- Wiki source page: `~/llm_wiki/wiki/sources/aside-browser-default-switch-2026-06-27.md`
- Wiki entity: `~/llm_wiki/wiki/entities/AsideBrowser.md`
- Wiki concept: `~/llm_wiki/wiki/concepts/ReversibleFacadePattern.md`
- Roadmap learnings: `~/roadmap/learnings-2026-06.md` (2026-06-27 entry)
- Rollback script: `~/.hermes/scripts/rollback-aside-default.sh`
- Aside docs: <https://docs.aside.com/help/developers>
- Install: `curl -fsSL https://releases.aside.com/install.sh | bash`