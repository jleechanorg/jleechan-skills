---
name: dispatch-task
version: 1.3.0
description: Dispatch a bead-tracked task via ao spawn/ao send, register the mapping, and ack in Slack thread. Includes the `env -i` ARG_MAX wrapper, the `running.json` bootstrap for "lifecycle polling is inactive" errors, the post-spawn branch-reset + copy-briefs + `ao send` steer pattern, sibling-vs-bundle dispatch framing for multi-PR fanouts, and the `br` (beads_rust) CLI flag pitfalls.
---

# dispatch-task

Use this skill when $USER asks you to work on a task and you decide to dispatch it to an agent.

## When to use

- $USER asks you to implement, fix, or investigate something that warrants spawning an agent
- You have decided the task merits a full agent run (not a quick inline answer)
- This applies regardless of how the request arrived: Slack, HTTP gateway, cron, or inline prompt

## NEVER use `sessions_spawn` for coding tasks

`sessions_spawn` is hermes's internal nested-agent tool. It does NOT create a git worktree, does NOT handle PR lifecycle, pastes prompts without auto-submitting Enter, and allows silent task rewriting. **It is banned for any task involving code, files, or PRs.**

Always use this skill and the `ao` CLI (agent-orchestrator), not Hermes's nested `sessions_spawn`.

## Task description: preserve + expand, never condense

Build the task body you pass to `ao send` (via `--file`) in two parts:
1. **User's original text verbatim** — copy it exactly, do not shorten or paraphrase
2. **Memory expansion** — append relevant findings from `/mem-search` or the memory MCP: past failures, known gotchas, patterns that apply to this task

Final task = original text + appended memory context. Never replace the user's words with a summary. If the original is long, that is intentional.

## Steps

### 1. Claim or create the bead

```bash
# If bead exists:
br update <bead-id> --status in_progress

# If new task (match CLAUDE.md / PROJECTS_BEADS.md):
br create "short description" --type task --priority 1 --labels repro,latency,worldarchitect
# Note the bead ID from output. **ID format on this host is `$USER-XXXX`
# (8-char alphanumeric), NOT `rev-xxx` or `bd-xxx` or `ORCH-xxx`.**
# Example: `Created $USER-6zmz: ...` (verified 2026-06-20, /repro
# latency-timer + latency-regression dispatch in C0AH3RY3DK6).
```

`br` CLI flag pitfalls (verified 2026-06-20):
- `br create` labels flag is `--labels` (plural), NOT `--label`. Singular form
  fails with `error: unexpected argument '--label' found` and suggests
  `--labels` in the tip.
- `br update` takes `[IDS]...` BEFORE its options, not after. Correct:
  `br update $USER-6zmz --status in_progress`. Wrong:
  `br update --status in_progress $USER-6zmz` (positional IDs come first).
- `br update` notes flag is `--notes` (replaces the whole notes string), NOT
  `--append-notes`. To append, prefix with the existing notes content
  yourself, or use `br show <id>` to read the current notes first, then
  `br update <id> --notes "<existing> + <new>"`.

Full flag pitfall table and ID-format notes in `references/beads-rust-cli-gotchas.md`.

### 2. Ack in Slack thread (REQUIRED)

**This is the Deterministic Slack Thread Response Contract.**

Record the Slack context from $USER's original message:
- `SLACK_TRIGGER_TS` = the `ts` field from $USER's message (e.g. `1772857900.668299`)
- `SLACK_TRIGGER_CHANNEL` = the channel ID (e.g. `C0AH3RY3DK6`)

Reply to $USER's original Slack message in the same thread:

> On it. Spawning agent for **<bead-id>** — will reply here when done.

While the dispatched task is active, supervisor/nudge automation must post progress in-thread at least every 5 minutes until done (or blocked).

