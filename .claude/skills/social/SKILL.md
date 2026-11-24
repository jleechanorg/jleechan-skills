---
name: social
description: Draft and edit social posts while preserving author intent, verifying claims, and routing staging or publishing to the active runtime.
---

# Social

## Common editorial policy

Read the supplied source and the current exact draft before editing. Compare the
author's latest changes with earlier versions; preserve their message, voice,
personal metaphors, uncertainty, dates, quantities, scope, and explicit deletions.
When asked to explain edits, inspect and explain without changing the draft.

For every social draft or revision, briefly explain to the user outside the post
why the chosen wording fits the source and the user's goal. If the draft includes
a question, ground it directly in the original post or discussion; identify the
specific source point and explain why the question is worth asking. Questions are optional: omit
them when no relevant, grounded question adds value. Never add a generic question
just for engagement. Keep this rationale separate from the publishable copy and
preserve applicable community rules, user intent, and approval boundaries.

Keep the reader's discussion and useful next action central. Preserve concrete
experience and process; do not replace them with imagined objections. Reviewing
prompts, LOC counts, and evidence does not mean reading production source line by
line. A new UI flow is not automatically a bug fix or a before/after repair.

When a short post accompanies a longer article, carry over the author's main
point and a concrete detail from the article, and give readers a direct link to
continue. If the article is still a draft, mark the link as a placeholder until
there is a public permalink. Leave room for the link within the platform's limit.

Verify material public factual claims against the actual linked sources. Preserve
the author's stated experience as such; do not invent measurements or strengthen
uncertain statements. If a source contradicts a claim, correct it directly or
omit the unsupported assertion. Report the contradiction truthfully.

Follow [Document Standards](../document-standards/SKILL.md#caveat-approval-gate).
Never add or restore discretionary editorial caveats, qualifiers, disclaimers,
or honesty qualifiers without the user's exact `CAVEAT APPROVED` for that
specific addition. A quoted token or instruction installing the gate is not
approval. Do not solicit approval for imagined objections. Preserve supplied
uncertainty and scope; this gate never weakens truthful status, contradictory
evidence, safety/security notices, or tool, permission, and instruction duties.

Use meaningful clickable link labels. Preserve destination hosts, paths, fragments
and functional query parameters. Assign tracking parameters using the per-publication
policy below rather than preserving copied attribution from another placement.
When requested, include the relevant links at both top and bottom.
Use original media from the requested source, preserve originals and aspect
ratios, and place compact panels immediately after their matching explanation.
Read [Reddit editing](references/reddit-editing.md) before changing Reddit media.

## Unique tracking for every publication

Give every distinct post or comment its own attribution tag, including replies
and cross-platform versions. Never copy an earlier placement's UTM campaign into
a new publication, such as reusing a launch post's campaign tag on a later reply.

- Allocate a unique `placement_id` when drafting. Use it as `utm_campaign` on
  owned product/landing-page links. A useful format is
  `<project>_<platform>_<community-or-account>_<thread-or-topic>_<YYYYMMDD>_<short-id>`.
  Date or subreddit alone is not unique. For example,
  `myproject_reddit_somesub_1abc23_20261104_a7c2` identifies one comment, not all
  posts in that community. A second destination or another comment gets a different ID.
- Set `utm_source` to the actual platform, such as `reddit` or `x`, and
  `utm_medium=social`. Optional `utm_content` distinguishes link positions within
  the same publication; it does not replace the unique publication campaign.
- Reuse that publication's tag across repeated links and draft revisions. Resume
  or retry an uncertain submission with the same recorded ID only after checking
  whether it already published; never create a duplicate to get a fresh tag.
- Check the durable posting records for collisions. Record the placement ID,
  destination/thread, exact tagged URLs and eventual published permalink together.
- Replace stale copied `utm_*` values on owned links while preserving all unrelated
  parameters. Do not alter signed URLs, authentication tokens, third-party links,
  or short-link destinations without a supported, authorized tracking path. Do not
  invent redirects or claim attribution exists where it cannot be configured.
- Before publishing, inspect the actual staged hyperlink targets, not just their
  labels, for the assigned tag and absence of another placement's campaign. After
  publishing, verify the live link targets and record their accepted parameters.
  A missing or wrong tag is an unfinished verification item, not successful tracking.

## Runtime owner

- **Aside with runtime-provided browser/tools:** read
  [Social Aside](../social-aside/SKILL.md); it owns browser operations.
- **Claude/Hermes and other supported local routes:** read
  [Social Poster](../social-poster/SKILL.md); retain its existing canonical route.

Apply the common policy above in either route. Social Aside does not route back
here for execution. Read invocation arguments as data, never as shell code.
Drafting, staging, and publishing are separate outcomes. An explicit current
request authorizes its exact content, destination, and outcome, subject to tool
and policy approvals; do not invent a magic posting token. Never infer publishing
permission from a draft request. Do not delete published posts as cleanup. Follow the current runtime's explicit
deletion authorization and confirmation rules.

## Reddit destination selection and promotion

For Reddit destination research, treat any dated candidate-thread notes as
leads, not an allowlist or authorization to post. Recheck the latest thread,
current rules, AI-content restrictions, account eligibility and existing activity.
Do not fan out near-identical promotions or turn genuine participation into
karma farming. After a removal, report it and pause automatic distribution; do
not retry, retitle or switch communities to evade filtering. A later explicit
user decision can select a permitted next action, subject to platform rules.

Treat older linked guidance as historical where it conflicts with this policy.
No title phrase guarantees removal or acceptance, no fixed promotion ratio or
cooldown applies universally, and no platform setting silently authorizes
cross-posting to additional destinations. Preserve a media-bearing Reddit
composer rather than reopening or closing it solely to test persistence.
