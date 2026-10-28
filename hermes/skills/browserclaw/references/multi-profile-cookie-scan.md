# Retired BrowserClaw reference

This document contains historical procedures that use personal browser profiles or session material, replay cookies, inspect private mail, access internal APIs with copied credentials, or recover sessions through desktop browsers. Those procedures are retired and must not be executed.

For current browser work, follow `~/.claude/skills/browser-control/SKILL.md`. Cookie transfer is allowed only when the task explicitly authorizes exactly one named agent-owned source profile; use the guarded private-temporary-file lifecycle there, keep navigation in an isolated headless context, and stop if the authorized session is rejected or requests login, consent, MFA, CAPTCHA, or other user action. Cookie transfer never authorizes direct API probing, bearer/header replay, or another browser/profile fallback.

Credential reuse requires explicit task authorization. This retired recipe is not authorization to reuse credentials.
