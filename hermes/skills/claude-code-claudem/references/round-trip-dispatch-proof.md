# Round-trip Dispatch Proof — Verifying the `claudem` Wrapper End-to-End

> Session lesson from the v1.6.0 patch (2026-07-28). The pattern was developed when the user asked: *"Is this using the same default `claude-code` skill? its supposed to wrap it. lets drive a new slack thread in <#C0B9W8D609M> that proves the coder updates the original requesting thread."* This document is the full reproduction recipe, transcript, and diagnostics.

## When to use this pattern

Use this when you need to prove — visibly, in a channel the operator is watching — that `claudem` (or `claudeminimax`) actually works as a coding worker. **Not** just that the model identity is correct, but that:

1. The wrapper accepts a real coding task
2. The wrapper executes it end-to-end (reads files, edits, commits, pushes, opens PR)
3. The wrapper reports back to the operator in the **same** Slack thread the request came from

If any of these three fail, the round-trip is broken — even if the model identity is right. The live M3 probe (separate concern; see `references/bashrc-global-leak.md`) tests the first piece. The round-trip test tests all three together in an operator-observable channel.

## The 4-step protocol

### Step 1 — Open a top-level request in a dispatch channel

```bash
# Pick a channel the operator monitors. Common choices:
#   - #claw-dispatch (operator's coding-worker dispatch channel)
#   - #ai-general (operator's home channel for system reports)
#   - any channel the user explicitly named

# Post a top-level (not reply) message describing a SMALL, well-scoped coding task.
# Capture the ts from the response — that's the thread anchor.

curl -fsS -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "$(jq -Rn --arg ch "C0B9W8D609M" \
    '{channel: $ch, text: "<task description with acceptance criteria>"}')"
```

The task must be:
- **One file change** (or one tightly-coupled group of files)
- **< 20 lines diff** ideally (so the worker can finish in one `claudem -p` pass)
- **Clearly scoped** with acceptance criteria in the message body
- **Verifiable from the PR URL alone** (no need to ask the worker clarifying questions)

If the task is too large, the worker will run out of `--max-turns` and leave the round-trip half-done.

### Step 2 — Spawn the `claudem -p` worker

```bash
# Build the worker prompt. Include:
#  1. The exact task description
#  2. The Slack channel + thread_ts to post the result to
#  3. The INSTRUCTION to post via chat.postMessage with thread_ts
#  4. Any context the worker needs (repo, branch, file paths)

WORKER_PROMPT="$(cat <<'EOF'
You are a coding worker spawned by Hermes via the claudem wrapper. ...

## When done

Reply to the ORIGINAL Slack thread (not a new top-level message):
  curl -fsS -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d '{"channel":"C0B9W8D609M","thread_ts":"<THREAD_TS>","text":"DONE — PR #<N> at <url>"}'

EOF
)"

# Fire the worker from a bashrc-sourced login shell.
# pty=true because the wrapper's TUI banner ("⚠ claude.ai connectors...") can hang a foreground poll.
# background=false because we want to wait for the round-trip to complete in one turn.
# --max-turns 15 is enough for think+read+edit+commit+push+gh+post.
bash -lic "claudem -p \"\$WORKER_PROMPT\" --allowedTools 'Read,Edit,Glob,Grep,Bash' --max-turns 15 --output-format text"
```

**Critical details for the worker prompt:**

- The Slack post instruction **must be at the end of the prompt** as a "When done" section. The worker is a coding agent; it will optimize for "what code do I write" and only attend to "reply to Slack" if you make it explicit and terminal.
- Include the **exact** `channel` id and `thread_ts` value. The worker doesn't have access to your conversation history.
- Include a curl example so the worker doesn't have to guess the Slack API shape.

### Step 3 — Worker executes

The worker runs in `bash -lic 'claudem -p "..."'` per the v1.5.0 pattern. Typical wall time for a one-file change: 1–4 minutes. The worker will:

1. Read the relevant files
2. Make the edits
3. Commit on a branch (off `origin/main`)
4. Push the branch
5. Open the PR via `gh pr create`
6. Post to the Slack thread

### Step 4 — Operator observes

After the worker exits, the operator (or you, on the next turn) checks:

```bash
# Did the reply land in the SAME thread?
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=<THREAD_TS>&limit=10" \
  | jq '.messages[] | {ts: .ts, thread_ts: .thread_ts, user: .user, text: .text[0:120]}'
```

If the worker's reply has `thread_ts == <THREAD_TS>` AND the user is the worker (e.g. `B0A3MS7G08P` for `mcp_agent_mail`, or `U0AEZC7RX1Q` for hermes bot), the round-trip is **proven**.

## Live proof (2026-07-28)

