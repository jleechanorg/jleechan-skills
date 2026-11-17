# Independent final approval

## Source votes when external lanes are blocked

Keep the selected route's quorum, reviewer-class caps, and all stronger
repository, human, external-only and specialist requirements. A route already
eligible for direct static review needs no external-attempt exception.
Otherwise, at most one eligible cold native static source vote may fill an
open source seat only after the authorized external lanes are genuinely
unavailable. Use [advice](../advice/SKILL.md) for eligibility and ordering and
[static-review](../static-review/SKILL.md) for cold full-coverage review. Do
not count the driver, a repeated instance of an already-counted seat, a
partial or stale vote, or a review that reached a blocking finding. Findings remain review evidence, even when the vote does not count.

Before substitution, record every applicable external lane in the existing
ledger, with original attempt/probe time, scope, outcome and share-safe receipt,
or a specific, substantiated reason why it could not be attempted. State
quota/reset, transport failure, authorization boundary or deadline separately.
A viable unattempted or still-running seat is not blocked. A known reset
within the applicable allowed wait is not exhaustion. Lack of approvals,
budget or alternate seats cannot waive a quorum or stricter gate. Fix competent
blocking findings; do not relabel a negative verdict as unavailable. Publish
the complete share-safe attempt record both in the PR and to the user before
claiming the substitution. Do not disclose credentials or private identities.

Insufficient independent votes after an eligible substitution still mean
WITHHELD. The [self-review for progress](review-recovery.md#self-review-fallback-when-independent-votes-cannot-be-obtained)
is distinct and never an independent vote or final approval.

## Closing reviewer and stamp

After the other closing gates pass, assign a separate, fresh, packet-only
adversarial [static reviewer](../static-review/SKILL.md). It cannot be the
author, driver, any counted source reviewer, or the producer or counted
reviewer of applicable evidence/visual approval. The final reviewer is not
another source vote and does not replace an existing independent visual seat.
Reserve it within the candidate's active round and applicable assignment and round budgets; do not close the round merely because earlier seats returned. Expose an
insufficient budget as a blocker, not an implicit extra seat. Use the existing
lifecycle attempt deadline, or the user's narrower limit.

Follow the [static closing access contract](../static-review/SKILL.md#closing-review-boundary). Use its read-only preamble, the unchanged versioned [final reviewer prompt](final-approval-prompt.md) and a separate structured packet. Record its SHA256 and the attributable
review invocation/account binding. Reviewers are read-only and must derive the
verdict, not adopt the driver's. They author the exact receipt through a trusted
reviewer channel. The driver may relay the unchanged, verifiably attributable
receipt into the PR ledger if the reviewer cannot publish it, but cannot stamp
on the reviewer's behalf. A negative stamp requires a new qualified cold review
after fixes; a same-seat addendum can reaffirm or withdraw, not flip it to PASS.

Bind the stamp to the repo and PR, full base and head, effective diff digest,
applicable governing route and complete counted source, specialist, visual,
evidence and CI gate snapshot, goal/spec digest, claim-bearing PR-body digest,
evidence/media identities and hashes, and the external-lane ledger if used.
Freeze substantive PR-body prose, non-closing obligation records and evidence
before review. The frozen ledger must link the candidate's authoritative
[closeout task record](review-records.md#final-closeout-record), which tracks
the live closing obligation and same-candidate CI rerun events without rewriting
frozen claims. Compute the UTF-8 body digest by removing only the following complete blocks, including
their marker lines, when present:
- The exact current receipt between `<!-- pr-final-stamp:begin -->` and
  `<!-- pr-final-stamp:end -->`. The receipt is verified separately.
- The generated final-stage status between `<!-- pr-final-stage:begin -->` and
  `<!-- pr-final-stage:end -->`. The block contains only one line,
  `Final status: WITHHELD` or `Final status: FINAL_READY`. Reject other content.

Markers must each occupy a whole line. Duplicate, nested or unmatched markers
invalidate the projection. Title and labels are separate from body bytes.
Before freeze, write substantive Stage 5 body prose with the owner and the
remaining action as a closing checkpoint, not a second live status. Any
change to the covered prose, ledger or evidence requires fresh applicable final
review. Any PR-body update to publish or withdraw readiness or its receipt
must use a conditional edit, true block-level update, or verified exclusive
write ownership until readback; an unguarded whole-body replacement is not
safe even with post-write verification. If none is available, preserve the
receipt in the linked task history and keep the gate open. Publish the
unchanged attributed receipt with generated status WITHHELD. Check the
authoritative tuple before writing FINAL_READY: exact
receipt and reviewer attribution, head/base, effective diff, spec and rendered
PR claims, governing requirements, eligible votes/findings, evidence, live
inline media and live required checks. Use an atomic conditional write when
supported; update only generated status and applicable title/labels. Then
read back the full authoritative tuple, the closeout task record and all
written presentation surfaces again. Until that post-write readback agrees,
do not report or act on readiness. If drift or inability to verify is detected,
withdraw the generated readiness for that attempt only, without overwriting
newer unrelated changes, and verify the repair. If repair cannot be verified,
report the presentation as stale or uncertain and keep the gate blocked.

Head or material base, claim, governing route, evidence, prompt or receipts
changes, a withdrawn vote, a blocking finding, or a failing required check
invalidate readiness. A successful rerun of the same required check at the
unchanged candidate can retain the stamp only if the required check set and
all results still pass; append the new event in the linked closeout task record.
A pending, failed or missing required check prevents readiness.

Applicable UI proof must be inspected directly in the actual rendered media,
and each image or playable video that the selected route requires must be
verified inline in the live PR body and traceable to the reviewed evidence.
A still-only route does not gain a video requirement. Preserve the separate
[visual verification](../visual-verification/SKILL.md) obligations. Bare links,
unreadable assets and author claims are not enough. A route-authorized visual
exemption is recorded with its reason; do not manufacture media.

The stamp is the last technical gate, not merge authorization. For a PR that
introduces or changes this policy, run the candidate workflow in shadow from
the pinned source read-only, without changing PR or repository state, but enforce the already-governing sensitive-review route independently in parallel. Use the stricter result. This policy cannot grant authority for its
own adoption.
