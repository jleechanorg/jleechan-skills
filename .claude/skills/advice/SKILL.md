---
name: advice
description: Use when a focused second opinion is needed; collect two independent, full-coverage reviewer votes on an exact change or saved-document bundle.
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

Approval needs two independent votes, each covering the whole scope. Votes come from three rungs, tried in order:
CLI seats, then outside routes, then static reviewers. Launch every candidate on a rung concurrently; never
serialize healthy seats. The orchestrator's own synthesis and `/research` (nonvoting, only for material open
questions) are never votes. One competent objection can block.

### Rung 1: CLI seats

| Seat (preference order) | Command |
|---|---|
| Codex | `ADVICE_CODEX_CMD`, else `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` |
| Opus | `ADVICE_CLAUDE_CMD`, else `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `ADVICE_CLAUDE_ALT_CMD`, else the Opus argv with `--model <actual-model>` |
| Cursor alternate | `cursor agent -p --force` |
| AGY alternate | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |
| Extra seats | `ADVICE_EXTRA_CLIS`, in listed order (unset by default) |

Start with Codex and Opus together; when one is known unavailable, start the next eligible seat alongside the
other. The order only decides which verdict fills a slot when several could: a later seat never displaces an
eligible earlier one. No slot is reserved for a particular label, so a quorum without Codex or Claude is valid once
those seats are genuinely exhausted.

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

### Rung 2: outside routes

As soon as the remaining CLI seats cannot fill every open slot (typically all are quota-walled, missing or void),
dispatch every authorized outside route at once (accounts within one route follow that route's order), without
waiting for static reviewers or asking the user to choose. Two outside votes from distinct identities are a full
quorum.

**Authorization is machine-local.** These routes send PR content off the machine, so this portable skill grants
nothing by itself. A route is authorized only when the machine's `ADVICE_OUTSIDE_ROUTES` lists it (a
comma-separated subset of `dot,hermes,web`, exported in that machine's `~/.bashrc`) or the current task explicitly
authorizes it. That opt-in is the standing authorization pr-lifecycle's optional-`/wa` rule and `/hermes`'s
disclosure rule require. Unlisted routes are `UNAVAILABLE — disclosure not authorized`, and so is any route when the
user, task or repository restricts external disclosure of the reviewed content, or the content holds secrets. (The
repository owner opted in on 2026-11-04: "when all cli reviewers out of quota ... it should try to use /wa and ask
hermes hermes pc and the dots in dot coordination for a review".)

The Dot route as a whole shares one §3 budget across its accounts, so trying accounts one at a time never delays the
static-reviewer rung by more than one budget.

| Route | Transport | Seats |
|---|---|---|
| Dot | the [`/dot` skill](../dot/SKILL.md), coordinator ask, `isolation: remote` | one Dot account at a time, in its configured `rotation` order (the Dots [dot-coordinator](../dot-coordinator/SKILL.md) is configured for), each addressed explicitly with `--account <name>`, never by automatic rotation; only when an account is busy, limited, blocked or timed out is it recorded `UNAVAILABLE` and the next account asked, matching pr-lifecycle's `/dot` rotation; the Dot route still runs concurrently with the other routes; revision review only |
| Hermes | the `/hermes` skill's Slack-only transport (host-installed; absent means `UNAVAILABLE`), coordinator ask, `isolation: remote`. **When the machine's `ADVICE_HERMES_CHANNEL` names a Slack channel (the owner's is `#dot-coordination`) and it is available to the sending identity, post there, one thread per Hermes instance;** otherwise use the conversation `/hermes` resolves | one per configured Hermes instance, for example the primary Hermes and `hermes-pc`, resolved from machine-local configuration; revision review only |
| Web advice | [`/web-advice`](../web-advice/SKILL.md) (user shorthand `wa`), `isolation: packet` for revisions, `none` for documents | one per authenticated provider and account; the orchestrator records the signed-in account from the web session as `attested.account` |

A reply is a vote only once it carries full-scope `COVERAGE:` and the SHA-bound `VERDICT:` line, read back at the
source. An acknowledgement, "on it", a reaction or a delegated-coder promise is `SENT`/`ACKNOWLEDGED` (per
`/hermes`), not a verdict. A missing transport (no Slack connector, no authenticated Dot profile, no reachable
browser, no configured Hermes) makes that route `UNAVAILABLE` with the exact blocker; never substitute a transport
its owning skill forbids.

### Rung 3: static reviewers

