---
name: real-claude-teammate-tmux
description: Launch, verify, and regression-protect real Claude Code teammates running in tmux with the `--teammate-mode tmux` primitive. Use when the user wants a real parallel Sonnet Claude Code team (not pseudo-agent narration), when fixing slash commands that drifted into `Agent(...)` / `TaskCreate` / `SendMessage` pseudo-primitives, when wiring `/team-claude` or `/sidekick` style commands to actually start teammates, when the user says "use real claude team" / "use tmux" / "sonnet only" / "actually start the team" / "use the real claude team", or when a regression contract test is needed so future docs cannot regress into Agent/TaskList pseudo-primitive language. Covers the launch recipe, the verification recipe, the Sonnet-only model policy, the regression-contract test pattern, and the /rg + /advice sign-off workflow.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [claude-code, teammates, tmux, sonnet, --teammate-mode, regression-contract, rg, advice, sidekick, team-claude]
    related_skills: [claude-code, agento, advice, finish-the-job, system-wide-review, test-tui-claude-feature-via-cmux]
changelog:
  - "1.0.0 (2026-07-10): Initial authoring. Captures the real-vs-pseudo Claude Code teammate lesson from jleechanorg/claude-commands PR #321 and `tests/test_real_claude_team_contract.py`. Pin the Sonnet-only model policy from user feedback (\"just use sonnet models with claude code\") and the /rg + /advice sign-off workflow pattern."
---

# real-claude-teammate-tmux

When a slash command's docs (or a session's plan) need to "start a Claude team",
they MUST spawn real Claude Code processes in tmux, NOT narrate a pseudo team
from an in-memory `Agent(...)` / `TaskCreate` / `TaskUpdate` / `SendMessage`
surface. The real primitive is:

```bash
claude --model sonnet --teammate-mode tmux
```

