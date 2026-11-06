---
name: claude-code-claudem
description: "Delegate coding work to Claude Code CLI routed through the user's bashrc `claudem` (alias `claudeminimax`) wrapper that points at a non-Anthropic provider (typically MiniMax M3). Thin wrapper over the bundled `claude-code` skill — same two modes (print + tmux), but the default binary is `claudem`, not `claude`. Use this skill when dispatching a `claudem -p` worker that must post progress to a Slack thread (round-trip or multi-step babysit), when running the bashrc-vs-binary decision for a new provider wrapper, or when auditing any wrapper layer that uses default-if-unset for ANTHROPIC_MODEL/ANTHROPIC_BASE_URL globals."
tags: [Coding-Agent, Claude, Provider-Routing, Coding, Refactoring, PTY, Automation, Wrapper]
related_skills: [claude-code, codex, hermes-agent, opencode]
version: 1.8.3
author: Hermes Agent
license: MIT
platforms: [linux, macos]
changelog:
  - "1.8.3 (2026-07-30): Two new references — `references/stale-agent-prompt-worktree-recovery.md` (verified 2026-07-30 on gemini-flash-vs-luna-compare task: `git worktree add /tmp/<topic>` collided with a prior session's `.agent_prompt_<other-branch>.txt`, worker rebound to old prompt and wrote to `/private/tmp/<topic>-new/` instead; recipes for pre-clean, parent-finishes-from-evidence-dir, and safe-path selection) AND `references/gcp-secret-manager-gemini-fallback.md` (verified 2026-07-30: `~/.gemini_api_key_secret` returned `API_KEY_INVALID`, service account lacked `aiplatform.endpoints.predict`, but `gcloud secrets versions access latest --secret=gemini-api-key --project=worldarchitecture-ai` returned a working key `AIzaSyAvyb...`; OpenRouter chat-completions also covered all 5 models as universal fallback for cross-vendor benchmarks). Anti-pattern: declaring 'Gemini key broken' after probing only one auth source — there are typically 3-4 paths and any one being alive is enough."
  - "1.8.0 (2026-07-28): Added `references/giant-batch-then-parent-closeout.md` — when a wave of ≥3 subagents dispatches in parallel via `delegate_task` and all hit the 600s runtime timeout during the commit/push/PR-open closeout, the parent session finishes the mechanical step from the worktree state (NOT re-dispatch). Verified on a 5-subagent wave shipping PR-A (generic shared contracts + AI mystery/internal-drive arcs) + PR #8661 (Spellblade fixes); 3 of 5 timed out but 90% of work landed; parent finished AGENTS.md rule + test file + commit + push + open PR + posted per-blocker reply comment. Anti-pattern: re-dispatching the timed-out worker re-burns 600s re-analyzing the same files."
  - "1.8.1 (2026-07-30): Added a 5th sizing-table row \"Research + reproduction + report, single ping\" → 60-80 turns. Verified on the gemini-3.5-flash-lite vs Gemini 3 Flash vs GPT-5.6 Luna comparison task (6 evidence rows + real Gemini/OpenRouter API probes + comparison_report.md write): `--max-turns 50` burned every turn on 2 of 6 probes + R2 setup retries, never got to R3/C-tests/report. Each `python3 -c` API probe ≈ 3 turns (script-write + run + parse + retry-on-auth-fail), not 1. When the brief has ≥6 evidence rows AND real API calls AND a final report write, budget 60-80 turns minimum. Parent can finish a partially-completed report from the worktree's `evidence/` dir directly — no re-dispatch needed."
  - "1.7.0 (2026-07-28): Added `references/no-silent-babysit-multi-ping.md` — the 5-ping contract for multi-step verification work (the user's 'never hear anything again' pattern). Verified on PR #785 (4 min 12 s wall time, 6 in-thread pings, zero silent gaps). Adds a 'Pattern — No-silent-babysit multi-ping' section to the skill body, a max-turns sizing table (12 too tight for 5 pings, 30 right), and the 'honest reporting' rule: when the target is already N-green, verify and report, do not fabricate work to fill time."
  - "1.6.0 (2026-07-28): Added `references/round-trip-dispatch-proof.md` — the 4-step protocol for proving the wrapper works end-to-end in an operator-observable Slack channel (dispatch → claudem -p → PR → in-thread reply). Verified live in #claw-dispatch on 2026-07-28 (PR #806, ~3 min wall time). Refined the v1.5.1 'workers cannot post to Slack' pitfall: workers DO have curl + bash and CAN post to Slack if given the channel id + thread_ts + HERMES_SLACK_BOT_TOKEN in the prompt (no MCP needed). What workers cannot do is see the user's conversation context — the gateway is the only layer that knows which thread is 'the one I'm in'."
  - "1.5.1 (2026-07-28): Skill library sync after PR #800 head `0eafbfb228` landed. Patched the alias-convention callout (was still saying `claude_minimax` with underscore after the v1.5.0 body update — drift between the worktree copy and the registry copy). Patched the v1.4.0 changelog entry to mark it SUPERSEDED rather than describe its shim-recommended pattern as current. The class-level parent (`claude-codex-provider-routing`) was also updated: removed the 'Three layers (incl. `~/bin/<wrapper>` shim)' rule, rewrote the bashrc-globals leak pitfall to be about ANY wrapper layer that uses default-if-unset (not just binary shims), and added an explicit user-preference pitfall: bashrc functions over binary shims, no underscores, single source of truth."
  - "1.5.0 (2026-07-28): Bashrc-only wrapper. Removed the `~/bin/claudem` binary shim (and `claude_minimax` / `claude_minimaxc` symlinks) because it drifted from the bashrc function. Added `claudeminimax` (no underscore, matches the `claudeg`/`claudek`/`claudeds`/`claudegz` family form) as a pure bashrc alias of `claudem`. Updated all skill docs, contract tests, and references to use `bash -lic 'claudem …'` for non-interactive callers (pytest, launchd, AO workers, GitHub Actions)."
  - "1.4.0 (2026-07-26): [SUPERSEDED by 1.5.0 — kept for history] Documented a `~/bin/claudem` binary shim as the canonical non-interactive invocation pattern. The shim had a real drift bug (default-if-unset `ANTHROPIC_MODEL` inherited bashrc's global `sonnet`, silently routing to `claude-sonnet-5`) that the slow M3 probe caught on 2026-07-28. The fix at the time was to change `${VAR:-default}` → force-export. v1.5.0 made the larger call to drop the binary entirely — `bash -lic 'claudem …'` solves the same problem without a second source of truth."
  - "1.3.0 (2026-07-26): Two new pitfalls. (1) tmux send-keys paste handler splits long bodies into two [Pasted text #N] blocks; the trailing Enter only submits the FIRST block — always issue a second literal Enter after sleep 2. Verified PR #8629 (~20KB brief). (2) gh pr create is GraphQL-backed and fails when that bucket is exhausted even though REST is fine; worker recovery is file-edit-then-push via git (no API), then POST /repos/.../pulls via REST with $GH_TOKEN. Verified PR #8629. The companion one-shot skill long-ta[REDACTED_OPENAI_KEY] has been consolidated into this umbrella's pitfall section; the leaf was deleted (curator guidance: class-level skills, not flat one-session leaves)."
  - "1.2.0 (2026-07-26): Verified-case pitfall added for claudem bashrc function vs binary, with --agent minimax not-on-ao-go-daemon fallback via existing scoped worktree + claudem -p background + verify-remote-SHA + cron verify-after-rate-limit-reset. Full transcript + verified PR #24 (jleechanorg/agent-orchestrator, commit 7e97d91e1)."
  - "1.1.0 (2026-07-22): Added claude_minimax alias contract (zero-churn pure alias of claudem); idempotent installer recipes; new pitfalls (wrapper-model quality vs Claude; --chrome-dropped variance; CLAUDEM_MODE=1 export)."
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Provider-Routing, Coding, Refactoring, PTY, Automation, Wrapper]
    related_skills: [claude-code, codex, hermes-agent, opencode]
    replaces_default_binary_for: [claude-code]
    binary_aliases: [claudem, claudeminimax]
    invocation_pattern_non_interactive: "bash -lic 'claudem …'"
