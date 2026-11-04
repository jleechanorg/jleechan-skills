---
name: advice
description: Use when a focused second opinion is needed; collect the applicable independent, full-coverage reviewer votes on an exact change or saved-document bundle.
---

# /advice — independent second opinion

Use `/advice [question]` instead of `advisor()`. This skill owns reviewer orchestration: which reviewers run, the
quorum, deadlines, isolation and receipts. [static-review](../static-review/SKILL.md) owns what each reviewer
receives. pr-lifecycle's [Advice applicability](../pr-lifecycle/SKILL.md#advice-applicability) section owns phases,
thresholds, applicability and publication; evidence-standards owns evidence classes. Do not restate those here.

## 1. Pin the question and complete scope

Every reviewer gets only the static-review channel preamble plus its template: no question, summary, excerpt or
framing. The user's `[question]` stays with the orchestrator, which records it in the §5 report and answers it from
the reviewers' findings; if the template cannot surface what the question needs, report that gap. Send a pointer to
the complete change, never a transcription. A verdict built on truncated input is never `APPROVED`.

- **Revision review** covers exactly the pinned commit.
- **Document-only review** covers explicitly named, non-ignored, non-symlink Markdown files, committed or not. Give
  every reviewer identical complete bytes (an existing CLI input path, or an upload for web seats), keep the packet, and record per-file
  and bundle SHA256 hashes (integrity, not immutability). It never approves code, `HEAD` or dirty state.
- Each approver reads the whole declared scope. Partial coverage is never combined across reviewers into an
  approval.

## 2. Select independent reviewers

**Required quorum.** Use two independent full-scope source votes by default.
Use one only when pr-lifecycle positively selects a one-source-review route and
the reviewer confirms its eligibility; preserve that route rather than starting
extra advice seats. An explicitly requested advice invocation follows the same
qualified count. Archive-integrity review is not source approval, and a local
record-only exemption must not cite an absent governing rule.
Stricter user, repository, security and domain requirements remain binding.
The mandatory supplementary-review substitution still needs two eligible advice
votes and applicable evidence review. Record the route/count before dispatch;
neither one-vote readiness nor advice approval changes merge authority.

### Capability profile and tier selection

Use only capabilities actually available and authorized for this task. No machine needs every reviewer.
Keep one machine-local profile of seat label, host, actual account/identity key, model, transport and command or
profile reference, permitted scope/isolation row, disclosure authorization, availability and attempt receipt.
Use existing ADVICE configuration and owning transport skills; this is an orchestration record, not a new runner,
configuration parser or prompt framework. Do not put personal accounts, destinations, credentials or host paths
in this repository. Preference for a different CLI/model does not make aliases of one account independent.

| Tier | Available reviewers | Admission and counting |
|---|---|---|
| 1 — preferred | Available authorized CLI seats, including configured extra CLIs; authorized ChatGPT Dot accounts | Prefer different eligible CLI/model identities. CLI and Dot are alternatives in the same tier; no brand or mixture is mandatory. Count at most one Dot vote. |
| 2 — fallback | Native static subagents; Hermes or Hermes-PC | Static subagents collectively count as at most one vote; Hermes instances collectively count as at most one distinct vote. Each counted vote must independently cover the entire scope. |
| 3 — last fallback | Existing authorized authenticated web chats through /web-advice | Use only after earlier-tier candidates cannot fill the remaining quorum. Preserve packet, upload, account-attestation and receipt rules. |

Start independent eligible candidates concurrently where their transport and resource rules permit. Retain valid
earlier-tier votes and fill only remaining slots. Advance when available candidates in the current tier cannot
fill them; a missing brand is not a reason to wait. An already-running eligible attempt remains bounded by §3,
not declared unavailable merely to prefer a later result. Stop new dispatch once the applicable quorum is met
unless another workflow obligation requires it; retain competent findings from valid in-flight attempts.
The author, orchestrator and /research do not vote. One competent blocking objection can block.

Record availability separately from verdicts: AVAILABLE; UNAVAILABLE with missing capability, unsupported scope
or authorization reason; BUSY with an existing handle when known; QUOTA with a printed reset time when available;
or DUPLICATE with the shared identity key. Busy, missing, quota-blocked and duplicate seats do not reserve votes
or justify indefinite waits. Do not duplicate an active request. Keep the existing deadline and explicit-wait
rules for in-flight attempts. Delivery, acknowledgement and assignment are not approval.

### CLI capabilities

