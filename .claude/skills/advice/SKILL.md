---
name: advice
description: "Token-efficient second opinion /advice. Extracts a decision and change pointer, runs the Codex + Opus CLI primary pair concurrently where available, and uses eligible independent CLI reviewers to reach the mandatory two-vote quorum. Reviewer attempts are bounded to 600 seconds. /research is nonvoting; /extended-library:secondo is an eligible approval reviewer. Use instead of advisor() which ships the full conversation uncached."
---

# /advice — Token-Efficient Second Opinion

**Replaces `advisor()`. Never call advisor() — use this instead.**

For PR lifecycle applicability, follow `pr-lifecycle` § Advice applicability;
its size exception does not change this command's reviewer quorum when it runs.
Record each run under that owner's Review records in the PR description contract.

## When invoked

`/advice [optional: specific question]` — invoked manually or automatically at a decision point.

## Step 1: Build the review packet

From the current conversation, extract:
- **Decision** (3–5 sentences): what specifically needs a second opinion — be concrete about constraints and tradeoffs
- **Pointer**: where the reviewer can read the change *itself* — a PR number, a `base...head` ref, or an explicit file-path list. Include `git diff --stat` (or `gh pr diff --name-only`) so the reviewer sees the shape of what it is about to read.

If no specific question was passed, infer from most recent context.

**Send the pointer, not a transcription.** Every reviewer transport in Step 2 is an *agent* that can read the repo for itself — Codex and Opus run in independent exact-SHA clones, `cursor -p` has access to write and shell tools, `agy`/`claude -p` run with permissions pre-approved, and `/secondo` gathers its own `git diff origin/main...HEAD`. Handing them a pre-chewed excerpt does not save them a fetch; it *removes* their ability to look. Give the pointer and let each one pull the context it decides it needs.

### The inline-artifact fallback (≤150 lines) — narrow, and it caps the verdict

Inline an artifact only when the reviewer genuinely cannot fetch: no repo access, no PR, or the subject is not in version control (a plan, a pasted stack trace, an architecture sketch). Then keep it under ~150 lines.

**A verdict built on a truncated inline artifact may not be `APPROVED`.** Record `REVIEWED: <n> of <total> lines (<what was omitted>)`, carry it into the synthesis, and emit `WITHHELD` — see Quorum. This is not a formality: across the last 300 merged PRs in `jleechanorg/worldarchitect.ai`, **65% exceed 150 changed lines** (median 349), and for those, a 150-line cap shows a reviewer a median **22.5%** of the diff. A gate that says `APPROVED at <SHA>` after seeing a fifth of the change is asserting something it did not check.

## Document-only review (including /sq plans)

For saved specifications or plans, add repeated `--document <repo-relative-path.md>`
arguments to the same primary-pair runner. Read the complete documents; do not truncate
them to the inline-artifact limit. Documents may be committed, staged, modified, or
untracked. No commit, stash, clean checkout, or publication is required for this mode.
The runner overlays only explicitly named, non-ignored, non-symlink Markdown documents
into each independent reviewer clone, records their SHA256 hashes and bundle identity,
and checks that source and reviewer copies remain unchanged. HEAD is context only;
unrelated uncommitted code is outside this review and is not approved.

Preserve normal reviewer selection, quorum, coverage, authorization, and failure rules.
Bind the final verdict to `DOCUMENTS sha256:<document_bundle_sha256>` plus the per-file
hashes in the receipt. This is document approval only, never `APPROVED at <HEAD>` for
code or a PR. Save the synthesis with the local review receipt; the PR/commit publication
section below applies only to revision reviews. External publication still requires
applicable user authority. If a selected document changes, re-review its new bytes.

## Step 2: Fan out the reviewers in parallel

**Size/risk gate first.** For low-risk diffs (docs/tests/config-only, or under ~100 changed production lines with no schema/security/prompt-contract surface), the concurrent Codex + Opus primary pair is sufficient when both return independent, full-coverage verdicts; skip B/C. Reserve the full A+B+C fan-out for diffs touching production behavior, schemas, security, or above that threshold. Whenever `/advice` runs, `APPROVED` still requires two independent, full-coverage approval votes. The quorum, coverage, and inline-artifact rules below apply unchanged regardless of which lanes run.

