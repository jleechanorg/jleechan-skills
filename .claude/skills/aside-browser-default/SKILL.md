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

Apply [browser-control's personal browser isolation contract](../browser-control/SKILL.md#personal-browser-isolation--required-for-every-route) first. Aside is primary only when it can operate in the background in an agent-owned tab; otherwise use isolated headless Playwright Chromium. Never attach to, focus, or import cookies from the personal Chrome browser.

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
2. **Do not inspect personal tabs or profiles.** If ownership or background behavior is uncertain, do not probe further; use isolated headless Chromium.
3. **For complex multi-step work** (scraping, public-data lookups, forms), prefer `aside "..."` NL agent with `--effort ultrabrowse`.
4. **For deterministic scripted work** (screenshot a URL, click a button, fill a form), prefer `aside repl "..."` with the Playwright-shaped API (`openTab`, `snapshot`, `listBrowserTabs`).
5. **For agent-runtime MCP tool exposure** (Claude Code/Codex tool calls), use `mcp__aside-mcp__*` if the runtime exposes it; otherwise drop to `aside repl` from a terminal tool call.
6. **Otherwise use** `mcp__playwright-mcp` (headless Chromium) in an isolated context.

### Authentication and API boundary

Do not turn a browser login, consent, or MFA failure into a direct request to an internal API using browser cookies, copied headers, or bearer tokens. Do not mine HARs or browser storage for credentials. Use a provider-owned API/OAuth flow when the task authorizes it. The one permitted local cookie-transfer exception is a task that explicitly authorizes transfer from exactly one named agent-owned profile; follow browser-control's guarded lifecycle and stop on login, consent, or MFA. This does not authorize direct API probing.

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
- **OAuth:** use only the provider's supported OAuth flow in an already authorized, isolated browser context. Do not intercept a system opener, log authorization URLs, launch or drive a desktop browser, clear cached tokens, or reuse personal browser state. The legacy recipe at `references/oauth-capture-and-drive.md` is retired and non-executable.
- **Session continuity** (continue a prior NL session):
  ```bash
  aside --session <id> "Continue from where we left off"
  ```
- **Account switching** (rare; for multi-account flows):
  ```bash
  aside --account <agent-owned-account-id> "open https://example.com"
  ```

### Phase 3 — After session

- Close only the exact tabs opened by this task when they are no longer useful. Never call `closeAllTabs()` on a shared browser.
- Keep Chromium headless by default. If the current thread explicitly requests visible automation, use only a separate, verified task-owned browser process/profile/context; never the personal/default browser.

## Aside is not running

Start it in background mode (§ Background mode). If the app is not installed, background start fails, or the frontmost app changes, use isolated headless Chromium. Never use plain `open -a Aside`, `open <url>`, or anything that activates the app.

If the Aside CLI or app is not installed, use isolated headless Chromium; installing or repairing Aside is outside this skill's browser-task path.

## Additional rules from the 2026-07-11 social-staging run

- A visible compose form is not proof the draft is staged. Read the field back or otherwise verify the text persisted.
- Login walls, chooser screens, and consent prompts are access boundaries. Continue only through the provider-supported flow in the already authorized isolated context; do not bypass them, request credential entry, or treat cookie transfer as recovery from these controls.
- Prefer current live browser evidence over stale session logs, old failure notes, or previous daemon incidents.
- If the source content came from a LinkedIn post that links outward, extract and propagate the canonical outbound URL instead of reposting the LinkedIn shortlink.
- If media is central to the post, carry the exact asset path through the workflow so the agent knows what to upload.

## Anti-patterns (BANNED)

- ❌ Falling back to a personal browser when the isolated headless route is unavailable
- ❌ Declaring a platform "staged" from a screenshot of an empty compose box or login wall
- ❌ Treating a broken `openTab()` path as proof that all existing Aside tabs are unusable
- ❌ Reporting generic "Aside broken" status without separating transport, browser-bridge, and auth-state failures
- ❌ Calling `show_browser` by default or launching headed mode as an ordinary fallback; the headless-only default applies to Playwright/browserclaw fallback routes. An explicit current-thread visible-mode request may use a separate verified task-owned profile.
- ❌ Using `mcp__claude-in-chrome__*` for any browser work (requires extension, fails headless/CI)
- ❌ Copying cookies between browsers. The only permitted exception is the explicitly authorized, one-agent-owned-source transfer in browser-control; it must use the guarded private-temp lifecycle and must not bypass an access control.
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

- `references/aside-repl-api-gotchas.md` — verified REPL API surface (2026-07-05): `screenshot()` doesn't exist, `fs`/`require`/`process` not available, `listBrowserTabs()` is a Promise, `openTab()` returns CDP target object. Must-read before writing any `aside repl` automation.
- `references/oauth-capture-and-drive.md` — retired OAuth recipe notice. Do not execute the former opener-shadowing, desktop-browser, or direct API-probe flow.
- `/learn` capture for this switch: `~/.claude/projects/-Users-$USER--hermes/memory/feedback_2026-06-27_aside-browser-default-switch.md`
- Wiki source page: `~/llm_wiki/wiki/sources/aside-browser-default-switch-2026-06-27.md`
- Wiki entity: `~/llm_wiki/wiki/entities/AsideBrowser.md`
- Wiki concept: `~/llm_wiki/wiki/concepts/ReversibleFacadePattern.md`
- Roadmap learnings: `~/roadmap/learnings-2026-06.md` (2026-06-27 entry)
- Aside docs: <https://docs.aside.com/help/developers>
