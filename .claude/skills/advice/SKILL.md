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
subagent seats) the static review prompt below verbatim, filling only
`<PR URL>` and `<SHA>`; for document-only review, use the packet path and
`DOCUMENTS sha256:<bundle hash>`. The orchestrator adds nothing else: no question, summary
or framing. The pointer must reach the complete change; a summary or excerpt
never replaces the source.

Static review prompt (skill-owned, verbatim):

```text
Review <PR URL> at head <SHA>. Ensure it follows the /prw stages and focus on
evidence review before approval. Report P0/P1/P2 with file:line; approve only
with no P0/P1; end with VERDICT: APPROVED|NOT APPROVED at <SHA>.
```

Each channel may prepend only its fixed, skill-owned preamble for mechanics.
The reviewer preamble below is used for CLI reviewers and subagent seats; the
coordinator preamble is the configured account mentions followed by `/advice
vote requested.` on its own line. Every receipt records the exact prompt sent;
any deviation from preamble plus template voids that vote.

Reviewer preamble (skill-owned, verbatim):

```text
Work in a fresh clone of the PR repository without an `origin` remote, pinned
to the given SHA. Use the GitHub token already present in your environment and
never print it. Do not modify the original checkout, refs, config or hooks. Do
not post anything; return your review as your final output.
```

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
two eligible CLI reviewers or per the subagent-seat fallback below. Use Codex
and Opus concurrently when both are viable; pair a healthy CLI vote with a
distinct eligible alternate when needed. If Opus is known unavailable, launch
Codex and an eligible alternate concurrently; do not serialize healthy seats.
The orchestrator's synthesis and research-only output are not approval
reviewers. `/research` is nonvoting and only for material unanswered questions.
One competent objection may block.

Subagent-seat fallback. This is an owner-authorized exception, chosen by the
repository owner on 2026-10-29. When the orchestrator also has an external
review coordinator (for example a Dot reviewer), it sends the coordinator
preamble plus the §1 static review prompt to each configured
coordinator account in rotation and, in parallel, launches adversarial review
subagent seats. A subagent seat fills only a vote slot still unfilled after the
primary and every alternate CLI attempt in the table below, and every
configured coordinator account, have ended under their §3 attempt deadlines.
Any outside full-coverage vote fills a slot first; one outside vote pairs with
one subagent seat.

No double substitution: when a coordinator verdict is itself being substituted
by `/er` plus two `/advice` votes under pr-lifecycle, subagent seats cannot
also be that whole quorum. That case needs a real outside vote or a third
distinct subagent seat. Consistent with pr-lifecycle, the orchestrator never
self-awards a vote, and one seat's verdict is never counted twice.

Seats must be distinct reviewer identities. Each seat reports its actual model;
if a model cannot be reported, the seats must differ by both subagent type and
harness. Each seat starts cold and blank, like a fresh terminal: no parent
context, summary or framing of the change. Its entire input is the reviewer
preamble plus the §1 static review prompt; the orchestrator writes nothing
else. The orchestrator, not the seat, timestamps launch and return; each seat
has one 600-second end-to-end acceptance deadline from launch, as in §3. Seats
run in separate contexts and do not read other seats' output first.

A subagent-seat receipt replaces the runner receipt. It records the seat
identity (type, harness and model), the exact SHA, orchestrator launch and
return times, the exact input sent (checked byte for byte against §1), a
`COVERAGE:` statement, the `VERDICT:` line, the clone path, and a read-only
check that the original checkout, refs, local config and hooks are unchanged.
It replaces the runner exit, surviving-process and cleanup fields; the
deadline, isolation, full coverage, SHA binding and §5 rules still apply. The
orchestrator publishes verdicts through pr-lifecycle; seats do not. A late
objection blocks until resolved and reopens the affected stage per
pr-lifecycle. Record each unavailable seat in the §5 report as `UNAVAILABLE:
<seat> — <attempt time> — <reason>`.