Before dispatch, use existing quota/session receipts and non-model capability
checks to identify viable reviewers and whether they can meet the approval quorum.
Do not spend a separate paid model call solely to probe quota; when availability is
unknown, launch selected review lanes concurrently. Independent CLI reviewers
and Reviewer C may vote. `/research` seats, including Gemini, may inform the
synthesis but never substitute for a quorum vote.

Dispatch independent eligible reviewers concurrently where practical. If a primary seat is unavailable, fails, or times out, dispatch an eligible independent reviewer when needed to reach two votes. Do not serialize healthy reviewer attempts; sequential dispatch is only for a replacement after an earlier attempt failed or timed out. Eligible executions are `claude`, `claudewa`, `codex`, `agy`, and Cursor (`agent` / `cursor agent`). Declare the actual CLI, account or reviewer identity, and model for every execution. A wrapper, alias, retry, or second call does not create another vote when it represents the same execution or reviewer; record each distinct execution separately. Independent CLI reviewers and Reviewer C may vote. `/research` seats, including Gemini, may inform the synthesis but never substitute for a quorum vote. **C depends on personal infrastructure** and is skipped, not faked, when unavailable.

---

**Reviewer A — Primary pair, in parallel when the full-budget invocation is available:**

**Codex + Opus run concurrently when both are available.** Each reviewer reads
the change independently and returns its own verdict. If either seat is unavailable
or fails, continue with another eligible CLI execution on an independent clone so
the final review can still reach two independent votes. Dispatch healthy reviewers
concurrently; do not wait for one healthy reviewer before starting another.

Use the same review packet for both reviewers:

Before invoking the existing primary-pair runner, verify that the specific
supported invocation bounds the complete attempt to its remaining 600-second
budget, including queueing, setup, dispatch, review, output capture, receipt
recording, and cleanup. Its legacy per-reviewer timeout or default timeout does
not prove that whole-attempt bound. If no existing invocation can enforce it,
mark the primary runner unavailable and use another independently bounded,
eligible reviewer path; do not count that runner's output as an approval. Do not
add a wrapper or implementation to impose the limit. A missing primary vote may
be paired with a separately bounded eligible CLI reviewer; it never shares or
inherits another reviewer's vote.

After the shared review packet is ready, capture the queue boundary immediately
before dispatch and pass it to the runner. The timestamp is mandatory; if it
cannot be captured, mark the primary attempt unavailable rather than invoke the
runner without it:

```bash
read -r QUEUED_AT_EPOCH_NS QUEUED_AT_MONOTONIC_NS <<< "$(
  python3 -c 'import time; print(time.time_ns(), time.monotonic_ns())'
)"
```

These timestamps are captured together on the caller host. The runner must execute on that same host and boot because monotonic values are host-local. UTC epoch time is retained for audit only. Cross-host orchestration tracks its own outer budget separately; do not compare monotonic timestamps from different hosts.

Add this required option to the runner command:

```bash
--queued-at-epoch-ns "$QUEUED_AT_EPOCH_NS" \
--queued-at-monotonic-ns "$QUEUED_AT_MONOTONIC_NS" \
```

```
You are a senior engineer giving a focused second opinion.

DECISION:
[decision, 3–5 sentences]

WHAT TO REVIEW:
[PR number / base...head ref / file-path list, plus diff --stat]

Read the change yourself — do not rely on any summary in this prompt.
Read as much of it as your judgment requires. If you could not read
what you needed, say so in COVERAGE rather than guessing.
Apply `/ponytail` (`~/.claude/skills/ponytail/SKILL.md`): reject parallel-module
duplication (re-implementing an existing pipeline in a new module), post-hoc
undo / mutate-then-reverse-diff machinery (mutating shared state before
preconditions or persistence succeed and building an inverse-diff engine instead
of staging before merge), and additive compensator accretion across review
rounds (never demand round-trip preservation of malformed legacy wrappers when
canonicalizing at the ingestion boundary suffices).

Return exactly:
VERDICT: [recommended approach, one line]
REASONING: [3–4 sentences]
RISK: [main risk, one sentence]
COVERAGE: [what you actually read; note anything you could not reach]
CONFIDENCE: [high / medium / low]
```

