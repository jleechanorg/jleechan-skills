---
name: static-review
description: Use for independent code, advice or static revision review; owns cold prompts, complete source coverage, access-mode preambles and receipts. Evidence-only review follows evidence-review.
---

# /static-review — cold, complete-source review

This skill owns reviewer input and coverage. [advice](../advice/SKILL.md) owns
selection, quorum, identity deduplication, deadlines and the access-mode table;
pr-lifecycle owns applicability and publication.

## Scope

Evidence-only /er follows [evidence-review](../evidence-review/SKILL.md) and
[evidence-standards](../evidence-standards/SKILL.md). Derive its claim map from
the complete diff and inspect claim-relevant source and artifacts. Do not impose
this full-code contract on evidence-only work or count an evidence verdict as a
source/advice vote. Separately requested source correctness uses this contract.

Each source approver reads the complete pinned diff and every changed path at
both revisions, or verifies absence. Include binary, mode, symlink, submodule
and LFS payloads. Verify unchanged spans before reusing a fully read version;
changed hunks with small context do not establish full-file coverage. Missing
or unretrievable required content means WITHHELD; recover truncated tool outputs
with narrower ranges within the fixed attempt deadline (600s for static-review §4;
1800s for advice §3; no timer reset) before concluding. Never combine
partial reviewers into one complete vote.

## 1. Cold input and access mode

Start a fresh reviewer context without parent history, findings, question,
summary or framing. The orchestrator keeps the user's question and answers it
from the findings. Send exactly one channel preamble below plus one filled
template. Fill only fields declared by advice §4 for that access mode.

Prefer read-only GitHub/API or an existing checkout when it supplies complete
pinned objects. Use an export, saved revision packet or isolated clone when
needed for complete access or isolation; a review does not require a new copy
merely because it is independent. Advice §4 is the sole mode/field table.

A revision verdict binds the verified head, comparison base and declared scope.
A document verdict binds only the named documents and bundle hash. A hash
establishes integrity, not immutable storage or correct contents.
An independent source/document verdict does not wait for prior approval or a
completed review; report readiness, quorum and evidence gaps separately.

## 2. Templates

Shared revision template for clone, export, read-only and remote modes:

```text
Review <PR URL> at head <SHA> (base <BASE SHA>). Assess the changed claims under
the /prw stages; prior approval or a completed review is not a prerequisite. Read
the complete base-to-head diff and full
content of every changed path at both revisions, or verify its absence, including
binary, mode, symlink, submodule and LFS payloads. Retrieve via bounded per-file or
range requests; if tool output truncates, recover remaining content with narrower
ranges within the fixed attempt deadline (600s for static-review §4; 1800s for advice §3;
no timer reset). The model must directly read all content (fetching bytes into a
script variable or reading only a required-content subset is not coverage). If required content is missing
or cannot be retrieved completely by the deadline, report incomplete COVERAGE and
withhold.
Report P0/P1/P2 with file:line and MODEL: for the reviewer's actual
runtime/model when exposed, or `unreported` when hidden. Never name the
reviewed system or scope as the model. Add COVERAGE: naming all files and the diff read. Approve source only with
no P0 and full coverage; P1/P2 are nonblocking. Report separate readiness/evidence
gaps without presenting this source vote as quorum or merge authority. End with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Revision packet template for web-provider seats:

```text
Review the attached change packet for <PR URL> at head <SHA> (base <BASE SHA>),
bundle sha256:<BUNDLE HASH>. Read its complete diff and full changed-path content
at both revisions, or verified absence, including special-object payloads.
Assess the changed claims under /prw; prior approval or a completed review is not
a prerequisite. Retrieve via bounded per-file or range requests; if tool output
truncates, recover remaining content with narrower ranges within the fixed attempt
deadline (600s for static-review §4; 1800s for advice §3; no timer reset). The
model must directly read all content (fetching bytes into a script variable or
reading only a required-content subset is not coverage). If required content is missing, unreadable or
cannot be retrieved completely by the deadline, report incomplete COVERAGE and
withhold. Report P0/P1/P2 with file:line and MODEL: for the reviewer's actual
runtime/model when exposed, or `unreported` when hidden. Never name the
reviewed system or scope as the model. Add COVERAGE: naming every file and diff actually read. Approve source only with
no P0 and full coverage; P1/P2 are nonblocking. Keep readiness, quorum and merge
authority separate. End with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Saved-material template for named documents or a revision-bound packet:

```text
Review the saved material in <PACKET PATH>, bundle sha256:<BUNDLE HASH>,
for <REVIEW TARGET>. Use the full 40-hex head SHA only when the PR URL,
base/head SHAs and complete revision-bound coverage are verified. A complete
unbound packet uses exactly `DOCUMENTS sha256:<BUNDLE HASH>` and approves only
its declared bundle. Incomplete claimed revision binding means WITHHELD; never
use an abbreviated SHA or mutable HEAD. Read only the complete declared files and evidence; prior
approval or a completed review is not a prerequisite. If the
packet claims revision binding, also read its complete base-to-head diff and
changed-path content at both revisions, including special objects or verified
absence. Retrieve via bounded per-file or range requests; if tool output
truncates, recover remaining content with narrower ranges within the fixed attempt
deadline (600s for static-review §4; 1800s for advice §3; no timer reset). The
model must directly read all content (fetching bytes into a script variable or
reading only a required-content subset is not coverage). If required content is missing or cannot be
retrieved completely by the deadline, report incomplete COVERAGE and WITHHELD.
Report P0/P1/P2 with file:line and MODEL: for the reviewer's actual
runtime/model when exposed, or `unreported` when hidden. Never name the reviewed
system or scope as the model. Add COVERAGE: naming the files and diff actually read.
Approve only with no P0 and full coverage;
P1/P2 are nonblocking. Bind revision approval only to verified revision metadata;
otherwise approve only the named documents, never code or HEAD. End with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <REVIEW TARGET> (WITHHELD with a reason).
```