Static reviewers (an owner-authorized exception chosen on 2026-10-29) follow
[static-review](../static-review/SKILL.md) for identity, cold start, deadline and receipts. Launch them alongside
rung 2, or alongside rung 1 when no outside route is configured. A static vote fills only a slot still open after
every CLI seat and every outside route and account has ended under §3 (a quota wall ends a seat at once) and been
recorded as below. One outside vote may pair with one static vote. When a coordinator verdict is itself being
substituted by `/er` plus two `/advice` votes under pr-lifecycle, static reviewers cannot be that whole quorum; it
needs a real outside vote. A late objection still blocks and reopens the affected stage per pr-lifecycle.

### Identity

- One account is one vote, whatever its label, wrapper, alias or retry. Two seats whose commands reach the same
  account count once; an outside reviewer whose coder ran the account that just hit its quota is that account.
- A CLI seat must report the model it ran, or it is `UNAVAILABLE`. Outside routes report model and account as
  `attested.` values. Codex models may be only `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol` or `gpt-6.1-sol`.
- The orchestrator never awards itself a vote, and no verdict counts twice: a Dot account whose verdict fills the
  pr-lifecycle `/dot` leg at this head is not also an `/advice` vote.
- Run every seat with full permissions and record its actual command, model, account and transport.

Record every unavailable or skipped reviewer as `UNAVAILABLE: <host> — <reviewer> — attempted|skipped — <time> —
<reason>` and tell the user. A failure on one host (a cloud box) says nothing about the same CLI on another host (a
Mac or Ubuntu machine); try or record each host separately. When no rung yields two eligible votes, the result is
`WITHHELD`, listing every `UNAVAILABLE` line and the earliest known quota reset.

## 3. Enforce the attempt deadline

- **Budget `B`.** Each attempt gets 1800 seconds end to end (static reviewers: 600 seconds, per static-review) unless the user set a limit, shorter or longer, before
  dispatch. A specific user instruction to await a named reviewer overrides that attempt's deadline, even without
  a duration, per pr-lifecycle § Reviewer timeout and completion; record the instruction and the wait actually
  honoured in the receipt. A CLI attempt already running under a native timeout cannot have that timeout
  lengthened: when it expires, record it `TIMED_OUT` and keep the gate open for that reviewer instead of counting
  late output. Never preempt a valid in-deadline result, count late output, claim a wait that did not
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
  partial findings, record cleanup status, and use another eligible reviewer. Never reuse a resource whose process
  or cleanup state is unresolved, and never claim cleanup without receipt evidence.

## 4. Isolate review copies

The contract is one table. A receipt records exactly the row's `isolation:` value, and the review template's fields are
derived from the same row, so the two skills cannot drift apart.