Write the packet to a temporary file before starting each reviewer attempt.

Create `$ADVICE_TMP/review-packet.txt` before invoking the runner. The output
directory is deliberately outside the repository and must be a fresh path that
does not already exist. The runner atomically reserves that path and exits 2
before dispatch if it already exists, preserving its contents; create a new
results directory for every invocation. Read `codex.txt`, `opus.txt`,
and `receipt.json`; the receipt records the resolved SHA, each transport, launch
times, each clone SHA, cleanup status, and any changed original-repository
fingerprint components. The
input checkout must be clean, including untracked files, for revision reviews only.
For document-only review, use `--document` as described above; that mode accepts saved
documents regardless of their commit status. The runner refuses a
dirty checkout because those changes are not represented by the requested SHA.

The runner creates two independent disposable clones with `git clone --no-local`,
removes their `origin` remotes, and detaches both at the exact same SHA. It then
starts A1 and A2 behind one concurrency barrier, gives them disjoint output
files, and removes the clones afterward. It preserves the requested
full-permission transports explicitly: `codex exec --yolo` for A1 and
`claude -p --model opus --dangerously-skip-permissions` for A2. Independent
clones prevent reviewer writes to refs, config, or hooks from sharing the
original repository's `.git` state; they are deliberately **not** an OS security
sandbox. If the original checkout, refs, local config, or hooks change, the
runner fails closed and its verdicts may not be used.

While each reviewer root is alive, the runner samples the macOS/Linux process
tree, retains PID plus process-start identity for discovered descendants even
after reparenting, and on timeout terminates those descendants before/with the
root process group. The receipt lists discovered, signaled, and surviving PIDs
plus whether termination was verified. Bounded drain then guarantees that a
remaining inherited pipe cannot block runner return or clone cleanup.

This lifecycle supervision does not change full-permission mode and is not an
OS sandbox: it does not restrict network, environment, or process creation. An
arbitrary daemon that forks, reparents, and disappears from the sampled lineage
before the first observation can evade user-space process-tree tracking. For
descendants observed while the reviewer root is alive, a surviving verified PID
is recorded as a termination failure rather than silently treated as contained;
after successful cleanup the runner exits 7 even if the peer returned a verdict.

Each reviewer attempt has a hard 600-second end-to-end limit, starting when
that reviewer request is queued or sent. Record that timestamp. Queueing and
delivery, review-specific setup, dispatch, review, output capture, receipt
recording, and cleanup all consume the same wall-clock budget; do not pause,
reset, or extend it. Shared immutable packet preparation may happen before the
attempt begins. Bound each transport call and poll/wait to the time remaining in
the attempt.

Use existing supported execution tools. Do not create an adapter, supervisor,
watchdog, helper script, or embedded executable implementation to meet this
limit. If no available execution path can enforce the complete bound, record
that reviewer as unavailable and continue with another eligible reviewer. A
timed-out, failed, incomplete, or over-deadline attempt is never an approval
vote. Do not start a replacement in a resource whose prior execution or cleanup
state is unresolved; record the uncertainty and continue with an independent
eligible path when safe.

For every attempt, retain a record with the pinned SHA, reviewer identity,
actual CLI/account and model, queued/sent and completion times, elapsed time,
exit or timeout status, complete output and coverage, and available cleanup
result. Preserve timeout output and any partial receipt. Do not claim cleanup
succeeded without evidence. Once an attempt times out or fails, dispatch the next
eligible independent reviewer; keep healthy reviewers concurrent where
practical. Any unresolved process or cleanup state remains disclosed and cannot
be counted as an approval.

