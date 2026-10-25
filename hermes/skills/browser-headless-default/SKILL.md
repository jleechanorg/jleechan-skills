---
name: browser-headless-default
description: "Enforce headless browser automation by default for Hermes — Playwright MCP and superpowers-chrome. Use when opening browsers, scraping, UI tests, localhost verification, or any chrome_use_browser / Playwright call. Never headed unless Jeffrey explicitly requests visible browser."
when_to_use: Browser automation, scraping, screenshots, localhost UI checks, Luma/cookie flows, /browser command
allowed-tools: mcp__playwright-mcp, mcp__plugin-superpowers-chrome__chrome_use_browser
context: hermes
---

# Browser Headless Default

## Contract

Apply the personal browser isolation contract in `~/.claude/skills/browser-control/SKILL.md` before every browser action. The user's main Chrome is off-limits, including its cookies and login state. Headed opt-in permits a separate automation window only.

**Default: headless always.** Jeffrey's Mac is not a demo kiosk — do not pop Chrome windows during agent work.

**Primary tool (2026-06-27):** **Aside browser** (`aside` CLI / `aside-mcp`). Use it first for all browser work. This skill is the fallback for Playwright MCP / superpowers-chrome paths.

| Tool | Default | Forbidden unless explicit user opt-in |
|------|---------|--------------------------------------|
| **Aside CLI / `aside-mcp`** | **PRIMARY** only when verified to stay in the background in an agent-owned tab | activating/focusing a window; metadata calls alone do not prove background navigation |
| **Playwright MCP** | fallback, headless | headed / `headless: false` |
| **superpowers-chrome** (`chrome_use_browser`) | fallback, headless (`hide_browser`, `browser_mode` → `headless: true`) | `show_browser`, headed restart |
| **claude-in-chrome / GUI Chrome** | do not use for localhost | driving Jeffrey's visible Chrome for automation |

**Explicit opt-in phrases only:** The user says *"show browser"*, *"headed mode"*, *"visible browser"*, or *"I want to see the window"* in the **current thread**.

## Phases

### Phase 1 — Before any browser action

1. Run `bash ~/.hermes/skills/browser-headless-default/scripts/validate-browser-mode.sh` when unsure.
2. For superpowers-chrome: first verify it owns a separate automation browser/profile. Never hide or restart a shared/personal browser. Once ownership is proven, check `browser_mode` and use headless mode before navigate/click.
3. For Playwright MCP: never pass headed options.

### Phase 2 — During automation

- Prefer Playwright MCP for localhost (`http://127.0.0.1`, `http://localhost`).
- Prefer `human_type` only when bot-detection requires it; still stay headless.
- Capture evidence via screenshots in headless mode (works fine).

### Phase 3 — After session

- If you called `show_browser` for debugging, call `hide_browser` before ending the turn.

## Anti-patterns (BANNED)

- Calling `show_browser` "to help Jeffrey see progress"
- Starting Chrome headed on macOS because DISPLAY is available
- Using visible Chrome for Luma scrape / cookie injection without explicit approval
- `mcp__claude-in-chrome__*` for localhost testing (use Playwright MCP)
- **Calling `tell application "Google Chrome" to activate`** from any agent session — this steals keyboard focus from whatever the user is currently working in (verified 2026-07-18, user response: "work headless stop stealing my screen focus"). To add a tab to the user's existing Chrome without focus steal, use AppleScript `make new tab at end of tabs of front window with properties {URL:"..."}` — verified safe (front app stayed `cmux DEV` throughout the tab creation).
- **Driving the user's existing visible Chrome via CDP at all** — even without `activate`, CDP-driven navigation can scroll / push the user's cursor off their work. Default to a freshly-spawned headless browser (Aside CLI / Aside MCP / Playwright MCP) for any automation that needs Chrome behavior; only attach to the user's existing Chrome when the user explicitly says so in the current thread.
- **Stopping at "this page requires authentication, I can't read it"** — when the user asks you to read content behind a Google / Microsoft / vendor auth gate (Gemini share link, ChatGPT shared conversation, Google Doc with restricted access, Notion shared page, etc.), the wrong move is to declare the task blocked and ask the user to paste the content. The right move is `browserclaw cookies decrypt` (Chrome Default cookies for the target domain) + `browserclaw cookies inject` against headless Chromium to read the page *as the user*. This is exactly what "use /browser or /browserclaw headless next time without asking" means — reach for the auth-aware recipe on the first refusal, not after being told. Verified 2026-07-20 on Gemini share `Td7fA4pzuvMs`: 79 Google cookies decrypted from Chrome Default, injected into headless Chromium, full 169KB page text extracted in one shot. See `~/.hermes/skills/browserclaw/references/gemini-share-link-as-user.md` for the full recipe.

## Automatic-auth default (added 2026-07-30, browserclaw v2 design review)

The headless default extends one level deeper: **the operator should not have to open a browser at all for routine web work**. Login, session recovery, MFA, passkey, SSO, and device-confirmation must all be driven autonomously by Aside (or the equivalent browser runtime). Manual fallback — asking the operator to log in, paste a credential, or complete a CAPTCHA — is the exception, not the default, and only fires after bounded autonomous recovery is exhausted.

This applies regardless of which tool is driving the browser:

- For browserclaw: the v2 design `references/browserclaw-v2-design-2026-07-30.md` supersedes the prior "manual auth only" / "no auth bypass" ceiling.
- For ad-hoc Playwright / Aside work: do not propose "please open the browser and log in" as a first move — drive the login flow via Aside's password autofill + SSO + MFA handlers, and only escalate to the operator if the autonomous path genuinely cannot complete.
- Forcron / babysit jobs that need auth: route through the headless Aside CLI with the operator's existing profile (`aside account list` to confirm profile is wired) instead of scheduling an interactive browser session.

Operator verbatim (2026-07-30, Slack browserclaw design review): *"I want automatic auth and never wanna use my browser unless forced."*

## Verification

```bash
python3 -m pytest tests/test_browser_headless_policy.py -q
bash ~/.hermes/skills/browser-headless-default/scripts/validate-browser-mode.sh
```

## Output format

When reporting browser work, include: `browser_mode: headless` (or Playwright headless) in the status line.