| Seat | Machine-local command override or default |
|---|---|
| Codex | `ADVICE_CODEX_CMD`, else `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` |
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
- **No runner.** This skill ships instructions only (the owner's *markdown only, zero runner code* decision). The
  orchestrator launches each seat itself under §3, and a machine-local capability never requires code in this
  repository. A seat the orchestrator cannot bound end to end, or cannot produce a receipt for, is `UNAVAILABLE`; do not add a runner,
  wrapper, watchdog or timer.
- **Quota walls fail fast.** A usage limit, quota exhaustion, an exhausted 429 retry, "rate limit reached", an
  expired plan or a similar account-level refusal makes the seat `UNAVAILABLE` at once with reason `quota` and the
  reset time when printed. Do not wait out its budget, retry the same account or switch models to get around it.
  Another account (a `claudewa`-style alternate) is a separate seat and is still tried.

### Outside-route authorization and transports

**Authorization is machine-local.** These routes send PR content off the machine, so this portable skill grants
nothing by itself. A route is authorized only when the machine's `ADVICE_OUTSIDE_ROUTES` lists it (a
comma-separated subset of `dot,hermes,web`, exported in that machine's `~/.bashrc`) or the current task explicitly
authorizes it. That opt-in is the standing authorization pr-lifecycle's optional-`/wa` rule and `/hermes`'s
disclosure rule require. Unlisted routes are `UNAVAILABLE — disclosure not authorized`, and so is any route when the
user, task or repository restricts external disclosure of the reviewed content, or the content holds secrets. (The
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

Static reviewers follow [static-review](../static-review/SKILL.md) for cold input,
full coverage, identity, deadlines and receipts. Admit them in tier2 alongside
an eligible Hermes instance when needed; together they do not reserve slots or
override the aggregate caps. Each counted verdict itself covers the whole scope.
The supplementary-review fallback still requires two independent advice votes.
Apply the same tiers/caps: eligible CLI pairs, CLI plus static, or eligible
outside combinations may supply them. There is no generic remote minimum or
remote-only prohibition. Preserve any separately explicit user/repository
outside-review requirement as a distinct obligation, or leave that obligation
open. Review votes never replace missing substantive evidence.

### Identity

- One account is one vote, whatever its label, wrapper, alias or retry. Two seats whose commands reach the same
  account count once; an outside reviewer whose coder ran the account that just hit its quota is that account.
- A CLI seat needs its actual model from reliable CLI/runtime metadata, or it is `UNAVAILABLE`.
  Outside routes record exposed model/account fields as `attested.` values; never invent a hidden runtime SKU.
  A verified configured Dot account is its own CLI/model identity under the one-Dot cap. An unreported public
  model/account field does not invalidate a privately verified session; an actually unverified account remains
  unavailable. Keep its frozen expected binding, positive identity probe and source-author independence proof. Codex models may be only `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol` or `gpt-6.1-sol`.
- Neither the author nor the orchestrator awards itself a vote, and no verdict counts twice: a Dot account whose verdict fills the
  pr-lifecycle `/dot` leg at this head is not also an `/advice` vote.
- Run every seat with full permissions and record its actual command, model, account and transport.

Record every unavailable or skipped reviewer as `UNAVAILABLE: <host> — <reviewer> — attempted|skipped — <time> —
<reason>` and tell the user. A failure on one host (a cloud box) says nothing about the same CLI on another host (a
Mac or Ubuntu machine); try or record each host separately. When the tiers cannot supply the required eligible votes within their counting caps, the result is
`WITHHELD`, listing every `UNAVAILABLE` line and the earliest known quota reset.

## 3. Enforce the attempt deadline

- **Budget `B`.** Each attempt gets 1800 seconds end to end (static reviewers: 600 seconds, per static-review) unless the user set a limit, shorter or longer,
  which governs that attempt. A specific user instruction to await a named reviewer overrides that attempt's deadline, even without
  a duration, per pr-lifecycle § Reviewer timeout and completion; record the instruction and the wait actually
  honoured in the receipt. A CLI attempt already running under a native timeout cannot have that timeout
  lengthened: when it expires, record it `TIMED_OUT`, mark the requested wait route `UNAVAILABLE`, and keep the gate open
  for that reviewer instead of counting late output. Never preempt a valid in-deadline result, count late output, claim a wait that did not
  happen, or issue a duplicate review. Status updates never pause or reset the clock.
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
- **Bound.** Choose a positive cleanup reserve `C` and wait grace `G`, both inside `B`, or the seat is `UNAVAILABLE`.
  Launch with a native timeout of `B - C` measured from the queue boundary, reclaim cleanup inside `C`, and bound
  the wait by the same absolute deadline. For outside routes, `C` covers only readback and receipt writing. Record
  the queue boundary, absolute deadline and actual exit in the receipt, never in the prompt. The orchestrator's own
  bounded tool call is the mechanism.
- **Outcome.** Setup, delivery, review, output capture, receipt writing and cleanup all count against `B`. The
  deadline decides eligibility; it is not a real-time guarantee. A cleanup or receipt write that overruns makes the
  attempt nonzero and voids its vote. A late, incomplete, failed or timed-out result is not an approval: keep its
  partial findings, record cleanup status, and use another eligible reviewer. Do not keep waiting for unresolved cleanup or
  reuse a resource whose process or cleanup state is unresolved, and never claim cleanup without receipt evidence.

## 4. Review access modes and isolation

Select the cheapest complete access before dispatch. Read-only API or existing
checkout access needs no donor, clone or export. Use a copy only when object
access or mutation isolation requires it. Shared immutable preparation may
precede the attempt; per-seat setup, capture, technical receipt and cleanup
remain inside §3's bound. This table owns mode names, template fields and checks;
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

The orchestrator owns copies and verifies every measurable cell. A reviewer
does not clone/delete its own isolation copy or attest facts the orchestrator
can measure. Label genuinely remote facts attested; never use that label as
proof for an orchestrator-verified cell. Do not claim a copy or cleanup for a
mode that created none.

Base is computed once for the attempt. Later clone checks test ancestor/head
and never replace it with a moving branch tip. Source approval always covers
complete required objects at both pins, including binary/mode/symlink/gitlink/LFS
content. Verified identical spans can be reused; partial readers cannot be
combined. Unpushed revisions need complete local access; remote routes require
reachable objects.

Full permissions do not authorize repairs, external writes, credential changes
or unrelated destructive actions. Reviewers remain read-only. Original state
must be unchanged after each attempt. Preserve actual process/native completion
and mode-specific post-checks; a failed copy check or unresolved required cleanup
makes that attempt non-countable, while its findings are retained.

Copies live in configured Scratch, never a code/home tree or a new /tmp clone.
Remove only exact owned copies after their processes exit, preserving original
source and private receipts. The private technical receipt and required cleanup
complete inside the attempt budget. Later sanitized publication is a separate
lifecycle event: retain original review/capture clocks rather than extending or
restamping them.

## 5. Reconcile and report

**Counting a vote.** A counted reviewer returns full-scope `COVERAGE:` and a nonempty `VERDICT:`. Its receipt shows
a zero exit, a present and parseable receipt, no mutation of the original checkout, no surviving reviewer process,
and no cleanup failure. A static-review receipt replaces only the exit field; an outside-route receipt (`remote` or
`packet`) replaces the exit, process and cleanup fields with that row's evidence. When a seat returns nonzero, ignore its
whole receipt, since a failed late rewrite can leave an older success-looking one. If clone setup timed out,
directory removal does not prove its descendants exited: record that and do not count the attempt.

**Verdict.** Reconcile disagreements within the declared scope yourself; do not ask the user to pick between
reviewers. A competent blocking objection, even from a partial-coverage reviewer, means `NOT APPROVED`; partial
coverage never supplies an approval. Without the required independent full-coverage approvals under §2's tier caps, the result is
`WITHHELD`.

**Report.** Give the reviewed SHA (or `DOCUMENTS sha256:<bundle hash>`; never `HEAD`), each reviewer's verdict,
coverage, reasoning, risk and findings, the question's answer, and every `UNAVAILABLE` line. Keep a receipt per
attempt: identity, actual CLI, account and model, start and completion times, exit or timeout, the exact prompt
(any deviation voids the vote, per static-review), complete output, coverage and cleanup result. End with exactly
one line: `VERDICT: APPROVED at `<SHA>``, `VERDICT: NOT APPROVED at `<SHA>``, or `VERDICT: WITHHELD at `<SHA>` — <reason>`;
for document-only review, `DOCUMENTS sha256:<bundle hash>` takes the place of ``<SHA>``.

**Applicability.** Keep the original reviewers and reviewed SHAs. Before relying on them at a later head, inspect
the complete delta, claims, evidence and phase; applicability is not a new vote, and material uncovered changes
need affected independent review. Classify instruction changes by behaviour and contract effect, never by path.
Never claim approval, applicability or publication without its receipt.
