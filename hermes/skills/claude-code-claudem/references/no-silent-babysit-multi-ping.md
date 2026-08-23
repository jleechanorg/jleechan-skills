# No-Silent-Babysit — Multi-Ping Round-Trip for Verification Work

> Session lesson from the 2026-07-28 PR #785 babysit. The user said: *"show me proof the coding agent is generating updates vs task started and we never hear anything again."* This document is the protocol for proving a worker is NOT silent during multi-step work, and the diagnosis pattern when one goes silent.

## When to use this pattern

Use this when the task is **multi-step verification or babysitting** — NOT a single coding change. Examples:

- Drive a PR through `/green /er /advice` review stages
- Run a long diagnostic where each step has its own conclusion
- Coordinate a multi-PR fix (plan + execute + verify)
- Any work where the operator wants to see **progress**, not just a final answer

If the task is "open PR #X with one commit", use `round-trip-dispatch-proof.md` instead — single ping at the end is enough.

## The 5-ping contract (minimum)

When dispatching a multi-step worker, require AT LEAST 5 in-thread messages to the dispatch thread:

| # | When | Content |
|---|---|---|
| 1 | Within 30s of receiving the prompt | "🟡 Starting — worker spawned, branch + SHA + worktree path" |
| 2 | After each verification step | "🟢 Step N /<review-name> done — <1-line result>" |
| 3 | (repeat 2 per step) | (one ping per stage) |
| 4 | If a step blocks >3 min | "🟡 Still working on X — <what's slow>" |
| 5 | Final | "🟢 Final verdict — N-green, ready for human review + merge" |

The whole point is **observable liveness**. The operator watches the thread in real time. Each ping is 1-3 lines, includes the step name and an emoji status. The worker must NEVER go more than ~5 minutes without a ping during compute.

## How to encode the contract in the worker prompt

The worker is a coding agent — it optimizes for "what code do I write." If you want it to **also** post progress pings, the Slack post instructions must be **explicit, terminal, and per-step**. Pattern:

```markdown
# Round-trip contract (READ CAREFULLY)

You MUST post AT LEAST 5 messages to the dispatch thread (C0B9W8D609M,
thread_ts=<THREAD_TS>) before you exit:

1. **"Starting"** — within 30 seconds of receiving this prompt
2. **"Step 1 /green done"** — after the green-gate re-verify
3. **"Step 2 /er done"** — after the evidence review
4. **"Step 3 /advice done"** — after the second opinion
5. **"Final verdict"** — combining all three + recommended human action

Each message must be 1-3 lines, include the step name, and have an emoji
status. The whole point of this test is that the operator sees continuous
activity, not one end-of-run summary.
```

Then provide the **exact curl incantation** as a copy-pasteable template, including the channel ID and thread_ts as literal values. The worker doesn't have access to your conversation history — it doesn't know which thread it's "in" unless you tell it.

## Sizing `--max-turns` for multi-ping work

Each ping is a `Bash` tool call (~1 turn). Each verification step is 2-5 turns (read file + gh query + curl post). For a 5-ping task with 3 verification steps, budget **~30 turns**:

| Worker step | Turn budget |
|---|---|
| Spawn ping | 1 |
| Step 1 verify (1 gh query + 1 curl post) | 3-5 |
| Step 2 verify (multiple file reads + 1 curl post) | 5-8 |
| Step 3 verify (design critique + 1 curl post) | 5-8 |
| Final verdict (1 curl post) | 2-3 |
| **Total** | **~20-25** |

Use `--max-turns 30` for a typical multi-step babysit. Use `--max-turns 15` only for single-step work per `round-trip-dispatch-proof.md`. The 2026-07-28 first attempt used `--max-turns 12` and died after step 1 — the worker had to be re-fired with `--max-turns 30` to complete the round-trip.

If the worker runs out of turns mid-step, post a "retry with larger budget" ping to the thread before re-firing. The operator wants to see the recovery, not silent re-fires.

## The honest-reporting pattern

When the worker discovers the target is **already in the desired state** (e.g., PR already N-green, bug already fixed, evidence already complete), it should:

1. **Verify the state independently** (don't take the user's word for it)
2. **Post the "already done" finding** with full evidence (gate-by-gate, file-by-file)
3. **Surface any extra caveats** found during the verification
4. **Recommend next human action** (e.g., "REVIEW + MERGE, no auto-merge per CLAUDE.md")

The operator wants honest reporting, not fabricated changes to make the test look productive. The 2026-07-28 PR #785 babysit found that the PR was already N-green (Green Gate SUCCESS at 20:30:41Z, CR APPROVED, MERGEABLE) — the worker correctly reported this with full evidence, then surfaced two extra caveats (a side-channel script referenced but not in the diff; the after-restart smoke depends on a Slack side-channel that could itself fail). That's the right shape.