| Step | ts | actor | channel / context | result |
|---|---|---|---|---|
| 1. Dispatch | `1785284123.726119` | mcp_agent_mail (operator) | top-level in `#claw-dispatch` | task posted |
| 2. Worker | (~3 min wall) | `claudem` via M3 | `bash -lic 'claudem -p "..."'` | 1 file / +6 lines |
| 3. PR | `60109e03bc` | `jleechan2015` | `feat/claudeminimax-routing-table-row` | [#806](https://github.com/jleechanorg/jleechanclaw/pull/806) opened |
| 4. Reply | `1785284261.068169` | mcp_agent_mail | in-thread (`thread_ts=1785284123.726119`) | "Round-trip complete — PR #806..." |

PR body had the full `## Evidence` section with exact `git diff`. Worker took 3 minutes from dispatch to in-thread reply.

## Common failure modes

### Failure 1 — Worker forgets `thread_ts`, reply lands top-level

**Symptom:** `conversations.replies` returns only the original dispatch message; the worker's "DONE — PR #N" message is in `conversations.history` for the channel instead.

**Fix:** the worker prompt must show a complete `chat.postMessage` example with `thread_ts`. Pattern:
```json
{"channel":"<chan>","thread_ts":"<ts>","text":"<body>"}
```

If the worker uses MCP `mcp__slack__conversations_add_message`, the equivalent parameter is `thread_ts=<ts>` (verified for the built-in MCP).

### Failure 2 — Worker posts to the wrong channel

**Symptom:** operator watches the dispatch channel and never sees the reply; the worker's reply is in some other channel.

**Fix:** include the exact channel ID in the worker prompt. Don't say "post back to the operator" — say `channel_id=C0B9W8D609M` (the literal hex ID). The worker doesn't have context for "wherever the operator is".

### Failure 3 — Worker runs out of `--max-turns` before posting to Slack

**Symptom:** PR is opened but no Slack reply. The worker exits mid-flow.

**Fix:** for a one-file change, `--max-turns 15` is enough. For two-file changes, use `--max-turns 25`. If the worker is going to spawn subprocesses (e.g. for tests), add `--max-turns 30`.

### Failure 4 — `HERMES_SLACK_BOT_TOKEN` not exported in the worker's env

**Symptom:** the worker's curl returns `missing_scope` or `not_authed`.

**Fix:** make sure the worker is launched via `bash -lic 'claudem ...'`. The `-l` (login) flag forces `~/.bashrc` to source, which sets `HERMES_SLACK_BOT_TOKEN` (if it's exported there). For launchd contexts, use `launchd-env-wrapper.sh`. For AO workers, set the env var in the agent config.

### Failure 5 — Worker uses MCP agent mail identity instead of Hermes bot identity

**Symptom:** the reply appears under `mcp_agent_mail` (user `U0A4G7LDJ4R`) instead of the hermes bot (`U0AEZC7RX1Q`). Not a failure, but operator might prefer the canonical bot identity.

**Fix:** per SOUL.md `prefer-builtin-slack-mcp`, default to `mcp__slack__conversations_add_message` (built-in Hermes Slack MCP, posts under bot identity). Only use `mcp_agent_mail.slack_post_message` if the user explicitly asked for that identity.

## Verification commands

After the round-trip, verify from the operator side:

```bash
HERMES_SLACK_BOT_TOKEN=$(grep -E "^export HERMES_SLACK_BOT_TOKEN=" ~/.bashrc | head -1 | sed 's/^export //' | cut -d= -f2- | tr -d '"')

# 1. Thread contains exactly the dispatch + worker reply
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=1785284123.726119&limit=10" \
  | jq '.messages | length'

# 2. The worker's reply is in-thread (thread_ts == original_ts)
curl -fsS -H "Authorization: Bearer $HERMES_SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.replies?channel=C0B9W8D609M&ts=1785284123.726119&limit=10" \
  | jq '.messages[] | select(.ts != "1785284123.726119") | {ts: .ts, thread_ts: .thread_ts}'

# 3. The PR is open and authored by the right account
gh pr view 806 --json state,author,url --jq '{state, author: .author.login, url}'

# 4. The PR diff matches the dispatch task scope
git -C $HOME/.worktrees/jleechanclaw/claudeminimax-table \
  diff --shortstat origin/main..HEAD
```

If all four pass, the round-trip is proven. If any fails, the corresponding failure mode above is the most likely cause.

## See also

- `references/subprocess-vs-interactive-shell.md` — why `bash -lic` is the canonical non-interactive pattern
- `references/bashrc-global-leak.md` — why the binary had to go and what the v1.5.0 cleanup changed
- SKILL.md "Pattern — Round-trip dispatch proof" section — the concise summary that lives in the skill body
- SOUL.md `dispatched-task-progress-5min` — the related 5-min progress-ping contract (for long-running tasks)
- SOUL.md `slack-reply-inherit-thread-ts` — the related MCP thread-routing contract