**Proof-First Requirement**: When the supervisor posts completion, it MUST include at least one reviewable proof URL (PR, commit, or artifact):
- PR URL: `https://github.com/OWNER/REPO/pull/NUMBER`
- Commit URL: `https://github.com/OWNER/REPO/commit/SHA`
- Artifact URL: durable build/test/deploy artifact link
It SHOULD include multiple proof URLs when available (for example, PR + commit). No "task done" without at least one proof URL. See SOUL.md "Autopilot Policy" for the full contract.

### 3. Before dispatching: Search memories

**Always search memories before writing the task prompt.** Use `/mem-search` or the memory MCP to find:
- Past successes/failures for similar tasks
- Specific gotchas or patterns for this type of work
- Any injected context from previous failures

Inject relevant learnings into the task prompt to prevent repeat failures.

### 4. Dispatch via ao

Determine the ao project ID from cwd or pass `-p` explicitly. **On this host's
`ao` CLI version, `ao projects list` does NOT exist** — the only top-level
commands are `start / spawn / session / status / init / stop`. Project
resolution falls back automatically:

```bash
# Project is inferred from cwd (preferred), or $AO_PROJECT_ID, or explicit -p.
# There is no `ao projects list` on this host. `ao spawn -p <id>` works;
# `ao projects list` returns: `error: unknown command 'projects'`.
# Verified 2026-06-18 (session /repro mH03aODj4wQ9k6t5Ohjb dispatch).

# To find the project ID from inside a repo worktree, inspect agent-orchestrator.yaml
# (the configured project IDs are listed under `projects:`), or just `cd` into
# the repo root and let ao infer. Example: from `$HOME/projects/your-project.com`,
# `ao spawn rev-0xsff` auto-resolves to the `worldarchitect` project.

# Look up which project the bead belongs to by description text:
br show <bead-id>
# The description often names the repo/project ("mvp_site", "worldarchitect", etc.).
```

Example project IDs (NOT authoritative — confirm via `agent-orchestrator.yaml` or
cwd): `worldarchitect`, `agent-orchestrator`, `jleechanclaw`, `worldai`, `mctrl`.

If $USER explicitly requests Codex (or another agent CLI), use the override flags your
`ao spawn` supports (`ao spawn --help`); defaults live under `defaults.agent` in
`agent-orchestrator.yaml`. Do not fall back to `sessions_spawn`.

Then spawn and send. **ALWAYS wrap the spawn in `env -i` on macOS** to avoid the ARG_MAX overflow from the gateway shell's fat env (see §"Spawn wrapper" below):

```bash
# 1. Resolve tokens in the outer shell (the env -i wrapper strips PATH so
#    inline `$(gh auth token)` calls would find no `gh` binary).
GH_TOKEN_VAL="$(gh auth token)"
AO_TOKEN_VAL="$(gh auth token)"

# 2. Spawn with env -i to drop the fat bashrc env (~245 vars) that exceeds
#    macOS 256KB ARG_MAX when bash concatenates the launcher + env into the
#    tmux new-session command. Verified 2026-06-19 (wa-2404, mobile page
#    not loading repro): the tmux session itself inherits the full env via
#    `~/.bashrc` once it spawns, so the worker still has every secret.
cd ~/.openclaw && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c '~/bin/ao spawn -p <project> "<short task summary>"'

# 3. Send task verbatim (longer than ~200 chars → write to /tmp/ and pass the
#    short summary as the positional arg above; the full brief goes in the
#    worktree root as AO-TASK-BRIEF.md and is read by the worker).
TASK_FILE=$(mktemp)
trap 'rm -f "$TASK_FILE"' EXIT
cat > "$TASK_FILE" <<'TASK'
<full task description enriched with memory learnings>
TASK

# 3a. For short bodies (under 2 KB) and an already-running worker, `ao send` works.
ao send <session-name> --file "$TASK_FILE"

# 3b. For LONG bodies (>4 KB) on a FRESH spawn, `ao send` does NOT auto-submit.
#     Use tmux load-buffer + paste-buffer + Enter. See references/ao-spawn-long-ta[REDACTED_OPENAI_KEY]
#     Verified 2026-06-16 (wa-2369, level-up label fix): the worker received the
#     8.3 KB brief into its input box but never started processing until
#     `tmux send-keys -t <tmux-name> Enter` was issued explicitly. `ao send`'s
#     "auto-submit" claim does not hold for fresh spawns in the current runtime.
```

