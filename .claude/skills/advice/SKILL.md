---
name: advice
description: Use when a focused second opinion is needed; collect two independent, full-coverage reviewer votes on an exact change or saved-document bundle.
---

# /advice — independent second opinion

Use `/advice [question]` instead of `advisor()`. This skill owns reviewer
orchestration. The `pr-lifecycle` owner has the
[Advice applicability](../pr-lifecycle/SKILL.md#advice-applicability) section;
it owns phases, thresholds, applicability, and review publication. The
evidence-standards skill owns evidence classes and publication rules. Do not
duplicate those procedures here.

## 1. Pin the question and complete scope

**Pointer**: Send the pointer, not a transcription.
A verdict built on a truncated inline artifact may not be `APPROVED`.

Give every reviewer (CLI primary and alternates, the coordinator ask, and
static reviewers) only the cold, verbatim input owned by
[static-review](../static-review/SKILL.md): its channel preamble plus its
template, with no question, summary or framing. Its receipt and deviation rules
apply to every vote. The user's `[question]` is never sent to reviewers: the
orchestrator records it in the §5 report and answers it in its own synthesis
from the reviewers' findings; if the template cannot surface what the question
needs, report that gap rather than adding framing. The pointer must reach the complete change; a summary or
excerpt never replaces the source.

For revision review, pin the requested commit and use an eligible clean
checkout. For saved specifications, plans, or other document-only reviews, use
an existing CLI input path to give each reviewer identical complete bytes for
explicitly named, non-ignored, non-symlink Markdown files, committed or not.
Keep a temporary packet of the named files and record per-file and bundle
SHA256 hashes. Byte checks verify integrity, not filesystem immutability. This
Markdown skill does not require a particular runner; do not add a wrapper or
runtime mechanism to deliver files.

Document-only review excludes code outside the named files and never approves
`HEAD` or dirty code. Revision review covers the exact pinned code scope. Each
reviewer must independently read the entire declared scope.
The combined scope covers the whole declared change
only when each approver reads it in full. Partial coverage cannot be combined
across reviewers to approve.

## 2. Select independent reviewers

Approval requires two independent votes, each covering the whole scope, from
two eligible CLI reviewers or per the static-review fallback
below. Use Codex
and Opus concurrently when both are viable; pair a healthy CLI vote with a
distinct eligible alternate when needed. If Opus is known unavailable, launch
Codex and an eligible alternate concurrently; do not serialize healthy seats.
The orchestrator's synthesis and
research-only output are not approval reviewers. `/research` is nonvoting and
only for material unanswered questions. One competent objection may block.

Static-review fallback. This is an owner-authorized exception, chosen by the
repository owner on 2026-10-29. When the orchestrator also has an external
review coordinator (for example a Dot reviewer), it sends the static-review
coordinator ask and, in parallel, launches static reviewers. With no
coordinator configured, it launches static reviewers in parallel with the CLI
attempts, and the trigger below counts only those CLI attempts. A static reviewer
fills only a vote slot still unfilled after the primary and every alternate CLI
attempt in the table below, and every configured coordinator account, have
ended under their §3 attempt deadlines and each attempt or skip, including
unsupported or unconfigured routes, is recorded in the `UNAVAILABLE` format
below with the user told. Any outside full-coverage vote fills a
slot first; one outside vote pairs with one static reviewer. Identity, cold
start and receipts follow [static-review](../static-review/SKILL.md); the
deadline, isolation, full coverage, SHA binding and §5 rules still apply. A
late objection blocks until resolved and reopens the affected stage per
pr-lifecycle.

No double substitution: when a coordinator verdict is itself being substituted
by `/er` plus two `/advice` votes under pr-lifecycle, static reviewers cannot
also be that whole quorum; that case requires a real outside vote. Consistent
with pr-lifecycle, the orchestrator never self-awards a vote, and one
reviewer's verdict is never counted twice.

Record every unavailable or skipped reviewer in the §5 report as `UNAVAILABLE:
<host> — <CLI or static reviewer> — attempted|skipped — <attempt time> —
<reason>`, and tell the user which reviewers were unavailable. A failure on one
host (for example a cloud box) does not make the same CLI unavailable on
another host (for example a Mac or Ubuntu machine); try or record each host
separately.

Preserve full-permission reviewer execution and declare the actual command,
model, account or reviewer identity, and transport for every attempt.

### Portable defaults, machine-local overrides

This repository ships **defaults only**. Every seat resolves its command from an environment variable and
falls back to the default below when the variable is unset, so a bare machine still works. For any of these
variables, a value that is set but empty, unparseable, or names a program that is missing or not executable
makes **that seat `UNAVAILABLE`**; it never falls back to the default, because the fallback would run as the
default identity and let one account vote twice.

| Reviewer | Resolution |
|---|---|
| Codex | `ADVICE_CODEX_CMD` → `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` |
| Opus | `ADVICE_CLAUDE_CMD` → `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `ADVICE_CLAUDE_ALT_CMD` → the same default argv as Opus, with `--model <actual-model>` |
| Extra CLIs | `ADVICE_EXTRA_CLIS` (unset by default) |
| Cursor alternate | `cursor agent -p --force` |
| AGY alternate | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |

There is **no bundled runner**. This skill ships instructions only: the orchestrator launches each seat
itself - directly, in parallel - under the bounded-attempt, independence and receipt rules below, and records the
resolved command, model and credential-store label in that attempt's receipt. A seat whose command cannot be
resolved that way, or whose route cannot produce a full receipt, is `UNAVAILABLE` rather than a vote. Keeping
every alternative path in this instruction file is deliberate: the slimming decision for this skill is *markdown
only, zero runner code*, so a machine-local capability must never require a Python change to this repository.

**Machine-specific configuration never lives in this repository.****Machine-specific configuration never lives in this repository.** A credential store directory, a
profile directory, a per-host wrapper path, a host-specific model alias or an account identifier belongs in
that machine's `~/.bashrc` as an exported `ADVICE_*` value, never in a skill file, a PR or a document. This
file may name the shape of a runner (for example `claudewa`-style wrapper that selects another credential
store and records its model) but never a concrete path, digest or profile of any machine.

A label is not an identity: two seats whose resolved command reaches the same account are one vote, and a seat
whose model the CLI does not report is `UNAVAILABLE` rather than an unlabelled vote. A wrapper, alias, retry, or
duplicate reviewer identity is not another vote. Codex models may be only
`gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, or `gpt-6.1-sol`; 5.6 and unknown IDs are not eligible. A wrapper
such as `claudewa` counts only when it resolves to a distinct reviewer identity and the attempt records the
actual model it ran. Each alternate needs a supported invocation the orchestrator can bound end to end - the orchestrator's own
bounded tool call, which records the queue boundary, the absolute deadline, the exit and the cleanup, is that
mechanism; a bare per-process timeout with no receipt is insufficient. If no eligible path can meet the full
bound, record it as `UNAVAILABLE`. Do not add a particular runner, wrapper, watchdog, or runtime
mechanism.

### `ADVICE_EXTRA_CLIS`

Registers additional reviewer CLIs without editing this file. Format: seats separated by `|`, each
`<label>=<executable and literal arguments>`.

```
ADVICE_EXTRA_CLIS='gemini-cli=gemini --approval-mode yolo -p|local-qwen=qwen -p'
```

Rules:
- Seat separation is honoured **outside quotes**: scan the value with shell-style quoting, treat `|` as a separator
  only when it is not inside quotes, then for each seat take everything before the first unquoted `=` as the label
  and `shlex` the remainder as the executable plus literal arguments. A quoted argument may therefore contain `|` or
  `=` without breaking the parse.
- No shell evaluation, glob expansion, command substitution or `~` expansion beyond what the process
  environment already provides; quotes group one literal argument.
- `{prompt}` may appear as a whole token or inside a token (for example `--print={prompt}`); each occurrence is
  replaced by the request text, and only when no occurrence exists is the request appended as one final argument.
- An entry with an empty label, an empty right-hand side, a duplicate label, an unparseable remainder, or a missing
  or non-executable program makes **that seat `UNAVAILABLE`**. It never silently falls back to another seat and never
  becomes a second vote from the same identity another seat already used.

**Ordered preference per vote slot.** This order decides *which* seat fills a slot, never *when* it is launched:
§2 still requires launching the eligible candidates concurrently, and this list only resolves which candidate fills
the slot when more than one could. Fill each required slot from this order and stop at the first seat that produces
an eligible verdict: **Codex → Opus → Claude alternate → Cursor → AGY → `ADVICE_EXTRA_CLIS` in listed
order.** An extra seat is reached only when every earlier candidate for that slot is `UNAVAILABLE` or its verdict is
void; it never displaces a successful seat and never supplies the second vote for an identity another seat used.

The extra seats obey the same independence, deadline, evidence and receipt rules as the built-in ones, and the
ordering above governs them. No seat is "the required Codex vote" or "the required Opus vote" by label: what a vote
slot requires is one independent, eligible identity that covers the whole scope, so a quorum reached without a Claude
or Codex seat is valid when the ordering genuinely exhausted those candidates.

## 3. Enforce the attempt deadline

Each reviewer attempt has one default 1800-second (30-minute) end-to-end budget
beginning when that request is queued or sent. Record the start time. An
explicit user-specified limit governs that requested attempt, whether shorter or
longer; otherwise the 30-minute default applies. A later specific user
instruction to await a named reviewer overrides this deadline for that
requested attempt, even without a numeric duration. Shared immutable packet
preparation may precede the clock; review-specific setup, queueing, delivery,
dispatch, review, output capture, receipt writing, and cleanup all consume the
same budget. The deadline decides vote eligibility; it is not a hard real-time
guarantee that the process returns within the budget. Bound supported
subprocesses and waits by the remaining time. Filesystem cleanup and receipt
writes may overrun if the operating system blocks; when they return, the orchestrator
must record the overrun, report a nonzero attempt result, and invalidate every vote. A missing or
unparseable receipt, or any nonzero seat result, makes the attempt unavailable.
Routine status updates do not pause or reset the deadline. Apart from an
explicit user-specified limit or the named-review wait instruction above, do
not pause, reset, or extend it. Use existing CLI timeouts with native tool
deadlines and cancellation. If the supported route cannot enforce the complete
attempt and produce its receipt, mark it `UNAVAILABLE`; do not build timer
machinery.

The later named-review instruction remains controlling. The orchestrator computes one absolute deadline per
attempt from its own queued monotonic timestamp and records that deadline in the seat's receipt (never in the prompt, which must
stay byte-identical to preamble plus template); there is no
interface for extending an already-running attempt. A result completed with verified cleanup before that deadline
remains eligible. If a later user instruction would require waiting beyond it, the orchestrator cannot extend
that attempt: on actual expiry record it `TIMED_OUT` and non-approving, record cleanup, mark the requested wait
route `UNAVAILABLE`, and leave the applicable review gate open unless another already-supported route honours it.
Do not preempt a valid within-deadline result, reinterpret the instruction as a shorter limit, count late output,
claim a wait that did not happen, or issue a duplicate review.

