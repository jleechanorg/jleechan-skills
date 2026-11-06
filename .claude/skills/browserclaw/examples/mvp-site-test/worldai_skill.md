# Retired BrowserClaw example

This historical example includes authenticated API access and credential-reuse instructions. It is retained only as a location marker and must not be executed or treated as current guidance.

For browser work, follow `../../SKILL.md` and `../../../browser-control/SKILL.md`. BrowserClaw capture is limited to public, non-sensitive traffic. An explicitly authorized transfer from exactly one named agent-owned browser profile must use the guarded private-temporary-file lifecycle in browser-control, navigate only in an isolated headless context, stop at any authentication challenge, and must never be used for direct API probing or bearer/header replay.
