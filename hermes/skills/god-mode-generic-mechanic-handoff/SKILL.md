---
name: god-mode-generic-mechanic-handoff
description: Use when handing a Jeff-approved, setting-agnostic god-mode/divine mechanic to AO — covers "generic" framing rules, the four-mechanic contract set (avatar partition/dual-sheet, original→shell interpolation, shell-vs-original separation, rank-anchored DHP), canonical formula-registry directive surface, TDD RED→GREEN harness, /es real-LLM capture, mandatory clean replay on origin/main, and forced-recovery from agent drift or untracked worktrees. Trigger phrases include "approve generic mechanic", "generalize avatar partition", "surface formula registry", "god mode directives / canonical formula registry", "/repro god mode", "issue 8538", "bead rev-ct974", "PR #8541".
---
# god-mode-generic-mechanic-handoff

Replay-safe handoff for a Jeff-approved, setting-agnostic god-mode/divine mechanic into `$GITHUB_REPOSITORY` via Agent-Orchestrator. Lessons learned during the 2026-07-22→2026-07-23 implementation cycle that drove PR #8541 (HEAD `0b0bc4ac7`) and audit failures on earlier failed workers (`wa-3380`, `wa-3382`, `wa-3384`).

## When to use
- Jeffrey approves a generic (setting-agnostic, no campaign-specific names) god-mode/divine mechanic.
- An issue like #8538 or bead like `rev-ct974` is opened tracking a 4-part contract: avatar partition/dual-sheet, original→shell interpolation, shell-vs-original separation, rank-anchored DHP + canonical formula registry directive surface.
- The BQ evidence base already shows the model is reading the prompt but the loaded block omits the canonical formula or dual-sheet rules.

## Generic framing rules (non-negotiable)
1. No campaign-specific names, numbers, or lore in shared `$PROJECT_ROOT/prompts/**` files, `agent_prompts.py`, or contract tests. Put those in `custom_campaign_state.formula_registry` / `directives` only.
2. `current_shell_level` is the mortal sheet (HP, stats, Story Mode reads). `original_level` is the underlying divine level. Never collapse the two.
3. `current_shell_level` is interpolated via `formula_registry.shell_level_from_original` (lower/upper anchors). Never copy `original_level` into `current_shell_level`. Never flatten every divine actor to the mortal cap.
4. HP is bounded by the mortal HP table at `current_shell_level`. Divine HP (DHP) is a separate stat read from `formula_registry.divine_hp_cap` (or named equivalent) anchored on `rank_table[original_level]`. DHP is **NEVER** `hp_current * k`.
5. The "Canonical Formula Registry" block must be appended verbatim to the god-mode directives block when `custom_campaign_state.formula_registry` is present, and **omitted** when absent (no spurious empty section).

## Branching & clean-replay contract
1. `git checkout -B <branch> origin/main` BEFORE writing code. Never branch off an existing non-clean history.
2. Stage ONLY the four intended files: `$PROJECT_ROOT/agent_prompts.py`, `$PROJECT_ROOT/prompts/god_mode_instruction.md`, `$PROJECT_ROOT/tests/test_god_mode_formula_registry_contract.py`, `testing_mcp/test_god_mode_avatar_partition_contract_real_api.py`.
3. After staging, run `git diff --name-only origin/main..HEAD` and STOP if you see drift files (`bq_logging.py`, `world_logic.py`, `roadmap/**`, deleted test files unrelated to the task, `.beads/**`, `.claude/settings.json`).
4. Recovery pattern when the agent already polluted history: `git checkout -B <branch> origin/main`, `git show <bad-sha> -- <four intended files> | git apply --include=<each path>`, commit cleanly, `git push --force-with-lease origin <branch>`.
5. After force-push, verify with `git rev-parse origin/<branch>` and confirm `gh pr view <N> --json files` lists only the four intended paths. If PR #8541 already existed, the headRefOid will update on the same PR — do NOT close and re-open.

## Spawn the right worker (lesson: MiniMax-M3 + agy gate)
1. AO exposes 2-3 worker harnesses. Prefer mid-tier explicit override.
   - MiniMax-M3 (`ao spawn ... --agent minimax`) — fastest path, but verify it has not silently hung with `kill -CONT $(pgrep -P <pane>)` if pane stalls.
   - `agy --prompt-interactive ... --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` — works well for TDD cycles; needs `HOME=$HOME GEMINI_CLI_TRUST_WORKSPACE=true` in the env block.
   - Codex harness — historical reliability issues; do NOT use it for prompt-only contracts.