Immediately before dispatch, once the shared review packet is ready, capture the queue boundary on the host that
will launch the seat, and record both timestamps in that seat's receipt:

```bash
read -r QUEUED_AT_EPOCH_NS QUEUED_AT_MONOTONIC_NS <<< "$(
  python3 -c 'import time; print(time.time_ns(), time.monotonic_ns())'
)"
```

Capture both values together on the caller host. The seat must run on that same host and boot, because monotonic
timestamps are host-local; retain the UTC epoch only for audit, and never compare monotonic values across hosts. If
the boundary cannot be captured, mark that attempt `UNAVAILABLE` instead of launching it.

For every seat, derive the effective reviewer-attempt budget `B` (the user's explicit limit when supplied,
otherwise 1800 seconds), a positive cleanup reserve `C`, and a positive timeout-grace `G`. **`C` and `G` must both
fit inside `B`, otherwise the seat is `UNAVAILABLE`** - never launch an attempt whose setup and cleanup cannot fit
its own budget. Launch the seat with a native timeout of `B - C` measured from the queue boundary, not from launch,
so setup time is already spent; reclaim cleanup inside `C`; and bound the wait by the same absolute deadline, so
`G` is the grace the wait itself may consume. Record the queue boundary, the absolute deadline and the actual exit
in the receipt. No timer machinery
is added to this repository; the orchestrator's own bounded tool call is the mechanism.