## Live proof (2026-07-28)

| Time (UTC) | Δ | Event | ts |
|---|---|---|---|
| 00:28:27 | — | 🟢 Dispatch (operator, top-level) | `1785284907.621589` |
| 00:29:12 | +45s | 🟡 Worker spawn #1 (--max-turns 12) | `1785284952.332609` |
| 00:30:00 | +48s | 🟢 Step 1 /green done | `1785285000.566059` |
| 00:30:34 | +34s | 🟡 Worker spawn #2 (--max-turns 30, after retry) | `1785285058` |
| 00:31:39 | +65s | 🟢 /green re-verified (6/6 PASS) | |
| 00:32:16 | +37s | 🟢 /er evidence PASS w/ 1 caveat | |
| 00:32:31 | +15s | 🟡 /advice MINOR CAVEATS | |
| 00:32:39 | +8s | 🟢 Final verdict — N-green, ready for human review | |

Total wall time: 4 min 12 s. **Six in-thread messages** (one retry ping included). Zero silent gaps longer than ~65s. The operator saw the entire timeline.

## Common failure modes

### Failure 1 — Worker exhausts `--max-turns` mid-step

**Symptom:** worker exits with `Error: Reached max turns (N)` after step 1 or 2. PR may exist but no final verdict.

**Fix:** re-fire with a larger `--max-turns`. The first attempt's transcript is useful diagnostic data — read the worker's final output to see how far it got, then re-dispatch with a budget that covers the remaining steps. Tell the operator via the same thread: "🟡 Worker exhausted max-turns after step 1 — re-firing with --max-turns 30."

### Failure 2 — Worker posts one "done" message but no progress pings

**Symptom:** the thread shows dispatch → final reply, with no in-between activity. The worker optimized for "finish the task" and skipped the contract.

**Fix:** the round-trip contract must be at the TOP of the prompt with the explicit "AT LEAST 5 messages" requirement. Add an emoji-status-per-ping requirement to make it visible. Do NOT trust the worker to derive the contract from "be chatty" — it will not.

### Failure 3 — Worker fabricates work to fill the time

**Symptom:** worker reports "fixed the bug" / "added the missing test" / "pushed a follow-up commit" when the target was actually already in good shape. The worker's commits are unnecessary or wrong.

**Fix:** explicit instruction in the prompt: "If the target is already N-green, DO NOT push any commits. Just verify the state independently and post the honest finding. The operator values honest reporting over productive-looking activity." Combine with the "honest-reporting pattern" above.

### Failure 4 — Operator misses the activity

**Symptom:** the worker posts pings correctly but the operator isn't watching the channel.

**Fix:** for high-priority babysits, the gateway session should also post a summary to the operator's primary channel (e.g., `#ai-general` per `slack-channel-routing-policy`) at task start ("🟡 Babysitting PR #785 in `#claw-dispatch` thread `…`, expected 4-min wall time") and at task end. The in-thread pings satisfy the round-trip contract; the cross-channel ping satisfies the operator-visibility contract.

## Verification commands

After the multi-ping round-trip, verify from the operator side:

```bash
HERMES_SLACK_BOT_TOKEN=$(grep -E "^export HERMES_SLACK_BOT_TOKEN=" ~/.bashrc | head -1 | sed 's/^export //' | cut -d= -f2- | tr -d '"')

# 1. Thread contains all expected messages (≥5)
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=<THREAD_TS>&limit=20" \
  | jq '.messages | length'

# 2. All replies are in-thread (thread_ts == original_ts)
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=<THREAD_TS>&limit=20" \
  | jq '[.messages[] | select(.ts != "<THREAD_TS>") | {ts: .ts, thread_ts: .thread_ts, has_status_emoji: (.text | test("🟢|🟡|🔴"))}]'

# 3. No gap longer than ~5 minutes between consecutive pings
# (run the message list through a small Python script that computes deltas)
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=<THREAD_TS>&limit=20" \
  | jq -r '.messages[] | "\(.ts) \(.text[0:80])"' | sort

# 4. The PR (or target) is in the expected final state
gh pr view 785 --json state,mergeable,reviewDecision --jq '{state, mergeable, reviewDecision}'
```

If items 1-3 pass, the round-trip is proven. If item 4 reveals a different state than the worker reported, re-fire with an explicit "double-check your facts before posting" instruction.

## See also

- `references/round-trip-dispatch-proof.md` — the single-ping shape (one PR, one in-thread reply)
- SKILL.md "Pattern — No-silent-babysit multi-ping" section — the concise summary in the skill body
- SKILL.md "Gotchas — Worker scope vs gateway scope" — why the gateway must own the cadence, not the worker
- SOUL.md `dispatched-task-progress-5min` — the related 5-min progress-ping contract for cron-driven work