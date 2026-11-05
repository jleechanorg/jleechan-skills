---
description: Discover relevant Reddit communities and Reddit/X discussions per source post, then draft standalone posts or tailored replies. Other platforms require explicit selection; staging and publishing require their own authorization.
type: execution
execution_mode: deferred
---

# /social — Draft, Stage, or Approved Publish

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
3. Default to discovery + drafting for Reddit and Twitter/X. Exclude LinkedIn, Instagram, Facebook, and Meta Threads unless explicitly selected for this request. X threads are Twitter/X discussions, not Meta Threads. Stage only when requested; a draft request never auto-stages. For requested staging, verify actual field contents, carry the approved source/media assets, and use the site’s real compose controls rather than generic page controls.
4. Draft/stage requests never publish. For an explicit publish/crosspost request, verify the reviewed content, intended account, and selected platform allowlist. Do not demand a magic phrase; preserve any independently required tool/policy confirmation.
5. Verify staged fields and capture evidence. For draft-only requests, return draft files for review. For authorized publishing, verify the final permalink and visible content after the gated action.

## Safety

- Publishing follows verified user authorization; the legacy `POST APPROVED` script token is internal bookkeeping. `/social` invocation, login, and staging alone do not authorize publication.
- Never treat a loaded compose form or login-wall screenshot as proof a draft was staged.
- Drafting works without Aside. Optional browser staging requires an active Aside browser bridge and authenticated site session; if unavailable, return the drafts without staging.
- Prefer canonical outbound links and explicit media assets over reposting LinkedIn shortlinks.
- Instagram media flows require explicit opt-in. Keep Threads/Facebook cross-share disabled unless each destination is explicitly selected and publication is authorized.
- The local template CLI makes no LLM/provider calls and performs no discovery. Follow the canonical per-source research workflow before returning recommendations.