If ao spawn or ao send fails, report the failure instead of claiming the task was queued.

**`ao spawn` "timeout" is NOT a spawn failure (verified 2026-06-20).** The
spawn CLI itself can hit the shell timeout (`exit_code 124`) while the
underlying tmux session IS being created. **Always verify with
`ao session ls -p <project>` before treating a timeout as a failure.**
If the session appears in the list with `[spawning]` state, the spawn
landed and the orchestrator is just slow to return its handshake. Verified
on the 2026-06-20 latency-repro dispatch: `ao spawn -p worldarchitect
"latency-timer-wrong..."` timed out at 180s but `wa-2455` was live in
`ao session ls` 90s later, and the subsequent `ao send --file` accepted
the brief normally.

## Spawn wrapper — `env -i` is mandatory on macOS

Verified 2026-06-19 (wa-2404): spawning from a fat-env shell (the gateway) hits `Argument list too long` on macOS's 256KB `ARG_MAX` when bash concatenates the tmux launcher with ~245 vars from `~/.bashrc` (AO_BOT_GH_TOKEN, GH_TOKEN_AGENTF, WAFER_API_KEY, VOYAGE_API_KEY, ANTHROPIC_API_KEY, full GCP service-account JSON in GOOGLE_APPLICATION_CREDENTIALS, etc.). The fix is to wrap the spawn in `env -i` and pass only the four vars `ao` needs to start the tmux subprocess. The tmux session itself inherits the full env via `[runtime-tmux] loaded 176 vars from ~/.bashrc` once it spawns, so the worker inside the tmux still has everything.

Pattern (use on every spawn from a gateway shell):

```bash
GH_TOKEN_VAL="$(gh auth token)"   # resolve in outer shell — env -i strips PATH
AO_TOKEN_VAL="$(gh auth token)"
cd ~/.openclaw && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c '~/bin/ao spawn -p <project> "<short task summary>"'
```

Pre-computing the token also makes the spawn idempotent. Inline `$(gh auth token)` inside the `env -i` wrapper would find no `gh` binary because PATH is stripped — the resulting `GH_TOKEN=""` causes `ao spawn` to 401. **Do not pre-flight this — the error is obvious (`command too long` in stderr) and the retry is cheap.**

## Spawn recovery — `lifecycle polling is inactive`

Symptom: `ao spawn` fails with `✗ AO is not running — lifecycle polling is inactive. Run \`ao start\` before spawning sessions so they get CI/review routing and state advancement.` even though `ao status` works and a dashboard is listening on :3020.

**The `lifecycle-worker` subcommand does NOT exist on this host's `ao` CLI** (verified 2026-06-20, $USER-ny4j dispatch). The correct recovery is to start the full orchestrator, which spawns the lifecycle worker as one of its children. `ao start` is a long-lived foreground process — launch with `terminal(background=true)`, then poll for readiness:

```bash
# Launch in background — MUST specify the project when multiple are configured
cd <project-path> && ~/bin/ao start <project> --no-dashboard --no-open
# Example: ~/bin/ao start worldarchitect --no-dashboard --no-open
# Bare `ao start --no-dashboard --no-open` fails with
#   Error: Multiple projects configured. Specify which one to start:
#     ao start agent-orchestrator
#     ao start worldarchitect
#     ...
# Verified 2026-06-20 (wa-2455 + wa-2458 latency repro dispatch).

# Poll for readiness (the orchestrator pid lands within ~5s)
for i in $(seq 1 18); do
  sleep 5
  if [ -f ~/.agent-orchestrator/running.json ]; then
    PID=$(python3 -c "import json; print(json.load(open('$HOME/.agent-orchestrator/running.json')).get('pid',''))" 2>/dev/null)
    [ -n "$PID" ] && kill -0 $PID 2>/dev/null && { echo "READY at poll $i"; break; }
  fi
done
```