| record | who clones | what the receipt must prove | who verifies | who deletes | template fields |
|---|---|---|---|---|---|
| `pin` (internal; never sent to a seat, never a seat's working directory) | orchestrator: clone the original checkout into allocated scratch with `--no-local`, check out `<SHA>`, fetch the base-branch tip from the PR remote | `donor_path`; `review_sha` = donor `HEAD`; `base_sha` = `git merge-base <SHA> <fetched base tip>`; `--git-common-dir` = `--git-dir`; `donor_removed` = `test ! -e <donor path>` | orchestrator | orchestrator, after the last seat clone is gone | none |
| `isolation: orchestrator-clone` | orchestrator: clone the donor into `<SCRATCH PATH>`, then `git remote remove origin` | `clone_path` = `<SCRATCH PATH>`; `cwd: set` or `attested.cwd: instructed`; at launch **and again after the seat process is gone**: `--git-common-dir` = `--git-dir`, `HEAD` = `review_sha`, `git merge-base --is-ancestor <BASE SHA> HEAD` exits 0, `git remote` is empty; then `clone_removed` = `test ! -e <SCRATCH PATH>` | orchestrator, every key except any `attested.` one | orchestrator, whatever the seat's outcome | `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` |
| `isolation: none` | nobody | `packet_path`; per-file SHA-256; `bundle_sha256`; `clone_path: none`; `clone_removed: n/a` | orchestrator | nobody; the packet is kept as evidence | `<PACKET PATH>` `<BUNDLE HASH>` |
| `isolation: remote` (Dot, Hermes) | nobody: the outside reviewer reads `<SHA>` from a checkout it already has (fetching only the missing objects, no new clone, no branch switch); the orchestrator clones nothing for it | `<SHA>` is reachable on the PR remote (`git ls-remote` or the PR API) both at send and at reply readback; route and message reference/permalink; the returned `VERDICT:` line names `<SHA>`; `attested.model`; `attested.account`; `attested.clone_path`; `clone_path: remote`; `clone_removed: n/a` | orchestrator, every key except any `attested.` one | the outside reviewer; never claimed | `<PR URL>` `<SHA>` `<BASE SHA>` |
| `isolation: packet` (`/web-advice` revision review) | nobody; the orchestrator writes a packet of the complete `git diff <BASE SHA>..<SHA>` plus the full post-change content of every changed file, from the `pin` donor, in place of `/web-advice`'s own `origin/main...HEAD` packet | `packet_path`; per-file SHA-256; `bundle_sha256`; every file delivered as an upload, not pasted inline; provider shows no truncation; `COVERAGE:` names every packet file; `clone_path: none`; `clone_removed: n/a` | orchestrator | nobody; the packet is kept as evidence | `<PR URL>` `<SHA>` `<BASE SHA>` `<PACKET PATH>` `<BUNDLE HASH>` |

- **The orchestrator owns every copy.** Seats never clone, delete or attest. The orchestrator creates each copy,
  verifies every key it can measure, and removes the copy once the seat process is confirmed gone, whatever the
  outcome. A failed check or failed removal voids that vote. A key it could not measure is written `attested.<key>`
  and never satisfies an orchestrator-verified cell.
- **Base.** `<BASE SHA>` is computed once, in `pin`; later checks use `git merge-base --is-ancestor <BASE SHA>
  HEAD` and never compare branch tips.
- **No seat gets a git remote.** Only `pin` uses the PR remote. Staying in `<SCRATCH PATH>` is an instruction, not
  a sandbox; the post-return checks detect a changed `HEAD` or remote and void the vote.
- **Unpushed SHAs** work for clone seats, which come from the local donor; if `<SHA>` is missing from the original
  checkout, `pin` fails and revision mode is `UNAVAILABLE`. Remote seats need `<SHA>` pushed and reachable: a
  verdict naming another SHA, or `<SHA>` becoming unreachable, voids the vote.
- **Document-only review** has no donor or clone: CLI, web and static seats use `none` (Dot and Hermes cannot
  read a local packet and are `UNAVAILABLE`), record `clone_path: none`, and never
  claims a clone or cleanup.
- **Host guards.** Clones live only in an allocated scratch directory, never `/tmp` (the scratch-routing guard
  refuses it), and deletion names the literal absolute path, never `rm -rf "$VAR"` (the destructive-path guard
  refuses it).
- **Not a sandbox.** Copy isolation protects Git metadata and review state, not the host's network, environment or
  processes. Full permissions do not authorize unrelated destructive actions, credential changes or publication.
  Before and after each attempt, check read-only that the original checkout, refs, local config and hooks are
  unchanged; any mutation voids that vote.

## 5. Reconcile and report

**Counting a vote.** A counted reviewer returns full-scope `COVERAGE:` and a nonempty `VERDICT:`. Its receipt shows
a zero exit, a present and parseable receipt, no mutation of the original checkout, no surviving reviewer process,
and no cleanup failure. A static-review receipt replaces only the exit field; an outside-route receipt (`remote` or
`packet`) replaces the exit, process and cleanup fields with that row's evidence. When a seat returns nonzero, ignore its
whole receipt, since a failed late rewrite can leave an older success-looking one. If clone setup timed out,
directory removal does not prove its descendants exited: record that and do not count the attempt.

**Verdict.** Reconcile disagreements within the declared scope yourself; do not ask the user to pick between
reviewers. A competent blocking objection, even from a partial-coverage reviewer, means `NOT APPROVED`; partial
coverage never supplies an approval. Without two independent full-coverage approvals from any rung, the result is
`WITHHELD`.

**Report.** Give the reviewed SHA (or `DOCUMENTS sha256:<bundle hash>`; never `HEAD`), each reviewer's verdict,
coverage, reasoning, risk and findings, the question's answer, and every `UNAVAILABLE` line. Keep a receipt per
attempt: identity, actual CLI, account and model, start and completion times, exit or timeout, the exact prompt
(any deviation voids the vote, per static-review), complete output, coverage and cleanup result. End with exactly
one line: `VERDICT: APPROVED at <SHA>`, `VERDICT: NOT APPROVED at <SHA>`, or `VERDICT: WITHHELD at <SHA> — <reason>`.

**Applicability.** Keep the original reviewers and reviewed SHAs. Before relying on them at a later head, inspect
the complete delta, claims, evidence and phase; applicability is not a new vote, and material uncovered changes
need affected independent review. Classify instruction changes by behaviour and contract effect, never by path.
Never claim approval, applicability or publication without its receipt.
