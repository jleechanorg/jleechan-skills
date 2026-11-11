## 1. Pin the question and complete scope

Before queueing reviewers, inspect existing verdicts under §5's resubmission and applicability rules. An eligible approval for unchanged
claims needs no phase, format or frozen-head restamp. Preserve original eligibility; request only genuinely missing
or affected independent judgment, or an explicitly requested further review.

Every reviewer gets only the static-review channel preamble and its filled template: no user question, summary,
excerpt or framing. Keep the user's `[question]` with the orchestrator, record it in the §5 report, and answer it
from the reviewers' findings; if the template cannot surface what the question needs, report that gap. Send a pointer to
the complete change, never a transcription. A verdict built on unrecovered truncated input is never APPROVED; if display/tool output truncates, complete required content recovered via narrower range requests within the attempt deadline satisfies full coverage.

- **Revision review** covers exactly the pinned commit.
- **Document-only review** covers explicitly named, non-ignored, non-symlink Markdown files, committed or not. Give
  every reviewer identical complete bytes (an existing CLI input path, or an upload for web seats), keep the packet, and record per-file
  and bundle SHA256 hashes (integrity, not immutability). It never approves code, `HEAD` or dirty state.
- Revision-bound saved-content review uses the full 40-hex head SHA only when the PR URL, base/head SHAs, and complete
  revision-bound coverage are verified. A complete unbound packet uses exactly `DOCUMENTS sha256:<BUNDLE HASH>` and approves
  only that bundle. Incomplete claimed revision binding means `WITHHELD`; never use an abbreviated SHA or mutable `HEAD`.
- Each approver reads the whole declared scope. Partial coverage is never combined across reviewers into an
  approval.

An advice vote scoped only to source or a PR diff is source review; it does not
approve evidence or establish inspection of underlying raw evidence. Evidence
approval remains a separate `/er` claim-coverage verdict under
[evidence-review](../evidence-review/SKILL.md), including its direct raw-data
inspection and explicit inspected/unavailable coverage requirements.

## 3. Enforce the attempt deadline

- **Budget `B`.** Each attempt gets 1800 seconds end to end (static reviewers: 600 seconds, per static-review) unless
  the user sets a limit. A specific user instruction to await a named reviewer overrides that attempt's deadline, even
  without a duration, per pr-lifecycle § Reviewer timeout and completion; record the instruction and actual wait. A CLI
  attempt already under native timeout cannot be lengthened: on expiry record `TIMED_OUT`, mark that route
  `UNAVAILABLE`, and keep the gate open rather than counting late output. Never preempt a valid result, count late
  output, claim a wait that did not happen, or issue a duplicate review. Status updates do not reset the clock.
- **Clock.** Shared, immutable packet preparation may happen first. Immediately before dispatch, capture the queue
  boundary on the host that launches the seat:

  ```bash
  read -r QUEUED_AT_EPOCH_NS QUEUED_AT_MONOTONIC_NS <<< "$(
    python3 -c 'import time; print(time.time_ns(), time.monotonic_ns())'
  )"
  ```

  Monotonic values are host- and boot-local, so a CLI seat runs on that same host and the epoch value is audit-only.
  Outside routes take both the send and the reply-observed times on the orchestrator's host; the remote side's
  timestamps are `attested.` audit values. If the boundary cannot be captured, the seat is `UNAVAILABLE`.
- **Bound.** Choose positive cleanup reserve `C` and wait grace `G` inside `B`, or the seat is `UNAVAILABLE`. Launch
  with native timeout `B - C` from the queue boundary, reclaim cleanup inside `C`, and bound the wait by the same
  deadline. For outside routes, `C` covers only readback and receipt writing. Record queue boundary, deadline and
  actual exit in the receipt, never the prompt; the orchestrator's bounded tool call is the mechanism.
- **Outcome.** Setup, delivery, review, capture, receipt writing and cleanup all count against `B`; the deadline
  decides eligibility, not a real-time guarantee. The captured pre-dispatch prompt/hash and actual completion
  timestamp govern the attempt receipt; later sanitized PR/gist publication and protected or encrypted session
  archives do not alter that clock or invalidate a verified plaintext dispatch receipt. Receipt archive handling
  follows static-review §5. Shared immutable preparation may precede the attempt; per-seat setup, capture, technical
  receipt and cleanup stay inside this section's bound.
  Cleanup or receipt overrun makes the
  attempt nonzero and voids its vote. A late, incomplete, failed or timed-out result is not approval: keep partial
  findings and cleanup status, then use another eligible reviewer. Do not wait on unresolved cleanup, reuse an
  unresolved resource, or claim cleanup without receipt evidence. Non-mandatory bookkeeping must never delay an
  authorized merge.