2. Heartbeat the agent before `ao spawn`: `agy --print --model <tier> --print-timeout 60s --prompt "pong"`. If it stalls >90s, kill and switch tiers. **Never** retry the same tier that failed.
3. Provide the task brief via `env -i ... $AO spawn -p worldarchitect --agent minimax "<task text>"`. Pass full task brief as the task argument — never condense.
4. Include in the brief, verbatim: `Issue 8538 / bead rev-ct974. Explicit mid-tier <tier>. Immediately implement via TDD; no broad research. Use current origin/main. Write RED tests, minimal generic loaded prompt/dynamic-delivery fix, GREEN, real /es, commit, push, clean draft PR. Do not stop before push + PR.`
5. DO NOT trust `--agent agy` AO plugin flag without confirming with `ao spawn --help`; MiniMax plugin is currently the explicit mid-tier option.

## TDD contract tests (RED→GREEN)
1. Write `$PROJECT_ROOT/tests/test_god_mode_formula_registry_contract.py` FIRST. Required assertions:
   - `Canonical Formula Registry` block is appended when `formula_registry` is set.
   - Section header, formula `name`, expression, anchors (`lower_anchor`/`upper_anchor`) are all rendered verbatim.
   - Empty `formula_registry` produces no spurious block.
2. Write the prompt-text assertions for the four protocol rules:
   - `current_shell_level` bounded by mortal cap; not flat-translated from `original_level`.
   - DHP comes from rank-table, NOT HP multipliers.
   - Lower-case the prompt text in the test, not the assertions, to dodge case-fold edge cases (`do NOT flatten` ⇆ `do not flatten`).
3. GREEN with the `_build_formula_registry_block` helper that joins `name`, `expression`, `anchors`, `applies_when` only when `expression` is a non-empty string. Skip entries that aren't dicts or have no expression.
4. Re-run the broader regression suite under `$PROJECT_ROOT/tests/test_god_mode_*` — the canonical block must not break neighboring tests.

## /es real-server + real-LLM evidence (non-negotiable)
1. The repo AGENTS.md says any non-test change under `$PROJECT_ROOT/**` requires `/es` (real local server + real services + real LLM where the path uses an LLM). Unit tests alone FAIL the gate.
2. Required: `testing_mcp/test_god_mode_avatar_partition_contract_real_api.py` that uses `MCPTestBase`, starts a real `gunicorn mvp_site.main:app` on a free port (e.g. 8055 or 56958), runs a real god-mode LLM turn, then greps the captured JSONL traces for:
   - `Canonical Formula Registry` header
   - `shell_level_from_original` formula name
   - The interpolation expression text (read the file with `cat` and copy the exact expected string verbatim)
   - `lower_anchor` and `upper_anchor` substrings
   - `rank_table[original_level]` expression
3. The grep helper must walk nested dicts/lists and stringify any string field — do NOT rely on `row.get("system_text")` shape. Working pattern:
   ```python
   def _row_string_fields(row):
       parts=[]; _walk(row)  # recursive walk
       def _walk(v):
           if isinstance(v,str): parts.append(v)
           elif isinstance(v,list): [ _walk(i) for i in v ]
           elif isinstance(v,dict): [ _walk(x) for x in v.values() ]
       return parts
   def _grep_all_jsonl(paths, needle):
       nl=needle.lower()
       for p in paths:
           for row in _scan_jsonl(p):
               for v in _row_string_fields(row):
                   if nl in v.lower(): return True
       return False
   ```
4. Use `$PROJECT_ROOT/CLAUDE.md` as a hint for what trace files exist (`llm_request_responses.jsonl`, `provider_http_request_responses.jsonl`, `request_responses.jsonl`). Check `MCP_TEST_EVIDENCE_DIR` env var if available.
5. Real `/es` takes ~3–7 minutes per turn because of full server startup + real LLM call. Budget 10m timeout.