---

# Claude Code via `claudem` — Hermes Orchestration Guide

> **What this skill is:** a thin wrapper over the bundled [`claude-code`](https://hermes-agent.nousresearch.com/docs) skill. The bundled skill is the source of truth for everything Claude-Code-CLI-related (flags, modes, error handling, session resumption, JSON output, cost controls, tmux orchestration). This wrapper exists to swap the **binary** invoked by your coding work from `claude` to a user-defined `claudem` bashrc function (the convention used in `~/.claude-codex-provider-routing`) without forking the upstream skill.
>
> **Read the bundled `claude-code` skill first** for the comprehensive guide. Then come back here for the differences.
>
> **Alias convention:** `claudem` and `claudeminimax` (no underscore) resolve to the same bashrc function. Use whichever the operator prefers; both are first-class on this skill.

## When to use this skill

Use `claude-code-claudem` (this skill) when:

- You want to delegate coding work to Claude Code CLI but **routed through a custom `claudem` shell function** that overrides the upstream API endpoint, model, and auth (commonly a MiniMax/Anthropic-compatible proxy with model `MiniMax-M3`).
- You explicitly want to avoid hitting Anthropic first-party (rate-limit isolation, cost routing, fallback to a different provider).
- You're working in a session where the wrapper is the active LLM and you want the delegated worker to use the same provider family.
- You are dispatching a `claudem -p` worker that must post progress to a Slack thread (round-trip or multi-step babysit — see "Pattern — Round-trip dispatch proof" and "Pattern — No-silent-babysit multi-ping" below).
- You are auditing a wrapper layer that uses `default-if-unset` for ANTHROPIC_MODEL / ANTHROPIC_BASE_URL — the v1.5.0 era bug class.

Use the bundled `claude-code` skill (NOT this one) when:

- You need Anthropic first-party routing (real Claude Opus/Sonnet) and have OAuth or a separate `ANTHROPIC_API_KEY` you want to honour.
- The task is in a your-project.com PR review context where `/er` / `/advice` comments must come from the real Anthropic identity (see `wa-green-gate-pr-shape/SKILL.md`).
- The user explicitly says "use Anthropic" / "real Claude" / "not the wrapper" / "not claudem".

## What `claudem` is

`claudem` is a **bashrc shell function** (NOT a binary on `$PATH`) that wraps `claude` with overridden environment variables. It is defined in `~/.bashrc` (typically near line 1063, alongside the other `claudeg` / `claudek` / `claudeds` / `claudegz` family functions) and sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL="MiniMax-M3"`, and `ANTHROPIC_API_KEY` (from `$MINIMAX_API_KEY`) before `exec claude --dangerously-skip-permissions --effort high "$@"`.

> **There is no `~/bin/claudem` binary by design.** A binary shim existed from 2026-07-22 to 2026-07-28 and was removed because (a) it drifted from the bashrc function (default-if-unset vs force), and (b) every non-interactive caller on this host can use `bash -lic 'claudem …'` to source the bashrc. See `references/subprocess-vs-interactive-shell.md` for the full failure-mode table.

### Alias: `claudeminimax`

The bashrc family uses no-underscore naming: `claudeg` (GLM), `claudek` (Kimi), `claudeds` (DeepSeek), `claudegz` (Z.AI direct), and `claudem` (MiniMax). The spelled-out form `claudeminimax` is a pure bashrc alias that delegates to `claudem`. Both names resolve to the same wrapper — same env vars, same flags, same model. The recipe (already in `~/.bashrc`, shown here for reference):

```bash
# In ~/.bashrc, alongside the claudem family:
claudeminimax() { claudem "$@"; }
claudeminimaxc() { claudem --continue "$@"; }
```

The two functions are pure aliases — no second wrapper, no second source-of-truth. Same env vars, same flags, same model. Either name works in print mode, tmux orchestration, and AO worker contexts.

Companion aliases commonly shipped alongside: `claudeme` (typo fix → `claudem`), `claudemc` (= `claudem --continue`).

## The three differences vs the bundled `claude-code` skill

1. **Binary name is `claudem`, not `claude`.** Every `claude` invocation in the skill body becomes `claudem`. Print mode: `claudem -p '...'`. Interactive: `tmux send-keys ... 'source ~/.bashrc && claudem ...'`.
2. **`--dangerously-skip-permissions` and `--effort high` are usually baked in** by the wrapper. You do NOT need to pass them yourself. Passing them again is harmless (Claude Code accepts the duplicate).
3. **The wrapper env (`ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_API_KEY`) must reach the child process.** For print mode (a subprocess of a bashrc-sourced shell) this is automatic. For tmux interactive mode, **the tmux pane is a separate process tree** — see the hardened guidance below. For non-interactive callers (`subprocess.run`, launchd, AO workers, GitHub Actions runners), use `bash -lic 'claudem …'` so the bashrc is sourced.

## Two orchestration modes (mirrors the bundled skill)

### Mode 1 — Print Mode (`claudem -p`) — non-interactive, PREFERRED for most tasks

**Interactive shell (bashrc already sourced):**
```bash
terminal(command="claudem -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10", workdir="/path/to/project", timeout=120)
```

**Non-interactive caller (pytest, launchd, AO workers, GitHub Actions):**
```bash
terminal(command="bash -lic 'claudem -p \"Add error handling to all API calls in src/\" --allowedTools Read,Edit --max-turns 10'", workdir="/path/to/project", timeout=120)
```

The `-l` (login) flag forces `~/.bashrc` to source inside the spawned bash, making the `claudem` function visible. This is the canonical pattern for any non-interactive caller — see `references/subprocess-vs-interactive-shell.md` for why a binary shim is no longer needed.

The wrapper sets `--dangerously-skip-permissions` itself, so you don't need to repeat it. If you pass it again, Claude Code silently accepts the duplicate.

### Mode 2 — Interactive PTY via tmux — multi-turn (HARDENED)

> **Critical tmux detail:** `tmux send-keys` does **not** carry the caller's environment into the existing pane. If the pane was started by a non-login shell (launchd, AO worker, any daemon that strips env) the three `ANTHROPIC_*` vars will be missing, and `claudem` inside the pane will fall through to Anthropic first-party. **Always source the shell-rc that defines the wrapper before launching `claudem` inside the pane.**

```bash
# Start a tmux session
terminal(command="tmux new-session -d -s claudem-work -x 140 -y 40")

# Launch claudem inside it — ALWAYS source the shell-rc first so the
# wrapper's ANTHROPIC_* env vars are defined in the pane.
terminal(command="tmux send-keys -t claudem-work 'source ~/.bashrc && cd /path/to/project && claudem' Enter")

# Wait for startup, then send your task (~3-5s for the welcome screen)
terminal(command="sleep 5 && tmux send-keys -t claudem-work 'Refactor the auth module to use JWT tokens' Enter")

# Monitor progress
terminal(command="sleep 15 && tmux capture-pane -t claudem-work -p -S -50")

# Exit when done
terminal(command="tmux send-keys -t claudem-work '/exit' Enter")
```

If you want to avoid the `source` step, set the three `ANTHROPIC_*` env vars on the tmux server itself before any pane is created:

```bash
tmux new-session -d -s claudem-work -x 140 -y 40
tmux set-environment -t claudem-work ANTHROPIC_BASE_URL "https://api.minimax.io/anthropic"
tmux set-environment -t claudem-work ANTHROPIC_MODEL    "MiniMax-M3"
tmux set-environment -t claudem-work ANTHROPIC_API_KEY   "$MINIMAX_API_KEY"
tmux send-keys -t claudem-work 'claude --dangerously-skip-permissions' Enter
```

Either approach is valid; pick the one that matches your launch context.

## Pattern — Giant-batch-then-parent-closeout (wave-of-subagents → parent finishes mechanical)

When a wave of ≥3 subagents dispatches in parallel via `delegate_task` whose deliverable is a complete PR (or set of PRs) — file authoring + commit + push + PR open — every subagent will hit the 600s runtime timeout during the mechanical closeout (file authoring is fast; each `git add` + `git commit` + `git push` + `gh pr create` is a separate tool call). The compiled report arrives with `status=timeout` for every subagent even when 90% of the work landed. **Do NOT re-dispatch.** Re-dispatch wastes another 600s re-doing the file work. The parent session inspects `git status` on each worktree and finishes the closeout from the worktree state. Full recipe + lived proof: `references/giant-batch-then-parent-closeout.md`. Anti-pattern: re-dispatching the timed-out worker re-burns 600s re-analyzing the same files.

## Pattern — Round-trip dispatch proof (single ping)

Use this when dispatching a worker to do a **single coding change** and you want proof in the operator-observable channel that the worker completed it. Full reproduction recipe, transcript, and failure modes: `references/round-trip-dispatch-proof.md`. Summary:

1. Post a top-level (not reply) message describing a SMALL, well-scoped task in a dispatch channel the operator monitors (e.g. `#claw-dispatch`). Capture the `ts` from the response — that's the thread anchor.
2. Spawn the worker: `bash -lic "claudem -p \"$(cat worker_prompt.md)\" --allowedTools 'Read,Edit,Glob,Grep,Bash' --max-turns 15 --output-format text"`. The worker prompt MUST include (a) the task, (b) the channel id + thread_ts as literal values, (c) the exact `chat.postMessage` curl example with `thread_ts`.
3. The worker reads/edits/commits/pushes/opens-PR/posts-back to the same thread via curl.
4. After the worker exits, verify the reply landed in-thread with `conversations.replies`.

Live proof (2026-07-28): PR #806 in `#claw-dispatch` (ts `1785284123.726119`), 3 min wall time, worker reply at ts `1785284261.068169`.

## Pattern — No-silent-babysit multi-ping (≥5 pings)

Use this when the worker is doing **multi-step verification or babysitting** (e.g. drive a PR through `/green /er /advice`, run a long diagnostic, coordinate a multi-PR fix). The user wants to see continuous activity, not one end-of-run summary. Full reproduction recipe, transcript, and failure modes: `references/no-silent-babysit-multi-ping.md`. Summary:

1. Same dispatch setup as the single-ping pattern, but the task has **multiple verification stages**.
2. The worker prompt MUST explicitly require AT LEAST 5 in-thread messages: spawn + one ping per verification step + final verdict. Each message 1-3 lines with an emoji status (🟡/🟢/🔴).
3. **Sizing `--max-turns`:** for a 5-ping task with 3 verification steps, budget `--max-turns 30`. The first attempt with `--max-turns 12` died after step 1 on 2026-07-28; `--max-turns 30` completed cleanly.
4. **Honest reporting rule:** if the worker discovers the target is already in the desired state (e.g. PR already N-green), verify and report — DO NOT fabricate commits or edits to fill the time. The operator values honest reporting over productive-looking activity.

Live proof (2026-07-28): PR #785 babysit in `#claw-dispatch` (ts `1785284907.621589`), 4 min 12 s wall time, 6 in-thread pings (including one retry ping after `--max-turns 12` exhaustion), zero silent gaps longer than ~65 s. Worker correctly reported "PR already N-green" with full evidence and surfaced two extra caveats (a side-channel script referenced but not in the diff; the after-restart smoke depends on a Slack side-channel that could itself fail).

## Sizing `--max-turns` — quick reference

| Worker shape | Recommended `--max-turns` |
|---|---|
| Single ping, single file change | 15 |
| Single ping, two-file change | 25 |
| Multi-ping, 3 verification steps (this skill's "no-silent-babysit" pattern) | 30 |
| Multi-ping, with tests spawned from worker | 35-40 |
| **Research + reproduction + report, single ping** (≥6 evidence files, real API probes via `curl`/`python3 -c`, end with a verdict-table write) | **60-80** |

Each `Bash` tool call ≈ 1 turn. Each verification step ≈ 3-5 turns (read + gh query + curl post). When the worker runs out of turns, the right move is **re-fire with a larger budget**, not shrink the scope — the operator wants the full round-trip, not a truncated one.

**Sequencing pitfall for research/reproduction workers (verified 2026-07-30, gemini-flash-vs-luna-compare task):** a worker given a brief like "reproduce 3 bugs + run 3 comparisons + write a report" with `--max-turns 50` burned every turn on R1 + R2 setup (two of six planned probes) and exited before R3/C-tests/report. Root cause: each `python3 -c` API probe ≈ 3 turns (script-write → run → parse output, plus a retry when auth fails the first time), not 1. When the brief contains ≥6 evidence rows AND real API calls AND a final report write, budget 60-80 turns minimum. If the worker runs out mid-report, parent can finish the report from the worktree's `evidence/` dir directly (no re-dispatch needed). Anti-pattern: raising `--max-turns` to 60 in the brief but still expecting the worker to do R1+R2+R3+C1+C2+C3+report within 50 — pick the smaller scope or larger budget.

## Prerequisites

- `claudem` (or its alias `claudeminimax`) must be defined in `~/.bashrc`. Verify: from a bashrc-sourced shell (`bash -lic 'type claudem'`) you should see `claudem is a function`. For non-interactive callers (AO workers, launchd, `subprocess.run`, Go PATH shims, GitHub Actions), use `bash -lic 'claudem …'` so the function is visible. See `references/subprocess-vs-interactive-shell.md` for the failure-mode table.
- The auth-token env var (`MINIMAX_API_KEY`) must be exported in the shell that runs `claudem` (the wrapper reads it at call time). For launchd-driven invocations, use `launchd-env-wrapper.sh` to inject it (see `hermes-deploy-pipeline/references/launchd-env-injection-and-wrapper.md`).
- Claude Code v2.x+ (`bash -lic 'claudem --version'` should report `2.x.y (Claude Code)`).
- The local `or-anthropic-proxy` at `127.0.0.1:8767` is **NOT** used by `claudem` in the standard setup — `claudem` calls the configured `ANTHROPIC_BASE_URL` directly. If your environment has the proxy on a different port, double-check the wrapper's `ANTHROPIC_BASE_URL` doesn't accidentally point at it.

## Gotchas

- **`claude.ai connectors disabled` warning** at the top of every response: expected, because the wrapper exports `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) which takes precedence over a `claude.ai` OAuth login. Not a failure.
- **First call takes ~3-5s** for the model warmup. Print-mode `--max-turns 1` round-trips in ~6-8s end-to-end.
- **Wrapper-model quality ≠ Claude quality.** Outputs come from the model named in the wrapper's `ANTHROPIC_MODEL` (commonly a MiniMax-family model), not from Claude Opus/Sonnet. Use the bundled `claude-code` skill when you need real Claude judgment (e.g. adversarial design review, code review of sensitive PRs). Use `claudem` / `claudeminimax` for routine coding delegation.
- **Some wrappers drop `--chrome`**, unlike the Agnt-F `claudeaf` variant which adds it. Don't expect browser automation from a session started by a minimal `claudem`.
- **`CLAUDEM_MODE=1` is exported into the child shell** by the canonical wrapper. If a downstream tool checks this var, it will know it's running under `claudem`. Don't clear it manually. `claudeminimax` inherits the same `CLAUDEM_MODE=1` since it is a pure bashrc alias, not a second wrapper.
- **Wrapper composability**: `claudemc` = `claudem --continue`; `claudeminimaxc` = `claudeminimax --continue`. There is no `claudem --resume` alias — pass `--resume <id>` directly.
- **Subprocess vs interactive-shell behaviour** is the #1 gotcha. `subprocess.run(['claudem', …])` from Python fails with `claudem: command not found` because subprocesses don't inherit the parent shell's function table. The canonical pattern is `subprocess.run(['bash', '-lic', 'claudem …'])`, which forces `~/.bashrc` to source inside the spawned bash. This is what the contract tests in `tests/test_claude_code_claudem.py` do. See `references/subprocess-vs-interactive-shell.md` for the full failure-mode table.
- **`claudeminimax` vs other CLI patterns.** The `claude<family>` convention (no underscores, no separator) is consistent across the family: `claudeg`, `claudek`, `claudeds`, `claudegz`, `claudem`, and now `claudeminimax` as the spelled-out alias. If a future provider needs its own wrapper, the recipe is a bashrc function in the same family form, NOT a binary. The recipe in `~/.claude-codex-provider-routing/SKILL.md` is the canonical source for adding new provider wrappers.
- **`ANTHROPIC_MODEL` global in `~/.bashrc:939` is intentional, not a bug.** The bashrc exports `ANTHROPIC_MODEL="sonnet"` so plain `claude` defaults to sonnet and does NOT persist `--model MiniMax-M3` into `~/.claude/settings.json` (which would pollute every subsequent bare `claude` run). The bashrc `claudem()` function overrides this at call scope. **Any wrapper layer that does `export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-MiniMax-M3}"` (default-if-unset) silently inherits the global `sonnet` and routes to `claude-sonnet-5` instead.** Always use `export ANTHROPIC_MODEL="MiniMax-M3"` (force) in any wrapper layer — bashrc functions are immune because they set inline, only executable shims and exported env layers are at risk. Verified bug class 2026-07-28 (the v1.1.0–v1.4.0 binary era); full reproduction in `references/bashrc-global-leak.md`.
- **Stale `.agent_prompt_<branch>.txt` worktree collision (verified 2026-07-30, gemini-flash-vs-luna-compare task).** When `git worktree add <path> -b <branch> origin/main` is invoked from a parent dir that already contains a `.agent_prompt_<other-branch>.txt` from a previous unrelated session (Hermes agent workflow leaves these around), Claude Code's runtime detects the existing prompt string and starts the new session at the OLD prompt's working directory, NOT the new worktree. Symptom: worker exits with `Reached max turns` and the only file it created is in the wrong directory (e.g. `/private/tmp/gemini-luna-compare-new/` instead of `/tmp/gemini-luna-compare/`), with the new worktree directory empty. Detection: `ls -la /tmp/gemini-luna-compare*/` shows the wrong path has a `.agent_prompt_<other-branch>.txt` AND all evidence files, while the intended worktree path has only `worker_brief.md`. Fix: before `git worktree add`, `rm -f .agent_prompt_*.txt` in the parent directory; or pass an explicit worktree path that has no Hermes agent footprint (`/private/tmp/wt-<topic>` is the canonical safe path on macOS). Anti-pattern: trusting `git worktree add <path>` to give you a clean slate when the parent dir has prior session state — always `ls -la` the new worktree before `bash -lic 'claudem …'`. Same failure mode as session `20260722_155550_273bd3e1` ("Stale prompt artefact in worktree"). Full recipe + parent-finishes-from-evidence-dir pattern: `references/stale-agent-prompt-worktree-recovery.md`.

- **Dead local Gemini key + working GCP secret-manager key (verified 2026-07-30).** When `~/.gemini_api_key_secret` returns `API_KEY_INVALID` AND the service account `~/serviceAccountKey.json` lacks `aiplatform.endpoints.predict` role on Vertex AI, the local-Gemini path is dead — but `gcloud secrets versions access latest --secret=gemini-api-key --project=worldarchitecture-ai` returns a working key. OpenRouter's chat-completions endpoint also covers all 5 models (Gemini 3 Flash / 3.5 Flash / 3.5 Flash Lite / 3.6 Flash / GPT-5.6 Luna) as a universal fallback for cross-vendor benchmarks. Full recipe + 4-auth-path probe matrix: `references/gcp-secret-manager-gemini-fallback.md`. Anti-pattern: declaring "Gemini key broken" after probing only one auth source — there are typically 3-4 paths and any one being alive is enough.

- **Worker scope vs gateway scope — workers have curl but not Slack MCP.** A `claudem` worker runs `claude --dangerously-skip-permissions --effort high` as a child process. Its tool surface is whatever Claude Code exposes: `Read`, `Edit`, `Bash`, `Grep`, `Glob`, `WebFetch`, etc. **Slack MCP tools (`mcp__slack__conversations_add_message`, `chat.postMessage`, etc.) are NOT part of that toolset.** The worker does not know the user's `thread_ts`, the channel ID, or that it is running inside a Slack thread — that context lives in the gateway session's conversation, not the worker's. Workers CAN post to Slack if the gateway session passes them the channel id + thread_ts + `HERMES_SLACK_BOT_TOKEN` in the prompt and tells them to use `curl` (verified 2026-07-28 in `#claw-dispatch`, PR #806 — worker replied in-thread via `bash -lic 'curl …'`). But workers cannot **discover** the thread context themselves. When the user asks the gateway session "tell the worker to update this thread every minute," the correct answer is structural: the worker cannot do that autonomously — only the gateway session can. Recipe for the gateway: (a) state the limitation directly in the thread, (b) offer the alternative — "I will poll `process(action='poll')` + `git -C <wt> status --short` from this session and post updates every N minutes", (c) execute that polling cadence for the duration of the worker run, (d) on worker exit, surface the durable state (commit SHA + file list + test output + PR URL) in a single terminal reply. Verified 2026-07-28: user asked "Are you really executing? ... Will I actually see updates in this thread or will you never update it again?" after a worker exited with zero edits — the lesson is that observable checkpoints MUST come from the gateway, never promised from the worker. The same limitation applies to all background workers (claudem / `ao spawn` / opencode / Codex / openhands) — none have Slack-thread identity unless explicitly wired at the gateway. For the worker-side pattern that DOES work (worker reads channel+thread from prompt, posts via curl), see `references/round-trip-dispatch-proof.md`. For the multi-step variant with continuous pings, see `references/no-silent-babysit-multi-ping.md`.

## vs `claude-code`

- **`claude-code`** — the bundled Hermes skill. Binary = `claude`, routes to Anthropic first-party. Use for real Claude judgment, worldarchitect PR review, anything that needs Claude Opus/Sonnet quality or `claude.ai` OAuth.
- **`claude-code-claudem`** (this skill) — wrapper skill. Binary = `claudem` (or its alias `claudeminimax`), routes to whatever provider your bashrc function configures (commonly MiniMax M3). Use for routine coding delegation where you want wrapper-based routing (rate-limit isolation, cost, fall-through behaviour).
- Both share the same two-mode structure (print + tmux) and the same flag semantics. Switching between them is a 6-character diff (`claude` ↔ `claudem` or `claudeminimax`).
