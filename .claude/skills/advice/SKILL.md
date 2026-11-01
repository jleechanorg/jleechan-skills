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
falls back to the default below when the variable is unset, so a bare machine still works:

| Reviewer | Resolution |
|---|---|
| Codex | `ADVICE_CODEX_CMD` → `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` |
| Opus | `ADVICE_CLAUDE_CMD` → `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `ADVICE_CLAUDE_ALT_CMD` → the same default argv as Opus, with `--model <actual-model>` |
| Extra CLIs | `ADVICE_EXTRA_CLIS` (unset by default) |
| Cursor alternate | `cursor agent -p --force` |
| AGY alternate | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |

The Codex and Opus lanes of `scripts/run_primary_pair.py` honour `ADVICE_CODEX_CMD` and `ADVICE_CLAUDE_CMD`
directly: the value is split with `shlex` (never shell-evaluated) and **replaces the whole default argv** - it is
a complete command line, never a prefix that the runner extends, so a value that omits `--model` runs the CLI's
own default. The receipt records the resolved argv (not the canonical label) and the model read from `-m`/`--model`
in that argv, so an override that names an ineligible Codex model or hides its model makes the seat
`UNAVAILABLE` instead of silently voting. A
wrapper that selects another credential store runs as that seat and its resolved command is what the receipt
records. A variable that is set but empty, unparseable, or names a missing or non-executable program makes that
seat `UNAVAILABLE`; it never falls back to the default, because falling back would let one account cast two
votes. The pair runner accepts the Codex and Opus lanes only, so `ADVICE_CLAUDE_ALT_CMD` and `ADVICE_EXTRA_CLIS`
seats are launched directly by the orchestrator under the same bounded-attempt and receipt rules.

**Machine-specific configuration never lives in this repository.** A credential store directory, a
profile directory, a per-host wrapper path, a host-specific model alias or an account identifier belongs in
that machine's `~/.bashrc` as an exported `ADVICE_*` value, never in a skill file, a PR or a document. This
file may name the shape of a runner (for example `claudewa`-style wrapper that selects another credential
store and records its model) but never a concrete path, digest or profile of any machine.

A label is not an identity: two seats whose resolved command reaches the same account are one vote, and a seat
whose model the CLI does not report is `UNAVAILABLE` rather than an unlabelled vote. A wrapper, alias, retry, or
duplicate reviewer identity is not another vote. Codex models may be only
`gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, or `gpt-6.1-sol`; 5.6 and unknown IDs are not eligible. A wrapper
such as `claudewa` counts only when it resolves to a distinct reviewer identity and the attempt records the
actual model it ran. Each alternate needs an existing supported invocation that bounds its complete attempt
and produces its own receipt; a per-process timeout alone is insufficient. If no eligible path can meet the
full bound, record it as `UNAVAILABLE`. Do not add a particular runner, wrapper, watchdog, or runtime
mechanism.

### `ADVICE_EXTRA_CLIS`

Registers additional reviewer CLIs without editing this file. Format: seats separated by `|`, each
`<label>=<executable and literal arguments>`.

```
ADVICE_EXTRA_CLIS='gemini-cli=gemini --approval-mode yolo -p|local-qwen=qwen -p'
```

Rules:
- Split on `|`, then on the **first** `=`; the label is the seat name used in the receipt, the right side is
  an executable plus literal arguments tokenized with `shlex`, exactly like the built-in seats. No shell
  evaluation, glob expansion, command substitution or `~` expansion beyond what the process environment
  already provides; quotes group one literal argument.
- The review request is appended as one final argument. If the right side contains `{prompt}`, that token is
  replaced by the request text instead and nothing is appended.
- An unparseable entry, an empty label, or an executable that is not found makes that seat `UNAVAILABLE`; it
  never silently falls back to another seat and never becomes a second vote from the same identity.
- These seats obey the same independence, deadline, evidence and receipt rules as the built-in ones. Extra
  seats never replace the required Claude or Codex vote: they fill an unfilled slot only when the built-in
  seat is genuinely unavailable.

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
writes may overrun if the operating system blocks; when they return, the runner
must record the overrun, exit nonzero, and invalidate every vote. A missing or
unparseable receipt, or any nonzero runner exit, makes the attempt unavailable.
Routine status updates do not pause or reset the deadline. Apart from an
explicit user-specified limit or the named-review wait instruction above, do
not pause, reset, or extend it. Use existing CLI timeouts with native tool
deadlines and cancellation. If the supported route cannot enforce the complete
attempt and produce its receipt, mark it `UNAVAILABLE`; do not build timer
machinery.

