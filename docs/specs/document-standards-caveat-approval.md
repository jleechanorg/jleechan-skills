# Document Standards caveat approval

## Outcome

Editors add discretionary reader-facing caveats, qualifiers, disclaimers, and
honesty qualifiers only after the user types `CAVEAT APPROVED` for the specific
addition. Installing this gate does not approve an addition.

## Non-goals

No social workflow migration, browser operation, model/provider change, or
relaxation of truth, safety/security, tool, permission, or failure-reporting rules.
No removal of author-supplied meaning or facts to create stronger claims.

## Acceptance

- The blanket protected class for honesty qualifiers is removed.
- The exact token gates each discretionary addition and restoration.
- A token in a gate-installation request, quotation, or agent message is not approval.
- Editors write direct accurate claims, omit unsupported assertions, and do not
  ask permission for imagined objections.
- Author intent, latest deletions, certainty, quantities, dates, scope, meaningful
  hyperlinks, and compact inline media are preserved.
- Reviewing LOC counts remains distinct from reviewing source code.
- Truthful blocked/failed status, contradictory evidence, required safety/security
  notices, and tool/permission compliance remain unconditional.
- Concise-writing and humanizer point to the single Document Standards owner.

## User stories

An author removes a defensive disclaimer. Previously a review could restore it
under blanket honesty protection; now it stays deleted unless that specific
addition receives the exact approval token.

An author supplies a personal schedule or describes reviewing LOC counts. The
editor preserves those statements without adding a measurement disclaimer or
claiming that the author read production code.

A test fails or evidence contradicts a claimed result. The agent reports the
failure and evidence directly without waiting for an editorial token.

## Proof plan

Compare baseline and candidate instructions; run existing dispatcher, contract,
portability, and installer checks; inspect the complete diff. Run fresh native
model scenarios for token mention versus approval, specific versus blanket
approval, author meaning, latest deletions, truthful failure, contradictory
evidence, and safety/security notices. Record unavailable proof as pending;
old material-qualifier prose checks do not establish this gate's behavior.

## Mock exemption

No application interface changes. The acceptance artifact is the instruction
text and resulting prose; browser screenshots add no proof for this scope.

## Risk

An editor could mistake required factual reporting for a discretionary addition
or strip source uncertainty. The explicit unconditional duties and preservation
of author-supplied meaning define that boundary.
