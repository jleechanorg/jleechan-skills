---
title: "Multi-profile cookie scan — historical reference"
type: reference
date: 2026-07-14
status: RETIRED — background only; the canonical lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md`.
---

# Multi-profile cookie scan — historical reference

> **Background reference only.** Do not execute historical multi-profile sweep snippets from this file. The canonical guarded lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md` (**Authorized credential reuse**). **Credential reuse requires explicit task authorization.**

This document records why older browserclaw workflows looked across several local browser profiles. Those workflows are retired because profile discovery and cookie sweeps can inspect personal browser state and can select the wrong session.

## Current authorized-source rule

- Use exactly one explicitly authorized, agent-owned source profile or cookie database for the requested task.
- Use quoted portable placeholders such as `"<agent-owned-source-db>"`, `"<agent-owned-output>"`, and `"<domain-filter>"`; resolve them only from task-scoped machine-local configuration.
- Follow the canonical browser-control lifecycle, including the matching browser/session family, private temporary files, cleanup, and fail-closed error handling.
- If that authorized source has no matching session or decryption is unsupported, report the blocker or use the provider-owned recovery path.
- Never inspect personal Chrome, Brave, Edge, Aside, or other desktop stores; never sweep profiles; never copy personal profiles; and never schedule polling, cron jobs, or relaunches to wait for cookies.

## Historical scope

The former multi-profile loop, hardcoded desktop paths, and profile-specific decrypt examples are intentionally omitted. This reference no longer provides an executable sweep recipe.

## References

- Canonical browser routing and credential lifecycle: `~/.claude/skills/browser-control/SKILL.md`.
- Auth-gated share-link background reference: `gemini-share-link-as-user.md`.
