---
name: social-aside
description: Research, draft, edit, stage, and explicitly authorized publishing of social posts using Aside's runtime-provided browser and tools.
---

# Social Aside

Apply the [Social common editorial policy](../social/SKILL.md#common-editorial-policy)
without re-entering its runtime dispatcher. This package owns Aside operations;
Claude/Hermes continues through Social Poster. Keep local Claude masters
canonical; discovery projections should link to them rather than fork content.

## Scope and tools

Default to drafting for the requested destinations. Use current context to
resolve sources and accounts; do not silently expand a request into a campaign.
Staging populates a composer. Publishing sends live. Explicit current authority
covers only its identified outcome, content, account, and destinations. Preserve
required tool/policy approvals; no extra magic posting token is required.
Do not delete a published post as cleanup; follow the runtime's explicit
deletion authorization and confirmation rules.

Use only browser/tools supplied by the current Aside runtime. Read their current
interfaces before operating. Do not use legacy cookie extraction, publisher
scripts, private service endpoints, Hermes handoffs, or a fresh unauthenticated
browser. Do not invent a fixed helper, launcher, profile, or account requirement.
Resolve available paths and identities from runtime configuration. Coordinate a
single editor for an observed shared composer; an account is not reserved merely
because a note says so. A missing capability blocks its dependent operation,
not independent drafting.

## Workflow

1. Inspect the exact current draft/composer URL and author's latest edits.
   Back up title, body, links, media provenance, captions and order before edits.
   Use supplied source/PR images rather than a substitute or an old template.
2. Read current destination rules, permitted format, promotion and AI-writing
   restrictions, required flair and account eligibility. Historical lists do not
   establish eligibility. Before recommending or drafting for a subreddit,
   record the promotion-rule source/date and its allowed, conditional, prohibited
   or unverified disposition. Ambiguous or inaccessible rules do not establish
   permission to promote; do not publish promotion without established permission.
   Where AI writing is prohibited, provide private factual
   planning notes only, not paste-ready copy or a way to evade the restriction.
   Verify the signed-in identity before staging or publishing.
3. Draft for the selected audience. Verify public claims and linked sources,
   preserve voice and deletions, and use meaningful links at requested positions.
   Keep verification notes separate from public copy. When review is requested,
   review the exact revision and sources; report failed or unavailable reviewers
   honestly, without carrying an old approval onto revised content.
4. Save every exact draft and revision under `~/roadmap`, or the configured
   durable roadmap location. Reuse the campaign folder; otherwise use
   `social/YYYY-MM-DD-topic/`. Record title/body/captions, source URLs, intended
   account/destination, revision, media paths/provenance, composer URL and status.
   Keep full original media and exact staged composites there, or reference
   existing durable copies. Do not store credentials. Read saved files back.
5. For Instagram media posts, keep “Share to Threads” and “Share to Facebook”
   disabled unless each destination is explicitly selected for this request.
   Verify and report both controls before staging or publishing; selection
   alone is not publication approval. If their state cannot be verified, stop
   the dependent staging or publication.
   Stage only when requested. Verify actual visible field values, hyperlink
   elements and media positions. For Reddit read
   [Reddit editing](../social/references/reddit-editing.md) before mutation.
   Compare substantive paragraphs and links with the pre-edit backup; preserve
   unrelated user edits. Capture a screenshot and exact composer URL.
6. Save/status checks must preserve a working media composer. Report local draft,
   browser-staged, saved text, staged media, persisted media, and published state
   separately according to evidence. Never reload or close a media-bearing
   composer merely to test persistence. A successful upload is not saved bytes.
7. Publish only within explicit current scope. After uncertain submission, inspect
   account history or the existing permalink before any retry. Verify the live
   permalink's author, text, links and media before reporting publication.
   Stop dependent mutations when the outcome is uncertain; preserve the draft
   and report the exact unresolved action. Never use deletion as cleanup.

Return concise status, durable draft/media paths, screenshot plus exact composer
URL or verified permalink, and concrete blockers. Do not claim the browser is
foreground or visible to the user. Finish requested draft/stage work without
publishing; proceed with already-authorized steps without an extra permission
question.
