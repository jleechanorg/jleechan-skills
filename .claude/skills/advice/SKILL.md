---
name: advice
description: Use when a focused second opinion is needed; collect the applicable independent, full-coverage reviewer votes on an exact change or saved-document bundle.
---

# /advice — independent second opinion

Use `/advice [question]` instead of `advisor()`. This skill owns reviewer orchestration: selection, quorum, deadlines,
isolation and receipts. [static-review](../static-review/SKILL.md) owns reviewer input. pr-lifecycle's [Advice
applicability](../pr-lifecycle/SKILL.md#advice-applicability) section owns phases, thresholds, applicability and
publication; evidence-standards owns evidence classes. Do not restate those here.

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

## 2. Select independent reviewers

**Required quorum.** Use two independent full-scope source votes by default.
Use one only when pr-lifecycle positively selects a one-source-review route and
the reviewer confirms its eligibility; preserve that route rather than starting
extra advice seats. An explicitly requested advice invocation follows the same
qualified count. Archive-integrity review is not source approval.
Stricter user, repository, security and domain requirements remain binding. The
mandatory supplementary-review substitution still needs two eligible advice
votes and applicable evidence review. Record the route/count before dispatch;
neither one-vote readiness nor advice approval changes merge authority.

### Capability profile and tier selection

Use only capabilities actually available and authorized. Keep one machine-local profile of seat label, host, actual
account/identity key, model, transport and command or profile reference, permitted scope/isolation row, disclosure
authorization, availability and attempt receipt. Use existing ADVICE configuration and owning transport skills; this
is an orchestration record, not a new runner, configuration parser or prompt framework. Do not put personal accounts,
destinations, credentials or host paths in this repository. Preference for a different CLI/model does not make aliases
of one account independent.

| Tier | Available reviewers | Admission and counting |
|---|---|---|
| 1 — preferred | Available authorized CLI seats, including configured extra CLIs; authorized ChatGPT Dot accounts; the Instinct WhatsApp peer (`/instinct`) | Prefer different eligible CLI/model identities. CLI, Dot and Instinct are alternatives in the same tier; no brand or mixture is mandatory. Count at most one Dot vote and at most one Instinct vote, and never combine Dot with Instinct into a two-vote quorum. |
| 2 — fallback | Native static subagents; Hermes or Hermes-PC | Static subagents collectively count as at most one vote; Hermes instances collectively count as at most one distinct vote. Each counted vote must independently cover the entire scope. |
| 3 — last fallback | Existing authorized authenticated web chats through /web-advice | Use only after earlier-tier candidates cannot fill the remaining quorum. Preserve packet, upload, account-attestation and receipt rules. |

Start independent eligible candidates concurrently where transport and resource rules permit. Retain valid earlier-tier
votes and fill only remaining slots. Advance when the current tier cannot fill them; a missing brand is not a reason to
wait. An eligible in-flight attempt remains bounded by §3, not declared unavailable merely to prefer a later result.
Stop new dispatch once quorum is met unless another workflow obligation requires it; retain competent findings from
valid in-flight attempts.
The author, orchestrator and /research do not vote. One competent blocking objection can block.

Record availability separately from verdicts: AVAILABLE; UNAVAILABLE with missing capability, unsupported scope
or authorization reason; BUSY with an existing handle when known; QUOTA with a printed reset time when available;
or DUPLICATE with the shared identity key. Busy, missing, quota-blocked and duplicate seats do not reserve votes
or justify indefinite waits. Do not duplicate an active request. Keep the existing deadline and explicit-wait
rules for in-flight attempts. Delivery, acknowledgement and assignment are not approval.

### CLI capabilities

| Seat | Machine-local command override or default |
|---|---|
| Codex | `ADVICE_CODEX_CMD`, else `codex exec --yolo -m gpt-6.1-sol --config model_reasoning_effort=high` |
| Claude | `ADVICE_CLAUDE_CMD`, else `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `ADVICE_CLAUDE_ALT_CMD`, else the Claude argv with `--model <actual-model>` |
| Cursor | `cursor agent -p --force` |
| AGY | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |
| Existing extra seats | `ADVICE_EXTRA_CLIS`, in configured order (unset by default); registration does not authorize a new reviewer |

These are capabilities, not required installed seats or a mandatory starting pair. Resolve eligible independent
identities from the machine-local profile before selecting them.

- **Configuration.** An `ADVICE_*` variable that is set but empty, unparseable, or names a missing or
  non-executable program makes that seat `UNAVAILABLE`. It never falls back to the default, because the default
  would run as another seat's identity. Machine-specific values (credential-store or profile directories, per-host
  wrapper paths, model aliases, account identifiers) live only in that machine's `~/.bashrc` as exported `ADVICE_*`
  values, never in this repository; this file may name a wrapper's shape (a `claudewa`-style wrapper that selects
  another credential store) but never a concrete path, digest or profile.
- **`ADVICE_EXTRA_CLIS`** registers more seats as `label=executable args`, separated by `|`, for example
  `ADVICE_EXTRA_CLIS='gemini-cli=gemini --approval-mode yolo -p|local-qwen=qwen -p'`. Parse it with shell-style
  quoting: `|` and the first `=` separate only outside quotes, then `shlex` the right-hand side into literal
  arguments, with no shell evaluation, globbing, command substitution or `~` expansion. Each `{prompt}`, as a whole
  token or inside one (`--print={prompt}`), is replaced by the request; with none, the request is appended as the
  last argument. An empty label or command, a duplicate label, an unparseable entry or a missing program makes that
  seat `UNAVAILABLE`.
- **No review-dispatch runner.** The orchestrator still launches each seat under §3 and owns its deadline and receipt.
  `quota_cache.py` only reads/writes the bounded quota hint; it never invokes a provider or starts/retries a review.
  A capability the orchestrator cannot bound end to end or cannot receipt is `UNAVAILABLE`; do not add a runner,
  wrapper, watchdog or timer.
- **Review readback discipline.** Bind each read to the existing attempt and
  inspect its complete attributable result once. An identical unchanged read is
  not a new verdict or progress: use the existing attempt deadline and
  completion signal, do independent work, and do not loop on the same capture.
  A completed, timed-out, or unavailable attempt is not polled again; route a
  missing vote through an eligible independent seat without duplicating work.

- **Quota walls fail fast.** A usage limit, quota exhaustion, exhausted 429 retry, rate limit, expired plan or similar
  account refusal makes the seat `UNAVAILABLE` with reason `quota` and the printed reset time. Do not wait, retry the
  same account or switch models around it; a separate account remains eligible.
- **Remember only confirmed quota windows.** Before launching each CLI seat, check the short-lived quota record:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" check --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256>
  ```
  `ELIGIBLE` permits the normal launch. `QUOTA_BLOCKED` means skip that exact account until its printed UTC reset
  time and continue the fallback route. Derive the identity digest from the account identity in an existing,
  verified machine-local seat binding; checking the cache must not trigger a new provider request. Do not use a
  guessed seat label, email, token, credential path or model name as identity. Pass only this SHA-256 digest, never
  the raw account identity. If no verified account binding is available, fail open and use the normal seat admission
  path; do not use the cache to skip a reviewer. The cache key combines the verified provider and account-identity
  digest. Cache only an explicit provider quota response and reset time:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" record --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256> --model <actual-model> --observed-at <quota-response-observation-time> --reset-at <provider-reported-ISO-8601-reset>
  ```
  The record includes its observation time and is stored with private permissions under `/tmp`; it contains only a
  keyed hash of the provider/account digest plus provider, model and UTC times, never credentials, raw identity or raw error text. No printed reset
  means no cache entry. Record the timestamp from when the provider response was observed, not when the record
  command happens to run. The cache orders quota and success events by that timestamp, so a delayed quota write
  cannot re-block a seat after a later successful probe. A fresh successful probe performed by the normal review
  path clears an earlier record before counting that seat as available:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" clear --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256> --observed-at <successful-probe-observation-time>
  ```
  Expired records clear themselves. Cache lock contention, invalid paths, and unavailable storage fail open and must
  not stall or deny an authorized attempt. The cache is a scheduling hint, not a second quota detector: record only a quota error actually observed
  from that exact seat; transport timeouts, unrelated tool errors and missing authentication are not quota signals.

### Outside-route authorization and transports

**Authorization is machine-local.** These routes send PR content off the machine, so this portable skill grants
nothing by itself. A route is authorized only when `ADVICE_OUTSIDE_ROUTES` lists it (comma-separated `dot,hermes,web`)
in that machine's `~/.bashrc`, or the current task explicitly authorizes it. That opt-in is the standing authorization
required by pr-lifecycle's optional-`/wa` rule and `/hermes`'s disclosure rule. Unlisted routes are `UNAVAILABLE —
disclosure not authorized`, as are routes restricted by the user, task or repository, or content holding secrets. (The
repository owner opted in on 2026-11-04: "when all cli reviewers out of quota ... it should try to use /wa and ask
hermes hermes pc and the dots in dot coordination for a review".)

Each Dot account gets its own §3 attempt, capped at the Dot route's absolute deadline: one budget B after its
first send. No account is asked after that deadline; record a running one TIMED_OUT at it unless the user
explicitly required waiting under §3. Rotate on unavailable or failed attempts while a Dot vote is still needed.
After one eligible Dot vote, do not request another Dot to fill a second vote.

| Route | Transport and scope |
|---|---|
| Dot (tier 1) | Use the host-installed [dot](../dot/SKILL.md) skill and [dot-coordinator](../dot-coordinator/SKILL.md)'s configured account rotation, explicitly targeting `--account <name>` with `DOT_ROTATE_ON_LIMIT=0`; coordinator ask, `isolation: remote`, revision review only. |
| Hermes or Hermes-PC (tier 2) | Use the host-installed /hermes Slack-only transport, coordinator ask and `isolation: remote`, revision review only. Resolve the configured eligible instance; another instance may replace a failed/unavailable one, not add a second Hermes vote. Use an available authorized machine-local `ADVICE_HERMES_CHANNEL` destination, otherwise the conversation /hermes resolves. |
| Web (tier 3) | Use host-installed [web-advice](../web-advice/SKILL.md); `isolation: packet` for revisions, `none` for documents. Record the authenticated provider/account from the session as `attested.account`. |

Missing transports are UNAVAILABLE with the exact blocker; never substitute a forbidden transport. A reply
counts only with full-scope COVERAGE and the exact SHA-bound VERDICT read back at its source, not an
acknowledgement, reaction or promise. Route availability does not override disclosure restrictions.

### Native static fallback

Static reviewers follow [static-review](../static-review/SKILL.md) for cold input, full coverage, identity, deadlines
and receipts. Spawn each native seat (for example Codex `spawn_agent`) with packet-only context, its preamble and
template, never a parent-history fork such as `fork_turns: "all"`. Admit them in tier 2 with an eligible Hermes
instance when needed; §2's aggregate caps still apply (static reviewers collectively at most one vote, Hermes
instances collectively at most one), and each counted verdict covers the whole scope. Eligible CLI pairs, CLI plus
static, or eligible outside combinations may supply the quorum.
There is no generic remote minimum or remote-only prohibition; preserve any separately explicit outside-review
obligation. Review votes never replace missing substantive evidence.

### Identity

- One account is one vote, whatever its label, wrapper, alias or retry; seats reaching the same account count once,
  including an outside reviewer whose coder used the account that hit quota.
- A CLI seat needs its actual model from reliable CLI/runtime metadata, or it is `UNAVAILABLE`. Outside routes record
  exposed model/account fields as `attested.` values; never invent a hidden runtime SKU. A verified Dot account is its
  own CLI/model identity under the one-Dot cap. Missing public fields do not invalidate a privately verified session;
  an actually unverified account is unavailable. Keep its frozen expected binding, positive identity probe and source-
  author independence proof. Codex models may be only `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-terra` or `gpt-6.1-sol`.
- Neither the author nor the orchestrator awards itself a vote, and no verdict counts twice: a Dot account whose verdict fills the
  pr-lifecycle `/dot` leg at this head is not also an `/advice` vote.
- Run every seat with full permissions and record its actual command, model, account and transport.

Record every unavailable or skipped reviewer as `UNAVAILABLE: <host> — <reviewer> — attempted|skipped — <time> —
<reason>` and tell the user. A failure on one host (a cloud box) says nothing about the same CLI on another host (a
Mac or Ubuntu machine); try or record each host separately. When the tiers cannot supply the required eligible votes within their counting caps, the result is
`WITHHELD`, listing every `UNAVAILABLE` line and the earliest known quota reset.

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

**Before waiting or dispatching review.** Confirm the job actually started and its requested output exists; assignment
and packet presence are not progress. Confirm the declared packet is complete: full original review outputs and
affected-scope addenda, source/head bindings, child request and context provenance (or an explicit `unknown`), and
event-ID/context joins. Decode an API body field before hashing it. Do not retry a route already confirmed unavailable
in the same task, and do not poll status without a decision to make.

## 5. Reconcile and report

**Counting a vote.** A counted reviewer returns full-scope `COVERAGE:` and a nonempty `VERDICT:`. Its receipt shows
a zero exit, a present and parseable receipt, no mutation of the original checkout, no surviving reviewer process,
and no cleanup failure (receipt timing, archive handling, and non-mandatory bookkeeping follow §3).
A static-review receipt replaces only the exit field; an outside-route receipt (`remote` or
`packet`) replaces the exit, process and cleanup fields with that row's evidence. When a seat returns nonzero, ignore its
whole receipt, since a failed late rewrite can leave an older success-looking one. If clone setup timed out,
directory removal does not prove its descendants exited: record that and do not count the attempt.

**Verdict.** Reconcile disagreements within the declared scope yourself; do not ask the user to pick between
reviewers. A competent blocking objection, even from a partial-coverage reviewer, means `NOT APPROVED`; partial
coverage never supplies an approval. P1/P2 findings are nonblocking and alone neither withhold approval nor require
another round; the author batches them and records each fix or disposition in the report. Without the required
independent full-coverage approvals under §2's tier caps, the result is
`WITHHELD`.

**Report.** Give the full 40-hex reviewed SHA for revision-bound review or `DOCUMENTS sha256:<bundle hash>` for a
complete bundle-only review; never use an abbreviated SHA or mutable `HEAD`. Each reviewer's verdict,
coverage, reasoning, risk and findings, the question's answer, and every `UNAVAILABLE` line. Keep a receipt per
attempt: identity, actual CLI, account and model, start and completion times, exit or timeout, the exact prompt
(any deviation voids the vote, per static-review), complete output, coverage and cleanup result. End with exactly
one line: `VERDICT: APPROVED at `<SHA>``, `VERDICT: NOT APPROVED at `<SHA>``, or `VERDICT: WITHHELD at `<SHA>` — <reason>`;
for bundle-only saved-content review, `DOCUMENTS sha256:<bundle hash>` takes the place of ``<SHA>``.

**Resubmission and applicability.** Keep original reviewers, SHAs and findings; reliance at a later head follows
[review-routing's SHA-binding rule](../pr-lifecycle/review-routing.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain)
and is not a new vote. Before any re-dispatch, the author fixes every blocking finding in one batch, then (a) searches
all reviewed artifacts for each restatement of a corrected requirement and fixes every one, not only the cited line;
(b) verifies every cited path, line, link and artifact exists at the new pin. Inspect the complete delta, claims,
evidence and phase; applicability is not a new vote, and material uncovered changes need affected independent
review. When that rule's record is partially applicable with named gaps, send the affected review to the same seat
as static-review §4's addendum; otherwise request the complete review. Classify instruction changes by behaviour
and contract effect, never by path.
Never claim approval, applicability or publication without its receipt.

For visual follow-up, use [visual-verification's reuse and scoped follow-up](../visual-verification/SKILL.md#reuse-and-scoped-follow-up).
Repair mechanically verifiable receipt fields yourself rather than dispatching a
reviewer for bookkeeping; preserve §3 eligibility and original clocks. Such a
repair cannot supply missing coverage, alter a verdict or revive a void vote.
For human-judgment prose in a PR body, follow [document-standards' review and
publication owner](../document-standards/SKILL.md#pr-body-prose-review-and-publication).