## 4. Review access modes and isolation

Select the cheapest complete access before dispatch. Read-only API or existing
checkout access needs no donor, clone or export. Use a copy only when object
access or mutation isolation requires it. This table owns mode names, template fields and checks;
static-review owns the actual templates and per-channel preambles.

| Mode | Access and template | Required receipt and checks | Fields |
|---|---|---|---|
| pin (internal) | Resolve review SHA and true comparison merge-base against the fetched target tip using an existing checkout/API. For clone seats only, prepare one standalone --no-local donor pinned at that SHA. Never send it as a seat cwd. | Original/donor references, immutable head/base and object inventory. For a donor, git-common-dir equals git-dir; remove it after all seat clones are gone. | none |
| orchestrator-clone | Orchestrator clones donor into allocated Scratch and removes origin; shared revision template. | Before launch and after process exit: standalone Git, exact head, base ancestor, no remotes; original checkout/refs/config/hooks unchanged. Confirm no reviewer process remains, then remove this owned clone and record absence. | `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` |
| orchestrator-export | Orchestrator supplies a complete pinned export in Scratch, with full diff, base/head snapshots or absence, object inventory and hashes; shared revision template. | No .git or new repository. Verify all exported bytes and original checkout state before/after; confirm process completion, then remove this owned export. Missing required objects must be retrieved read-only at the pin or withheld. | `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` |
| read-only | GitHub/API or existing checkout; shared revision template. No new copy, fetch or branch switch. | Complete immutable objects/diff and requested SHA, API no-truncation/retrieval proof or existing-checkout before/after state. clone_path:none, clone_removed:n/a. A managed native completion replaces a CLI exit/process check only when there is no CLI process. | `<PR URL>` `<SHA>` `<BASE SHA>` |
| remote (Dot/Hermes) | Configured coordinator ask; shared revision template. Existing checkout or pinned API access; only missing objects may be fetched, without changing branch refs/working tree. No new clone. | Requested SHA reachable at send and reply readback; verified route/account binding, message reference, exact-SHA verdict and complete coverage. Record exposed fields as attested, not invented. API-only access has no checkout path to attest; existing-path details may remain private. clone_path:remote, clone_removed:n/a. | `<PR URL>` `<SHA>` `<BASE SHA>` |
| packet (web revision) | Orchestrator uploads the complete pinned diff, changed-path base/head content or verified absence, all special objects and relevant evidence; revision packet template. | Bundle/per-file hashes, actual attachment delivery, authenticated provider/account, full-file no-truncation and returned coverage/verdict at the SHA. Never substitute a summary, bare private URL or function-only excerpt for required full scope. clone_path:none, clone_removed:n/a. | `<PR URL>` `<SHA>` `<BASE SHA>` `<BUNDLE HASH>` |
| none (saved material) | Named complete documents, or a fully revision-bound saved packet; saved-material template. Web gets actual uploads and the attached-files path, never a local private path. | Per-file and bundle hashes, complete scope, and revision metadata/diff/base/head objects when revision approval is requested. Without verified revision binding approve only named documents, never code/HEAD. Keep this packet as evidence; no clone or cleanup claim. Dot/Hermes cannot use an inaccessible local packet. | `<PACKET PATH>` `<BUNDLE HASH>` `<REVIEW TARGET>` |

The orchestrator owns copies and verifies measurable cells; remote facts are
`attested.` and never proof of an orchestrator-verified cell. Do not claim a
copy or cleanup for a mode that created none. Compute base once; later clone
checks test ancestor/head and never replace it with a moving branch tip. Source
approval covers complete objects at both pins, including binary/mode/symlink/
gitlink/LFS content. Verified identical spans may be reused; partial readers
cannot be combined. Unpushed revisions need local access; remote routes need
reachable objects.

Reviewers remain read-only; full permissions do not authorize repairs, external
writes, credential changes or unrelated destructive actions. Original state must
remain unchanged. Failed copy checks or unresolved cleanup make an attempt
non-countable, while findings are retained. Copies live in configured Scratch,
never a code/home tree or new `/tmp` clone; remove only exact owned copies after
process exit, preserving source and private receipts. Technical receipt and cleanup complete within the attempt
budget; later sanitized publication is separate and retains the original clocks.

**Before dispatching review.** Check the declared packet: source/head bindings, complete pinned content or its
pointer, and, only for a static-review §4 same-seat addendum, the input that section defines. Record in the
orchestrator's receipt, never the prompt, where the request and its context came from, or `unknown`. Hash decoded
content, not an encoded API body field.