Only write `running.json` by hand if `ao start` was already run but the file went missing (e.g. orchestrator died ungracefully after writing the file and the file was deleted, or the file was never written because the orchestrator was killed during the first ~30s of startup). Full procedure + the hand-write fallback in `agento` skill → `references/ao-spawn-preflight-gotchas.md` §"Gotcha 2".

**Heuristic for "session ls shows working but spawn still fails":** `ao session ls` can show `[working]` for ~30s before `running.json` is written and the lifecycle polling loop is bound. Spawning during that gap fails with the "lifecycle polling is inactive" error even though `session ls` looks healthy. Always confirm `running.json` exists before re-spawning.

**Sibling failure mode — `tmux new-session: command too long`:** this is the documented runtime-tmux env-buffer overflow on $USER's host (243 exported bashrc vars, ~30KB of `-e K=V` args to `tmux new-session`). It is **prevented by the `env -i` wrapper in §"Spawn wrapper" above** — that's the whole reason the wrapper exists. If you spawn WITHOUT the wrapper and hit this error, retry once with the wrapper. If it still fails, load and follow the `ao-spawn-fallback-inline` skill — the 2-attempt cap there applies (one direct attempt + one `ao-spawn-lean.sh` wrapper attempt, then pivot to inline-implement in the worktree). Verified 2026-06-17 (RAG-seam cleanup on `worldarchitect` project): the failure reproduces 1:1 from the 2026-06-15 incident — the runtime-tmux plugin has not been patched yet. The real fix is a separate PR against `jleechanorg/agent-orchestrator-ts` (env whitelist or tmpfile-based env passing in `packages/plugins/runtime-tmux/src/index.ts:143-200` / `:404-435`); do not block the task on it.

## Coordinating with a stale / misrouted AO session (Jeffrey's red line)

When the user reports that an earlier `ao send` to a session ID was an operator mistake (e.g. "wa-2417 was misrouted, /claw should go through Slack/Hermes"), the gateway session has to **coordinate or supersede** that session to avoid duplicate/conflicting branches.