An exit code of zero is not enough: each successful lane must return a nonempty
line beginning with `VERDICT:`. Empty or malformed output records
`missing_verdict` and counts as an errored lane. A primary vote is usable only
when the runner exits zero, the receipt exists and parses, the process exits
zero, the lane returns a nonempty `VERDICT:` line, and the receipt shows no
original-checkout mutation, surviving reviewer process, or cleanup failure.
Ignore every receipt when the runner exits nonzero; a failed late-receipt rewrite
can leave an older success-looking receipt on disk. Setup-timeout cleanup status
covers removal of the disposable clone directory, not process-tree verification
for setup subprocess descendants; record that uncertainty and do not count the
attempt. If either primary lane fails
to return a recognizable verdict, use an eligible alternate reviewer when
needed to reach two independent full-coverage votes. The primary runner only
launches and supervises Codex and Opus; it does not launch, time, or receipt
alternate CLI executions. For each alternate, create a separate disposable
clone detached at the same reviewed SHA, remove its origin remote, run the
selected full-permission CLI in that clone, and remove the clone afterward.
Retain a receipt with the resolved SHA, reviewer identity and model, exact CLI
transport, dispatch/start/end times, timeout or exit status, complete verdict
and coverage, and clone cleanup result. If the clone cannot be cleaned up, do
not use that attempt as approval evidence.

**A1 — Codex CLI (primary):** `codex exec --yolo -m gpt-6-sol --config
model_reasoning_effort=high`. The explicit command guarantees full-permission
mode without relying on wrapper internals. Only the exact catalog IDs
`gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, and `gpt-6.1-sol` are accepted;
5.6 and unknown model IDs are forbidden.

**A2 — Opus CLI (primary):** `claude -p --model opus
--dangerously-skip-permissions`. It is dispatched concurrently with A1, not
after A1 returns.

**Alternate reviewer executions (when a primary vote is missing):**

Run eligible reviewers as needed until there are two independent, full-coverage
votes or every viable option has failed or timed out. An alternate vote may
pair with a successful Codex or Opus vote; alternates are not restricted to the
case where both primary lanes fail. Preserve concurrent Codex + Opus dispatch
when both are viable. Use the following CLI forms, adapting only model and
identity settings needed to declare the actual execution:

**`claude -p` or `claudewa -p`:**
```bash
claude -p --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
For `claudewa`, invoke the existing wrapper and pass the same packet; record
the actual account/profile and resolved model. Do not count `claude` and
`claudewa` as independent votes when they are merely aliases or duplicate
execution of the same reviewer. Distinct executions count only when each has
its own reviewer identity/model declaration, independent clone, output, and
receipt. Do not use `--cwd /tmp` if it would replace the required clone cwd.

**Cursor (`cursor agent -p` or the `agent` wrapper):**
```bash
cursor agent -p --force "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```