A late, incomplete, failed, or timed-out result is not an approval. Preserve
partial output and findings, record cleanup status, and use another independent
eligible reviewer when needed. Do not keep waiting for unresolved cleanup or
reuse a resource whose prior process or cleanup state is unresolved; continue
with another safe independent path when available. Never claim cleanup
succeeded without receipt evidence.

## 4. Isolate review copies

Every revision-mode receipt records exactly one `isolation:` value.

- **`isolation: orchestrator-clone` — local CLI seats whose working directory can be set.** The orchestrator builds one
  donor at the review SHA with standalone git metadata (never a linked worktree), verifies `--git-common-dir` equals
  `--git-dir`, `HEAD` equals the review SHA, the base resolves to its recorded SHA and that base commit object is
  present, then creates one clone per seat in that seat's allocated scratch directory (never `/tmp`, never inside a
  repository tree), with no `origin` remote. It re-runs those three checks on **each seat clone**, sets the clone as
  that seat's working directory, records the path, and afterwards deletes every clone by its literal absolute path and
  verifies the removal. A failed or unverified removal voids the vote.
- **`isolation: self-clone` — seats on this host with no working-directory parameter (a static-review subagent).** The
  orchestrator allocates one empty scratch directory per seat and passes the remote URL, the review SHA **and** the
  recorded base SHA in the launch context. The seat clones into exactly that directory, fetches **both** commits, and
  proves `rev-parse HEAD` equals the review SHA and `cat-file -e <base>^{commit}` succeeds with the merge-base equal to
  the recorded base - never the remote's current default branch. It records `git remote -v` before removing `origin`,
  records the absolute path, deletes the clone by that literal path before returning, and states `clone_removed: true`.
  The orchestrator counts the vote only when the path, the `remote -v` record, both SHA attestations and the removal
  statement are present **and** that path is absent from its own filesystem afterwards. The copy's provenance stays
  self-attested, exactly like the seat's VERDICT, and the receipt says so.