This skill encodes the launch recipe, the verification recipe, the
Sonnet-only model policy, the regression-contract test pattern, and the
`/rg` + `/advice` sign-off workflow that proved the pattern end-to-end
(jleechanorg/claude-commands PR #321, 2026-07-10).

## When to use this skill

- A project slash command (`/team-claude`, `/sidekick`, `/swarm`, etc.) is
  supposed to start parallel Claude Code teammates but currently describes
  pseudo-primitive `Agent(...)` / `TaskCreate` / `TaskUpdate` / `SendMessage`
  / `team_name=...` calls that don't actually spawn teammates.
- The user explicitly says "use real claude team", "use tmux", "sonnet only",
  "actually start the team", "use the real claude team", or complains that
  `/team-claude` / `/sidekick` "don't always start the real claude team".
- A teammate fan-out is needed and the orchestrator must verify each
  teammate is a real process, not a narrative.
- A regression contract test is needed so a future edit cannot regress the
  docs back into pseudo-primitive language.
- The user wants the `/rg` (RED → CODE → GREEN) loop with `/advice` Reviewer A
  sign-off on a fix.

## Hard contracts (non-negotiable)

1. **Real primitive only.** Every teammate is a real Claude Code process
   launched via `tmux new-session`. The launch command prefix is always:
   ```bash
   claude --model sonnet --teammate-mode tmux
   ```
2. **Sonnet-only by default.** Do not spawn haiku/opus/non-Sonnet scout lanes even
   if a slash command's docs nominally support them. The user has the final
   word on the model. No `--fallback-model` without explicit user approval.
3. **No pseudo-primitives.** No `Agent(subagent_type=...)`,
   `TaskCreate` / `TaskList` / `TaskUpdate` / `SendMessage` / `team_name=...`,
   `claude-pair-coder` / `claude-pair-verifier` strings in the production
   docs. They are documentation drift, not real.
4. **Verify before claiming success.** Four hard checks must all pass:
   - `tmux ls | grep "^${SESSION}:"`
   - `tmux list-panes ... | grep "^${SESSION} "`
   - `tmux capture-pane ... | tail -80` shows the Claude banner
   - `ps -ef | grep "claude --model sonnet --teammate-mode tmux" | grep -v grep`
5. **Panes stay open for evidence.** End the tmux wrapper with
   `rc=$?; printf '\n[done exit=%s]\n' "$rc"; exec bash` so the pane survives
   Claude exit and you can still `tmux capture-pane` after the run.
6. **Regression contract test required.** When patching a drifted slash
   command, ship a pytest contract that asserts both the required real
   command is present AND the forbidden pseudo-primitive strings are absent.
   See `templates/regression_contract_test.py` for the skeleton.
7. **`/rg` + `/advice` for sign-off.** Run the full RED→CODE→GREEN loop:
   write a failing regression test first, then the fix, then GREEN. Get
   `/advice` Reviewer A sign-off on the diff + proof before claiming ready.

## Canonical launch (Sonnet-only, real tmux teammate)

```bash
SESSION="team-${SLUG}-lane-${N}"
PROMPT_FILE="/tmp/${SLUG}/lane-${N}.prompt.md"
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 160 -y 48 \
  "cd '<repo>' && claude --model sonnet --teammate-mode tmux \
   --dangerously-skip-permissions -p \"\$(cat '$PROMPT_FILE')\"; \
   rc=\$?; printf '\n[team lane done exit=%s]\n' \"\$rc\"; exec bash"
```

For sidekick-style durable missions, write the prompt to a file next to
STATE.md (e.g. `/tmp/<project>/sidekick/<mission>/sidekick.prompt.md`) so a
respawn can re-read it.

## Verification recipe (mandatory before claiming success)

```bash
SESSION="team-${SLUG}-lane-${N}"
tmux ls | grep "^${SESSION}:" || { echo "FAIL: no session"; exit 1; }
tmux list-panes -a -F '#{session_name} #{pane_pid} #{pane_current_command}' \
  | grep "^${SESSION} " || { echo "FAIL: no pane"; exit 1; }
tmux capture-pane -t "$SESSION" -p -S -80 | tail -80
ps -ef | grep "claude --model sonnet --teammate-mode tmux" \
  | grep -v grep || { echo "FAIL: no process"; exit 1; }
```

## Regression contract test (the `/rg` RED step)

See `templates/regression_contract_test.py` for the skeleton. The pattern:

1. Read each production file as a string.
2. Assert the required real command is present:
   `"claude --model sonnet --teammate-mode tmux" in text`
3. Assert each forbidden pseudo-primitive is absent:
   `"TaskCreate" not in text`,
   `"claude-pair-coder" not in text`, etc.
4. Tests must run on a fresh `git checkout -B fix/... origin/main` of the
   target repo (no mocks, no monkeypatching) and FAIL before the fix.

## `/rg` + `/advice` sign-off workflow (the proven recipe)

This is the loop that shipped jleechanorg/claude-commands PR #321:

1. **RED.** Write the regression contract test on a fresh worktree at
   `origin/main`. Run `pytest -q` — confirm test FAILS with the exact error
   you expected (missing real command, or forbidden pseudo-primitive still
   present).
2. **CODE.** Apply the fix to the production docs. Re-run `pytest -q` —
   confirm test PASSES.
3. **Real tmux smoke.** Independently launch a tmux session with the
   documented command and verify with the four-check recipe. Capture
   `tmux capture-pane` output for the PR description.
4. **Forbidden grep.** Run `! grep -RInE 'TaskCreate|TaskList|...|Agent\('`
   across the changed production files. Zero hits required.
5. **`/advice` Reviewer A.** Fan out via `delegate_task` for a read-only
   second opinion on the diff and proof. Require a sign-off verdict
   (`SIGN-OFF APPROVED` or specific blockers) BEFORE opening the PR.
6. **Push + open PR.** Commit, push, open PR with body containing the
   RED→GREEN pytest transcript and the real tmux smoke output. Schedule
   a one-time follow-up cron for status checks.

## Pitfalls (verified in the 2026-07-10 incident)

- **Pseudo-primitive docs feel plausible.** The old `/team-claude` and
  `/sidekick` docs in `jleechanorg/claude-commands` read like real
  orchestration but only described a fictional `Agent(subagent_type=...)`
  API. Always check the live CLI (`claude --help | grep team`) for the
  real primitive BEFORE writing teammate docs.
- **`team_name` / `TaskList` are drift signals.** When you see them in
  teammate-related docs, that's the pseudo-primitive pattern — replace
  with the real tmux recipe.
- **`--fallback-model` is a hidden cost hole.** Pinning `--model sonnet`
  without `--fallback-model haiku` is intentional. The user can opt-in
  to fallbacks explicitly, but the default must not silently downshift.
- **Panes close when Claude exits.** If you don't append `exec bash` to
  the tmux wrapper, you lose the launch evidence. The post-mortem on the
  2026-07-10 incident is exactly this: 4 of the 4 verification checks
  require `tmux ls` / `tmux list-panes` / `tmux capture-pane`, and all
  three fail if the pane closed.
- **Quarantined test fixtures ≠ real repro.** A regression contract that
  only checks string content can pass on docs that are correct in the
  contract's *language* but wrong in *real orchestration*. Always pair
  the contract test with a real tmux smoke (step 3 above) — the contract
  catches the doc-drift, the smoke catches the doc-truth.
- **Don't let Agent pseudo-primitive language survive in code comments or
  examples either.** Even if the production body uses real primitives, a
  stray `TeamCreate(...)` example block in a "Why these docs differ from
  a generic guide" section is still drift that future copy-paste can
  amplify. Audit the entire file.
- **`claude-3-5-sonnet` ages out.** Use `--model sonnet` (latest alias)
  in all docs and commands. The fixed model string silently downgrades
  when the CLI default rotates.

## How this skill connects to others

- `claude-code` (bundled, not editable) — the canonical CLI surface; this
  skill adds the operational recipe for the `--teammate-mode tmux`
  primitive that the bundled skill only documents as a flag.
- `agento` — for *task* delegation to Agent-Orchestrator workers (not
  for *teammate* orchestration in tmux). Different primitive, different
  cost model, different failure modes.
- `advice` — the `/advice` sign-off workflow (step 5 above) is
  Reviewer A second opinion on a fix. Always required for any teammate-
  recipe change.
- `finish-the-job` — the surrounding drive-to-completion discipline
  (commit, push, PR, schedule follow-up cron). The end-state of any
  teammate-recipe change is a merged PR, not a local commit.
- `test-tui-claude-feature-via-cmux` — when verifying a *TUI* feature
  inside the launched teammate (not the launch itself). Different scope.

## Files in this skill

- `references/real-teammate-pattern-2026-07-10.md` — full transcript of
  the 2026-07-10 incident: drifted docs, real tmux smoke, regression
  contract test, /advice sign-off, PR #321.
- `templates/regression_contract_test.py` — the pytest skeleton used
  in PR #321. Copy + edit forbidden/required token lists for the next
  teammate-recipe change.
