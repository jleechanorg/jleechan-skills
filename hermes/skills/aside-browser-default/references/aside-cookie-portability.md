---
title: "Aside cookie portability — historical reference"
type: reference
date: 2026-07-22
status: RETIRED — background only; the canonical lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md`.
---

# Aside cookie portability — historical reference

> **Background reference only.** Do not execute historical cookie-sweep or cross-browser transfer snippets from this file. The canonical guarded lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md` (**Authorized credential reuse**). **Credential reuse requires explicit task authorization.**

This document records why a session in an authorized Aside profile may differ from a session in another browser. It is retained for provenance only; it does not authorize inspection of personal browser state or provide a cookie-transfer recipe.

## Current authorized-source rule

- Use the already signed-in Aside session through the Aside contract when it is available and authorized for the task.
- If a headless fallback is required and explicitly authorized, use exactly one authorized, agent-owned source profile or cookie database and the matching browser/session family.
- Use quoted portable placeholders such as `"<agent-owned-source-db>"`, `"<agent-owned-output>"`, and `"<domain-filter>"`; resolve them only from task-scoped machine-local configuration.
- Follow the canonical browser-control lifecycle for private temporary files, cleanup, and fail-closed errors.
- If the authorized source has no matching session or decryption is unsupported, report the blocker or use provider-owned recovery.

## Retired portability guidance

The former instructions to sweep every browser database, copy cookies between browsers, call protected APIs with extracted cookie values, or create a new login solely to populate a database are retired. Do not inspect personal Chrome, Brave, Edge, Aside, or other desktop stores; do not sweep profiles; and do not schedule polling, cron jobs, or relaunches.

## References

- Canonical browser routing and credential lifecycle: `~/.claude/skills/browser-control/SKILL.md`.
- Aside is a headed GUI browser; use its separately authorized agent-owned session through the Aside skill, or use the canonical isolated headless fallback when permitted.
