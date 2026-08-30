---
description: Draft social-media posts for 9 platforms (LinkedIn, HN, Twitter, Reddit, Threads, Facebook, Instagram, Mastodon, Dev.to). Optionally stages in Aside browser with screenshots. Never publishes.
type: execution
execution_mode: deferred
---

# /social — Draft + Stage Social Posts

Loads `~/.claude/skills/social-poster/SKILL.md` first, which routes to the canonical Hermes social-poster skill. `/social` is cross-platform: it applies only to the sites selected by `--platforms`, with platform-specific checks layered on top.

## Usage

```
/social <intent> [--platforms=...] [--reddit-subs=...] [--link=...] [--image=...]
```

## Examples

```
/social announce jleechanclaw open-source release
/social draft a Show HN for jleechanclaw
/social draft a tweet thread about jleechanclaw's deploy pipeline
```

## Behavior

1. Read and execute `~/.claude/skills/social-poster/SKILL.md`.
2. That skill should resolve to `~/.hermes/skills/social-poster/SKILL.md` as the canonical workflow.
3. Follow the skill-defined draft + Aside staging flow for every selected site: verify actual field contents, carry the approved source/media assets, and use the site’s real compose controls rather than generic page controls.
4. Never click Publish, Post, Submit, Share, or an equivalent live action. `POST APPROVED` is not a publishing trigger for `/social`.
5. If staging is requested, verify the actual draft fields and capture evidence. Otherwise, return the draft files for the user to review or publish manually.

## Safety

- `/social` never invokes `post_approved.py`. Publishing is intentionally outside this command.
- Never treat a loaded compose form or login-wall screenshot as proof a draft was staged.
- Drafting works without Aside. Optional browser staging requires an active Aside browser bridge and authenticated site session; if unavailable, return the drafts without staging.
- Prefer canonical outbound links and explicit media assets over reposting LinkedIn shortlinks.
- Instagram may require a media-upload flow instead of text-only staging, especially when the intended creative is an image/screenshot plus an outbound video link. For those media posts, cross-share to Threads and Facebook by default unless the user opts out.
- Default mode is pure templating — no LLM call. Pass `--use-llm` to enable LLM refinement.