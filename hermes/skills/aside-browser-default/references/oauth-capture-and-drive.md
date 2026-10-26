# OAuth browser isolation

This reference replaces the historical capture-and-drive recipe. It is a
policy pointer, not an executable procedure. The old workflow intercepted the
system URL opener, exposed OAuth URLs in logs, and drove a real desktop browser;
do not execute or adapt it.

For OAuth, use the provider's supported authorization flow in an isolated,
agent-owned browser context. Do not invoke or wrap `/usr/bin/open`, `open`,
`xdg-open`, or another system URL handler; do not launch, activate, or drive a
personal or desktop browser; do not clear cached grants or extract tokens to
force a new flow. If the supported flow requires a human consent or MFA step,
stop at that step and report the blocker. A task that explicitly authorizes
transfer from one named agent-owned browser profile may use only the guarded
cookie-transfer lifecycle in
[`browser-control`](../../../../.claude/skills/browser-control/SKILL.md#authorized-credential-reuse-the-safe-cookie-copy-contract).
That exception does not permit internal API requests with copied browser
cookies, headers, or bearer tokens.

The shared personal-browser isolation policy and the current browser-control
workflow take precedence over dated examples or skill copies elsewhere. See
[`browser-control`](../../../../.claude/skills/browser-control/SKILL.md#personal-browser-isolation--required-for-every-route).
