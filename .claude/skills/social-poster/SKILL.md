---
name: social-poster
description: Route draft, stage, and explicitly approved publishing workflows to the canonical Hermes social-poster skill.
version: 0.1.0
summary: Local shim for the canonical Hermes social-poster skill.
---

# Social Poster

This is the local Claude skill entrypoint for social-post drafting, staging, and explicitly approved publishing.

Canonical implementation:
- `~/.hermes/skills/social-poster/SKILL.md`

## Routing rule

When this skill is invoked:
1. Read and follow `~/.hermes/skills/social-poster/SKILL.md` as the source of truth.
2. Prefer the skill-defined workflow over re-specifying individual script calls in slash commands.
3. **Intent and approval:** draft/stage requests never publish. An explicit publish/crosspost request follows the canonical publishing workflow only after its mandatory `POST APPROVED` confirmation and platform allowlist. Requesting `/social`, logging in, or staging is not posting approval.
4. Treat current live browser state as higher-confidence evidence than old logs, stale session notes, or previous failed runs.

## Operational rules added from the 2026-07-11 Fable run

1. Verify the actual field contents after paste. A loaded compose form is not a staged draft.
2. Distinguish transport failure from browser-state failure:
   - MCP/CLI can be healthy while a specific tab/openTab flow is broken
   - existing signed-in tabs may still be usable even if a fresh openTab path is flaky
3. Before declaring a platform blocked, check for one-click auth continuations such as:
   - Google account chooser
   - Continue with Instagram
   - Continue as Jeffrey / existing-account OAuth buttons
4. For LinkedIn-source posts, extract and use the canonical outbound asset URL in drafts when possible instead of reposting LinkedIn shortlinks.
5. When the creative is already known, carry the asset explicitly through the workflow:
   - canonical source-post URL
   - direct video URL
   - exact screenshot path
   - platform notes on whether media upload is required or optional
6. When the user asks for both source and video links, include both in every platform draft. Use the full source text when platform limits allow; otherwise use a faithful summary plus both links.
7. For Instagram, prefer a real media-post workflow when a screenshot/image asset is part of the creative. Do not treat Instagram as caption-only if the intended post mirrors a LinkedIn image + video-link format.
8. For Instagram media posts, leave “Share to Threads” and “Share to Facebook” enabled by default unless the user explicitly opts out. Mention the cross-post state in the staging summary.
9. Do not trust screenshots of login walls or empty compose boxes as proof of staging.

For Twitter/X, follow the canonical **Twitter/X browser workflow** before generic
staging or auth recipes; it verifies identity, duplicates, media, limits, and results.

## Universal stage verification

For every selected platform, whether running inside Aside or from another local harness:

1. Drafting produces platform-specific files and works without Aside.
2. If browser staging is requested and Aside’s live browser bridge is available, populate the actual draft fields and capture evidence. Keep staging separate from the gated publishing phase.
3. Use named/semantic fields and verify the visible text. A composer, redirect, login screen, or unchanged form is not a staged draft.
4. If Aside/browser staging is unavailable, report the drafts as ready for manual use. Do not block drafting and do not substitute a fresh unauthenticated browser.

## Reddit staging supplement

This is a Reddit-only supplement to the universal staging flow:

1. Read the subreddit rules and choose a required post flair before staging. Use a context-appropriate flair such as `Discussion`; do not assume a flair is optional.
2. On old Reddit self-post forms, target named fields: `textarea[name="title"]` and `textarea[name="text"]`. Do not use generic `input` selectors, which can reach hidden fields or page-level search controls.
3. Verify the staged visible title, body, and selected flair. A submit form, search page, unchanged fields, or a page that merely loaded is **not staged**.
4. Exclude zero-self-promotion communities from default targets unless the user explicitly names them.

Do not configure PRAW, OAuth credentials, or a Reddit posting MCP inside `/social`. Keep credential setup separate from this workflow.

## Why this shim exists

- Keeps `~/.claude/commands/social.md` skill-first
- Gives Claude a stable local skill path
- Avoids command drift when the canonical Hermes skill evolves