Preserve full-permission reviewer execution and declare the actual command,
model, account or reviewer identity, and transport for every attempt:

| Reviewer | Invocation form |
|---|---|
| Codex | `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` |
| Opus | `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `claude -p --model <actual-model> --dangerously-skip-permissions` |
| Claude wrapper alternate | `claudewa -p "<review request>" --dangerously-skip-permissions` |
| Cursor alternate | `cursor agent -p --force` |
| AGY alternate | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |

Each `<review request>`, and the stdin of forms without one, is exactly the
reviewer preamble plus the §1 static review prompt.
A wrapper, alias, retry, or duplicate reviewer identity is not another vote.
Codex models may be only `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, or
`gpt-6.1-sol`; 5.6 and unknown IDs are not eligible. Count `claudewa` only when
it resolves to a distinct reviewer identity and records the actual model. Each
alternate needs an existing supported invocation that bounds its complete
attempt and produces its own receipt; a per-process timeout alone is
insufficient. If no eligible path can meet the full bound, record it as
`UNAVAILABLE`. Do not add a particular runner, wrapper, watchdog, or runtime
mechanism.

## 3. Enforce the attempt deadline

Each reviewer attempt has one 600-second end-to-end acceptance deadline
beginning when the request is queued or sent. Record the start time. Shared
immutable packet preparation may precede the clock; review-specific setup,
queueing, delivery, dispatch, review, output capture, receipt writing, and
cleanup all consume the same budget. The deadline decides vote eligibility; it
is not a hard real-time guarantee that the process returns within 600 seconds.
Bound supported subprocesses and waits by the remaining time. Filesystem cleanup
and receipt writes may overrun if the operating system blocks; when they return,
the runner must record the overrun, exit nonzero, and invalidate every vote. A
missing or unparseable receipt, or any nonzero runner exit, makes the attempt
unavailable. Do not pause, reset, or extend the deadline, or add timer machinery.

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
full-scope `COVERAGE`. Reconcile disagreements within the declared scope; do not
ask the user to choose between reviewer axes. One competent blocking objection
means `NOT APPROVED`, including a competent objection from a reviewer with
partial coverage; partial coverage never supplies an approval. Use `WITHHELD`
when two independent full-coverage approvals, from eligible CLI reviewers or
per the subagent-seat fallback, are unavailable. A vote also
requires receipt evidence of zero exit, no original checkout mutation, no
surviving reviewer process, and no cleanup failure; a subagent-seat receipt
replaces the exit, process and cleanup fields as defined in §2. For the primary-pair runner, also require its zero exit, a present and parseable receipt, and a nonempty VERDICT line. Ignore the entire receipt when the runner exits nonzero; a failed late-receipt rewrite can leave an older success-looking receipt. If clone setup times out, directory-removal evidence does not prove setup descendants exited; record that uncertainty and do not count the attempt.

Report the exact reviewed SHA or `DOCUMENTS sha256:<bundle hash>` for
document-only review, with verdict, coverage, concise reasoning, risk, and
findings. Require `COVERAGE: <files/diff scope actually read>`. End with
exactly one SHA-bound line: `VERDICT: APPROVED at <SHA>`,
`VERDICT: NOT APPROVED at <SHA>`, or `VERDICT: WITHHELD at <SHA> — <reason>`.
For document-only review, use `DOCUMENTS sha256:<bundle hash>` in place of
`<SHA>`; never use `HEAD`. Preserve a receipt for every attempt: reviewer
identity, actual CLI, account and model, start/completion times, exit or timeout
status, exact prompt sent (any deviation from §1 voids the vote), complete
output, coverage, and cleanup result.
Preserve the original reviewers and reviewed SHAs.
Before applicability, inspect the complete actual delta, claims, evidence and phase.
Applicability is not a new independent vote.
Material uncovered changes require affected independent review.
Classify instruction changes by behavior and contract effect, never by directory or
path alone. Do not claim approval,
applicability, or publication without its supporting receipt.