The later named-review instruction remains controlling. The current
`run_primary_pair.py` route computes `attempt_deadline` and `work_deadline` once
from the queued monotonic timestamp and timeout flags; it then fixes each
reviewer's deadline and passes it to the subprocess wait. There is no existing
interface to extend an active attempt. A result completed with verified cleanup
before that fixed deadline remains eligible. If fulfilling the later user
instruction would require waiting beyond the deadline, this route cannot extend
it: only on actual expiry record the attempt `TIMED_OUT` and non-approving, wait
for and record cleanup, mark the requested wait route `UNAVAILABLE`, and leave
the applicable review gate open unless another already-supported route can
honor it. Do not preempt a valid within-deadline result, reinterpret the
instruction as a shorter limit, count late output, claim the primary pair
waited for the requested interval, or issue a duplicate review. This records a
runner capability boundary; it does not cancel or shorten the user's
instruction.

Immediately before dispatch, after the shared review packet is ready, capture
the queue boundary and pass both timestamps to the primary-pair runner. If the
timestamp cannot be captured, mark that attempt unavailable instead of invoking
the runner:

```bash
read -r QUEUED_AT_EPOCH_NS QUEUED_AT_MONOTONIC_NS <<< "$(
  python3 -c 'import time; print(time.time_ns(), time.monotonic_ns())'
)"
```

Capture both values together on the caller host. The runner must execute on
that same host and boot because monotonic timestamps are host-local. Retain the
UTC epoch only for audit; cross-host orchestration must account for its outer
budget separately and never compare monotonic values across hosts.

Pass both required runner options:

```bash
--queued-at-epoch-ns "$QUEUED_AT_EPOCH_NS" \
--queued-at-monotonic-ns "$QUEUED_AT_MONOTONIC_NS" \
```

For `run_primary_pair.py`, also pass both timeout limits explicitly on every
invocation. Let `B` be the effective reviewer-attempt budget: the user's
explicit limit when supplied, otherwise 1800 seconds. Let `C` be a positive
cleanup reserve smaller than `B`, and let `G` be the positive timeout-grace
period. Set `--attempt-timeout-seconds` to `B`, `--timeout-seconds` to `B - C`,
`--cleanup-budget-seconds` to `C`, and `--timeout-grace-seconds` to `G`. The
runner starts the attempt clock at the queued timestamps, reserves `C` for
cleanup and receipt work, then bounds each reviewer by the remaining work
deadline and `G`. Its built-in 600-second attempt and 1200-second reviewer
defaults do not implement this policy; do not omit either timeout flag. If the
requested budget cannot leave room for both cleanup reserve and grace, report
the route `UNAVAILABLE` instead of silently changing the user's limit.

| Effective budget `B` | Cleanup reserve `C` | `--attempt-timeout-seconds` | `--timeout-seconds` |
|---:|---:|---:|---:|
| 300 seconds (explicit) | 10 seconds | 300 | 290 |
| 1800 seconds (default) | 10 seconds | 1800 | 1790 |
| 2700 seconds (explicit) | 10 seconds | 2700 | 2690 |

A late, incomplete, failed, or timed-out result is not an approval. Preserve
partial output and findings, record cleanup status, and use another independent
eligible reviewer when needed. Do not keep waiting for unresolved cleanup or
reuse a resource whose prior process or cleanup state is unresolved; continue
with another safe independent path when available. Never claim cleanup
succeeded without receipt evidence.

## 4. Isolate review copies

Before taking snapshots for a revision review, materialize the requested commit
in a standalone donor repository with independent Git metadata; do not use a
linked worktree. Verify the donor's Git directory is a real directory,
`git rev-parse --git-common-dir` resolves to the same directory as
`git rev-parse --git-dir`, its `HEAD` equals the requested review SHA, and the
required base resolves to its recorded SHA. Run the existing revision-review
workflow from that donor so its original-checkout, ref, config, and hook
mutation checks continue to apply to the donor. Document-only reviews retain
the existing named saved-Markdown-byte overlay and per-file/bundle hash checks;
they require no donor, commit, or Git context SHA.

Use independent temporary clones without an `origin` remote. For revision
reviews, pin each clone to the same exact SHA. For document-only reviews,
overlay only the explicitly named Markdown files as saved bytes in those copies;
unrelated code stays outside the review scope. Copy isolation protects Git
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
replaces only the runner exit field. For the primary-pair runner, also require
its zero exit, a present and parseable receipt, and a nonempty VERDICT line.
Ignore the entire receipt when the runner exits nonzero; a failed late-receipt
rewrite can leave an older success-looking receipt. If clone setup times out,
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
