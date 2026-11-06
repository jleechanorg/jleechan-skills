# Retired BrowserClaw v2 design reference

This dated design document is retained in Git history as historical context; its browser and authentication guidance is retired and is not an operational contract.

For current browser work, follow [`browser-control`](~/.claude/skills/browser-control/SKILL.md) and the current `browserclaw` skill. Use only an already authorized, isolated agent-owned browser context. Do not use personal browser state or automate or bypass login, consent, MFA, passkey, CAPTCHA, or device-confirmation requirements. If the provider requires human action, stop and report the blocker.
