---
description: Control real websites and authenticated browser sessions, inspect pages, complete approved UI flows, or troubleshoot browser automation. Uses Aside in background (no-focus-steal) mode on an agent-owned profile for live and authenticated sites, isolated headless Chromium otherwise, and routes deterministic app testing to playwright-ui-testing.
type: skill
execution_mode: immediate
---

# /browser [task]

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/browser-control/SKILL.md` (or discover `browser-control/SKILL.md`) and execute the workflow for `$ARGUMENTS`. Use the cookie-transfer recipe only when the user has explicitly authorized access to the requested authenticated content.

Keep browser automation headless by default; use a visible browser only when the current request explicitly asks for one, in a separate task-owned profile.

Use the installed `playwright-ui-testing` skill only when the task is deterministic UI testing, CI, isolated profiles, traces, video, or multi-browser coverage.