**Recipe (verified 2026-06-20, issue #7722 — wa-2417 misroute):**

```bash
# 1. Inspect the stale session BEFORE writing anything new
tmux list-sessions 2>&1 | grep -E "<session-id>"
tmux capture-pane -t <tmux-name> -p -S -25 | tail -25
cd ~/.worktrees/<project>/<session-id> && \
  git rev-parse --abbrev-ref HEAD && git log --oneline -3 && git status -sb

# 2. Compare the stale session's branch + commits to the user's new request.
#    If they are on an UNRELATED branch (e.g. wa-2417 was on feat/fix-mobile-
#    auth-idb-deadlock-hard-reset while user is asking for #7722 homepage work),
#    they are doing a different job — let them finish or kill them.
#
# 3. Send a stop/pause message via ao send so the worker idles out cleanly
~/bin/ao send <stale-session-id> \
  "STOP/PAUSE: this task was misrouted. /claw is taking over with <new work>.
   Do NOT open new branches or PRs for <new-task> from this session.
   Report idle/stopped when you finish your current turn."

# 4. If the worker does NOT idle out within one poll cycle (~30s),
#    escalate to ao session kill:
~/bin/ao session kill <stale-session-id>

# 5. ALWAYS tell the user explicitly in the Slack thread reply that the
#    stale session was paused/killed and the new dispatch is independent.
#    "wa-2417 was on the unrelated mobile-auth IDB hard-reset; sent it
#     a stop message. If it doesn't idle, I'll kill it on the next poll."
```

**Pitfall — pre-existing branch on the stale session can collide with the new dispatch's auto-derived branch.** AO derives the new session's branch from the first ~64 chars of the task slug. If the stale session is already on `feat/fix-mobile-auth-idb-deadlock-hard-reset` and the new dispatch would derive `feat/homepage-static-asset-fanout`, there is no collision. But if the user copy-pastes a similar task twice, both sessions might derive overlapping branches. **Defense:** name the new dispatch's task slug to include the bead ID + issue number (`"PR1 lazy-load non-auth homepage assets (#7722 rev-9n1pd)"`) so the auto-derived branch always embeds both anchors.

## DON'T pre-create worktrees for AO dispatch — let AO do it

**Anti-pattern (verified 2026-06-20, issue #7722):** I ran `git worktree add ~/.worktrees/<project>/wa-7722-pr1-lazy -b fix/7722-lazy-load-non-auth-homepage-assets origin/main` BEFORE `ao spawn`. Then AO's spawn auto-derived its own branch (`feat/pr1-lazy-load-non-auth-homepage-assets-7722-rev-9n1pd`) and created its OWN worktree (`~/.worktrees/<project>/wa-2420`). My pre-prepared worktree became dead weight — the worker never touched it, and the PR landed on the auto-derived branch.

**The right pattern:**

1. **Write the brief to `/tmp/<project>-<phenotype>/ao-task-brief.md`** (NOT to a worktree, because you don't have one yet — the brief lives at `/tmp/` until AO makes the worktree).
2. **Spawn AO.** AO prints the worktree path + tmux name + auto-derived branch.
3. **Copy the brief into the worker-created worktree root** (`cp /tmp/<project>/ao-task-brief.md ~/.worktrees/<project>/<N>/AO-TASK-BRIEF.md`). Worker reads it from the worktree root.
4. **Don't reset the branch unless the auto-derived name is genuinely unusable.** For bead IDs + issue numbers embedded in the slug, the auto-derived name is fine. For vague prose, reset to `fix/<bead>-<phenomenon>` (see `agento` skill "Spawn Output — Branch Name Auto-Derivation").

**Exception — when pre-creating IS correct:** if you are operating in the same worktree an earlier session already used (e.g. bring-to-green on PR #N), the existing worktree IS the dispatch target and you should NOT pre-create. `ao spawn --claim-pr N` reuses the PR head branch.

## Multi-PR fanout from one issue (N AO workers in parallel)

When one parent issue splits into N child PRs (verified 2026-06-20, issue #7722 → rev-9n1pd + rev-7exd6; verified again 2026-06-20, latency-timer + latency-regression twin dispatch into wa-2455 + wa-2458), the dispatcher has to spawn N workers in parallel and babysit them simultaneously.

**Sibling-vs-bundle decision rule:** when the user says "investigate two things" or "two symptoms at once", the default is **siblings (N PRs, not 1) IF the symptoms have different root mechanisms** even if they touch the same code path or are triggered by the same user action. The `/repro` skill §1.5.0 sibling-vs-duplicate pre-file decision applies: same root + different surface = siblings (parallel PRs); different root + same surface = siblings (parallel PRs); same root + same surface = duplicate (one PR). The user's "two things" framing is itself a signal — treat each "thing" as its own bead + branch + worker unless they share an obvious single root.

**Anti-pattern:** bundling two symptoms into one PR with one worker "because they're related" produces a fix that mixes measurement-integrity and performance-regression changes, makes reviewers accept a 2-in-1 trade, and blocks merge of the clean fix behind the other. Verified failure mode: a "fix streaming latency" PR that secretly also moves the timer edge gets CR CHANGES_REQUESTED on the edge move and the whole PR stalls.

**Recipe:**

1. **Write one brief per child PR** to `/tmp/<project>-<phenotype>/pr<N>-ta[REDACTED_OPENAI_KEY]`. Each brief must declare:
   - **Scope boundary** — what THIS PR owns vs what is the OTHER PR's territory (Jeffrey hates scope creep across the fanout).
   - **Shared evidence paths** — when two PRs need to reference the same evidence bundle (e.g. `docs/evidence/pr-7722-shared/`), name the path once and have each brief point to it.
   - **Cross-PR coordination markers** — name the other PR's bead ID explicitly so each worker can grep for it and avoid stepping on the other PR's files.

2. **Spawn each worker in its own `ao spawn` call.** The per-project spawn lock (`agento` skill §"Per-project concurrent-spawn lock") allows ONE in-flight spawn per project at a time, but serial spawns for the same project within a single session are fine — wait for the first `✔ Session <id> created` before issuing the next.

3. **Babysit all N sessions with one bash loop** (see `scripts/multi-session-babysit.sh` template). The loop polls `ao status` for each session, posts a single Slack thread reply every ~15 min with status for all of them, and exits when all hit terminal state. **DO NOT spawn one babysit per session** — N loops means N Slack posts, which is noise.

4. **Final reply shape for multi-PR fanout:**
   - One row per PR with session ID, branch, evidence paths, current state.
   - One "next reply" promise: "I'll post the final PR URLs + commit SHAs when both workers reach terminal state."
   - One "blockers" line if any.

## Post-spawn workflow — reset branch, copy briefs, send steer

After `ao spawn` returns, do THREE things before letting the worker commit (the auto-derived branch name from the task slug is often too long; reset it BEFORE the worker's first commit):

```bash
# 1. Get the worktree path + tmux name from the spawn output
#    Output:
#      Worktree: $HOME/.worktrees/worldarchitect/wa-2404
#      Branch:   feat/short-summary-repro-rg-fix-for-mobile-game-page-not-loading
#      Attach:   tmux attach -t 953501c04ccc-wa-2404
WT="$HOME/.worktrees/worldarchitect/wa-2404"
TMUX_NAME="953501c04ccc-wa-2404"

# 2. Copy the long task brief + any root-cause evidence into the worktree root
#    (the worker reads these as ./AO-TASK-BRIEF.md and ./root-cause-evidence.md
#     — make them visible from inside the worktree)
cp /tmp/<project>-<phenotype>/ao-task-brief.md "$WT/AO-TASK-BRIEF.md"
cp /tmp/<project>-<phenotype>/root-cause-evidence.md "$WT/root-cause-evidence.md"

# 3. Reset the branch name BEFORE the worker commits (auto-derived slugs are
#    truncated to ~64 chars and often ugly)
cd "$WT"
git fetch origin main
git checkout -B fix/<descriptive-name> origin/main
# Example: fix/mobile-page-not-loading-btF3Nu4mqQRTVLG6F7tu

# 4. Send the steer via ao send — this enqueues in the worker's input buffer
#    and the auto-submit works for nudges to already-running workers
cd ~/.openclaw && ~/bin/ao send <session-name> "Branch reset to fix/<descriptive-name>. Briefs at worktree root. [any project-specific steers the worker needs]"
```

**Why reset the branch before the worker commits:** `ao spawn` derives the initial branch from the first ~64 chars of the task text. A long or prose-style task produces something like `feat/user-s-original-request-verbatim-spawn-ao-worker-unless-its` which then becomes the PR's head ref. Resetting AFTER the worker has committed requires `git reset --hard` + force-push, which is messier. Always reset immediately.

**Why copy briefs into the worktree root:** the worker reads from the worktree, not from `/tmp/` on the host. Files at `/tmp/<project>/brief.md` are invisible to the worker unless copied. Use `AO-TASK-BRIEF.md` (all-caps) and `root-cause-evidence.md` as the canonical filenames so the worker knows they're authoritative.

**Why `ao send` the steer even though the worker has the task:** the spawn's positional arg is just a short summary (truncated to ~64 chars for branch derivation). The steer via `ao send` is where you put the project-specific instructions that don't fit in the slug — which file to edit first, which tests to run, which bead to use, which Slack thread to post in, etc.

For GitHub/PR automation, the lifecycle lane should map directly into this
dispatch path. `comment-validation`, `fix-comment`, and `fixpr` are mctrl
lanes, not Mission Control board tasks.

**Your Project compliance-gate interaction with SPA route changes** (added 2026-06-20, PR #7726): if the dispatched task adds or modifies an SPA route/redirect that fires on `/` (dashboard) — including auto-redirects for empty states, auth-redirects, canonical-URL normalization, theme-mode routing — the worker MUST also verify the `Light/Fantasy Compliance Gate` (the `testing_ui/test_smoke_theme_common.py` smoke suite) still passes. If the gate's dashboard assertion breaks because the redirect now lands on a different view, the worker adds a `?test_mode=true&skip_redirect=true` opt-in bypass (both flags required, production traffic can never set them) and passes the bypass flag in the test URL. Do not silently disable the gate or revert the redirect — the bypass is the correct primitive. Full transcript in `~/.hermes_prod/skills/wa-visual-proof-playwright/references/auto-redirect-capture-and-compliance.md`.

### PR body template (for `[antig]` PRs)

When the dispatched task creates a PR, use the canonical body shape at
`templates/antig-pr-body.md`. It enforces:
- Production symptom with GCP-log evidence
- Three-fix TDD structure (RED → GREEN, with specific files/lines)
- Out-of-scope declaration (prevents scope creep on bring-to-green)
- Dispatch blocker note (if AO failed at runtime-tmux layer)

### Multi-session babysit (bash template)

For a fanout of N AO workers, use the reusable bash template at
`scripts/multi-session-babysit.sh`. It polls `ao status` for all listed sessions,
posts ONE Slack thread reply every ~15 min with status for all of them, and exits
when all hit terminal state (max 4h budget).

**Invocation shape (verified 2026-06-20, wa-2455 + wa-2458 latency fanout):**

```bash
PHENOTYPE=<short-slug> HERMES_SLACK_BOT_TOKEN="$HERMES_SLACK_BOT_TOKEN" \
  ~/.hermes_prod/skills/hermes-imports/dispatch-task/scripts/multi-session-babysit.sh \
  <CHANNEL> <THREAD_TS> "<session-1> <session-2> ..."
```

- `PHENOTYPE` env var controls the log path (`/tmp/${PHENOTYPE}-babysit.log`)
  and the done-marker path (`/tmp/${PHENOTYPE}-babysit-done`). Set it to a
  short slug matching the dispatch (e.g. `wa-latency`).
- `HERMES_SLACK_BOT_TOKEN` is required (the script reads no fallbacks).
- Polls every 5 min (`SLEEP_SEC=300`); posts combined status every 15 min
  (every 3rd poll); posts immediate ping on any terminal state.
- Max budget: 48 polls × 5 min = 4 hours. After that the loop exits even
  if sessions are still working.
- Launch the script itself with `terminal(background=true)` so the
  babysit lives independently of the gateway session — otherwise a
  gateway context-reset kills the babysit and progress notifications
  stop.

See §"Multi-PR fanout from one issue" above for the dispatch side.

### Single-session babysit (simpler, more common case)

For the typical 1-worker dispatch (e.g. /a, /green, single-PR fix), use
`scripts/babysit-one-session.sh <session> <bead> <channel> <thread_ts> [max_polls=24] [sleep_sec=300]`.
It polls one session, posts per-poll status to the thread, detects terminal
state from `ao status` (exited/killed/done/merged/closed/errored/failed), and
captures the PR URL via `gh pr list --head <branch>`. Launch the script itself
with `terminal(background=true)` so the babysit lives independently of the
gateway session.

Token resolution order (in script): `$OPENCLAW_SLACK_BOT_TOKEN` →
`$SLACK_MCP_XOXB_TOKEN` → `$HERMES_SLACK_BOT_TOKEN`. Verified 2026-06-20
(wa-2428 / $USER-ny4j) — the first var was empty in the gateway's plain
`env` but the third was set and the post worked.

**Babysit script permission pitfall (verified 2026-06-20, $USER-c2kv latency dispatch):**
the shipped scripts ship as `-rw-r--r--` (NOT executable). Calling via `bash <script>` works, but invoking via `<script>` path fails with `Permission denied` and exits silently after ~4 min — the babysit appears broken (no Slack "armed" ack, no status updates) while the AO workers are perfectly healthy. Both babysit scripts now self-chmod at startup as a defensive layer, so this is auto-recovering going forward. If you dispatch a babysit and see no `🔭 Babysit armed for N session(s)` ack in the Slack thread within 30s, check `ps aux | grep babysit` and the `/tmp/<phenotype>-babysit.log` for the failure mode. Manually `chmod +x` if needed; if the script is gone or won't run, fall back to a manual `terminal(background=true)` polling loop.

### Cross-repo PRs

When the task involves making a PR to a different repo than the worktree:
- DO NOT clone the target repo into a subdirectory
- Use `gh pr create --repo owner/repo --base main --head <branch>` to PR cross-repo
- Example: for mctrl_test repo, use `gh pr create --repo jleechanorg/mctrl_test --base main`

Ensure the task text instructs the agent to push before it stops. Include wording like:

> After making and committing the change, run `git push origin <branch>` and only then stop.

### 5. Confirm dispatch

The `ao spawn` command prints the session name. Note it for tracking.

Update bead notes with the session name **and Slack context** so the supervisor knows which thread to reply to. Note `br update --append-notes` does not exist; concat the old notes yourself:
```bash
OLD_NOTES=$(br show <bead-id> --json | python3 -c "import json,sys; print(json.load(sys.stdin).get('notes',''))")
NEW_NOTES="${OLD_NOTES}
Dispatched to session <session-name>. slack_trigger_ts=<SLACK_TRIGGER_TS> slack_trigger_channel=<SLACK_TRIGGER_CHANNEL>. Supervisor watching."
br update <bead-id> --notes "$NEW_NOTES"
```

The mctrl supervisor reads `slack_trigger_ts` and `slack_trigger_channel` from bead notes to post the completion reply in the correct Slack thread.

## What happens next (automatic)

The mctrl supervisor loop (`ai.mctrl.supervisor` launchd agent) runs every 30s and:
1. Checks if the tmux session is still alive
2. When session ends: checks `git log start_sha..HEAD` for commits and verifies the branch is reachable on a configured remote
3. Posts DM to $USER + thread reply under the original Slack message; during long runs, periodic in-thread progress updates should be emitted at least every 5 minutes
4. Sends MCP Agent Mail notification to Hermes

**You do not need to poll.** The supervisor handles completion notification, but it will only classify the task as finished if the review surface exists on remote.

## Notes

- `ao spawn` creates an isolated git worktree for each task automatically (configured in `agent-orchestrator.yaml`)
- Finished means remote-reviewable on a configured remote, not merely committed locally inside the worktree
- If `ao spawn` fails, check that `ao` is on PATH and agent-orchestrator is properly configured
- **Stale / misrouted session recovery:** see §"Coordinating with a stale / misrouted AO session"
- **Don't pre-create worktrees:** see §"DON'T pre-create worktrees for AO dispatch"
- **N-worker fanout from one issue:** see §"Multi-PR fanout from one issue"

## References (companion files)

- `references/ao-spawn-long-ta[REDACTED_OPENAI_KEY]` — Fresh-spawn `ao send --file` does NOT auto-submit for bodies >4 KB; `tmux load-buffer` + `paste-buffer` + Enter is required. Verified 2026-06-16, wa-2369.
- `references/beads-rust-cli-gotchas.md` — `br` CLI flag pitfalls table (`--label` vs `--labels`, positional ID ordering, `--append-notes` does not exist), host ID format (`$USER-XXXX`), and the append-notes recipe. Verified 2026-06-20, wa-2455 + wa-2458 latency-repro twin dispatch.
- `templates/antig-pr-body.md` — Canonical PR body shape for `[antig]` PRs (production symptom + RED→GREEN + out-of-scope declaration).
- `scripts/babysit-one-session.sh` — Single-session babysit template; polls every 5 min, posts per-poll status.
- `scripts/multi-session-babysit.sh` — N-session babysit template; one Slack post every ~15 min with all sessions' status.