**`agy`:**
```bash
agy --print --model gemini-3.8-flash-high --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
Note: agy is the Antigravity CLI (reads CLAUDE.md on startup like any CC session, but starts fresh — no current conversation history). Independent perspective, slightly slower than cursor. When selecting Gemini models, never use `gemini-3.1-pro` (or older Gemini Pro models); always use `gemini-3.8-flash` or later (`gemini-3.8-flash-high`).

All attempts must use the same pinned review scope and independent clones. Do
not reuse one execution's result under another CLI name. If fewer than two
independent full-coverage votes succeed after viable options are attempted,
record each unavailable, failed, or timed-out reviewer and emit `WITHHELD` (or
`NOT APPROVED` if any competent reviewer blocks).

Every attempt, primary or alternate, must fit the same deadline and produce
its own receipt. A single surviving primary or alternate vote can block, but
cannot approve.

---

**Reviewer B — Research:**

Invoke `/research [decision topic distilled to 6 words]`

---

**Reviewer C — Secondo (optional — needs infrastructure):**

Invoke `/extended-library:secondo` with the decision and declared review scope, and let it gather
its own context — it already captures `git diff origin/main...HEAD` under its own
budget (`SECOND_OPINION_MAX_DIFF_CHARS`, default 32,000 chars). Require
`COVERAGE: <files/diff scope actually read>` in its response. Do **not** hand it
a ≤150-line extract instead; that throttles it to a fraction of the context it
would have collected on its own.

Requires the AI-Universe MCP endpoint (`AI_UNIVERSE_MCP_ENDPOINT`) and its OAuth flow. `/extended-library:secondo` bans substituting WebSearch or direct provider MCPs, so there is no portable fallback — if the endpoint is unreachable, mark **C unavailable** and continue.

---

## Step 3: Synthesize

Present:

```
| Reviewer    | Verdict              | Key concern         | Confidence |
|-------------|----------------------|---------------------|------------|
| A1 Codex    | ...                  | ...                 | high/med/low |
| A2 Opus     | ...                  | ...                 | high/med/low |
| B Research  | [consensus finding]  | [main caveat]       | —          |
| C Secondo   | ...                  | ...                 | —          |
```

- Give every reviewer a row, including the ones that failed — write `unavailable (<reason>)` in the Verdict column. Never drop a row; a missing row hides a missing opinion.
- 2+ available reviewers may inform a recommendation. Only the full-coverage
  reviewer quorum below may emit `APPROVED`.
- Available reviewers diverge → surface the disagreement, ask user which axis matters most (speed / safety / cost).

## Quorum — what you are allowed to conclude (mandatory)

**The orchestrating agent and research-only output are not approval reviewers.**
They write or inform the table; they do not vote. Approval votes come from
independent CLI reviewer executions or Reviewer C; each must declare
`COVERAGE` after reading the change. Distinct reviewer identities and
executions, not fallback labels, determine independence.

| Independent full-coverage reviewers that returned a verdict | What you may emit |
|---|---|
| 2 or more | `APPROVED` or `NOT APPROVED`, per the synthesis |
| exactly 1 | `NOT APPROVED` allowed; `APPROVED` is **not** — emit `WITHHELD` |
| 0 | `WITHHELD` |

Below quorum a lone reviewer may still block — one competent objection is enough to stop — but may never approve. Never resolve unreachable reviewers into `APPROVED`: an unreachable reviewer is missing evidence, not assent.

**Worked seats (examples, not a second rule set):**

| Reviewers that returned a verdict | Votes | May emit |
|---|---|---|
| Codex PASS + Opus PASS, both declare full `COVERAGE`, neither blocks | 2 (A) | `APPROVED` (or `NOT APPROVED` if either blocks) |
| Codex PASS + Opus unavailable | 1 (A) | `WITHHELD`, or `NOT APPROVED` when the single vote blocks |
| Codex unavailable + Opus unavailable + one alternate APPROVE | 1 | `WITHHELD` |
| One primary PASS **plus** one distinct alternate APPROVE, both full coverage | 2 | `APPROVED` (or `NOT APPROVED` if either blocks) |
| One primary PASS plus a retry, wrapper alias, or duplicate reviewer execution | 1 | `WITHHELD` |
| A vote + C (`/extended-library:secondo`) vote, both full `COVERAGE`, neither blocks | 2 (A + C) | `APPROVED` (or `NOT APPROVED` if either blocks) |

No row relaxes coverage or single-objection blocking: one competent objection still stops the change.

**Coverage gates approval too.** Each approving reviewer must independently
declare `COVERAGE` that covers the entire declared diff/scope. Do not combine
partial coverage across reviewers to meet the approval quorum. A reviewer whose
coverage is incomplete still counts toward *blocking*, but not toward
*approving*. The combined scope covers the whole declared change only when
each counted approval independently covers it. Otherwise emit `WITHHELD`.

## Final verdict format — SHA-bound (mandatory)

When `/advice` is being run as the gate in the `pr-lifecycle` lifecycle (`~/.claude/skills/pr-lifecycle/SKILL.md`), the synthesis MUST end with exactly one verdict line, bound to what was reviewed:

```
VERDICT: APPROVED at <SHA>
```
```
VERDICT: NOT APPROVED at <SHA>
```
```
VERDICT: WITHHELD at <SHA> — <quorum or availability reason>
```

`WITHHELD` means the review did not happen, not that it failed. It fails the gate exactly like `NOT APPROVED`, so consumers that look for `APPROVED` need no change — the distinction only tells a later reader whether to re-run reviewers or fix the code.

**Capturing `<SHA>`:**
- Reviewing a PR — `gh pr view <N> --json headRefOid --jq '.headRefOid'`
- Reviewing the working tree — `git rev-parse HEAD`, **but HEAD does not identify uncommitted changes.** If `git status --porcelain` is non-empty, that SHA does not name the tree you reviewed. Commit the intended state before review; the primary-pair runner refuses dirty input and no approval verdict may be emitted for it.

The verdict records the exact state actually reviewed. Apply the reasoned SHA-applicability rule in `pr-lifecycle/SKILL.md`: compare it with the candidate and inspect the complete actual delta, claims, evidence and phase. Preserve the original reviewers and reviewed SHAs. An assessor may document that their existing approvals remain applicable without recalling every reviewer solely to restamp a new SHA. This is an applicability record, not a new independent vote or a claim that a reviewer inspected new bytes. Uncovered material changes, changed evidence within the review scope, unresolved findings or uncertain applicability require affected independent review. Classify runner, script and skill-instruction changes by behavior and contract effect, never by directory or path alone. A genuinely harmless non-behavioral delta may be re-affirmed after documenting why its coverage remains intact; do not force a full `/advice` rerun for the hash change alone.
Preserve the two independent full-coverage approvals required by Quorum;
re-affirmation never turns one reviewer into approval. Do not emit a bare
"APPROVED"/"looks good" without the SHA — an unbound verdict cannot be checked
for staleness.

## Token budget

What `/advice` saves is **the conversation**, not the change. `advisor()` ships the entire uncached transcript; `/advice` sends a decision plus a pointer, and each reviewer pulls only the code it decides it needs. That is the whole economy — and it is preserved without capping the diff.

| Reviewer | What you send |
|---|---|
| A1 Codex | Decision + pointer (reviewer fetches the rest) |
| A2 Opus CLI | Decision + pointer (reviewer fetches the rest) |
| B — /research | Web queries only |
| C — /extended-library:secondo | Decision; it gathers its own diff under its own budget |

Do not cite a percentage saving — none has ever been measured here. And do not shrink the pointer to buy tokens: sending a 349-line diff is nothing like sending an 80K-token transcript, so trading review coverage for that margin is a bad trade in the only direction that matters.

## Fallback chain summary

| Priority | CLI | When |
|---|---|---|
| Primary 1 | `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` | Concurrent primary pair (exact IDs: `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-sol`; 5.6 and unknown IDs forbidden) |
| Primary 2 | `claude -p --model opus --dangerously-skip-permissions` | Concurrent primary pair |
| Alternate | `claude -p` or `claudewa -p` | Dispatch when needed for a second independent vote |
| Alternate | `cursor agent -p --force` (or the configured Cursor print wrapper) | Dispatch when needed for a second independent vote |
| Alternate | `agy --print --model gemini-3.8-flash-high --dangerously-skip-permissions` | Dispatch when needed for a second independent vote |

Notes:
- Codex + Opus remain the concurrent primary pair whenever both are viable. If either is unavailable or fails, record that result and dispatch an eligible alternate reviewer when needed to reach two independent full-coverage votes; a successful primary vote may pair with a successful alternate vote.
- A fallback or retry is not an additional vote when it reuses the same execution or reviewer identity. The same scope SHA, reviewer identity and model, actual CLI transport, independent clone, separate output, and receipt must be recorded for every counted execution.
- Check a CLI is on `PATH` before counting it as a rung. An absent CLI is an unavailable rung, not a failed reviewer — drop to the next rung without recording a failure.
- `agy --print-timeout` defaults to 5m. For a full 150-line artifact, pass a longer value only when it fits within the remaining 600-second end-to-end deadline; otherwise record the timeout and continue with another eligible reviewer.
- A reviewer attempt counts as a successful approval vote only when it exits zero, emits a nonempty `VERDICT:` line, declares full coverage, and its receipt shows no original-checkout mutation, surviving reviewer process, or clone-cleanup failure. Otherwise preserve the failure in its receipt and dispatch a replacement reviewer if needed; a failed or timed-out reviewer does not prevent another healthy reviewer from running concurrently.