## Failures the agent WILL hit (and how to recover)
1. **Worker over-researches**: it will spend 5–8 minutes on file inspection when the brief names the loaded files explicitly. Send `ao send <session-id> 'You are over-researching. Stop now and execute TDD. Write the RED contract test immediately, run it, implement minimal fix. Do not inspect more files.'` The MiniMax harness responds to `ao send`; agy responds to tmux send-keys.
2. **Worker claims "pure prompt exception" for /es**: push back hard. Repo AGENTS.md is fail-closed for `$PROJECT_ROOT/**` non-test changes. Worker must run the real-LLM harness.
3. **Worker attaches evidence to an unrelated PR** (e.g. PR 8539 was an MBTI fix when this task wanted PR 8541). Verify `gh pr list --head <branch> --json number,headRefName` immediately. If the worker created PR 8539 by accident, send a correction: `'Critical topology correction: PR 8539 is unrelated... Do not reference, update, push to, or attach evidence to PR 8539. Your branch currently has no PR. After real /es + tests + commit + push, create a NEW clean draft PR from <branch> to main, closing issue 8538.'`
4. **Worker drift files**: 5 extra files land in the PR diff (`bq_logging.py`, `world_logic.py`, deleted unrelated test files, `roadmap/**`). Apply the recovery pattern under "Branching & clean-replay contract" §4.
5. **Worker tmux exits but `ao send` keeps queuing**: if you see the worker output stream go quiet for >2 min AND tmux session no longer in `tmux list-sessions`, the lifecycle manager killed it. Treat as killed. Inspect `$HOME/.agent-orchestrator/<project-hash>-*/observability/processes/lifecycle-manager-*.json` for `lifecycle.transition` events with `newStatus:"killed"`.
6. **Wdefunct agy.real pid blocking tmux pane**: when `kill -TERM` leaves a `<defunct>` zombie, do `kill -CONT <parent_tmux_pid>` to wake the tmux server so new sessions spawn. The zombie won't go away without sudo, but the parent tmux is the only thing you need for new sessions.

## Hard-coded paths the skill assumes
- `$HOME/projects/your-project.com/.claude/worktrees/bq-llm-logging/scripts/bq_evidence_query.sql` — schema-stable BQ query template for god-mode turns.
- `$HOME/.hermes/lib/outbound_secret_gate.py` — always run on PR body and any log artifacts before push.
- `$HOME/.hermes/skills/finish-the-job/SKILL.md` — for the FINISH state contract.
- `$HOME/.hermes/skills/agento/SKILL.md` — for AO spawn/send/review.
- `$HOME/.hermes/skills/eval-vendor-tooling/SKILL.md` — Pitfall P1 (directives must route via system_instruction, not contents[]) is what made this generic contract get lost in the first place.
- `$HOME/.hermes/skills/workflow/always-pr-never-local-edit/SKILL.md` — the durable end-state contract.
- `$HOME/.hermes/skills/workflow/pr-cleanup-replay/SKILL.md` — the recipe applied when the AO worker polluted the branch.

## Verification checklist before posting "done"
- [ ] `git -C $WT diff --name-only origin/main..HEAD` shows EXACTLY the 4 intended files (no `.claude/settings.json`, no `roadmap/**`, no deleted unrelated tests).
- [ ] `git -C $WT rev-parse origin/main origin/$BR` — local and remote HEAD match.
- [ ] `gh pr view <N> --json files` lists only the 4 paths and matches the diff above.
- [ ] `/es` evidence (real server + real LLM trace grep) is captured in a `/tmp/your-project.com/<branch>/god_mode_avatar_partition_contract_real_api/` artifact and pasted into PR description `## Evidence` section.
- [ ] No `gh pr merge` was issued; orchestrator owns the merge.
- [ ] Slack status posted to `#ai-general` with PR URL + the new HEAD SHA + the bq campaign id used for repro.

## Out-of-scope (do NOT do)
- Do not close PR 8541 if the same branch was force-pushed to a clean replay — the PR is updated in place.
- Do not create a fresh bead ID when one already exists in caller repo.
- Do not edit `.claude/settings.json` or include `AO-TASK-BRIEF.md` in git history.
- Do not propose "send raw" repro LLM requests to BQ from inside this skill — that lives in `repro-twin-clone-evidence`.
- Do not promise to "generalize later" — the brief is for the single, approved mechanic at a time.
