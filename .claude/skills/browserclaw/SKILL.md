---
name: browserclaw
description: Capture public browser traffic and generate API clients from non-sensitive HAR data. Use only with isolated headless Chromium and apply browser-control isolation rules first.
agent_scope: Any AI agent (Codex, Claude Code, Hermes, AO)
---

# browserclaw

Before using this CLI, follow [`browser-control`](../browser-control/SKILL.md)
for personal-browser isolation, browser selection, and the sole authorized
agent-owned cookie-transfer exception. The v2 design is design context only;
it does not override these runtime boundaries or authorize authentication
bypass.

## Safe use

`browserclaw capture`, `learn`, and `reverse` persist request/response traffic
to HAR files. Use them only against public, non-sensitive pages where no
credentials, cookies, authorization headers, private content, or secret-bearing
pages can enter the capture. Run with isolated Playwright Chromium in headless
mode. Do not use manual/visible capture, login flows, password filling, injected
bearer headers, token minting, or JavaScript auth/test-mode bypass flags.

If a page requires authentication, stop. Do not use browserclaw to read or
export personal browser state, scrape credentials, probe internal APIs with
copied cookies/headers/tokens, or capture an authenticated session. A user task
to access authenticated content does not itself authorize use of a personal
window, profile, or cookies. If the task explicitly authorizes transfer from
exactly one named agent-owned browser profile, use only the fail-closed,
private-temp lifecycle in browser-control; that transfer is for the isolated
browser context and does not permit direct API probing or HAR capture.

For OAuth or provider authentication, use the provider-supported flow in an
isolated agent-owned context. Never intercept or invoke `/usr/bin/open`, `open`,
`xdg-open`, or another system URL handler; never launch, activate, restart, or
kill a desktop browser or app to recover automation. The only exception is
starting Aside in background mode on an agent-owned profile (aside-browser-default § Background mode); if that
cannot be verified, use isolated headless Chromium.

## Public-page capture

```bash
browserclaw capture \
  --url https://docs.example.com/api \
  --output /tmp/public-api.har \
  --headless \
  --wait-after-load 5
```

Review the target and the resulting HAR before sharing or retaining it. HARs
can contain full request and response bodies; keep sensitive captures out of
them entirely. For public, non-sensitive data only, use `browserclaw infer`
to create an endpoint catalog and `browserclaw generate` to emit a client and
MCP definitions. Review generated clients before use.

## Precedence

The personal-browser isolation rules in `browser-control` and the no-auth-
bypass contract of the BrowserClaw v2 design supersede historical examples in
this skill's older copies, README files, and references. Those examples are
not authorization to log in, export credentials, broaden access, or bypass
provider/site authentication controls.
