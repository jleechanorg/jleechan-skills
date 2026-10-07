# Bug-hunt cron codex-review race — 2026-07-23 09:01 PT

The Daily Bug Hunt Report posted to Slack at `bug-hunt-20260723_090145.md` reported:

> PRs reviewed: 9 / Bugs found: 0 / Agent failures: 3/3

The agent-failures warning fired correctly — but the **root cause** was a parallel-CLI-process race the script's `FAILURE_WARNING` gate masked as "every agent failed independently". In reality, all three agents hit the same race at the same time, against the same CLI binary, against the same model.

## The smoking-gun: mixed empty/non-empty `.err` across the three lanes

| Lane (cosmetic label) | CLI binary that actually ran | Model | `.json` size | `.err` size |
|---|---|---|---|---|
| `claude` | `codex review` (Codex CLI v0.144.5) | `gpt-5.3-codex-spark` | 0 bytes | **0 bytes** |
| `codex` | `codex review` (Codex CLI v0.144.5) | `gpt-5.3-codex-spark` | 0 bytes | **0 bytes** |
| `minimax` | `codex review` (Codex CLI v0.144.5) | `gpt-5.3-codex-spark` | 0 bytes | **4083 bytes** |

All three labels resolved to the same `codex review -c "model=\"gpt-5.3-codex-spark\"" -` invocation — the labels are cosmetic. The `minimax` `.err` contained the actual error:

```
2026-07-23T16:46:24.841708Z ERROR codex_models_manager::manager: failed to refresh available models: timeout waiting for child process to exit
OpenAI Codex v0.144.5
--------
workdir: $HOME/.hermes
model: gpt-5.3-codex-spark
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019f8fdf-5bf2-7142-a341-f03534fdef95
--------
user
Bug Hunt Task for minimax:
[... TASK_PROMPT with the 9 PRs JSON array ...]
```

The `minimax` lane won the model-list cache lock long enough to print the banner, but then the lock conflict caused the timeout. The `claude` and `codex` lanes lost the lock entirely and produced 0-byte `.err`. All three lanes produced 0-byte `.json` because the markdown-fence extractor found no output before the process died.

## Script trace — lines that caused the race

### `bug-hunt-daily.sh` lines 161, 230-238 — parallel same-CLI spawn

```bash
AGENTS=("claude" "codex" "minimax")
...
for AGENT in "${AGENTS[@]}"; do
    ...
    (
        printf '%s\n' "$TASK_PROMPT" | codex review \
            -c "model=\"$REVIEW_MODEL\"" - 2>>"$ERR_FILE" | \
            extract_review_json > "$OUTPUT_FILE"
    ) 2>>"$ERR_FILE" &
    AGENT_PIDS+=($!)
done
```

Three backgrounded subshells, each `codex review`-ing the same prompt against the same `gpt-5.3-codex-spark` model, each trying to refresh the same local model-list cache. Single-writer lock → first process wins, others time out.

### `REVIEW_MODEL="${BUG_HUNT_REVIEW_MODEL:-gpt-5.3-codex-spark}"` (line 38)

The single model tier is hardcoded as a script-level default. There is no per-agent model variation; the cosmetic labels don't change what CLI/model runs.

## PR discovery worked correctly (Bucket A excluded)

`bug-hunt-daily.log` lines for this run:

```
[INFO] Found 8 merged PRs in $GITHUB_REPOSITORY
[INFO] Found 1 merged PRs in jleechanorg/ai_universe
[INFO] Starting bug hunt review lanes via codex review (gpt-5.3-codex-spark)...
[INFO] Starting claude agent for bug hunt...
[INFO] Starting codex agent for bug hunt...
[INFO] Starting minimax agent for bug hunt...
[INFO] Waiting for bug hunt agents to complete...
[WARN] claude output file is empty (0 bytes) — agent failed; see /tmp/hermes/bug_reports/bug-hunt-claude-20260723_090145.err
[WARN] codex output file is empty (0 bytes) — agent failed; see /tmp/hermes/bug_reports/bug-hunt-codex-20260723_090145.err
[WARN] minimax output file is empty (0 bytes) — agent failed; see /tmp/hermes/bug_reports/bug-hunt-minimax-20260723_090145.err
[ERROR] All bug hunt agents failed — 0 bugs recorded is NOT a clean sweep
```