- **`isolation: none` — document-only mode.** No donor and no clone: the orchestrator supplies the named Markdown files
  as saved bytes with per-file and bundle SHA256 hashes, each seat reads only those, and the receipt records
  `clone_path: none`, `clone_removed: n/a`.

**Eligibility.** Revision mode is available to the first two records only. A route that can neither take a working
directory nor clone on this host - a remote coordinator ask - is `UNAVAILABLE` for revision mode with the failing
condition named, and remains eligible for document-only mode. An unpushed SHA cannot use `self-clone`, because the
remote cannot serve it.

**The donor is internal staging.** It is never a seat's working directory, never inside a clone, never shared between
seats, and it is removed after the attempt. Only `orchestrator-clone` consumes it; `self-clone` binds to the same
recorded SHAs by attestation, so both routes review the identical base.

**Host guards are part of the contract.** Clones live only in an allocated scratch directory, never `/tmp`, because
the scratch-routing guard refuses `/tmp` workspaces; deletion always names the literal absolute path, never a computed
`rm -rf "$VAR"`, because the destructive-path guard refuses that form. A seat that cannot delete cleanly records
`clone_removed: false` and its vote does not count.

**Document-only mode.** No donor and no clone: the orchestrator supplies the named Markdown files as saved bytes
with per-file and bundle SHA256 hashes, and each seat reads only those. Record `none` for the clone path, and never
claim a clone was made or cleaned up. Unrelated code stays outside the review scope in both modes.

Copy isolation protects Git
metadata and review state, not the host: it is not an OS sandbox and does not
restrict network, environment, or process creation. Full-permission execution
preserves the requested reviewer transport; it does not authorize unrelated
destructive actions, credential changes, or publication. Before and after each
attempt, use the available receipt or read-only checks to verify the original
checkout, refs, local config, and hooks are unchanged; any detected mutation
invalidates that vote.

## 5. Reconcile and report

Require each counted reviewer to return a nonempty `VERDICT:` and explicit
full-scope `COVERAGE`. Reconcile disagreements within the declared scope; do
not ask the user to choose between reviewer axes. One competent blocking
objection means `NOT APPROVED`, including a competent objection from a reviewer
with partial coverage; partial coverage never supplies an approval. Use
`WITHHELD` when two independent full-coverage approvals, from eligible CLI
reviewers or per the static-review fallback, are unavailable. A vote also
requires receipt evidence of zero exit, no original checkout mutation, no
surviving reviewer process, and no cleanup failure; a static-review receipt
replaces only the seat-exit field. For every launched seat, also require a zero
result, a present and parseable receipt, and a nonempty VERDICT line. Ignore the entire receipt when the seat
returns nonzero; a failed late-receipt rewrite can leave an older success-looking receipt. If clone setup times out,
directory-removal evidence does not prove setup descendants exited; record that
uncertainty and do not count the attempt.

Report the exact reviewed SHA or `DOCUMENTS sha256:<bundle hash>` for
document-only review, with verdict, coverage, concise reasoning, risk, and
findings. Require `COVERAGE: <files/diff scope actually read>`. End with
exactly one SHA-bound line: `VERDICT: APPROVED at <SHA>`,
`VERDICT: NOT APPROVED at <SHA>`, or `VERDICT: WITHHELD at <SHA> — <reason>`.
For document-only review, use `DOCUMENTS sha256:<bundle hash>` in place of
`<SHA>`; never use `HEAD`. Preserve a receipt for every attempt: reviewer
identity, actual CLI, account and model, start/completion times, exit or timeout
status, exact prompt sent (any deviation voids the vote, per static-review),
complete output, coverage, and cleanup result.
Preserve the original reviewers and reviewed SHAs.
Before applicability, inspect the complete actual delta, claims, evidence and phase.
Applicability is not a new independent vote.
Material uncovered changes require affected independent review.
Classify instruction changes by behavior and contract effect, never by directory or
path alone. Do not claim approval,
applicability, or publication without its supporting receipt.
