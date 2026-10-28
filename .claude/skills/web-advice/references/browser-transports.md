# Browser transports

Choose the runtime before choosing a browser transport.

| Runtime | Preferred transport order |
| --- | --- |
| Interactive chat app | App browser only in a separate task-owned context; Aside in background mode on an agent-owned profile (aside-browser-default § Background mode) |
| Coding CLI or Bash | Aside in background mode on an agent-owned profile for logged-in reviewer sites; isolated headless Chromium/Playwright otherwise |

An app run must create a new vendor chat. A CLI/Bash run must not attach to an
existing GUI tab: unrelated conversation state invalidates review provenance.
Never attach to personal/default Chrome or use its profile or cookies. Cookie
transfer is allowed only when the current task explicitly authorizes exactly
one named agent-owned source; follow the guarded lifecycle in
`../../browser-control/SKILL.md`. Headless CDP is permitted only for an isolated,
task-owned browser process.

Every route must prove vendor authentication, a writable composer, exact visible
attachment names, a submitted prompt, and a response that echoes the requested
revision and attachment names. Do not enter credentials, bypass a login or
CAPTCHA, or treat an upload call without visible chips as success.

For strict-headless browser sessions, follow
[`browser-control`](../../browser-control/SKILL.md): prefer its bundled
Playwright Chromium with `headless=True` and a normal desktop user agent. Dot's
live-profile transport is a specific exception; follow [`dot`](../../dot/SKILL.md)
and do not generalize its installed-Chrome channel to other browser work. Vendor
upload controls are not interchangeable: use a documented unique file input
only where one exists, otherwise use the vendor's visible upload menu and a file
chooser.
