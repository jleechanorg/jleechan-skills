---
name: browser-testing
description: "Use when testing localhost URLs or web UIs. Default: isolated headless Playwright Chromium. Aside only in background mode on an agent-owned profile; forbids personal browser and desktop changes."
---

# Browser testing — isolated headless default

Before choosing a tool, apply [browser-control's personal browser isolation contract](../browser-control/SKILL.md#personal-browser-isolation--required-for-every-route). Use isolated headless Playwright Chromium by default. Aside is usable in background mode on an agent-owned profile (aside-browser-default § Background mode). A visible test request does not permit a personal browser or app activation.

**Aside (conditional):** Use the **Aside browser** CLI or `mcp__aside-mcp__*` only in background mode on an agent-owned profile ([aside-browser-default § Background mode](../aside-browser-default/SKILL.md#background-mode)); never activate it. Default testing remains isolated headless Playwright:

- `aside --account <agent-account> "Open http://localhost:8085 and screenshot the dashboard"` — NL agent, easy
- `aside repl --account <agent-account> "const p = await openTab('http://localhost:8085'); const s = await snapshot(p); console.log(s.tree)"` — deterministic
- `mcp__aside-mcp__*` — when the runtime exposes the MCP server as a tool

Use `mcp__playwright-mcp` (headless) for localhost and isolated browser testing, including trace/video needs. Never use `mcp__claude-in-chrome__*` — that requires a connected Chrome extension and may touch the user's personal browser.

Do not use desktop-wide browser-default changes, rollback scripts, or other machine-wide browser configuration as part of a test task.
