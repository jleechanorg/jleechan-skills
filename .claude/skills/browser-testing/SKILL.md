---
name: browser-testing
description: "Use when testing localhost URLs or web UIs. PRIMARY: aside browser (CLI / aside-mcp). FALLBACK: mcp__playwright-mcp (headless); forbids mcp__claude-in-chrome__* (requires extension)."
---

# Browser testing — Aside PRIMARY, Playwright MCP fallback

Before choosing a tool, apply [browser-control's personal browser isolation contract](../browser-control/SKILL.md#personal-browser-isolation--required-for-every-route). Aside is preferred only when it can operate in the background without touching the main Chrome window; otherwise use isolated headless Playwright Chromium. A visible test request permits a separate automation window only.

**PRIMARY (2026-06-27):** Use the **Aside browser** CLI or `mcp__aside-mcp__*` for all browser testing. Verify Aside alive first via `aside account list` (expect `* u0 '<account-email>'  signed in  profiles: Profile 0`). Default invocations:

- `aside "Open http://localhost:8085 and screenshot the dashboard"` — NL agent, easy
- `aside repl "const p = await openTab('http://localhost:8085'); const s = await snapshot(p); console.log(s.tree)"` — deterministic
- `mcp__aside-mcp__*` — when the runtime exposes the MCP server as a tool

**FALLBACK:** Use `mcp__playwright-mcp` (headless) only when Aside is unavailable or Playwright-specific fixtures are required (trace viewer, `--isolated` profile mode, video recording). Never use `mcp__claude-in-chrome__*` — that requires a connected Chrome extension and will fail or block in headless/CI contexts.

**Reversible:** To switch back to Playwright MCP as the default, run `bash ~/.hermes/scripts/rollback-aside-default.sh`.