## 3. Channel preambles

Every CLI and native static seat receives its access-mode preamble followed by
the selected template. Record the complete actual prompt and SHA256 privately.

Clone preamble:

```text
Work only in the isolated clone at <SCRATCH PATH>. Do not clone, fetch, check out
another commit, add a remote or make another copy. Never work in the original
checkout or donor. Leave this clone for the orchestrator's post-return checks
and cleanup. Remain read-only: do not modify source, evidence, refs, config or
hooks, and do not post, push or change PR metadata. Never print credentials.
Return your independent review as final output.
```

Export preamble:

```text
Work only in the exported tree at <SCRATCH PATH>. It has no .git. Read base.diff,
the complete pinned diff, and its full base/head snapshots and object manifest.
Do not clone, fetch, create a repository or make another copy. Obtain any missing
required objects only through read-only pinned GitHub/API access, or withhold.
Do not modify source, evidence, checkouts, refs, config or hooks; do not post,
push or change PR metadata. Never print credentials. Leave the export for the
orchestrator's verification and cleanup. Return your independent review.
```

Read-only preamble:

```text
Review read-only through GitHub/API or an existing checkout. Resolve mutable PR
references to the requested SHA and retrieve complete pinned source and evidence.
Do not clone, export, fetch, switch branches or modify any checkout, refs, config
or hooks. Do not post, push or change PR metadata. Never print credentials.
Return your independent review as final output.
```

Saved-material preamble:

```text
Read only the named saved files and evidence in the packet, checking their
recorded hashes and revision binding. Adjacent runtime, attempt or sibling-review
logs/files are out of scope unless explicitly named. Do not modify source, evidence, checkouts,
refs, config or hooks; do not post, push or change PR metadata. Never print
credentials. Return your independent review as final output.
```

Coordinator asks to Dot or Hermes use: the sender line required by the transport
owner, configured mentions, `Advice vote requested.`, then the remote preamble
and shared revision template. Record sender/mentions in the receipt. This is a
vote request, not a new task handoff: the PR URL and SHA already bind it.

Remote preamble:

```text
Review only. Use pinned GitHub/API objects or a checkout you already have; do not
make a new clone or switch branches. Fetch only missing immutable objects when
necessary, without changing branch refs or working-tree contents. Do not
implement fixes, mutate evidence/config/hooks, post, push, change PR metadata
or delegate the review to another account. Return findings in this conversation.
```

Web seats use the web preamble followed by the revision packet template, or by
the saved-material preamble and template for documents. Upload complete files;
never send a private local path as a provider field. For web documents,
`<PACKET PATH>` is `the attached files`.

```text
[web advice] Advice vote at <SUBJECT>
Title this conversation "[web advice] Advice vote at <SUBJECT>".
Advice vote requested.
```

Set `<SUBJECT>` to the revision SHA or `DOCUMENTS sha256:<BUNDLE HASH>`.

## 4. Identity and deadlines

Advice owns required count and reviewer-class caps. Native static subagents
collectively supply at most one advice vote, even when their models differ.
Identity eligibility never creates an extra vote or combines partial coverage.

Report the actual model from reliable runtime metadata when exposed. A CLI seat
without a verified actual model is unavailable. Outside interfaces may leave the
underlying runtime model unreported; never invent a SKU. The orchestrator still
verifies the configured account/session and independence privately. Missing
public fields are not evidence of an unverified account. Dot is its own
CLI/model identity under the at-most-one-Dot cap; aliases of one account remain
one account. Static identity is its type, harness and actual model; preserve
any stronger user/repository requirement.

Static attempts have a 600-second end-to-end deadline; other advice attempts
use advice §3. The orchestrator records queue/return and cleanup, not the model.
Reuse completed coverage only under pr-lifecycle's claim/delta/phase rule;
reaffirmation is not another vote. Preserve WITHHELD, failed and partial
attempts rather than relabeling them.

## 5. Receipt and publication

Keep the exact prompt/hash, scope and revision/bundle, actual identity,
queue/return, native exit/completion, coverage, verdict and the advice §4
mode-specific checks. The orchestrator captures the exact dispatched prompt and its
SHA256 before queueing and records managed completion/return at the moment the
attempt finishes (within the attempt deadline), never timing later PR/gist
publication against the attempt budget. A managed native completion replaces a CLI exit; never
demand a clone path or process cleanup for a mode that created neither.
Original checkouts, refs, local config and hooks must remain unchanged.

Capture the private technical receipt and required cleanup within the attempt
deadline. Later sanitized publication is a separate lifecycle step, preserving
original times and hashes; never replace actual completion clocks with later
publication timestamps. Publish final review and technical receipts; exclude
private reasoning, secrets and credentials. If a filled prompt contains private
paths/hosts, publish only its hash and template name outside the authorized
workspace; retain the exact original privately.

Check actual input byte-for-byte against the selected preamble and filled
template. Encrypted or protected rollout/archive representations are not source input:
never attempt to decrypt them, never compare encrypted archive blobs against plaintext
prompts to reject a valid receipt, and never replace actual completion clocks with
later publication timestamps. Added code framing or summaries invalidate the cold vote. Evidence-only
/er retains its own claim/artifact dispatch contract and never supplies an
unseen-code approval.
