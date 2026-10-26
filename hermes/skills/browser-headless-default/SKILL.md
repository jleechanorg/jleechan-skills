---
name: browser-headless-default
description: "Enforce isolated browser automation for Hermes — Playwright MCP and superpowers-chrome. Use when opening browsers, scraping, UI tests, localhost verification, or any chrome_use_browser / Playwright call. Keep Chromium headless by default; permit headed mode only for an explicit current-thread request in a separate verified task-owned profile."
when_to_use: Browser automation, scraping, screenshots, localhost UI checks, Luma/cookie flows, /browser command
allowed-tools: mcp__playwright-mcp, mcp__plugin-superpowers-chrome__chrome_use_browser
context: hermes
---

# Browser Headless Default

## Contract

Apply the personal browser isolation contract in `~/.claude/skills/browser-control/SKILL.md` before every browser action. Personal desktop browsers, profiles, cookies, and login state are off-limits. Keep Chromium headless by default. A current-thread explicit request for visible automation permits only a separate, verified task-owned browser process/profile/context; never use the personal/default browser or a bare system/default-browser launch.

**Headless by default.** Do not open a desktop browser window for routine work or as spontaneous recovery.

**Browser default:** isolated headless Chromium through Playwright MCP or another task-owned isolated runtime. Aside is an optional existing background context only when its agent ownership is verified; do not launch or activate the Aside app to make it available.

| Tool | Default | Visible-mode boundary |
|------|---------|--------------------------------------|
| **Playwright MCP** | **DEFAULT**, isolated headless | headed unless explicitly requested in the current thread and isolated in a separate task-owned profile/context |
| **Aside CLI / `aside-mcp`** | optional only when verified agent-owned and background | launching/activating app; using personal browser state |
| **superpowers-chrome** (`chrome_use_browser`) | fallback in isolated headless mode | headed unless explicitly requested in the current thread and isolated in a separate task-owned profile/context |
| **claude-in-chrome / GUI Chrome** | do not use for localhost | driving a visible desktop browser for automation |

Only an explicit current-thread request authorizes visible mode, and only in a separate, verified task-owned browser/profile. This never authorizes the personal/default browser or a bare system/default-browser launch.

## Phases

### Phase 1 — Before any browser action

1. Run `bash ~/.hermes/skills/browser-headless-default/scripts/validate-browser-mode.sh` when unsure.
2. For superpowers-chrome: first verify it owns a separate automation browser/profile. Never hide or restart a shared/personal browser. Once ownership is proven, check `browser_mode` and use headless mode before navigate/click.
3. For Playwright MCP: use headless by default. If visible mode was explicitly requested in the current thread, verify the separate task-owned browser/profile before using headed options. If isolation cannot be verified, report the blocker.

### Phase 2 — During automation

- Prefer Playwright MCP for localhost (`http://127.0.0.1`, `http://localhost`).
- Prefer `human_type` only when bot-detection requires it; use headless by default and follow the explicit visible-mode boundary above.
- Capture evidence via screenshots in headless mode (works fine).

### Phase 3 — After session

- Close only exact task-owned tabs and contexts created for the task.

## Anti-patterns (BANNED)

- Calling `show_browser` without an explicit current-thread request and verified separate task-owned browser/profile
- Starting a personal/default Chrome headed on macOS because DISPLAY is available
- Using a personal/default visible Chrome for scraping or cookie injection.
- `mcp__claude-in-chrome__*` for localhost testing (use Playwright MCP)
- **Using AppleScript or another desktop automation API to create tabs in the user's personal Chrome** — this can touch the user's window, tabs, or session. Use the browser-control contract and an agent-owned browser/profile for every executable recipe.
- **Driving a personal/default visible desktop browser via CDP** — use isolated headless Chromium by default; when visible mode is explicitly requested in the current thread, use only a separate, verified task-owned browser/profile. Aside CLI / Aside MCP remain limited to an already-running, verified agent-owned background context.
- **Treating authentication as a reason to use a headed or personal browser.** Continue only via a provider-supported flow in an already authorized isolated context. A separately explicit one-agent-owned-source cookie transfer is governed by browser-control and cannot bypass login, consent, MFA, or device confirmation.

## Automatic-auth default (added 2026-07-30, browserclaw v2 design review)

For routine web work, prefer provider-supported authentication and session recovery in an already authorized isolated agent-owned context. Do not attempt to automate or bypass human consent, MFA, passkey approval, SSO approval, or device confirmation. Stop and report when the provider requires one of these human actions; do not ask for or capture passwords, tokens, or other secrets, and do not use a personal browser. An explicit current-thread request for visible automation still permits only a separate, verified task-owned browser/profile, subject to these provider requirements.

This applies regardless of which tool is driving the browser:

- The browserclaw v2 design is design context only. It does not override the no-personal-browser, no credential capture, no bearer injection, or no auth-bypass rules in browser-control.
- For ad-hoc browser work, use only an already authorized isolated agent-owned context and the provider's supported authentication flow. Do not fill passwords, capture credentials, bypass authentication, or open/activate a desktop browser as an autonomous recovery step. If human consent, MFA, passkey approval, SSO approval, or device confirmation is required, stop and report that requirement.
- For cron or babysit jobs that need auth: use an explicitly authorized agent-owned profile through the browser-control contract; do not schedule recurring cookie polling or relaunches against a personal profile.

Operator verbatim (2026-07-30, Slack browserclaw design review): *"I want automatic auth and never wanna use my browser unless forced."*

## Verification

```bash
python3 -m pytest tests/test_browser_headless_policy.py -q
bash ~/.hermes/skills/browser-headless-default/scripts/validate-browser-mode.sh
```

## Output format

When reporting browser work, include: `browser_mode: headless` (or Playwright headless) in the status line.