`Found N merged PRs` lines confirm `gh pr list` worked. The agents were spawned. They all failed at the same point with the same root cause.

## Pre-existing failed run: 2026-07-22 09:01 (24h earlier)

Same script, same `codex review` invocation, same `REVIEW_MODEL`:

```
[INFO] Found 7 merged PRs in $GITHUB_REPOSITORY
[INFO] Spawning bug hunt agents via Hermes...
[INFO] Starting claude agent for bug hunt...
[WARN] hermes agent unavailable, writing empty findings for claude
[INFO] Starting codex agent for bug hunt...
[WARN] hermes agent unavailable, writing empty findings for codex
[INFO] Starting minimax agent for bug hunt...
[WARN] hermes agent unavailable, writing empty findings for minimax
[INFO] Waiting for bug hunt agents to complete...
[WARN] No bug hunt agent processes were started
```

Note the difference: 24 hours earlier, the script took a completely different code path (`hermes agent --agent <label>`) that also failed but for a different reason (`hermes agent subcommand not found`). The 2026-07-23 run switched to `codex review` directly — and exposed the race. Two consecutive days with the same end-state (3/3 agents failed, 0 bugs) but two distinct root causes.

## Durable fix — already in flight as PR #792

`jleechanorg/jleechanclaw#792` (`fix/durable-bug-hunt-harness`, MERGEABLE, CodeRabbit APPROVED, +536/-158 across `scripts/bug-hunt-daily.sh` + `tests/test_bug_hunt_daily_script.py`) replaces the parallel `codex review` race with per-agent `hermes -z -m <model>` invocations where each label maps to a distinct CLI:

- `claude` → Claude Code CLI (Anthropic)
- `gemini` → Gemini CLI (Google)
- `minimax` → minimax Anthropic-API shim (third-party)

Each CLI has its own model-list cache, no contention. The PR also:
- Replaces `configure_review_cli()` preflight with explicit `ACTIVE_AGENTS` probe per CLI
- Hardens `validate_finding_evidence()` to reject malformed/non-array shapes as agent failures
- Adds 5 regression tests: rate-limit failure, zero-PR runs, prose-without-fence output, explicit model routing, P1 fix-worker invocation
- Fixes a top-level `local fix_model` bash bug under `set -e`

As of 2026-07-23T00:09 PT, PR #792 is APPROVED + MERGEABLE. The only failing gates are Green Gate Gate 3 (`state=none`, stale CodeRabbit review) and Gate 5 (1 unresolved comment). Pushing through these is the path to durable fix.

## Diagnostic reply sent

Channel: `C09GRLXF9GR` (operator direct channel, `all-$USER-ai`)
Original bug-hunt post: 2026-07-23 09:01:46 PT (`bug-hunt-20260723_090145.md`)
Diagnosis posted in-thread with the three failure options (push-to-green / merge-now / replace-today's-run) per SOUL.md `no-pick-one-menus` rule.

## Cross-link

- Skill that captured this analysis: `scripted-multi-agent-review-cron-failure-diagnosis` v1.1.0 (this skill)
- Bucket E added in this version: see `SKILL.md` → `### Bucket E: Parallel-CLI-process race`
- Pitfall 11 added in this version: see `SKILL.md` → `### Pitfall 11: Treating a mixed empty/non-empty .err pattern as Bucket C only`
- Earlier Bucket A reference: `references/2026-07-22-bug-hunt-rate-limit-suppression.md`
- Script under diagnosis: `~/.hermes/scripts/bug-hunt-daily.sh` lines 38, 161, 230-238
- In-flight fix PR: https://github.com/jleechanorg/jleechanclaw/pull/792