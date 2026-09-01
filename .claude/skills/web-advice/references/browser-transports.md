# Browser transports

Choose the runtime before choosing a browser transport.

| Runtime | Preferred transport order |
| --- | --- |
| Interactive chat app | App-owned browser, then Aside MCP, then Aside REPL |
| Coding CLI or Bash | Playwright with isolated strict-headless Chrome and fresh local cookie state, then a portable Playwright route, then headless CDP |

An app run must create a new vendor chat. A CLI/Bash run must not attach to an
existing GUI tab: unrelated conversation state invalidates review provenance.

Every route must prove vendor authentication, a writable composer, exact visible
attachment names, a submitted prompt, and a response that echoes the requested
revision and attachment names. Do not enter credentials, bypass a login or
CAPTCHA, or treat an upload call without visible chips as success.

For strict-headless Chrome, use the installed Chrome channel with `headless=True`
and a normal desktop user agent. Vendor upload controls are not interchangeable:
use a documented unique file input only where one exists, otherwise use the
vendor's visible upload menu and a file chooser.
