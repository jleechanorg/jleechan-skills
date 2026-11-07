# Review records in the PR description

On-demand part of [pr-lifecycle](SKILL.md): load it whenever a review runs, obligations are updated, or the PR body's evidence marker or review records change.

## One current PR and task record

The obligation ledger and execution fields constitute the single current PR/task record in the PR description or task context. They track candidate obligations, execution ownership, and asynchronous resumption in one authoritative place. Observational stats JSON is a derived sidecar, never another authority or state controller.

### Unified obligation and review ledger

Maintain a structured obligation ledger in the PR description under `## Review Ledger`:

| Obligation | Required by | Status | Receipt | Candidate applicability |
|---|---|---|---|---|
| Source review quorum | Selected route | PASS / OPEN | <Reviewer receipt URL or ID> | Valid / affected / unknown (<rationale>) |
| Evidence review (/er) | Selected route | PASS / NOT REQUIRED | <Receipt URL or exemption> | Current candidate / Reason |
| Visual approval | Changed claims | PASS / NOT REQUIRED | VISUAL APPROVED at <40-char-sha> | Rendered frames inspected / Reason |
| CI and conflicts | Repository policy | PASS / OPEN | Live check run results | Current candidate |
| Closing coverage | Final phase | PASS / OPEN | Closing validation record | Current candidate |

For every review type that runs, including `/es`, `/er`, `/advice`, `/wa`, `/cs`, other named lanes and native reviews, record in the PR body the exact reviewed SHA, review type/phase, verdict or status, timestamp, and reviewer/coverage. Document reviews also retain document hashes; their context SHA does not turn document approval into code approval.

### Execution record

Track the active execution state in the PR description or task context:

```text
endpoint: FINAL_READY
candidate: <head-SHA>
next_action: <specific unmet obligation>
owner: <driver or delegated lane>
job_handle: <actual handle, when asynchronous>
wake_condition: <verified callback / poll / resume mechanism>
blocker: <only if no executable authorized action remains>
```

An actual handle plus a verified callback, polling, or resume mechanism must exist. A written wake condition alone does not schedule or execute resumption; ending a turn at "review requested" or "job submitted" without an active handle and verified resumption mechanism is forbidden.

**Blocking dependency PR ownership:** When progress depends on a blocking dependency PR, the executing agent/driver must retain ownership of the blocking dependency through its required endpoint or verify an accepted handoff to a confirmed executing owner. Merely delivering a handoff message or task note does not relieve ownership or unblock the parent; delivery alone is not enough, and the parent blocker remains preserved until the dependency reaches its verified endpoint or active handoff acceptance is proven.

## Observational Scratch runtime telemetry (`run.stats.json`)

Observational Scratch runtime telemetry (`run.stats.json`) is an optional derived sidecar for non-enforcing metrics, never a competing authority, schema enforcement, or second ledger. The executing agent/driver produces this telemetry optionally from already-fetched candidate, gate, or job events without making new model/tool calls, and human audit is the consumer for offline review without blocking gates or stage transitions. To capture execution telemetry without cluttering the repository or git history, write a tiny observational runtime snapshot to the host Scratch space (resolved dynamically via `~/.claude/skills/scratch-space/scripts/scratch-dir.sh [subpath]` or `diskm scratch-new`, falling back to `/tmp` only when unconfigured):

- **Producer and consumer roles:** The executing driver is the producer, updating fields optionally from already-fetched event data (no new model calls, scripts, or duplicate ledger); human audit is the consumer for non-blocking offline inspection (no schema enforcement or gating).
- **Non-enforcement invariant:** Stats are strictly observational. They cannot delay gates, block stage transitions, or become gating criteria.
- **Integrity invariant:** Unknown values MUST be `null`. Never fabricate cost, idle time, or token estimates.
- **Safety invariant:** Never include credentials, tokens, secrets, or private personal messages. Never write runtime telemetry into the repository tree or `$HOME`.
- **Event-driven update:** Update only on actual candidate, gate, or job events using already-fetched data.

Structure of `run.stats.json`:
```json
{
  "endpoint": "FINAL_READY",
  "candidate_sha": "<40-char-sha>",
  "timestamps": {
    "created_at": "<ISO-timestamp-or-null>",
    "pushed_at": "<ISO-timestamp-or-null>",
    "review_return_at": "<ISO-timestamp-or-null>",
    "green_at": "<ISO-timestamp-or-null>",
    "merged_at": "<ISO-timestamp-or-null>"
  },
  "model_usage": {
    "cached_input_tokens": null,
    "uncached_input_tokens": null,
    "output_tokens": null,
    "reasoning_tokens_subset": null
  }
}
```

## Publication and receipt integrity

Outside the canonical Markdown instruction-only route, the compact route and the one-liner fast path (in [exceptions.md](exceptions.md#proportional-exceptions-and-fast-paths)), publish each completed review's sanitized receipt as a gist within the approved disclosure scope, and keep one current marker in the PR body for evidence-gate compatibility: `**Evidence**: <gist-url> (head <sha>)`, pointing to the authorized sanitized evidence-review receipt for current applicability. Compact PRs use the outcome/checks/SHA/limitations/reviewer summary, linking an artifact only when needed to substantiate the claim; the one-liner fast-path `/es` record uses its before/after section. Update only that index; keep the historical ledger, receipt URLs and original capture SHAs. Underlying raw artifacts may stay private. Missing publication authority or an inaccessible required receipt leaves the marker incomplete; never fabricate its URL.

A gist is link-accessible, not private storage: omit credentials, private source, personal communications and sensitive artifacts unless separately authorized. Verify the gist URL and intended reviewer access before calling publication complete. If tools or permissions prevent publishing a required receipt, record `PUBLICATION BLOCKED` with the exact reason and local receipt location; never invent a gist URL or passing verdict, and do not claim the record complete.

Keep `PENDING`, `UNAVAILABLE`, `FAILED` and `SUPERSEDED` results visible alongside approvals. Read the current body before updating it. The idempotency key is review type + phase + reviewed SHA + receipt identity: append a record only when the key or status is new, and treat a retry with unchanged key and status as a no-op. A status transition (including PENDING to PASS with the same receipt) or an applicability change appends a dated superseding event identifying its prior record, without erasing history. Preserve prior rounds and visual tables. For a moved head, add a current-applicability review and keep the original tested SHA and capture link instead of rewriting historical receipts. Read back the PR body after each update; an uncertain write needs readback before retrying. Record optional or skipped reviews honestly, without fabricated gists.
