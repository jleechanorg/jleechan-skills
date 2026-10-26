---
name: advice
description: Use when a focused second opinion is needed; collect two independent, full-coverage reviewer votes on an exact change or saved-document bundle.
---

# /advice — independent second opinion

Use `/advice [question]` instead of `advisor()`. This skill owns reviewer
orchestration. [pr-lifecycle](../pr-lifecycle/SKILL.md) owns PR phases,
thresholds, applicability, and review publication. The applicable
evidence-standards skill owns evidence classes and publication rules. Do not
duplicate those procedures here.

## 1. Pin the question and complete scope

Write a focused decision question and give every reviewer the same exact
pointer: repository plus `base...head` and current head SHA, or an explicit
file list. Include `git diff --stat` and make the pointer reach the complete
change. A summary or excerpt never replaces the source.

For revision review, pin the requested commit and use an eligible clean
checkout. For saved specifications, plans, or other document-only reviews, use
an existing CLI input path to provide every reviewer the same complete Markdown
bytes, including uncommitted or untracked documents. Keep a temporary packet of
the named files and record per-file and bundle SHA256 hashes. Byte checks verify
integrity, not filesystem immutability. This Markdown skill does not require a
particular runner; do not add a wrapper or runtime mechanism to deliver files.

Document-only review excludes code outside the named files and never approves
`HEAD` or dirty code. Revision review covers the exact pinned code scope. Each
reviewer must independently read the entire declared scope; partial coverage
cannot be combined across reviewers to approve.

## 2. Select independent reviewers

Approval requires two independent votes, each covering the whole scope. They
may be two eligible CLI reviewers, or one eligible CLI reviewer plus eligible
Reviewer C (`/extended-library:secondo`). Use Codex and Opus concurrently when
both are viable; pair a healthy CLI vote with a distinct eligible alternate or
Reviewer C when needed. If Opus is known unavailable, launch Codex and an eligible
alternate concurrently; do not serialize healthy seats. Reviewer C counts only when
available, current and authorized, independent, and full-coverage. Follow the existing Secondo
AI Universe route; never substitute direct-provider calls. The orchestrator's
synthesis and `/research` are not votes; research is only for material
unanswered questions. One competent objection may block.

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

Each reviewer attempt has one 600-second end-to-end budget beginning when that
request is queued or sent. Record the start time. Shared immutable packet
preparation may precede the clock; all review-specific setup, queueing,
delivery, dispatch, review, output capture, receipt writing, and cleanup consume
the same budget. Do not pause, reset, or extend it; bound every call and wait by
the remaining time. Use existing CLI timeouts with native tool deadlines and
cancellation. If the supported route cannot enforce the complete attempt and
produce its receipt, mark it `UNAVAILABLE`; do not build timer machinery.

A late, incomplete, failed, or timed-out result is not an approval. Preserve
partial output and findings, record cleanup status, and use another independent
eligible reviewer when needed. Do not keep waiting for unresolved cleanup or
reuse a resource whose prior process or cleanup state is unresolved; continue
with another safe independent path when available. Never claim cleanup
succeeded without receipt evidence.

## 4. Isolate review copies

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
when two independent, full-coverage approvals are unavailable. A vote also
requires receipt evidence of zero exit, no original checkout mutation, no
surviving reviewer process, and no cleanup failure.

Report the exact reviewed SHA or `DOCUMENTS sha256:<bundle hash>` for
document-only review, with verdict, coverage, concise reasoning, risk, and
findings. End with exactly one SHA-bound line: `VERDICT: APPROVED at <SHA>`,
`VERDICT: NOT APPROVED at <SHA>`, or `VERDICT: WITHHELD at <SHA> — <reason>`.
For document-only review, use `DOCUMENTS sha256:<bundle hash>` in place of
`<SHA>`; never use `HEAD`. Preserve a receipt for every attempt: reviewer
identity, actual CLI, account and model, start/completion times, exit or timeout
status, complete output, coverage, and cleanup result. Keep prior reviewed SHAs
and receipts; assess later candidates under `pr-lifecycle/SKILL.md` and rerun affected review
for material scope or evidence changes. Do not claim approval, applicability,
or publication without its supporting receipt.
