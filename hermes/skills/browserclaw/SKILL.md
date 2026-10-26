---
name: browserclaw
description: Capture public, non-sensitive browser traffic for API-client generation. Authenticated browser work must follow the canonical browser-control isolation and cookie-transfer contract.
agent_scope: Any AI agent (Codex, Claude Code, Hermes, AO)
---

# browserclaw

Before any browser or authenticated-content task, apply `~/.claude/skills/browser-control/SKILL.md` § Personal browser isolation. The default is isolated headless Chromium. Never inspect, copy, attach to, launch against, or reuse a personal browser profile, cookies, login, or desktop window. Never launch, activate, restart, or kill a desktop browser or app as a recovery step.

## Public traffic capture

Use `browserclaw` capture/infer/generate only for public, non-sensitive pages in an isolated task-owned context. Do not capture authenticated pages or session-bearing traffic. Exclude credentials, authorization headers, cookies, private content, and session-bearing HARs from output, logs, generated clients, and evidence. Do not use capture as a way to extract a token from browser state.

## Explicitly authorized agent-owned cookie transfer

Cookie transfer is allowed only when the task explicitly authorizes transfer from exactly one named agent-owned source profile. Follow the guarded lifecycle in `~/.claude/skills/browser-control/SKILL.md`; use a private temporary destination, preserve the source, restrict to the task's domain, and clean up the temporary cookie material after use. Keep browser navigation in the isolated task-owned headless context. If the authorized session is rejected or requires sign-in, consent, MFA, CAPTCHA, or other user action, stop and report the blocker. Do not switch profiles, scan other stores, relaunch a browser, or try another auth path.

Cookie transfer does not authorize direct requests to internal GraphQL/REST endpoints with copied cookies, headers, or bearer tokens; API probing; credential-bearing HAR capture; or bypassing a browser/provider auth gate.

## Retired recipes

Historical references in this directory that instruct personal-profile scans, CDP cookie extraction, cookie replay across portals, credential-bearing HAR capture, direct API access using copied session material, or desktop-browser recovery are retired and must not be executed. In particular, follow no older `gemini-share-link-*`, `direct-graphql-*`, `cdp-decrypt-*`, `multi-profile-cookie-scan`, or `multi-portal-cookie-replay` instructions. Use the browser-control contract above.
