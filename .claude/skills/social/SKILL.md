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

Keep the reader's discussion and useful next action central. Preserve concrete
experience and process; do not replace them with imagined objections. Reviewing
prompts, LOC counts, and evidence does not mean reading production source line by
line. A new UI flow is not automatically a bug fix or a before/after repair.

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

Use meaningful clickable link labels. Preserve exact destinations and tracking
parameters; when requested, include the relevant links at both top and bottom.
Use original media from the requested source, preserve originals and aspect
ratios, and place compact panels immediately after their matching explanation.
Read [Reddit editing](references/reddit-editing.md) before changing Reddit media.

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
